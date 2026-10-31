"""End-to-end smoke test for the bank deposit planner (v1.5), with made-up data. Inside the app container:
    docker compose exec -T app python -m pfa.eval.deposits_smoke
Builds a Low-risk plan, checks the report's deposit section, then asks the chat three deposit questions.
Uses the configured OpenAI endpoint (with the mock in tools/mock_openai.py it costs nothing). Cleans up after itself."""
from __future__ import annotations

import asyncio
import re
import sys
from datetime import date, timedelta

from .. import db, pipeline, report
from ..ai import chat, llm
from ..profile import build_profile

USER = "deposit-smoke@test.local"
LOW = {"name": "Test Lowrisk", "age": "34", "currency": "INR", "ctc": "12L", "goal_type": "Buy a car", "goal_details": "",
       "target_amount": "8L", "target_date": (date.today() + timedelta(days=round(365.25 * 3.5))).isoformat(),
       "take_home": "88.5K", "expenses": "40K", "emergency": "2.4L", "term_cover": "1Cr", "health_cover": "10L",
       "loan_types": ["None - I'm debt-free"], "loans": {},
       "inv": {"mf_value": "1L", "mf_monthly": "5K", "fd_value": "50K", "pf_value": "2L", "pf_monthly": "3.6K"},
       "risk": "Low", "_loans_answered": True}
QUESTIONS = [
    ("What are the best FD rates at SBI?", "deposits", r"State Bank of India|%"),
    ("I have 3L now and can put 10k a month in RD. I need 8L by 2030 - which FDs and RDs?", "deposits", r"RD: \*\*|FD: \*\*|deposit planner"),
    ("Explain how fixed deposits work", "local", r"."),
]


async def main() -> int:
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= bool(cond)
        print(("PASS " if cond else "FAIL ") + label + (f" - {detail}" if detail and not cond else ""))

    await db.open_pool()
    llm.open_client()
    try:
        profile = build_profile(LOW, USER)
        rid = await pipeline.create_plan(profile, "deposit smoke test")
        for _ in range(60):                                    # wait for the (mock) AI text
            r = await db.load_report(rid, USER)
            if r.get("status") == "ready":
                break
            await asyncio.sleep(1)
        dp = r.get("deposit_plan")
        check("Low-risk plan has a deposit plan", bool(dp and dp.get("ok") and dp.get("steps")), str(dp)[:200])
        fi = next((x for x in r["monthly_plan"]["rows"] if x["bucket"] == "Fixed income"), {})
        check("Fixed income row names the banks", str(fi.get("instrument", "")).startswith("Bank RD: "), fi.get("instrument", ""))
        from ..main import templates
        html = templates.env.get_template("_report_main.html").render(**report.view(r), report_id=rid)
        check("Report shows the Bank deposits section", "Bank deposits for your fixed-income part" in html)
        if dp and dp.get("steps"):
            print("     ", " -> ".join(f"{s['bank']} {s['term_months']}m @ {s['rate_pct']}%" for s in dp["steps"]),
                  f"| value {dp['value_on_goal_date']:,} vs share {dp['goal_share']:,}")
        for q, want_route, want_text in QUESTIONS:
            res = await chat.answer(USER, q, rid)
            got = (res.get("route") or {}).get("kind")
            check(f"chat route for {q[:40]!r} is {want_route}", got == want_route, f"got {got}")
            check(f"chat answer for {q[:40]!r}", bool(re.search(want_text, res.get("reply", ""))), res.get("reply", "")[:200])
            print("     ", res.get("reply", "").replace("\n", " | ")[:300])
    finally:
        for t in ("chat_messages", "chat_pending", "advice_sessions", "users"):
            await db.execute(f"DELETE FROM {t} WHERE user_key = %s", USER)
        await llm.close_client()
        await db.close_pool()
    print("ALL PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
