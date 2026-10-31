"""Report view model: saved report JSON -> everything the template needs (charts pre-rendered)."""
from __future__ import annotations

import time
from datetime import date

from . import charts
from .money import fmt_short, money
from .profile import GOALS as GOAL_TYPES
from .usage import fmt_inr
from .engine.allocation import weights
from .engine.goals import MAX_EXTRA_GOALS, PRIORITIES

VERDICT = {"on_track": ("On track", "good"), "small_gap": ("Slightly behind", "warning"),
           "large_gap": ("Significant gap", "critical")}
CLASS_COLOR = {"equity": "var(--c-equity)", "debt": "var(--c-debt)", "gold": "var(--c-gold)", "cash": "var(--c-cash)"}
CLASS_LABEL = {"equity": "Equity", "debt": "Fixed income", "gold": "Gold", "cash": "Cash"}
PLAN_COLOR = {"Emergency fund top-up": "var(--c-cash)", "Fixed income": "var(--c-debt)", "Mutual funds": "var(--c-equity)",
              "Direct stocks": "var(--s2)", "Gold": "var(--c-gold)", "Cash buffer": "var(--neutral)"}
AI_TIMEOUT_S = 150
GOAL_STATUS = {"on_track": ("On track", "good"), "funded": ("Funded by the plan", "good"),
               "partly": ("Partly funded", "warning"), "not_funded": ("Not funded yet", "critical")}


def _month_text(v) -> str:
    try:
        return date.fromisoformat(str(v)[:10]).strftime("%b %Y")
    except (TypeError, ValueError):
        return str(v or "")


def _mix_text(mix: dict) -> str:
    names = {"equity": "equity", "debt": "fixed income", "gold": "gold", "cash": "cash"}
    return " · ".join(f"{mix[k]:g}% {names[k]}" for k in ("equity", "debt", "gold", "cash") if mix.get(k))


def goals_view(r: dict, cur: str) -> dict | None:
    """v1.7: the "Your goals" section - every goal's share of the money, status and the timeline chart."""
    gp = r.get("goals_plan")
    if not gp:
        return None                      # reports made before v1.7
    rows = []
    for g in gp["goals"]:
        label, status = GOAL_STATUS[g["status"]]
        rows.append({**g, "date_text": _month_text(g["target_date"]), "mix_text": _mix_text(g["mix"]),
                     "status_label": label, "status_color": charts.STATUS[status][0],
                     "reachable_text": _month_text(g["reachable_date"]) if g.get("reachable_date") else None})
    return {"gp": gp, "rows": rows, "chart": charts.goals_timeline(gp["timeline"], gp["goals"], cur),
            "can_add": gp["count"] - 1 < MAX_EXTRA_GOALS, "max_extra": MAX_EXTRA_GOALS, "priorities": PRIORITIES}


def _ddate(v) -> str:
    """'2027-04-01' -> '01 Apr 2027' (bank deposit dates)."""
    try:
        return date.fromisoformat(str(v)[:10]).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return str(v or "")


def view(r: dict) -> dict:
    p, s, pr, plan, mp, ai = r["profile"], r["snapshot"], r["projection"], r["risk_plan"], r["monthly_plan"], r["ai"]
    cur = p["profile"].get("currency") or "INR"
    sh = lambda n: fmt_short(n, cur)
    mo = lambda n: money(n, cur)
    verdict_label, status = VERDICT[pr["verdict"]]
    writing = r.get("status") == "writing" and time.time() - r.get("started_at", 0) < AI_TIMEOUT_S

    # where the pay goes (shares of in-hand pay; overspend shown past a marked pay line)
    salary = float(s["monthly_salary"] or 0)
    flow = [{"key": "Essentials", "value": s["monthly_expenses"], "color": "var(--s1)"},
            {"key": "Loan EMIs", "value": s["total_emi"], "color": "var(--s2)"},
            {"key": "Investing", "value": s["monthly_investing"], "color": "var(--s3)"},
            {"key": "Free cash", "value": max(0, s["free_cash_after_investing"]), "color": "var(--s4)"}]
    outflow = s["monthly_expenses"] + s["total_emi"] + s["monthly_investing"]
    overspend = outflow - salary
    scale = max(salary, outflow) or 1
    flow_bar = charts.stack_bar([{**f, "value": f["value"]} for f in flow], scale, cur)
    flow_items = [dict(f) for f in flow]
    if overspend > 0:
        flow_items[3] = {"key": "Shortfall", "value": overspend, "color": "var(--critical)"}

    # own vs owe
    tbc = r["allocation"]["totals_by_class"]
    class_parts = [{"key": "Equity", "value": tbc["equity"], "color": CLASS_COLOR["equity"]},
                   {"key": "Fixed income (FD/PPF)", "value": tbc["debt"], "color": CLASS_COLOR["debt"]},
                   {"key": "Gold", "value": tbc["gold"], "color": CLASS_COLOR["gold"]},
                   {"key": "Cash", "value": tbc["cash"], "color": CLASS_COLOR["cash"]}]
    own_parts = [dict(c, key="Cash & emergency fund", value=c["value"] + s["emergency_fund_amount"]) if c["key"] == "Cash" else c
                 for c in class_parts]
    own_total = sum(c["value"] for c in own_parts)
    loans = [{"key": f"{l['type']} @ {l['interest_rate']:g}%", "type": l["type"], "value": float(l["outstanding_amount"] or 0),
              "rate": float(l["interest_rate"] or 0), "emi": float(l["emi"] or 0),
              "color": "var(--critical)" if float(l["interest_rate"] or 0) > 12 else "var(--neutral)"}
             for l in p.get("liabilities", [])]
    owe_total = sum(l["value"] for l in loans)
    scale_max = max(own_total, owe_total) or 1

    # "What you own today" pie (investments by class + the emergency fund) and the target mix
    own_pie_parts = [{"key": "Equity (shares, equity funds)", "value": tbc["equity"], "color": CLASS_COLOR["equity"]},
                     {"key": "Fixed income (FD, PPF, EPF, debt funds)", "value": tbc["debt"], "color": CLASS_COLOR["debt"]},
                     {"key": "Gold", "value": tbc["gold"], "color": CLASS_COLOR["gold"]},
                     {"key": "Savings & cash", "value": tbc["cash"], "color": CLASS_COLOR["cash"]},
                     {"key": "Emergency fund", "value": s["emergency_fund_amount"], "color": "var(--s2)"}]
    tgt = plan["target_allocation"]
    target_pie_parts = [{"key": CLASS_LABEL[k], "value": tgt[k], "color": CLASS_COLOR[k]} for k in ("equity", "debt", "gold", "cash")]
    inv_total = sum(tbc.values())
    own_total_all = inv_total + s["emergency_fund_amount"]
    if inv_total > 0:
        eq_now = tbc["equity"] / inv_total * 100
        biggest = max(own_pie_parts, key=lambda x: x["value"])
        pie_sentence = (f"{biggest['value'] / own_total_all * 100:.0f}% of your money is in {biggest['key'].split(' (')[0].lower()}. "
                        f"Of your investments, {eq_now:.0f}% are in equity; your {plan['effective_risk']}-risk plan aims for "
                        f"{tgt['equity']}%" + (", so new money leans towards equity." if tgt["equity"] > eq_now + 5 else
                                              ", so new money leans towards fixed income and gold." if tgt["equity"] < eq_now - 5 else
                                              " - you are already close."))
    else:
        pie_sentence = "You have no investments recorded yet - the monthly plan below shows where to start."

    # ---- v1.3: where the monthly investing goes now, and "your SIPs now vs the plan"
    BUCKET_OF = {"equity": "Mutual funds", "debt": "Fixed income", "gold": "Gold", "cash": "Cash buffer"}
    now_by_bucket: dict[str, float] = {}
    sip_class = {"equity": 0.0, "debt": 0.0, "gold": 0.0, "cash": 0.0}
    for h in p.get("savings_investments", []):
        m = float(h.get("monthly_contribution") or 0)
        if not m:
            continue
        for k, w in weights(h.get("type")).items():
            sip_class[k] += m * w
            bucket = "Direct stocks" if h.get("_key") == "stocks" else BUCKET_OF[k]
            now_by_bucket[bucket] = now_by_bucket.get(bucket, 0) + m * w
    ef_monthly_now = float(p.get("emergency_fund", {}).get("monthly_topup") or 0)
    if ef_monthly_now:
        now_by_bucket["Emergency fund top-up"] = ef_monthly_now
    sip_total = sum(sip_class.values())
    sip_pie = charts.pie([{"key": "Equity (funds + stocks)", "value": sip_class["equity"], "color": CLASS_COLOR["equity"]},
                          {"key": "Fixed income", "value": sip_class["debt"], "color": CLASS_COLOR["debt"]},
                          {"key": "Gold", "value": sip_class["gold"], "color": CLASS_COLOR["gold"]},
                          {"key": "Savings & cash", "value": sip_class["cash"], "color": CLASS_COLOR["cash"]}],
                         "Where your monthly investing goes now", size=170, cur=cur) if sip_total else None
    plan_by_bucket = {x["bucket"]: x["amount"] for x in mp["rows"]}
    order = ["Emergency fund top-up", "Fixed income", "Mutual funds", "Direct stocks", "Gold", "Cash buffer"]
    tgt_pct = {"Fixed income": plan["target_allocation"]["debt"], "Mutual funds": plan["target_allocation"]["equity"],
               "Gold": plan["target_allocation"]["gold"], "Cash buffer": plan["target_allocation"]["cash"]}
    sip_rows = []
    for b in order:
        now, sug = now_by_bucket.get(b, 0), plan_by_bucket.get(b, 0)
        if not now and not sug:
            continue
        if b == "Emergency fund top-up":
            why = (f"Reach 6 months of essentials ({sh(s['emergency_fund_target'])}) first - "
                   + (f"about {mp.get('emergency_months_to_target')} months at this rate." if mp.get("emergency_months_to_target") else "it protects the plan."))
        elif b == "Direct stocks" and not plan["direct_stocks_allowed"]:
            why = "Paused for now: " + (plan["direct_stock_blockers"][0] if plan["direct_stock_blockers"] else "not part of this plan.")
        elif b == "Direct stocks":
            why = f"Your {plan['effective_risk']}-risk plan lets up to {plan['direct_stock_share_pct']}% of goal investing go to hand-picked stocks."
        else:
            why = f"Your {plan['effective_risk']}-risk mix puts {tgt_pct.get(b, 0)}% of goal investing here."
            if b == "Mutual funds" and now_by_bucket.get("Direct stocks") and not plan["direct_stocks_allowed"]:
                why += " It also takes the equity money paused from direct stocks."
        sip_rows.append({"bucket": b, "now": now, "suggested": sug, "delta": sug - now, "why": why,
                         "color": PLAN_COLOR.get(b, "var(--neutral)")})
    watchlist = [dict(x, worst_10k=mo(10000 * (1 - abs(x["max_drawdown_pct"]) / 100)))
                 for x in (r.get("screen") or {}).get("watchlist") or []]

    # allocation now vs target
    now = r["allocation"]["current_pct"]
    alloc_rows = []
    for k in ("equity", "debt", "gold", "cash"):
        n, t = float(now[k]), float(plan["target_allocation"][k])
        d = round(t - n, 1)
        alloc_rows.append({"key": k, "label": CLASS_LABEL[k], "color": CLASS_COLOR[k], "now": n, "to": t, "delta": d,
                           "dir": "up" if d > 0.5 else "down" if d < -0.5 else "flat",
                           "why": ai["allocation_rationale"].get("fixed_income" if k == "debt" else k) or plan["instruments"][k]})

    # safety net
    efm = s["months_of_expenses_covered"]
    term, term_rec = s["term_cover"], s["recommended_term_cover"]
    health, health_rec = s["health_cover"], s["recommended_health_cover"]
    dti = s["debt_to_income_pct"]
    meters = [
        charts.meter("Emergency fund", f"{efm:g} of 6 months", efm / 6, "good" if efm >= 6 else "warning" if efm > 0 else "critical",
                     "Six months of essentials covered." if efm >= 6 else
                     f"Target {sh(s['emergency_fund_target'])} - {sh(max(0, s['emergency_fund_target'] - s['emergency_fund_amount']))} to go."),
        charts.meter("Term life cover", sh(term) if term else "None", term / term_rec if term_rec else 0,
                     "good" if term >= term_rec and term > 0 else "warning" if term > 0 else "critical",
                     f"Guide: about 10× annual income ({sh(term_rec)})."),
        charts.meter("Health cover", sh(health) if health else "None",
                     health / health_rec if health_rec else (1 if health > 0 else 0),
                     "good" if health > 0 and (not health_rec or health >= health_rec) else "warning" if health > 0 else "critical",
                     f"Guide: at least {sh(health_rec)} for a family in a metro." if health_rec else "Check the cover suits local hospital costs."),
        charts.meter("EMIs vs take-home", f"{dti:.1f}%", dti / 60, "good" if dti <= 30 else "warning" if dti <= 40 else "critical",
                     "Within the 40% comfort line." if dti <= 40 else "Above the 40% comfort line.",
                     "Healthy" if dti <= 30 else "Watch it" if dti <= 40 else "Too high"),
    ]

    # stocks
    notes = {n["symbol"]: n["rationale"] for n in ai.get("stock_notes") or []}
    picks = [dict(x, rationale=notes.get(x["symbol"], x["rationale"]),
                  worst_10k=mo(10000 * (1 - abs(x["max_drawdown_pct"]) / 100))) for x in r.get("picks") or []]
    max_cagr = max([1] + [abs(x["five_year_cagr_pct"]) for x in picks])
    stock_monthly = next((x["amount"] for x in mp["rows"] if x["bucket"] == "Direct stocks"), 0)

    plan_segs = [{"key": x["bucket"], "value": x["amount"], "color": PLAN_COLOR.get(x["bucket"], "var(--neutral)")} for x in mp["rows"]]
    try:
        target_date_text = date.fromisoformat(pr["target_date"]).strftime("%b %Y")
    except (TypeError, ValueError):
        target_date_text = str(pr["target_date"])
    ctc_note = (f"CTC {sh(s['annual_ctc'])} · in-hand {sh(salary)}/mo" + (" (estimated)" if s["in_hand_source"] == "estimated_from_ctc" else "")
                if s.get("annual_ctc") else "")
    t = r.get("timings") or {}
    return {
        "r": r, "p": p, "s": s, "pr": pr, "plan": plan, "mp": mp, "ai": ai, "cur": cur, "sh": sh, "mo": mo,
        "dp": r.get("deposit_plan"), "ddate": _ddate,
        "goals": goals_view(r, cur), "goal_types": GOAL_TYPES, "month_text": _month_text,
        "writing": writing, "verdict_label": verdict_label, "status": status,
        "status_color": charts.STATUS[status][0], "status_icon": charts.STATUS[status][1],
        "ring": charts.ring(pr["progress_pct"], status),
        "projection_chart": charts.projection_chart(pr, cur),
        "target_date_text": target_date_text, "ctc_note": ctc_note,
        "flow_bar": flow_bar, "flow_legend": charts.legend(flow_items, salary, cur), "salary": salary,
        "overspend": overspend, "outflow": outflow, "pay_marker_pct": salary / scale * 100,
        "own_bar": charts.stack_bar(own_parts, own_total, cur), "own_total": own_total, "own_width": own_total / scale_max * 100,
        "own_legend": charts.legend([c for c in own_parts if c["value"] > 0], own_total, cur),
        "loans": sorted(loans, key=lambda l: -l["rate"]), "owe_total": owe_total, "owe_width": owe_total / scale_max * 100,
        "owe_bar": charts.stack_bar(loans, owe_total, cur),
        "donut": charts.donut(class_parts, sh(s["total_savings_investments"]), "invested", cur),
        "alloc_rows": alloc_rows, "meters": meters,
        "own_pie": charts.pie(own_pie_parts, "What you own today", cur=cur), "own_total_all": own_total_all,
        "target_pie": charts.pie(target_pie_parts, "Target mix for your investments", size=170, show_money=False),
        "pie_sentence": pie_sentence,
        "sip_pie": sip_pie, "sip_total": sip_total, "sip_rows": sip_rows,
        "sip_rows_total": (sum(x["now"] for x in sip_rows), sum(x["suggested"] for x in sip_rows)),
        "watchlist": watchlist,
        "plan_bar": charts.stack_bar(plan_segs, mp["total"], cur), "plan_color": PLAN_COLOR,
        "picks": picks, "max_cagr": max_cagr, "stock_monthly": stock_monthly,
        "timing_text": _timing_text(t),
        "usage_text": _usage_text(r.get("usage")),
    }


def _usage_text(u: dict | None) -> str:
    if not u:
        return ""
    tokens = u.get("input_tokens", 0) + u.get("output_tokens", 0)
    return (f"AI cost of this plan {fmt_inr(u['cost_inr'])} (${u['cost_usd']:.4f}) · {u.get('ai_calls', 0)} AI calls + "
            f"{u.get('embed_calls', 0)} search · {tokens:,} tokens")


def _timing_text(t: dict) -> str:
    parts = []
    if "first_view_ms" in t:
        parts.append(f"numbers and charts in {t['first_view_ms'] / 1000:.2f} s")
    if "total_ms" in t:
        parts.append(f"AI explanation in {t['total_ms'] / 1000:.1f} s")
    return "Built " + " · ".join(parts) if parts else ""
