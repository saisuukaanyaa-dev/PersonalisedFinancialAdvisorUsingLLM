"""Current allocation + the RISK PLAN (v3.2 'Compute Allocation Metrics').

The plan is decided here, in code, so every later step follows one rulebook: what the user said they
can stomach, capped by what their goal date and safety net can actually afford.
"""
from datetime import date

from ..money import fmt_short

LEVELS = ["Low", "Medium", "High"]
TARGET = {
    "Low": {"equity": 15, "debt": 70, "gold": 10, "cash": 5},
    "Medium": {"equity": 50, "debt": 35, "gold": 10, "cash": 5},
    "High": {"equity": 70, "debt": 20, "gold": 7, "cash": 3},
}
INSTRUMENTS = {
    "Low": {"equity": "Nifty 50 index fund (SIP)", "debt": "Bank FD / RD, PPF, short-term debt funds",
            "gold": "Sovereign Gold Bonds or gold ETF", "cash": "Savings account / liquid fund"},
    "Medium": {"equity": "Nifty 50 index fund + large-cap / flexi-cap mutual funds", "debt": "PPF, FD / RD",
               "gold": "Sovereign Gold Bonds or gold ETF", "cash": "Liquid fund"},
    "High": {"equity": "Flexi-cap & mid-cap mutual funds + index fund", "debt": "PPF / short-duration debt funds",
             "gold": "Sovereign Gold Bonds or gold ETF", "cash": "Liquid fund"},
}
CLASS_RETURN = {"equity": 11, "debt": 7, "gold": 8, "cash": 4}   # long-run planning returns, % a year


def weights(kind: str) -> dict[str, float]:
    """How one holding splits across the four classes. Hybrid funds count as half equity, half fixed income."""
    t = str(kind or "").lower()
    if any(k in t for k in ("gold", "sgb", "silver")):
        return {"gold": 1.0}
    if "hybrid" in t or "balanced" in t:
        return {"equity": 0.5, "debt": 0.5}
    if "liquid" in t or "money market" in t or "overnight" in t:
        return {"cash": 1.0}
    if "debt" in t or "gilt" in t or "bond" in t:
        return {"debt": 1.0}
    return {classify(kind): 1.0}


def classify(kind: str) -> str:
    t = str(kind or "").lower()
    if any(k in t for k in ("gold", "sgb", "silver")):
        return "gold"
    if any(k in t for k in ("etf", "stock", "equity", "mutual fund", "mf", "index", "nps", "elss")):
        return "equity"
    if any(k in t for k in ("fd", "fixed deposit", "bond", "ppf", "epf", "debt", "rd", "recurring")):
        return "debt"
    return "cash"


def goal_mix(stated: str, years: float) -> dict:
    """The risk a goal can carry and its target mix: the stated appetite, capped by the goal's own horizon.
    Shared by the main goal's risk plan and every extra goal (v1.7), so all goals follow one rulebook."""
    stated = stated if stated in LEVELS else "Medium"
    cap = "Low" if years < 3 else "Medium" if years < 5 else "High"
    effective = LEVELS[min(LEVELS.index(stated), LEVELS.index(cap))]
    target = dict(TARGET[effective])
    instruments = dict(INSTRUMENTS[effective])
    if years < 3:
        target = {"equity": 0, "debt": 85, "gold": 5, "cash": 10}
        instruments["debt"] = "Bank FD / RD matching your goal date, short-term debt funds"
    return {"stated": stated, "cap": cap, "effective": effective, "target": target, "instruments": instruments,
            "expected_return_pct": round(sum(target[k] / 100 * CLASS_RETURN[k] for k in target), 2)}


def months_to(target_date: str) -> int:
    try:
        t = date.fromisoformat(str(target_date)[:10])
    except ValueError:
        return 1
    return max(1, round((t - date.today()).days / 30.44))


def allocation_and_risk(d: dict) -> dict:
    cur = d["profile"].get("currency") or "INR"
    totals = {"equity": 0.0, "debt": 0.0, "gold": 0.0, "cash": 0.0}
    for h in d.get("savings_investments", []):
        for k, w in weights(h.get("type")).items():
            totals[k] += float(h.get("current_value") or 0) * w
    grand = sum(totals.values())
    pct = {k: round(v / grand * 100, 1) if grand else 0 for k, v in totals.items()}

    months = months_to(d["goal"].get("target_date"))
    years = months / 12

    # 1. The time horizon caps the risk the goal can carry, whatever the appetite.
    mix = goal_mix(d["profile"].get("risk_appetite"), years)
    stated, cap, effective = mix["stated"], mix["cap"], mix["effective"]
    reasons = []
    if effective != stated:
        reasons.append(
            f"Your goal is {years:.1f} years away - money needed that soon should not sit in shares, so we plan at Low risk."
            if years < 3 else
            f"Your goal is {years:.1f} years away - enough for mutual funds, but too short to ride out a deep market fall, "
            "so we plan at Medium risk.")

    # 2. Direct stocks need a safety net first.
    ef = d.get("emergency_fund", {})
    ef_months = float(ef.get("months_of_expenses_covered") or 0)
    expenses = float(ef.get("monthly_essential_expenses") or 0)
    health = sum(float(i.get("sum_assured") or 0) for i in d.get("insurance", []) if "health" in str(i.get("type")).lower())
    costly = [l for l in d.get("liabilities", []) if float(l.get("interest_rate") or 0) > 12]
    blockers = []
    if ef_months < 3:
        blockers.append(f"Build your emergency fund to at least 3 months of expenses ({fmt_short(expenses * 3, cur)}) - "
                        f"you have {ef_months:g} months today.")
    if health <= 0:
        blockers.append("Get health insurance - one hospital bill could force you to sell shares at a loss.")
    if costly:
        blockers.append("Clear loans above 12% interest first (" +
                        ", ".join(f"{l['type']} at {l['interest_rate']:g}%" for l in costly) +
                        ") - they cost more than shares typically earn.")
    if years < 3:
        blockers.insert(0, "Your goal is under 3 years away - that money should not be in shares at all, directly or through funds.")
    elif effective == "Low":
        blockers.insert(0, "Direct stocks do not suit a Low-risk plan - equity exposure stays in diversified index funds.")
    elif years < 5:
        blockers.insert(0, "Direct stocks need at least a 5-year horizon.")
    stocks_ok = not blockers

    # 3. Target mix per level.
    target, instruments, expected = mix["target"], mix["instruments"], mix["expected_return_pct"]

    return {
        "totals_by_class": totals, "total_value": grand, "current_pct": pct,
        "months_to_goal": months, "years_to_goal": round(years, 1),
        "risk_plan": {
            "stated_risk": stated, "horizon_cap": cap, "effective_risk": effective, "reasons": reasons,
            "target_allocation": target, "instruments": instruments,
            "direct_stocks_allowed": stocks_ok, "direct_stock_blockers": blockers,
            "direct_stock_share_pct": 0 if not stocks_ok else 25 if effective == "High" else 10,
            # rules for a "watchlist": the same limits, shown for when the safety net is ready
            "watch_rules": {
                "max_drawdown_pct": -45 if effective == "High" and years >= 10 else -35,
                "max_volatility_pct": 38 if effective == "High" else 30,
                "min_cagr_to_volatility": 0.5,
                "max_per_sector": 2,
            } if years >= 3 else None,
            "stock_rules": {
                "max_drawdown_pct": -45 if effective == "High" and years >= 10 else -35,   # no deeper fall than this
                "max_volatility_pct": 38 if effective == "High" else 30,
                "min_cagr_to_volatility": 0.5,                                        # growth >= half the swing
                "max_per_sector": 2,
            } if stocks_ok else None,
            "class_return_assumptions_pct": CLASS_RETURN,
            "expected_return_pct": expected,
        },
    }
