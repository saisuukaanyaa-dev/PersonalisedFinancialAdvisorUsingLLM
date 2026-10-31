"""Team usage report:  ./scripts/usage-report.sh   - plans, chat questions and AI cost per user."""
import asyncio

from . import db
from .usage import USD_TO_INR


async def main() -> None:
    await db.open_pool()
    rows = await db.usage_by_user()
    await db.close_pool()
    if not rows:
        print("No plans or chat questions yet.")
        return
    print(f"{'User':32} {'Plans':>6} {'₹/plan':>8} {'Questions':>10} {'₹/question':>11} {'Total ₹':>9} {'Total $':>9}")
    tp = tq = tusd = 0
    for r in rows:
        usd = (r["plan_usd"] or 0) + (r["chat_usd"] or 0)
        per_plan = r["plan_usd"] / r["metered_plans"] * USD_TO_INR if r["metered_plans"] else 0
        per_q = r["chat_usd"] / r["questions"] * USD_TO_INR if r["questions"] else 0
        print(f"{r['user_key'][:32]:32} {r['plans']:>6} {per_plan:>8.3f} {r['questions']:>10} {per_q:>11.3f} "
              f"{usd * USD_TO_INR:>9.2f} {usd:>9.4f}")
        tp, tq, tusd = tp + r["plans"], tq + r["questions"], tusd + usd
    print(f"{'ALL USERS':32} {tp:>6} {'':>8} {tq:>10} {'':>11} {tusd * USD_TO_INR:>9.2f} {tusd:>9.4f}")
    print(f"(prices from .env; $1 = ₹{USD_TO_INR}; ₹/plan averages metered plans only - plans made before metering have no cost record)")


if __name__ == "__main__":
    asyncio.run(main())
