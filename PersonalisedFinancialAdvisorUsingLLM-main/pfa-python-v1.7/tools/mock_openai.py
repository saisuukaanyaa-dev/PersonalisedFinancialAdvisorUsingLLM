#!/usr/bin/env python3
"""Stand-in for the OpenAI API, for testing without a key or cost.
Serves /v1/embeddings and /v1/chat/completions (structured outputs) with plausible answers.
Run:  python tools/mock_openai.py  (port 8787, set MOCK_DELAY_S to simulate model latency)
Then set OPENAI_BASE_URL=http://host.docker.internal:8787/v1 and OPENAI_API_KEY=mock in .env.
"""
import hashlib
import json
import os
import random
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DELAY = float(os.environ.get("MOCK_DELAY_S", "1.5"))


def vector(text: str) -> list[float]:
    rnd = random.Random(hashlib.sha1(text.encode()).digest())
    v = [rnd.uniform(-1, 1) for _ in range(1536)]
    n = sum(x * x for x in v) ** 0.5
    return [x / n for x in v]


def amount(s: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|l|lakh|cr)?\b", s, re.I)
    if not m:
        return None
    mult = {"k": 1e3, "l": 1e5, "lakh": 1e5, "cr": 1e7}.get((m.group(2) or "").lower(), 1)
    return float(m.group(1)) * mult


def answer(name: str, user: str) -> dict:
    if name == "report_story":
        return {"headline": "A steady plan - a few safety steps first",
                "summary": "You save a healthy share of your pay and already invest every month. Top up the emergency fund, "
                           "keep your insurance in place, and let the monthly plan do the work [1].",
                "projection_commentary": "The gap between the two lines is what extra monthly investing buys you. "
                                         "Staying invested through market dips matters more than timing [2].",
                "strengths": ["You keep more than half your pay after essentials and EMIs.", "You already invest every month."],
                "risks": ["Your emergency fund is below six months of expenses.", "Your term cover is below 10x your income."],
                "priority_actions": [
                    {"title": "Top up your emergency fund", "why": "It protects your plan from surprises.", "how": "Add the monthly top-up to a liquid fund."},
                    {"title": "Raise your term cover", "why": "It protects anyone who depends on your income.", "how": "Compare pure term plans online."},
                    {"title": "Start the monthly plan", "why": "Consistency beats timing.", "how": "Set up the SIPs shown in your plan."}]}
    if name == "report_details":
        syms = re.findall(r'"symbol": "([A-Z&]+)"', user)
        return {"debt_commentary": "Your car loan is at a moderate rate, so keep paying the EMI on schedule rather than prepaying.",
                "allocation_rationale": {"equity": "Your long horizon can carry equity through index and flexi-cap funds [1].",
                                         "fixed_income": "PPF and FDs steady the plan.", "gold": "A small gold slice hedges inflation.",
                                         "cash": "A little cash keeps you liquid."},
                "stock_notes": [{"symbol": s, "rationale": f"{s} combined steady growth with falls inside your limits."} for s in syms[:5]],
                "extra_assumptions": ["Salary grows with inflation"]}
    if name == "judge":
        return {"warm": 4, "answered": 4, "specific": 4, "note": "mock judge"}
    if name == "nifty_changes":
        return {"added": [{"symbol": "TESTCO", "company": "Test Company (test data)"}],
                "removed": [{"symbol": "HDFCLIFE", "company": "HDFC Life (test data)"}],
                "effective_date": "2026-09-30", "summary": "TEST DATA: one addition and one removal reported."}
    if name == "intake_extract":                           # v1.6 chat intake: a crude reader of the two example messages
        msg = user.split("PERSON SAYS:", 1)[-1]
        low = msg.lower()
        def grab(rx):
            m = re.search(rx, msg, re.I)
            return m.group(1).strip() if m else None
        x = {k: None for k in ("name", "age", "currency", "ctc", "take_home", "goal_type", "goal_details", "target_amount", "target_date",
                               "expenses", "emergency", "emergency_monthly", "term_cover", "health_cover", "has_loans", "has_investments", "risk")}
        x.update(loans=[], investments=[], heard=[])
        x["name"] = grab(r"(?:i'm|i am|^)\s*([A-Z][a-z]+)(?:,| here)")
        age = grab(r"\b(\d{2})(?:,| years)")
        x["age"] = int(age) if age else None
        x["ctc"] = grab(r"(?:ctc|earn)\s*(?:is\s*)?(\d+(?:\.\d+)?\s*(?:lakh|l)\b)")
        x["take_home"] = grab(r"take-?home (?:about |around )?(\d+(?:\.\d+)?\s*l)\b")
        x["target_amount"] = grab(r"(?:around|worth|about)\s+(\d+(?:\.\d+)?\s*lakh)")
        y = grab(r"by (20\d\d)")
        x["target_date"] = f"{y}-12-31" if y else None
        x["expenses"] = grab(r"(?:expenses|essentials) (?:are |roughly |about )*(\d+(?:\.\d+)?\s*k)\b")
        x["goal_type"] = "Buy a home" if re.search(r"2bhk|home|house|flat", low) else "Buy a car" if "car worth" in low else None
        if "no loans" in low:
            x["has_loans"] = False
        elif "car loan" in low:
            x["has_loans"] = True
            x["loans"] = [{"type": "Car loan", "outstanding": grab(r"car loan (\d+(?:\.\d+)?l)"), "rate": grab(r"at (\d+(?:\.\d+)?%)"), "emi": grab(r"emi (\d+k)")}]
        mf = grab(r"(\d+(?:\.\d+)?l) in mutual funds")
        if mf:
            x["has_investments"] = True
            x["investments"].append({"kind": "mf", "value": mf, "monthly": grab(r"(\d+k) sip"), "label": None})
        fd = grab(r"(\d+(?:\.\d+)?l) in fds?")
        if fd:
            x["investments"].append({"kind": "fd", "value": fd, "monthly": None, "label": None})
        if re.search(r"about my savings", low) and not x["investments"]:
            v = grab(r"mf (\d+(?:\.\d+)?\s*[kl])")
            if v:
                x["has_investments"] = True
                x["investments"].append({"kind": "mf", "value": v, "monthly": None, "label": None})
        x["heard"] = [{"field": k, "quote": str(x[k])} for k in ("ctc", "target_amount", "expenses") if x[k]]
        return x
    if name == "chat_reply":
        msg = user.rsplit("USER:", 1)[-1].strip()
        low = msg.lower()
        live_given = "LIVE DATA" in user
        base = {"needs_live_data": False, "live_query": None,
                "suggestions": ["How long until I can buy stocks?", "Show my monthly plan"]}
        changes = {k: None for k in ("monthly_sip_total", "target_amount", "target_date", "risk_appetite", "take_home",
                                     "annual_ctc", "expenses", "emergency_fund", "term_cover", "health_cover", "remove_loan")}
        no_dep = {"wanted": False, **{k: None for k in ("initial_amount", "monthly_installment", "goal_amount", "goal_date",
                                                        "inflation_pct", "senior", "banks")}}
        base["deposit_request"] = no_dep
        if "DEPOSIT PLAN (computed now" in user:                                   # v1.5: present the planner's result
            plan = json.loads(user.split("DEPOSIT PLAN (computed now by the team's deposit planner - present it):\n", 1)[1].split("\n\n", 1)[0])
            lines = [f"Here's what the deposit planner found ({plan['inputs']['inflation_pct']}% inflation, {plan['inputs']['inflation_source']}):"]
            for s in (plan.get("fixed_deposit_plan") or {}).get("steps", []):
                lines.append(f"- FD: **{s['bank']}** {s['tenor']} @ {s['rate_pct']}% × {s['times']} → ₹{s['value_at_end']:,}")
            best = (plan.get("recurring_deposit_plan") or {}).get("best") or {}
            for s in best.get("steps", []):
                lines.append(f"- RD: **{s['bank']}** {s['term_months']} months @ {s['rate_pct']}% → ₹{s['value_at_end']:,}")
            lines.append(f"**{plan['verdict']}**" + (f" - about ₹{best.get('installment_needed_for_goal', 0):,} a month would close it." if plan.get("shortfall_todays_money") else ""))
            return {**base, "on_topic": True, "plan_changes": changes, "reply": "\n".join(lines)}
        if re.search(r"\b(fd|rd|deposit)", low) and re.search(r"\b20[2-6]\d\b", low) and amount(msg):   # plan request
            nums = [float(x) * {"k": 1e3, "l": 1e5, "lakh": 1e5, "cr": 1e7}.get((u or "").lower(), 1)
                    for x, u in re.findall(r"(\d+(?:\.\d+)?)\s*(k|l|lakh|cr)\b", low)]
            year = re.search(r"\b(20[2-6]\d)\b", low).group(1)
            req = {**no_dep, "wanted": True, "goal_date": f"{year}-04-01", "senior": bool(re.search(r"senior|6\d years", low))}
            if len(nums) >= 3:
                req.update(initial_amount=nums[0], monthly_installment=nums[1], goal_amount=nums[2])
            elif len(nums) == 2:
                req.update(initial_amount=nums[0], goal_amount=nums[1])
            return {**base, "on_topic": True, "plan_changes": changes, "deposit_request": req, "reply": "Let me run the deposit planner…"}
        if '"deposit_rates"' in user:                                              # rate question: quote the table
            fd = re.findall(r'"bank": "([^"]+)", "type": "FD", "tenor": "([^"]+)", "general_pct": ([\d.]+)', user)[:3]
            asof = re.search(r'"as_of": "([^"]+)"', user)
            return {**base, "on_topic": True, "plan_changes": changes,
                    "reply": "Top FD card rates in the table" + (f" (as of {asof.group(1)})" if asof else "") + ":\n"
                             + "\n".join(f"- **{b}** {t}: {r}%" for b, t, r in fd) + "\n\nConfirm with the bank before opening."}
        if re.search(r"poem|cricket|weather", low):
            return {**base, "on_topic": False, "reply": "I can only help with your personal finance plan.", "plan_changes": changes}
        for k in ("emergency_lumpsum", "emergency_monthly"):
            changes.setdefault(k, None)
        if re.search(r"\d+\s*k\s+now", low) and "month" in low:                  # "50K now and 6K a month" (emergency, from context)
            nums = [float(x) * 1000 for x in re.findall(r"(\d+(?:\.\d+)?)\s*k\b", low)]
            if nums:
                changes["emergency_lumpsum"] = nums[0]
            if len(nums) > 1:
                changes["emergency_monthly"] = nums[1]
            return {**base, "on_topic": True, "plan_changes": changes,
                    "reply": "Great idea - moving **₹50,000** in now and adding **₹6,000** a month gets your safety net built much faster. Confirm below and I'll update your plan."}
        if re.search(r"(sug+e?s+t|best|top|rec+om+end)[^?]*(stock|share)", low):
            wl = re.search(r'"watchlist": \[(.*?)\]', user)
            syms = re.findall(r'"symbol": "([A-Z&-]+)"', wl.group(1) if wl else "")[:5]
            return {**base, "on_topic": True, "plan_changes": changes,
                    "reply": "Happy to help, Test!\n\nYour stocks are paused until the emergency fund reaches **₹1.95L**, so here's your watchlist for when you're ready:\n"
                             + "\n".join(f"- **{x}** - strong 5-year record within your limits" for x in syms)
                             + "\n\nMeanwhile, keep your SIPs in the index fund. Want me to show how fast you can reach ₹1.95L?"}
        g = re.search(r"move my goal to (20\d\d)", low)
        if g:
            changes["target_date"] = f"{g.group(1)}-06-30"
            return {**base, "on_topic": True, "plan_changes": changes, "reply": f"Sure - moving your goal to {g.group(1)} gives the money more time. Confirm below."}
        if "what if" in low or "invest" in low and amount(msg):
            if "invest" in low and amount(msg):
                changes["monthly_sip_total"] = amount(msg)
            for r in ("low", "medium", "high"):
                if f"{r} risk" in low:
                    changes["risk_appetite"] = r.capitalize()
            m = re.search(r"\b(20[3-6]\d)\b", msg)
            if m:
                changes["target_date"] = f"{m.group(1)}-06-30"
            return {**base, "on_topic": True, "reply": "Sure - I'll re-run your plan with that change.", "plan_changes": changes}
        if live_given:
            live = user.split("LIVE DATA (untrusted, fetched now):", 1)[1].split("CONVERSATION SO FAR", 1)[0].strip()[:160]
            return {**base, "on_topic": True, "reply": f"Here is today's data: {live} Educational information, not licensed advice.",
                    "plan_changes": changes}
        if "now" in low and "gold" in low:                                   # model asks for live data (ask_model route)
            return {**base, "on_topic": True, "reply": "Let me check today's gold price.", "plan_changes": changes,
                    "needs_live_data": True, "live_query": "gold price India today"}
        return {**base, "on_topic": True, "reply": "An emergency fund covers about six months of essential expenses, kept somewhere "
                                          "safe and instantly available, like a liquid fund [1]. Educational information, not licensed advice.",
                "plan_changes": changes}
    return {}


class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path.endswith("/audio/transcriptions"):
            return self._json({"text": "What if I invest 40K a month with medium risk?"})
        j = json.loads(raw or b"{}") if not self.path.endswith("/audio/speech") else json.loads(raw or b"{}")
        if self.path.endswith("/embeddings"):
            inp = j["input"] if isinstance(j["input"], list) else [j["input"]]
            n = sum(len(t) for t in inp) // 4
            return self._json({"data": [{"index": i, "embedding": vector(t)} for i, t in enumerate(inp)],
                               "usage": {"prompt_tokens": n, "total_tokens": n}})
        if self.path.endswith("/audio/speech"):
            b = b"ID3" + b"\x00" * 400                                      # a tiny fake mp3
            self.send_response(200); self.send_header("Content-Type", "audio/mpeg"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b); return
        if self.path.endswith("/chat/completions"):
            time.sleep(DELAY)
            name = ((j.get("response_format") or {}).get("json_schema") or {}).get("name", "")
            user = next((m["content"] for m in j["messages"] if m["role"] == "user"), "")
            content = json.dumps(answer(name, user))
            prompt = sum(len(m["content"]) for m in j["messages"]) // 4       # realistic-looking token counts
            reasoning = 256
            out = len(content) // 4 + reasoning
            return self._json({"id": "mock", "object": "chat.completion", "model": j.get("model"),
                               "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
                               "usage": {"prompt_tokens": prompt, "completion_tokens": out, "total_tokens": prompt + out,
                                         "prompt_tokens_details": {"cached_tokens": 0},
                                         "completion_tokens_details": {"reasoning_tokens": reasoning}}})
        self._json({"error": "unknown path"}, 404)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8787"))), H).serve_forever()
