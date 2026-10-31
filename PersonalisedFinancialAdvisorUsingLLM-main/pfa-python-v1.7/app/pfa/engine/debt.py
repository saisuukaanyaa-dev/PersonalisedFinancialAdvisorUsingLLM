"""Debt metrics (v3.2 'Compute Debt Metrics')."""


def debt_metrics(d: dict) -> dict:
    loans = d.get("liabilities", [])
    salary = float(d.get("profile", {}).get("current_monthly_salary") or 0)
    total = sum(float(l.get("outstanding_amount") or 0) for l in loans)
    emi = sum(float(l.get("emi") or 0) for l in loans)
    weighted = (sum(float(l.get("outstanding_amount") or 0) * float(l.get("interest_rate") or 0) for l in loans) / total
                if total > 0 else 0)
    costly = [l for l in loans if float(l.get("interest_rate") or 0) > 12]
    return {
        "liabilities": loans,
        "total_debt": total,
        "total_emi": emi,
        "weighted_interest_pct": round(weighted, 2),
        "debt_to_income_pct": round(emi / salary * 100, 1) if salary > 0 else 0,
        "high_interest": costly,
        "strategy": ("avalanche (highest interest first)" if costly else
                     "snowball (smallest balance first)" if len(loans) > 1 else "n/a - single or no debt"),
    }
