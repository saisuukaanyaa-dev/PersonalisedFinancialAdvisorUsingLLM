"""Goal projection, monthly plan and snapshot (v3.2 'Compute Future Projection').

FV = P(1+r)^n + PMT * (((1+r)^n - 1) / r). Every number in the report originates here, never in an LLM.
"""
from datetime import date


def _round100(x: float) -> int:
    return max(0, int(round(x / 100) * 100))


def emergency_and_investable(d: dict) -> dict:
    """Monthly money after essentials and EMIs, the emergency-fund top-up taken first, and what is left to invest
    (reach 6 months within about a year, never more than 40% of what is left - or the user's own top-up)."""
    expenses = float(d["emergency_fund"].get("monthly_essential_expenses") or 0)
    available = max(0.0, float(d["derived"]["surplus"]))
    ef_gap = max(0.0, expenses * 6 - float(d["emergency_fund"].get("current_amount") or 0))
    own_topup = float(d["emergency_fund"].get("monthly_topup") or 0)
    if ef_gap > 0 and own_topup > 0:              # the user chose their own monthly top-up
        ef_topup = _round100(min(own_topup, available))
    else:
        ef_topup = _round100(min(ef_gap / 12, available * 0.4)) if ef_gap > 0 else 0
    return {"available": available, "ef_gap": ef_gap, "own_topup": own_topup, "ef_topup": ef_topup,
            "investable": max(0.0, available - ef_topup)}


def projection(d: dict, alloc: dict, debt: dict, goals_plan: dict) -> dict:
    """The main goal's projection and the combined monthly plan. v1.7: the main goal uses its share of savings and
    SIPs from goals_plan; the monthly plan adds every goal's SIP, each split by that goal's own mix."""
    plan = alloc["risk_plan"]
    total_corpus = alloc["total_value"]
    main = goals_plan["goals"][0]
    corpus = float(main["corpus"]) if goals_plan["count"] > 1 else total_corpus
    monthly = float(main["current_monthly"]) if goals_plan["count"] > 1 else float(d["derived"]["monthlyContrib"])
    months = alloc["months_to_goal"]
    r = plan["expected_return_pct"] / 100 / 12
    inflation = 6

    def fv_at(m: int, pmt: float) -> float:
        g = (1 + r) ** m
        return corpus * g + pmt * ((g - 1) / r)

    growth = (1 + r) ** months
    fv = fv_at(months, monthly)
    target = float(d["goal"].get("target_amount") or 0)
    gap = round(fv - target, 2)
    required = max(0.0, (target - corpus * growth) / ((growth - 1) / r))
    verdict = "on_track" if gap >= 0 else "large_gap" if abs(gap) > target * 0.15 else "small_gap"

    series = []
    for y in range(max(1, -(-months // 12)) + 1):
        m = min(y * 12, months)
        series.append({"month": m, "current_path": round(fv_at(m, monthly)), "required_path": round(fv_at(m, required))})
        if m == months:
            break

    # Monthly plan: 1) what is left after essentials and EMIs, 2) emergency-fund top-up first (reach 6 months
    # within about a year, never more than 40% of what is left), 3) the goal amount split by the risk plan.
    cur = d["profile"].get("currency") or "INR"
    salary = float(d["profile"].get("current_monthly_salary") or 0)
    expenses = float(d["emergency_fund"].get("monthly_essential_expenses") or 0)
    ei = emergency_and_investable(d)
    available, ef_gap, own_topup, ef_topup, investable = ei["available"], ei["ef_gap"], ei["own_topup"], ei["ef_topup"], ei["investable"]
    ef_months_to_target = (-(-ef_gap // ef_topup)) if ef_gap > 0 and ef_topup > 0 else 0
    goal_monthly = main["funded_monthly"]              # = round100(min(investable, required)) with one goal
    t = plan["target_allocation"]
    equity_amt = goal_monthly * t["equity"] / 100
    stock_amt = _round100(min(equity_amt, goal_monthly * plan["direct_stock_share_pct"] / 100))
    # every goal's SIP split by its own mix (one goal: exactly the main goal's mix)
    by_class = {k: sum(g["funded_monthly"] * g["mix"][k] / 100 for g in goals_plan["goals"]) for k in t}
    extra = [g for g in goals_plan["goals"][1:] if g["funded_monthly"] > 0]

    def instrument(k):
        names = [plan["instruments"][k]] + [g["instruments"][k] for g in extra if g["mix"][k] > 0]
        return " · ".join(dict.fromkeys(names))
    rows = [
        {"bucket": "Emergency fund top-up", "instrument": "Liquid fund / savings account", "amount": ef_topup},
        {"bucket": "Fixed income", "instrument": instrument("debt"), "amount": _round100(by_class["debt"])},
        {"bucket": "Mutual funds", "instrument": instrument("equity"), "amount": _round100(by_class["equity"] - stock_amt)},
        {"bucket": "Direct stocks", "instrument": "NIFTY 50 shortlist below", "amount": stock_amt},
        {"bucket": "Gold", "instrument": instrument("gold"), "amount": _round100(by_class["gold"])},
        {"bucket": "Cash buffer", "instrument": instrument("cash"), "amount": _round100(by_class["cash"])},
    ]
    rows = [x for x in rows if x["amount"] > 0]
    plan_total = sum(x["amount"] for x in rows)

    annual_income = float(d["profile"].get("annual_ctc") or 0) or salary * 12

    def cover(words):
        return sum(float(i.get("sum_assured") or 0) for i in d.get("insurance", [])
                   if any(w in str(i.get("type")).lower() for w in words))

    ef = d["emergency_fund"]
    ef_months = float(ef.get("months_of_expenses_covered") or 0)
    return {
        "snapshot": {
            "annual_ctc": d["profile"].get("annual_ctc"),
            "monthly_salary": salary,
            "in_hand_source": d["profile"].get("in_hand_source"),
            "monthly_expenses": expenses,
            "monthly_surplus": d["derived"]["surplus"],
            "monthly_investing": monthly,
            "free_cash_after_investing": d["derived"]["surplus"] - monthly,
            "savings_rate_pct": d["derived"]["savingsRatePct"],
            "net_worth": d["derived"]["netWorth"],
            "total_liabilities": debt["total_debt"],
            "total_emi": debt["total_emi"],
            "debt_to_income_pct": debt["debt_to_income_pct"],
            "weighted_interest_pct": debt["weighted_interest_pct"],
            "total_savings_investments": total_corpus,
            "emergency_fund_amount": float(ef.get("current_amount") or 0),
            "emergency_fund_target": expenses * 6,
            "emergency_topup_monthly": own_topup,
            "emergency_fund_status": "none" if not ef.get("has_fund") else "adequate" if ef_months >= 6 else "insufficient",
            "months_of_expenses_covered": ef_months,
            "term_cover": cover(("term", "life")),
            "recommended_term_cover": annual_income * 10,
            "health_cover": cover(("health", "medic")),
            "recommended_health_cover": 1000000 if cur == "INR" else None,
        },
        "projection": {
            "target_amount": target,
            "target_date": d["goal"].get("target_date"),
            "months_remaining": months,
            "years_remaining": alloc["years_to_goal"],
            "current_corpus": corpus,
            "current_monthly_contribution": monthly,
            "assumptions": {"expected_annual_return_pct": plan["expected_return_pct"], "inflation_pct": inflation},
            "projected_value": round(fv, 2),
            "inflation_adjusted_target": round(target * (1 + inflation / 100) ** (months / 12), 2),
            "on_track": gap >= 0,
            "verdict": verdict,
            "gap_or_surplus": gap,
            "progress_pct": round(min(100.0, fv / target * 100), 1) if target > 0 else 0,
            "required_monthly": round(required, 2),
            "additional_monthly_needed": round(max(0.0, required - monthly), 2),
            "series": series,
        },
        "monthly_plan": {
            "available": available,
            "emergency_topup": ef_topup,
            "goal_investment": goals_plan["funded_total"],
            "main_goal_investment": goal_monthly,
            "main_fixed_income": _round100(goal_monthly * t["debt"] / 100),
            "goals_underfunded_total": goals_plan["underfunded_total"],
            "total": plan_total,
            "unallocated": max(0.0, available - plan_total),
            "goal_underfunded_by": max(0, round(required - goal_monthly)),
            "emergency_gap": ef_gap,
            "emergency_months_to_target": int(ef_months_to_target),
            "rows": rows,
        },
        "as_of": date.today().isoformat(),
    }
