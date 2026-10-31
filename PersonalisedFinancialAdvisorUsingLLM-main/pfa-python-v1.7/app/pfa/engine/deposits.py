"""Bank deposit planner - the team's OptimalBankDepositFinderAgent maths, in Python.

Same algorithm as the n8n Code node (tools/deposit_optimiser.js), kept in step by a parity test:
  - FD for a lump sum: the teammate's rate-sorted depth-first goal search (GoalSearch.BruteForce), each FD renewed
    `count` times, quarterly compounding.
  - RD for a monthly amount: every month up to the goal date filled with the best mix of back-to-back RDs.
Fixed from the original (see deposits/teammate-fixes/ and docs/BANK_DEPOSITS.md): the standard bank RD maturity
formula, inflation compounded over the whole period, and no crash when nothing fits.

Rates: app/pfa/data/deposit_schemes.csv (211 rows, 10 banks), built from the team's bank documents by
tools/build_deposit_db.py. Pure and fast; the only network call is india_inflation() (World Bank, cached).
"""
from __future__ import annotations

import csv
import math
import re
import time
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import httpx

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "deposit_schemes.csv"
GOAL_REACHED, GOAL_NOT_REACHABLE, GOAL_NOT_YET_REACHED = 1, 2, 3
NOT_POSSIBLE = "Not possible with current fixed/recurring deposits interest rates."
ALIAS = {"sbi": "state bank of india", "pnb": "punjab national", "bob": "bank of baroda", "baroda": "bank of baroda",
         "idfc": "idfc first", "kotak": "kotak mahindra", "indusind": "indusind", "canara": "canara"}
DAYS_PER_MONTH = 30.4375


def jsround(x: float) -> int:
    """Round half up, like JavaScript's Math.round (Python's round() rounds half to even: 730.5 -> 730).
    Keeps day counts and tenors identical to the n8n Code node."""
    return math.floor(x + 0.5)


@lru_cache(maxsize=1)
def load_rows() -> tuple[dict, ...]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            for k in ("duration_months", "interest_rate_general", "interest_rate_senior", "interest_rate_super_senior"):
                r[k] = float(r[k]) if r.get(k) not in (None, "") else None
            for k in ("duration_days", "compounding_months", "installment_months"):
                r[k] = int(float(r[k])) if r.get(k) not in (None, "") else None
            rows.append(r)
    return tuple(rows)


def as_of() -> str:
    rows = load_rows()
    return rows[0]["as_of"] if rows else ""


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        n = float(str(v).replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def _date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def bank_filter(banks) -> list[str]:
    if isinstance(banks, (list, tuple)):
        banks = ",".join(map(str, banks))
    parts = re.split(r"[,;]|\band\b", str(banks or "").lower())
    out = []
    for b in parts:
        b = _norm(b)
        if b and b not in ("any", "all"):
            out.append(_norm(ALIAS.get(b, b)))
    return out


def _norm(name: str) -> str:
    """'State Bank of India' -> 'state of india', 'HDFC Bank' -> 'hdfc': compare names without the word 'bank'."""
    return re.sub(r"\s+", " ", re.sub(r"\bbank\b", " ", str(name).lower())).strip()


def bank_matches(bank_name: str, banks: list[str]) -> bool:
    return not banks or any(b in _norm(bank_name) for b in banks)


def _deposits(kind: str, senior: bool, banks: list[str]) -> list[dict]:
    out = []
    for r in load_rows():
        if r["scheme_type"] != kind or not (r["duration_months"] or 0) > 0:
            continue
        if not bank_matches(r["bank_name"], banks):
            continue
        rate = r["interest_rate_senior"] if senior and r["interest_rate_senior"] else r["interest_rate_general"]
        if not rate or rate <= 0:
            continue
        m = r["duration_months"]
        out.append({"bank": r["bank_name"], "scheme": r["scheme_name"], "tenor": r["tenor_label"], "months": m,
                    "years": m / 12, "comp": (r["compounding_months"] or 3) / 12, "rate": rate, "rate_source": r["rate_source"]})
    return out


# ---------------------------------------------------------------- FD: the teammate's goal search
def plan_fd(amount: float, start: date, goal_date: date, goal: float, inflation: float, deposits: list[dict],
            budget: int = 60000) -> dict:
    sg_time = goal_date
    real = lambda bal, t: bal / (1 + inflation / 100) ** ((t - start).days / 365)
    total_days = (sg_time - start).days
    sort_base = lambda d: (1 + d["rate"] * d["comp"] / 100) ** ((d["years"] / d["comp"]) * math.floor(total_days / (365 * d["years"])))
    A = sorted(deposits, key=sort_base, reverse=True)

    def T(bal, t, d):
        count = math.floor(((sg_time - t).days) / (365 * d["years"])) or 1
        return bal * (1 + d["rate"] * d["comp"] / 100) ** ((d["years"] / d["comp"]) * count), t + timedelta(days=jsround(d["years"] * count * 365)), count

    def is_gr(bal, t):
        if t <= sg_time:
            return GOAL_REACHED if real(bal, t) >= goal else GOAL_NOT_YET_REACHED
        return GOAL_NOT_REACHABLE

    state = {"expanded": 0, "truncated": False, "best": (-1.0, [])}
    failed: dict[date, float] = {}
    stack: list[tuple[dict, int, float, date]] = []

    def brute(bal, t) -> int:
        r = is_gr(bal, t)
        if r != GOAL_NOT_YET_REACHED:
            return r
        if stack and real(bal, t) > state["best"][0]:
            state["best"] = (real(bal, t), list(stack))
        if failed.get(t, -1) >= bal:
            return GOAL_NOT_REACHABLE
        for d in A:
            state["expanded"] += 1
            if state["expanded"] > budget:
                state["truncated"] = True
                return GOAL_NOT_REACHABLE
            nb, nt, count = T(bal, t, d)
            stack.append((d, count, nb, nt))
            if brute(nb, nt) == GOAL_REACHED:
                return GOAL_REACHED
            stack.pop()
        failed[t] = max(failed.get(t, -1), bal)
        return GOAL_NOT_REACHABLE

    reached = brute(amount, start) == GOAL_REACHED
    path = list(stack) if reached else state["best"][1]
    steps, t = [], start
    for d, count, bal, nt in path:
        steps.append({"bank": d["bank"], "scheme": d["scheme"], "tenor": d["tenor"], "term_months": d["months"], "times": count,
                      "rate_pct": d["rate"], "rate_source": d["rate_source"], "start": t.isoformat(), "end": nt.isoformat(),
                      "value_at_end": round(bal), "value_at_end_in_todays_money": round(real(bal, nt))})
        t = nt
    last_bal, last_t = (path[-1][2], path[-1][3]) if path else (amount, start)
    return {"reached": reached, "steps": steps, "final_value": round(last_bal),
            "final_value_in_todays_money": round(real(last_bal, last_t)), "final_date": last_t.isoformat(),
            "search": {"expanded": state["expanded"], "truncated": state["truncated"]}}


# ---------------------------------------------------------------- RD: standard maturity + best back-to-back mix
def rd_maturity(installment: float, rate_pct: float, months: int) -> float:
    """Each monthly installment compounds quarterly until maturity (Indian bank RD formula)."""
    i = rate_pct / 400
    return sum(installment * (1 + i) ** ((months - k + 1) / 3) for k in range(1, months + 1))


def plan_rd(installment: float, start: date, goal_date: date, goal: float, inflation: float, deposits: list[dict]) -> dict:
    months_left = math.floor((goal_date - start).days / DAYS_PER_MONTH)
    cands = []
    for d in deposits:
        n = jsround(d["months"])
        if 1 <= n <= months_left:
            cands.append({"d": d, "n": n, "v": rd_maturity(1, d["rate"], n)})
    if not cands:
        return {"reached": False, "best": None, "alternatives": []}
    best = [0.0] * (months_left + 1)
    choice: list[dict | None] = [None] * (months_left + 1)
    for m in range(1, months_left + 1):
        best[m], choice[m] = best[m - 1] + 1, None            # this month kept as cash
        for c in cands:
            if c["n"] <= m and best[m - c["n"]] + c["v"] > best[m] + 1e-12:
                best[m], choice[m] = best[m - c["n"]] + c["v"], c
    segs: list[list] = []
    m = months_left
    while m > 0:
        c = choice[m]
        if not c:
            m -= 1
            continue
        if segs and segs[-1][0] is c:
            segs[-1][1] += 1
        else:
            segs.append([c, 1])
        m -= c["n"]
    segs.reverse()
    deflate = (1 + inflation / 100) ** (months_left / 12)
    steps, t = [], start
    for c, times in segs:
        end = t + timedelta(days=jsround(c["n"] * times * DAYS_PER_MONTH))
        steps.append({"bank": c["d"]["bank"], "scheme": c["d"]["scheme"], "tenor": c["d"]["tenor"], "term_months": c["n"], "times": times,
                      "rate_pct": c["d"]["rate"], "rate_source": c["d"]["rate_source"], "start": t.isoformat(), "end": end.isoformat(),
                      "value_at_end": round(installment * c["v"] * times)})
        t = end
    cash_months = months_left - sum(c["n"] * times for c, times in segs)
    plan = {"steps": steps, "months": months_left, "cash_months": cash_months, "total_paid": round(installment * months_left),
            "value_on_goal_date": round(installment * best[months_left]),
            "value_in_todays_money": round(installment * best[months_left] / deflate),
            "installment_needed_for_goal": round(goal * deflate / best[months_left]) if goal > 0 else 0}
    alts = []
    for c in cands:
        times = months_left // c["n"]
        v = c["v"] * times + (months_left - c["n"] * times)
        alts.append({"bank": c["d"]["bank"], "tenor": c["d"]["tenor"], "term_months": c["n"], "times": times,
                     "rate_pct": c["d"]["rate"], "value_in_todays_money": round(installment * v / deflate)})
    alts.sort(key=lambda x: -x["value_in_todays_money"])
    return {"reached": installment > 0 and plan["value_in_todays_money"] >= goal, "best": plan, "alternatives": alts[:3]}


# ---------------------------------------------------------------- the whole plan (FD first, then RD for the rest)
def plan_deposits(p: dict) -> dict:
    start = _date(p.get("start_date")) or date.today()
    goal_date = _date(p.get("goal_date"))
    goal, amount = _num(p.get("goal_amount")), _num(p.get("initial_amount")) or 0
    installment, inflation = _num(p.get("monthly_installment")) or 0, _num(p.get("inflation_pct"))
    senior = p.get("senior") is True or bool(re.match(r"^(true|yes|y|1|senior)$", str(p.get("senior") or ""), re.I))
    errors = []
    if not goal_date:
        errors.append("goal_date is required (YYYY-MM-DD)")
    elif goal_date <= start:
        errors.append("goal_date must be in the future")
    if not (goal and goal > 0):
        errors.append("goal_amount must be a positive rupee amount")
    if not amount > 0 and not installment > 0:
        errors.append("give initial_amount (lump sum) and/or monthly_installment")
    if inflation is None or not 0 <= inflation <= 30:
        errors.append("inflation_pct missing or out of range")
    if errors:
        return {"ok": False, "errors": errors}

    banks = bank_filter(p.get("banks"))
    fd = plan_fd(amount, start, goal_date, goal, inflation, _deposits("Fixed Deposit", senior, banks)) if amount > 0 else None
    remaining = max(0.0, goal - (fd["final_value_in_todays_money"] if fd else 0))
    rd = plan_rd(installment, start, goal_date, remaining, inflation, _deposits("Recurring Deposit", senior, banks)) if remaining > 0 else None
    covered = bool((fd and fd["reached"]) or remaining == 0 or (rd and rd["reached"]))
    if covered:
        verdict = "Goal reachable with bank deposits"
    elif (not fd or not fd["steps"]) and (not rd or not rd["best"]):
        verdict = NOT_POSSIBLE
    else:
        verdict = "Goal not reachable with the amounts given - see the shortfall and the installment needed"
    rd_value = rd["best"]["value_in_todays_money"] if rd and rd["best"] and installment > 0 else 0
    return {
        "ok": True, "verdict": verdict,
        "inputs": {"initial_amount": amount, "monthly_installment": installment, "goal_amount_todays_money": goal,
                   "goal_amount_on_goal_date": round(goal * (1 + inflation / 100) ** ((goal_date - start).days / 365)),
                   "start_date": start.isoformat(), "goal_date": goal_date.isoformat(), "inflation_pct": inflation,
                   "inflation_source": p.get("inflation_source") or "given", "rate_type": "senior citizen" if senior else "general",
                   "banks": banks or "all"},
        "fixed_deposit_plan": fd,
        "remaining_goal_after_fd_todays_money": round(remaining),
        "recurring_deposit_plan": rd,
        "shortfall_todays_money": 0 if covered else round(max(0.0, remaining - rd_value)),
        "as_of": as_of(),
    }


# ---------------------------------------------------------------- the advisor's use: Low risk -> deposits
def applies(facts: dict) -> bool:
    """Low risk (chosen or applied) or a goal under 3 years, and money going to fixed income."""
    plan, pr = facts["risk_plan"], facts["projection"]
    fi = next((r for r in facts["monthly_plan"]["rows"] if r["bucket"] == "Fixed income"), None)
    return bool(fi and fi["amount"] > 0 and (plan.get("effective_risk") == "Low" or plan.get("stated_risk") == "Low"
                                               or float(pr.get("years_remaining") or 99) < 3))


def for_plan(facts: dict, age: float | None = None) -> dict | None:
    """The deposit plan for the fixed-income part of the monthly plan (same as the n8n 'Attach Deposit Plan' node).
    Returns None when it doesn't apply. Mutates facts: adds deposit_plan and names the banks in the Fixed income row."""
    if not applies(facts):
        return None
    pr, plan = facts["projection"], facts["risk_plan"]
    row = next(r for r in facts["monthly_plan"]["rows"] if r["bucket"] == "Fixed income")
    fi = {**row, "amount": facts["monthly_plan"].get("main_fixed_income", row["amount"])}   # v1.7: the main goal's part only
    growth = (1 + float(pr["assumptions"]["expected_annual_return_pct"]) / 1200) ** float(pr["months_remaining"])
    to_fund = max(0.0, float(pr["target_amount"] or 0) - float(pr["current_corpus"] or 0) * growth)
    share = round(to_fund * float(plan["target_allocation"]["debt"]) / 100)
    res = plan_deposits({"initial_amount": 0, "monthly_installment": fi["amount"], "goal_amount": share,
                         "goal_date": str(pr["target_date"])[:10], "inflation_pct": 0,       # the advisor's target is nominal
                         "senior": "yes" if age and age >= 60 else "no"})
    if not res.get("ok"):
        dp = {"ok": False, "reason": "; ".join(res.get("errors") or []) or "deposit planner unavailable"}
    else:
        rd = res["recurring_deposit_plan"] or {}
        best = rd.get("best")
        dp = {"ok": True, "monthly_amount": fi["amount"], "goal_share": share, "goal_date": res["inputs"]["goal_date"],
              "rate_type": res["inputs"]["rate_type"], "reached": bool(rd.get("reached")),
              "verdict": res["verdict"] if not best else ("covers the fixed-income share of your goal" if rd.get("reached")
                                                          else "falls short of the fixed-income share"),
              "steps": [{**{k: s[k] for k in ("bank", "tenor", "term_months", "times", "rate_pct", "start", "end", "value_at_end")},
                         "rate_note": "RD rate" if "RD rate list" in (s.get("rate_source") or "") else "FD card rate for this tenor"}
                        for s in (best or {}).get("steps", [])],
              "cash_months": best["cash_months"] if best else 0,
              "cash_value": round(fi["amount"] * best["cash_months"]) if best else 0,
              "total_paid": best["total_paid"] if best else 0, "value_on_goal_date": best["value_on_goal_date"] if best else 0,
              "installment_needed": best["installment_needed_for_goal"] if best else None,
              "alternatives": [{"bank": a["bank"], "tenor": a["tenor"], "rate_pct": a["rate_pct"], "value": a["value_in_todays_money"]}
                               for a in rd.get("alternatives", [])],
              "as_of": res["as_of"]}
        if dp["steps"]:
            rd_text = "Bank RD: " + ", then ".join(f"{s['bank']} {s['term_months']}m @ {s['rate_pct']}%" for s in dp["steps"])
            # one goal: the RD is the whole row; several goals: name it as the main goal's part
            row["instrument"] = rd_text if row["amount"] == fi["amount"] else f"{rd_text} (main goal) · {row['instrument']}"
    facts["deposit_plan"] = dp
    return dp


# ---------------------------------------------------------------- for the chat
def best_rates(kind: str | None = None, bank: str | None = None, senior: bool = False, limit: int = 12) -> list[dict]:
    """Highest card rates, one row per (bank, type, tenor), best first; filtered by type and bank."""
    banks = bank_filter(bank)
    rows = [r for r in load_rows() if (not kind or r["scheme_type"] == kind)
            and bank_matches(r["bank_name"], banks)]
    key = "interest_rate_senior" if senior else "interest_rate_general"
    rows.sort(key=lambda r: (-(r[key] or r["interest_rate_general"] or 0), r["duration_months"] or 0))
    seen, out = set(), []
    for r in rows:
        k = (r["bank_name"], r["scheme_type"], r["tenor_label"])
        if k in seen:
            continue
        seen.add(k)
        out.append({"bank": r["bank_name"], "type": "FD" if r["scheme_type"] == "Fixed Deposit" else "RD", "tenor": r["tenor_label"],
                    "general_pct": r["interest_rate_general"], "senior_pct": r["interest_rate_senior"]})
        if len(out) >= limit:
            break
    return out


_inflation_cache: dict = {}


async def india_inflation() -> tuple[float, str]:
    """Latest India CPI inflation from the World Bank (cached a day); 4% (RBI target) if unreachable."""
    if _inflation_cache and time.time() - _inflation_cache["t"] < 86400:
        return _inflation_cache["v"], _inflation_cache["src"]
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            data = (await c.get("https://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL.ZG",
                                params={"format": "json", "per_page": 6})).json()[1]
        pt = next(x for x in data if x.get("value") is not None)
        v, src = round(float(pt["value"]), 2), f"World Bank, India consumer price inflation {pt['date']}"
        _inflation_cache.update(t=time.time(), v=v, src=src)
        return v, src
    except Exception:                                   # network, format - never block the chat
        return 4.0, "fallback 4% (RBI inflation target) - World Bank data unavailable"
