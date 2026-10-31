"""The plan pipeline.

1. compute()   - all numbers, in code (a few milliseconds)
2. screen()    - NIFTY 50 shortlist from one market-analyzer call (cached)
3. save        - profile + report with computed text  -> the report page can open immediately
4. background  - RAG + two parallel AI calls replace the computed text when ready (the page swaps it in)
"""
from __future__ import annotations

import asyncio
import copy
import logging
import secrets
import time

import httpx

from . import db, tracing, usage
from .ai import narrative
from .config import settings
from .engine import compute, deposits
from .engine.stocks import five_year_all, screen

log = logging.getLogger("pfa.pipeline")
_background: set[asyncio.Task] = set()
REPORT_VERSION = 1


async def _shortlist(facts: dict) -> tuple[list[dict], dict]:
    """Stocks for the plan (when allowed), or a watchlist under the same limits (when the safety net isn't ready)."""
    plan = facts["risk_plan"]
    rules = plan["stock_rules"] or plan.get("watch_rules")
    if not rules:
        return [], {}
    try:
        async with httpx.AsyncClient() as client:
            rows, period = await five_year_all(client)
        res = screen(rows, rules)
        info = {"screened": res["screened"], "passed": res["passed"], "period": period}
        if plan["stock_rules"]:
            return res["picks"], info
        return [], {**info, "watchlist": res["picks"]}
    except httpx.HTTPError as e:
        log.warning("market-analyzer unavailable: %s", e)
        return [], {"error": "Market data is unavailable right now."}


def _age(profile: dict) -> float | None:
    try:
        return float(profile.get("profile", {}).get("age"))
    except (TypeError, ValueError):
        return None


async def create_plan(profile: dict, question: str, change_log: list[str] | None = None,
                      parent: str | None = None) -> str:
    with tracing.span("Build plan", "CHAIN", pfa__trigger="chat" if change_log else "intake",
                      pfa__changes=change_log or None, pfa__parent_report=parent) as s:
        tracing.user(s, profile["user_key"])
        tracing.io(s, input={k: profile.get(k) for k in ("profile", "goal", "liabilities", "savings_investments",
                                                         "insurance", "emergency_fund")})
        report_id = await _create_plan(profile, question, change_log, parent)
        s.set_attribute("pfa.report_id", report_id)
        return report_id


async def _create_plan(profile: dict, question: str, change_log: list[str] | None, parent: str | None) -> str:
    t0 = time.perf_counter()
    with tracing.span("Compute numbers", "CHAIN") as s:
        facts = compute(profile)
        pr, plan = facts["projection"], facts["risk_plan"]
        tracing.io(s, output={"verdict": pr["verdict"], "projected": pr["projected_value"], "target": pr["target_amount"],
                              "required_monthly": pr["required_monthly"], "effective_risk": plan["effective_risk"],
                              "direct_stocks_allowed": plan["direct_stocks_allowed"], "monthly_plan": facts["monthly_plan"]["rows"]})
    # v1.5: Low risk (or a goal under 3 years) -> the team's bank deposit planner fills the fixed-income part
    if deposits.applies(facts):
        with tracing.span("Bank deposit planner", "TOOL", tool__name="engine.deposits.for_plan") as s:
            dp = deposits.for_plan(facts, age=_age(profile))
            tracing.io(s, input={"monthly_fixed_income": dp.get("monthly_amount"), "goal_share": dp.get("goal_share"),
                                 "goal_date": dp.get("goal_date")},
                       output={"ok": dp.get("ok"), "verdict": dp.get("verdict"),
                               "steps": [f"{x['bank']} {x['term_months']}m @ {x['rate_pct']}%" for x in dp.get("steps", [])]})
    t1 = time.perf_counter()
    with tracing.span("Screen NIFTY 50", "TOOL", tool__name="market-analyzer /five-year/all") as s:
        picks, screen_info = await _shortlist(facts)
        tracing.io(s, input=facts["risk_plan"]["stock_rules"] or "direct stocks not allowed",
                   output={"picks": [p["symbol"] for p in picks], **{k: v for k, v in screen_info.items() if k != "period"}})
    t2 = time.perf_counter()
    user_id = await db.save_profile(profile)
    snapshot = copy.deepcopy(profile)
    snapshot.pop("answers", None)
    report_id = secrets.token_hex(12)
    report = {
        "version": REPORT_VERSION,
        "status": "writing" if settings.ai_enabled else "ready",
        "profile": snapshot,
        **facts,
        "picks": picks, "screen": screen_info,
        "ai": narrative.fallback(profile, facts, picks),
        "change_log": change_log or [], "parent": parent,
        "timings": {"compute_ms": round((t1 - t0) * 1000, 1), "market_ms": round((t2 - t1) * 1000)},
        "started_at": time.time(),
    }
    await db.save_report(report_id, user_id, profile["user_key"], question, report)
    report["timings"]["first_view_ms"] = round((time.perf_counter() - t0) * 1000)
    await db.update_report_ai(report_id, report["ai"], report["status"], report["timings"])
    if settings.ai_enabled:
        task = asyncio.create_task(_write_ai(report_id, profile, facts, picks, t0))
        _background.add(task)
        task.add_done_callback(_background.discard)
    return report_id


async def _write_ai(report_id: str, profile: dict, facts: dict, picks: list[dict], t0: float) -> None:
    meter = usage.start()                       # this plan's own meter (not the chat's that may have started it)
    with tracing.span("Write explanation", "CHAIN", pfa__report_id=report_id) as s:
        tracing.user(s, profile["user_key"])
        await _write_ai_metered(report_id, profile, facts, picks, t0, meter, s)


async def _write_ai_metered(report_id, profile, facts, picks, t0, meter, s) -> None:
    try:
        ai, timings = await narrative.write(profile, facts, picks)
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000)
        summary = meter.summary()
        await db.update_report_ai(report_id, ai, "ready", timings, summary)
        tracing.io(s, output={k: ai.get(k) for k in ("headline", "summary", "priority_actions", "source")})
        if s.is_recording():
            s.set_attribute("pfa.cost_usd", summary["cost_usd"])
            s.set_attribute("pfa.cost_inr", summary["cost_inr"])
            s.set_attribute("llm.token_count.total", summary["input_tokens"] + summary["output_tokens"])
    except Exception as e:                         # the computed text stays; the page stops waiting
        log.exception("AI writing failed for %s", report_id)
        await db.update_report_ai(report_id, narrative.fallback(profile, facts, picks), "ready",
                                  {"ai_error": str(e)[:200]}, meter.summary())
