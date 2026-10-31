"""Evaluation: local knowledge base vs web search vs the router, on 30 fixed questions.

    ./scripts/run-eval.sh                 # all three modes -> docs/EVALUATION.md
    ./scripts/run-eval.sh --modes hybrid  # just the router

Each question runs as a fresh chat for a test user ("eval@pfa.local", made-up profile) so answers don't
leak into each other. Measured per answer: route taken, whether it is grounded (knowledge-base citation [n]
or a dated live source), a rough keyword check, time, AI cost and SerpAPI searches.
Cost note: 30 questions x 3 modes is ~90 AI calls (about ₹10) and ~30 SerpAPI searches (web-only mode;
the router reuses them from the cache).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .. import db
from ..ai import chat, llm
from ..config import settings
from ..profile import build_profile
from ..usage import USD_TO_INR

USER = "eval@pfa.local"
MODES = {"local": "Local knowledge base only", "live": "Web search only (SerpAPI)", "hybrid": "Router (local + live when needed)"}
PROFILE = {
    "name": "Eval Test", "age": "32", "currency": "INR", "ctc": "18L", "goal_type": "Buy a home", "goal_details": "2BHK",
    "target_amount": "80L", "target_date": (date.today() + timedelta(days=365 * 8)).isoformat(), "take_home": "1.22L",
    "expenses": "45K", "emergency": "1.5L", "term_cover": "50L", "health_cover": "5L", "loan_types": ["Car loan"],
    "loans": {"Car loan": {"outstanding": "3.2L", "rate": "9.2", "emi": "11K"}}, "_loans_answered": True,
    "inv": {"mf_value": "4.5L", "mf_monthly": "15K", "mf_type": "Equity", "fd_value": "2L", "pf_value": "6.4L", "pf_monthly": "3K"},
    "risk": "High",
}


def grounded(reply: str) -> bool:
    return bool(re.search(r"\[\d+\]", reply)) or "Live data:" in reply


async def run(modes: list[str], limit: int | None) -> str:
    questions = json.loads((Path(__file__).parent / "questions.json").read_text())[:limit]
    await db.open_pool()
    llm.open_client()
    await db.save_profile(build_profile(PROFILE, USER))
    rows = {m: [] for m in modes}
    try:
        for m in modes:
            for q in questions:
                await db.execute("DELETE FROM chat_messages WHERE user_key = %s", USER)       # each question starts fresh
                t0 = time.perf_counter()
                res = await chat.answer(USER, q["q"], None, force_route=None if m == "hybrid" else m)
                ms = (time.perf_counter() - t0) * 1000
                reply = res.get("reply", "")
                use = res.get("usage") or {}
                route = (res.get("route") or {}).get("kind") or "local"
                kw = q["keywords"]
                rows[m].append({
                    **q, "reply": reply, "ms": ms, "inr": use.get("cost_inr") or 0, "serp": use.get("serp_searches") or 0,
                    "route_taken": route, "route_reason": (res.get("route") or {}).get("reason", ""),
                    "live_how": (res.get("route") or {}).get("live") or "",
                    "grounded": grounded(reply),
                    "kw_ok": (any(k.lower() in reply.lower() for k in kw) if kw else None),
                    "route_ok": (route == q["route"]) if m == "hybrid" else None,
                })
    finally:
        await db.execute("DELETE FROM chat_messages WHERE user_key = %s", USER)
        await db.execute("DELETE FROM users WHERE user_key = %s", USER)
        await llm.close_client()
        await db.close_pool()
    return report(rows, len(questions))


def pct(xs) -> str:
    xs = [x for x in xs if x is not None]
    return f"{sum(xs) / len(xs) * 100:.0f}%" if xs else "-"


def report(rows: dict, n: int) -> str:
    out = [f"# Chat evaluation: local knowledge base vs web search vs router",
           f"Run {datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z')} · {n} questions · model {settings.chat_model} · "
           f"SerpAPI {'on' if settings.live_enabled else 'off'}", "",
           "| Mode | Grounded answers | Keyword check (concept + plan) | Live questions with a dated source | Median time | Total AI + search cost | SerpAPI searches |",
           "|---|---|---|---|---|---|---|"]
    for m, rs in rows.items():
        live = [r for r in rs if r["cat"] == "live"]
        out.append(f"| {MODES[m]} | {pct([r['grounded'] for r in rs])} | {pct([r['kw_ok'] for r in rs])} | "
                   f"{pct(['Live data:' in r['reply'] for r in live])} | {statistics.median([r['ms'] for r in rs]) / 1000:.1f} s | "
                   f"₹{sum(r['inr'] for r in rs):.2f} | {sum(r['serp'] for r in rs)} |")
    if "hybrid" in rows:
        rs = rows["hybrid"]
        out += ["", f"**Router accuracy:** {pct([r['route_ok'] for r in rs])} of questions took the expected route "
                    f"(concept and plan questions local, time-sensitive questions live).", ""]
        by = {}
        for r in rs:
            by.setdefault(r["cat"], []).append(r)
        out += ["| Category | Questions | Correct route | Grounded | Median time | Cost | Searches |", "|---|---|---|---|---|---|---|"]
        for c, xs in by.items():
            out.append(f"| {c} | {len(xs)} | {pct([x['route_ok'] for x in xs])} | {pct([x['grounded'] for x in xs])} | "
                       f"{statistics.median([x['ms'] for x in xs]) / 1000:.1f} s | ₹{sum(x['inr'] for x in xs):.2f} | {sum(x['serp'] for x in xs)} |")
        out += ["", "## Router decisions", "", "| # | Question | Expected | Taken | Why | Live source | Time | Cost |", "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rs, 1):
            mark = "✅" if r["route_ok"] else "❌"
            out.append(f"| {i} | {r['q']} | {r['route']} | {mark} {r['route_taken']} | {r['route_reason']} | {r['live_how'] or '-'} | "
                       f"{r['ms'] / 1000:.1f} s | ₹{r['inr']:.3f} |")
    out += ["", "## How to read this",
            "- **Grounded**: the answer cites a knowledge-base passage [n] or shows a dated live source.",
            "- **Keyword check** is a rough automatic test (the answer mentions the key term); read the answers in the JSON for quality.",
            "- **Local only** cannot answer today's prices or rates; **web only** answers concepts from unvetted pages and costs a "
            "search per question; the **router** uses each where it is strongest.",
            f"- Costs use the prices in `.env` ($1 = ₹{USD_TO_INR})."]
    Path("/tmp/eval_answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- conversations (v1.3)
JUDGE_SCHEMA = llm.obj({"warm": {"type": "integer"}, "answered": {"type": "integer"}, "specific": {"type": "integer"},
                        "note": llm.STR})
JUDGE = ("You grade one reply from a personal-finance chat assistant, 1 (poor) to 5 (excellent), on: warm (sounds like a "
         "caring human, uses the person's name naturally, acknowledges what they said), answered (addresses what was "
         "actually asked instead of refusing or deflecting), specific (uses concrete numbers, names or steps). Short note.")
REFUSAL = re.compile(r"\b(i can'?t|i cannot|i won'?t|i'm unable|i am unable|not able to)\b", re.I)
CONV_PROFILE = {**PROFILE, "emergency": "0", "risk": "High",
                "inv": {"mf_monthly": "3K", "mf_type": "Equity", "stocks_monthly": "2K", "gold_monthly": "500",
                        "fd_value": "1L", "pf_monthly": "6K"}}


async def run_conversations() -> str:
    from .. import pipeline
    convs = json.loads((Path(__file__).parent / "conversations.json").read_text())
    await db.open_pool()
    llm.open_client()
    out = ["# Conversation evaluation (Arth, v1.3)", f"Run {datetime.now().astimezone().strftime('%d %b %Y %H:%M %Z')} · "
           f"{len(convs)} conversations · model {settings.chat_model}", ""]
    totals = {"checks": 0, "passed": 0, "warm": [], "answered": [], "specific": [], "refusal_repeats": 0}
    try:
        for c in convs:
            await db.execute("DELETE FROM chat_messages WHERE user_key = %s", USER)
            profile = build_profile(CONV_PROFILE, USER)
            await db.save_profile(profile)
            rid = await pipeline.create_plan(profile, "eval")
            out += [f"## {c['name']}", ""]
            refusals = 0
            for t in c["turns"]:
                sips_before = (await db.load_profile(USER))["derived"]["monthlyContrib"]
                res = await chat.answer(USER, t["say"], rid)
                reply = res.get("reply", "")
                refusals += bool(REFUSAL.search(reply))
                checks = {}
                for e in t.get("expect", []):
                    if e == "watchlist":
                        rep = await db.load_report(rid, USER)
                        names = [x["symbol"] for x in (rep.get("picks") or (rep.get("screen") or {}).get("watchlist") or [])]
                        checks["names watchlist stocks"] = sum(n in reply for n in names) >= min(3, len(names)) if names else True
                    elif e == "confirm":
                        checks["asks before changing the plan"] = bool(res.get("confirm")) and not res.get("report_url")
                    elif e == "no_confirm":
                        checks["doesn't change the plan"] = not res.get("confirm") and not res.get("report_url")
                    elif e == "live_source":
                        checks["shows a dated live source"] = "Live data:" in reply
                    elif e == "guardrail":
                        checks["refused locally at ₹0"] = (res.get("usage") or {}).get("kind") == "guardrail"
                shown = reply
                if res.get("confirm") and "confirm" in t:
                    conf = await chat.confirm(USER, res["confirm"]["id"], bool(t["confirm"]))
                    shown += "\n[" + ("Yes" if t["confirm"] else "No") + "] " + conf.get("reply", "")
                    if t["confirm"] and conf.get("report_url"):
                        rid = conf["report_url"].rsplit("/", 1)[1]
                    if not t["confirm"]:
                        checks["declining keeps the plan"] = not conf.get("report_url")
                    if "sips_unchanged" in t.get("check", []):
                        checks["SIPs left unchanged"] = (await db.load_profile(USER))["derived"]["monthlyContrib"] == sips_before
                g = {"warm": 0, "answered": 0, "specific": 0, "note": "not graded (guardrail)"}
                if (res.get("usage") or {}).get("kind") != "guardrail":
                    try:
                        g = await llm.json_call(JUDGE, f"USER SAID: {t['say']}\n\nASSISTANT REPLIED:\n{reply}", "judge", JUDGE_SCHEMA, max_tokens=400)
                        for k in ("warm", "answered", "specific"):
                            totals[k].append(int(g[k]))
                    except Exception as ex:
                        g["note"] = f"judge failed: {ex}"
                totals["checks"] += len(checks)
                totals["passed"] += sum(checks.values())
                marks = " · ".join(("✅ " if v else "❌ ") + k for k, v in checks.items()) or "-"
                out += [f"**User:** {t['say']}", "", "> " + shown.replace("\n", "\n> "), "",
                        f"Checks: {marks}  ·  Judge: warm {g['warm']}/5, answered {g['answered']}/5, specific {g['specific']}/5 - {g['note']}", ""]
            totals["refusal_repeats"] += max(0, refusals - 1)
            out.append(f"Refusal-style replies in this conversation: {refusals}" + (" (repeated)" if refusals > 1 else ""))
            out.append("")
    finally:
        await db.execute("DELETE FROM chat_messages WHERE user_key = %s", USER)
        await db.execute("DELETE FROM chat_pending WHERE user_key = %s", USER)
        await db.execute("DELETE FROM advice_sessions WHERE user_key = %s", USER)
        await db.execute("DELETE FROM users WHERE user_key = %s", USER)
        await llm.close_client()
        await db.close_pool()
    avg = lambda xs: f"{sum(xs) / len(xs):.1f}/5" if xs else "-"
    summary = [f"**Automatic checks passed: {totals['passed']}/{totals['checks']}** · judge averages: warm {avg(totals['warm'])}, "
               f"answered {avg(totals['answered'])}, specific {avg(totals['specific'])} · repeated refusals: {totals['refusal_repeats']}", ""]
    return "\n".join(out[:3] + summary + out[3:]) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="local,live,hybrid")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--conversations", action="store_true", help="run the conversation evaluation instead")
    a = ap.parse_args()
    if a.conversations:
        print(asyncio.run(run_conversations()))
    else:
        print(asyncio.run(run([m for m in a.modes.split(",") if m in MODES], a.limit)))
