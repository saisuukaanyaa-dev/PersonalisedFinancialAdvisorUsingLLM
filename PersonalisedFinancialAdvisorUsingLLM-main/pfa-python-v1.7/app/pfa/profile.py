"""Intake answers -> the canonical profile (same shape as the v3.2 n8n workflow), plus the per-step
checks and the friendly "reactions" shown between intake steps."""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone

from markupsafe import escape

from .ai.guard import clean_goal_text

from .engine.goals import MAX_EXTRA_GOALS, PRIORITIES
from .money import (estimate_in_hand, first_name, fmt_short, month_year, months_until, parse_amount,
                    parse_optional, parse_rate, shorthand, trim2)

GOALS = ["Buy a home", "Retirement", "Child's education", "Child's wedding", "Buy a car",
         "Start a business", "Travel or sabbatical", "Build long-term wealth", "Other"]
CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "SGD"]
LOAN_TYPES = ["Home loan", "Car loan", "Personal loan", "Education loan", "Credit card dues", "Gold loan", "Other loan"]
INVESTMENTS = [  # key, label shown in the report
    ("mf", "Equity Mutual Funds"),
    ("stocks", "Direct Stocks"),
    ("gold", "Gold (SGB / coins / gold funds)"),
    ("fd", "FD / RD"),
    ("pf", "PPF / EPF / VPF"),
    ("cash", "Savings account / cash"),
    ("other", None),
]
RISK_OPTIONS = {
    "Low": "Low - I'd sell to stop the loss. Keep my money safe, even if it grows slowly (FDs, PPF)",
    "Medium": "Medium - I'd wait for it to recover. Some ups and downs are fine (mostly mutual funds)",
    "High": "High - I'd invest more while it's cheap. I'm fine with big swings (funds + stocks)",
}


def _b(x) -> str:
    """Bold, escaped - reactions are sent as small HTML snippets."""
    return f"<strong>{escape(x)}</strong>"


# ------------------------------------------------------------------ derived figures
def compute_derived(d: dict) -> dict:
    """Everything downstream reads `derived`; recompute it from the canonical profile."""
    salary = float(d.get("profile", {}).get("current_monthly_salary") or 0)
    ef = d.setdefault("emergency_fund", {})
    expenses = float(ef.get("monthly_essential_expenses") or 0)
    emergency = float(ef.get("current_amount") or 0)
    total_emi = sum(float(l.get("emi") or 0) for l in d.get("liabilities", []))
    total_debt = sum(float(l.get("outstanding_amount") or 0) for l in d.get("liabilities", []))
    savings = sum(float(i.get("current_value") or 0) for i in d.get("savings_investments", []))
    contrib = sum(float(i.get("monthly_contribution") or 0) for i in d.get("savings_investments", []))
    surplus = salary - total_emi - expenses
    ef["has_fund"] = emergency > 0
    ef["months_of_expenses_covered"] = round(emergency / expenses, 1) if expenses > 0 else 0
    d["derived"] = {
        "totalEmi": total_emi, "totalDebt": total_debt, "totalSavingsValue": savings,
        "monthlyContrib": contrib, "emergencyFund": emergency,
        "netWorth": savings + emergency - total_debt, "surplus": surplus,
        "freeCashAfterInvesting": surplus - contrib - float(ef.get("monthly_topup") or 0),
        "emergencyMonthly": float(ef.get("monthly_topup") or 0),
        "savingsRatePct": round(surplus / salary * 100, 1) if salary > 0 else None,
    }
    return d


# ------------------------------------------------------------------ per-step checks
def _need_amount(errors, answers, key, label, required=True, positive=True):
    raw = _get(answers, key)
    if raw is None or str(raw).strip() == "":
        if required:
            errors[key] = f"Please enter your {label.lower()}."
        return None
    v = parse_amount(raw)
    if v is None:
        errors[key] = f'I couldn\'t read "{str(raw)[:40]}" - try e.g. 85K, 12L or 1.5Cr.'
    elif v < 0 or (positive and required and v <= 0):
        errors[key] = f"{label} should be more than 0."
    return v


def _get(answers: dict, key: str):
    cur = answers
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def check_step(step: int, a: dict) -> dict[str, str]:
    """Field errors for one intake step, keyed by answer path (e.g. 'loans.Car loan.rate')."""
    e: dict[str, str] = {}
    if step == 1:
        if not str(a.get("name") or "").strip():
            e["name"] = "Please tell me your name."
        try:
            age = int(str(a.get("age") or "").strip())
            if not 18 <= age <= 100:
                e["age"] = "Age should be between 18 and 100."
        except ValueError:
            e["age"] = "Please enter your age in years."
        if a.get("currency") not in CURRENCIES:
            e["currency"] = "Please pick a currency."
        _need_amount(e, a, "ctc", "Current CTC")
        if a.get("goal_type") not in GOALS:
            e["goal_type"] = "Please pick what you are saving for."
        _need_amount(e, a, "target_amount", "Target amount")
        m = months_until(a.get("target_date"))
        if m is None:
            e["target_date"] = "Please pick a target date."
        elif m < 1:
            e["target_date"] = "The target date needs to be at least a month away."
        check_extra_goals(e, a)
    elif step == 2:
        _need_amount(e, a, "take_home", "Monthly in-hand salary")
        _need_amount(e, a, "expenses", "Monthly essential expenses")
    elif step == 3:
        for k, label in (("emergency", "Emergency fund"), ("emergency_monthly", "Monthly emergency top-up"),
                         ("term_cover", "Term cover"), ("term_premium", "Term premium"),
                         ("health_cover", "Health cover"), ("health_premium", "Health premium")):
            _need_amount(e, a, k, label, required=False)
    elif step == 4:
        for t in a.get("loan_types") or []:
            if t not in LOAN_TYPES:
                continue
            _need_amount(e, a, f"loans.{t}.outstanding", f"{t} amount outstanding")
            rate_raw = _get(a, f"loans.{t}.rate")
            if parse_rate(rate_raw) is None:
                e[f"loans.{t}.rate"] = "Please enter the yearly interest rate, e.g. 9.5."
            _need_amount(e, a, f"loans.{t}.emi", f"{t} EMI")
    elif step == 5:
        for k, _ in INVESTMENTS:
            _need_amount(e, a, f"inv.{k}_value", "Current value", required=False)
            _need_amount(e, a, f"inv.{k}_monthly", "Monthly amount", required=False)
        if a.get("risk") not in RISK_OPTIONS:
            e["risk"] = "Please pick the answer closest to how you'd feel."
    return e


def check_extra_goals(e: dict, a: dict) -> None:
    """v1.7: up to 3 more goals, each with a type, an amount and a date (blank rows are ignored)."""
    for i, g in enumerate((a.get("extra_goals") or [])[:MAX_EXTRA_GOALS]):
        if not isinstance(g, dict) or not any(str(g.get(k) or "").strip() for k in ("goal_type", "target_amount", "target_date")):
            continue
        if g.get("goal_type") not in GOALS:
            e[f"extra_goals.{i}.goal_type"] = "Please pick what this goal is for."
        own: dict[str, str] = {}
        _need_amount(own, g, "target_amount", "Target amount")
        if own:
            e[f"extra_goals.{i}.target_amount"] = own["target_amount"]
        m = months_until(g.get("target_date"))
        if m is None:
            e[f"extra_goals.{i}.target_date"] = "Please pick a date for this goal."
        elif m < 1:
            e[f"extra_goals.{i}.target_date"] = "The date needs to be at least a month away."


def extra_goals_of(a: dict) -> list[dict]:
    """Answers -> profile["goals_extra"]: only complete rows; free text is screened like the main goal's."""
    out = []
    for g in (a.get("extra_goals") or [])[:MAX_EXTRA_GOALS]:
        if not isinstance(g, dict):
            continue
        amount, months = parse_amount(g.get("target_amount")), months_until(g.get("target_date"))
        if g.get("goal_type") not in GOALS or not amount or not months or months < 1:
            continue
        details, flagged = clean_goal_text(g.get("details"), g["goal_type"])
        details = "" if flagged else details
        name = details if details and g["goal_type"] == "Other" else (f"{g['goal_type']} - {details}" if details else g["goal_type"])
        out.append({"id": f"g{len(out) + 1}", "name": name[:80], "goal_type": g["goal_type"], "details": details,
                    "target_amount": amount, "target_date": str(g["target_date"])[:10],
                    "priority": g.get("priority") if g.get("priority") in PRIORITIES else "Must-have"})
    return out


def new_goal_from(body: dict) -> tuple[dict | None, str | None]:
    """The "what if a new goal comes up?" form -> a goal for engine.goals (or a message saying what's missing)."""
    goal_type = body.get("goal_type") if body.get("goal_type") in GOALS else "Other"
    amount = parse_amount(body.get("target_amount"))
    when = str(body.get("target_date") or "")[:10]
    months = months_until(when)
    if not amount or amount < 1000:
        raw = str(body.get("target_amount") or "")[:30]
        return None, f"I couldn't read the amount \"{raw}\" - try e.g. 6L or 5,00,000."
    if months is None or months < 1:
        return None, "Please pick a date at least a month from now."
    details, flagged = clean_goal_text(body.get("name"), goal_type)
    details = "" if flagged or details.lower() == goal_type.lower() else details
    return {"goal_type": goal_type, "details": details, "name": details or goal_type, "target_amount": amount,
            "target_date": when, "priority": body.get("priority") if body.get("priority") in PRIORITIES else "Must-have"}, None


# ------------------------------------------------------------------ reactions between steps
def intro_bubble(name: str | None, returning: bool) -> dict:
    n = first_name(name)
    if returning:
        return {"title": f"Welcome back, {n}! 👋",
                "lines": ["Your last answers are filled in. Change only what's different, and I'll rebuild your plan in seconds."]}
    return {"title": "Hi, I'm your finance buddy 👋",
            "lines": ["I'll ask a few quick questions - about 3 minutes - and then build your personal money plan.",
                      f"Type amounts the way you'd say them: {_b('85K')}, {_b('12L')}, {_b('1.5Cr')}."]}


def reaction(step_done: int, a: dict) -> dict:
    """The advisor's reaction shown at the top of the NEXT step."""
    cur = a.get("currency") or "INR"
    n = escape(first_name(a.get("name")))
    if step_done == 1:
        target = parse_amount(a.get("target_amount"))
        months = months_until(a.get("target_date")) or 0
        years = months / 12
        horizon = (" - a short runway, so we'll keep this money safe rather than chase returns" if years < 3 else
                   " - a solid medium-term runway" if years < 7 else " - a long runway, so time is on your side")
        when = f"about {max(1, months)} months away" if years < 1 else f"about {trim2(round(years, 1))} years away"
        desc = a.get("goal_type") if a.get("goal_type") != "Other" else (a.get("goal_details") or "Your goal")
        lines = [f"🎯 {_b(desc)} - {escape(fmt_short(target, cur))} by {escape(month_year(a.get('target_date')))}. "
                 f"That's {when}{horizon}."]
        extras = extra_goals_of(a)
        if extras:
            names = ", ".join(f"{_b(g['name'])} ({escape(fmt_short(g['target_amount'], cur))} by {escape(month_year(g['target_date']))})"
                              for g in extras)
            lines.append(f"🗂️ Plus {names}. I'll plan every goal together - the nearest must-have goal is secured first, "
                         "and each goal gets its own risk level for its own timeline.")
        est = estimate_in_hand(parse_amount(a.get("ctc")), cur)
        if est:
            lines.append(f"💼 A CTC of {_b(fmt_short(parse_amount(a.get('ctc')), cur))} usually lands around "
                         f"{_b(fmt_short(est, cur) + ' a month')} in your account after PF, professional tax and income tax "
                         f"(new regime). I've filled that in - correct it if your payslip says otherwise."
                         if cur == "INR" else
                         f"💼 On a CTC of {_b(fmt_short(parse_amount(a.get('ctc')), cur))} I've guessed roughly "
                         f"{_b(fmt_short(est, cur) + ' a month')} after tax - please correct it with your real take-home.")
        title = f"Good to see you again, {n}! 🙌" if a.get("_returning") else f"Lovely to meet you, {n}! 🙌"
        return {"title": title, "lines": lines, "prefill": {"take_home": est}}
    if step_done == 2:
        th, ex = parse_amount(a.get("take_home")) or 0, parse_amount(a.get("expenses")) or 0
        pct = round(ex / th * 100) if th else 0
        left = th - ex
        r = (f"✅ Essentials take {_b(f'{pct}%')} of your pay, leaving about {_b(fmt_short(left, cur) + ' a month')} before any EMIs. That's healthy headroom." if pct <= 50 else
             f"👍 Essentials take {_b(f'{pct}%')} of your pay, leaving about {_b(fmt_short(left, cur) + ' a month')} before any EMIs. Workable - we'll look for extra room." if pct <= 80 else
             f"⚠️ Essentials take {_b(f'{pct}%')} of your pay, which is tight. The plan will focus on creating breathing room first.")
        return {"title": f"Thanks, {n}!", "lines": [r,
                f"🛟 Next, your safety net. For you, a comfortable emergency fund is about {_b(fmt_short(ex * 6, cur))} - six months of essentials."]}
    if step_done == 3:
        ex = parse_amount(a.get("expenses")) or 0
        emergency = parse_optional(a.get("emergency")) or 0
        months = emergency / ex if ex else 0
        term, health = parse_optional(a.get("term_cover")) or 0, parse_optional(a.get("health_cover")) or 0
        rec_term = (parse_amount(a.get("ctc")) or 0) * 10
        lines = []
        if months >= 6:
            lines.append(f"✅ Your emergency fund covers {_b(f'{trim2(round(months, 1))} months')} of expenses - a proper safety net.")
        elif months >= 3:
            lines.append(f"👍 Your emergency fund covers {_b(f'{trim2(round(months, 1))} months')} - more than halfway to the 6-month mark.")
        elif months > 0:
            lines.append(f"🟠 Your emergency fund covers {_b(f'{trim2(round(months, 1))} months')}. Topping it up will be an early step in your plan.")
        else:
            lines.append("🟠 No emergency fund yet - very common, and building one will be step one in your plan.")
        if term <= 0:
            lines.append("🛡️ No term cover yet. If anyone depends on your income, that's worth fixing - I'll include it.")
        elif term < rec_term:
            lines.append(f"🛡️ Term cover of {escape(fmt_short(term, cur))} - the usual guide is about 10× annual income ({escape(fmt_short(rec_term, cur))}).")
        else:
            lines.append("🛡️ Your term cover looks solid.")
        lines.append("🏥 No health cover - one hospital stay can undo years of saving, so I'll flag it as a priority."
                     if health <= 0 else "🏥 Good - you have health cover.")
        lines.append("Now, any loans or card dues? No judgement - most people have one.")
        return {"title": "Good to know", "lines": lines}
    if step_done == 4:
        th = parse_amount(a.get("take_home")) or 0
        ex = parse_amount(a.get("expenses")) or 0
        loans = _liabilities(a)
        emi = sum(l["emi"] or 0 for l in loans)
        lines = []
        if not loans:
            lines.append("🙌 Debt-free - that's a real advantage. Every rupee of surplus can work for your goal.")
        else:
            dti = round(emi / th * 100) if th else 0
            lines.append(f"💳 Your EMIs come to {_b(fmt_short(emi, cur) + ' a month')} - {dti}% of your take-home, which is "
                         + ("comfortably within limits." if dti <= 30 else "manageable." if dti <= 40 else
                            "on the heavy side, so a payoff plan will be part of your report."))
            pricey = sorted([l for l in loans if (l["interest_rate"] or 0) > 12], key=lambda l: -(l["interest_rate"] or 0))
            if pricey:
                p = pricey[0]
                plural = p["type"].endswith("dues")
                lines.append(f"🔥 Your {_b(p['type'].lower())} at {trim2(p['interest_rate'])}% {'are' if plural else 'is'} expensive money - "
                             f"we'll put {'them' if plural else 'it'} first in line.")
        surplus = th - ex - emi
        lines.append(f"That leaves roughly {_b(fmt_short(surplus, cur) + ' a month')} after essentials and EMIs." if surplus >= 0 else
                     f"Right now essentials and EMIs are about {_b(fmt_short(-surplus, cur) + ' more')} than your in-hand pay - we'll tackle that first.")
        lines.append("📈 Last step, and the fun part: what's already working for you? Current value and what you add each month. "
                     "Leave blank anything you don't have. Then one quick question about risk.")
        title = f"Thanks for being upfront, {n} 🙏" if loans else f"Almost there, {n}! 💪"
        return {"title": title, "lines": lines}
    if step_done == 5:
        lines = ["Here's what you told me. Check it over, fix anything with Edit, then build your plan."]
        inv = a.get("inv") or {}
        pf = parse_optional(inv.get("pf_monthly")) or 0
        eq = (parse_optional(inv.get("mf_monthly")) or 0) + (parse_optional(inv.get("stocks_monthly")) or 0)
        if pf >= 5000 and pf > eq:
            lines.append(f"🤔 Just checking: {_b(fmt_short(pf, a.get('currency') or 'INR') + ' a month')} goes to PPF / EPF / VPF - "
                         "your biggest monthly investment. That counts as fixed income. If it was meant for mutual funds, tap Edit on Investments.")
        return {"title": f"All set, {n}! ✨", "lines": lines}
    return {"title": "", "lines": []}


# ------------------------------------------------------------------ answers -> canonical profile
def _liabilities(a: dict) -> list[dict]:
    out = []
    for t in a.get("loan_types") or []:
        if t not in LOAN_TYPES:
            continue
        l = (a.get("loans") or {}).get(t) or {}
        out.append({"type": t, "outstanding_amount": parse_amount(l.get("outstanding")),
                    "interest_rate": parse_rate(l.get("rate")), "emi": parse_amount(l.get("emi"))})
    return out


AMOUNT_KEYS = ("ctc", "target_amount", "take_home", "expenses", "emergency", "emergency_monthly", "term_cover", "term_premium",
               "health_cover", "health_premium")


def _tidy_amounts(a: dict) -> dict:
    """Store amounts the way people type them: "eighteen lakh" -> "18L", 122000 -> "1.22L"."""
    cur = a.get("currency") or "INR"

    def tidy(v):
        if v is None or str(v).strip() == "":
            return v
        n = parse_amount(v)
        return shorthand(n, cur) if n is not None else v
    for k in AMOUNT_KEYS:
        if k in a:
            a[k] = tidy(a[k])
    for loan in (a.get("loans") or {}).values():
        for k in ("outstanding", "emi"):
            if k in loan:
                loan[k] = tidy(loan[k])
    for k, v in list((a.get("inv") or {}).items()):
        if k.endswith(("_value", "_monthly")):
            a["inv"][k] = tidy(v)
    for g in a.get("extra_goals") or []:
        if isinstance(g, dict) and "target_amount" in g:
            g["target_amount"] = tidy(g["target_amount"])
    return a


def build_profile(a: dict, email: str, previous: dict | None = None) -> dict:
    cur = a.get("currency") or "INR"
    ctc = parse_amount(a.get("ctc"))
    est = estimate_in_hand(ctc, cur)
    take_home = parse_amount(a.get("take_home"))
    inv = a.get("inv") or {}
    savings = []
    for k, label in INVESTMENTS:
        value, monthly = parse_optional(inv.get(f"{k}_value")), parse_optional(inv.get(f"{k}_monthly"))
        if not value and not monthly:
            continue
        if k == "mf":                       # the fund type decides whether it is equity, fixed income or both
            label = {"Debt": "Debt Mutual Funds", "Hybrid": "Hybrid Mutual Funds"}.get(inv.get("mf_type"), "Equity Mutual Funds")
        savings.append({"type": label or (str(inv.get("other_label") or "").strip() or "Other investment"),
                        "_key": k, "current_value": value or 0, "monthly_contribution": monthly or 0})
    insurance = []
    tc, tp = parse_optional(a.get("term_cover")) or 0, parse_optional(a.get("term_premium")) or 0
    hc, hp = parse_optional(a.get("health_cover")) or 0, parse_optional(a.get("health_premium")) or 0
    if tc or tp:
        insurance.append({"type": "Term Life", "sum_assured": tc, "premium_annual": tp})
    if hc or hp:
        insurance.append({"type": "Health", "sum_assured": hc, "premium_annual": hp})
    goal_type = a.get("goal_type") or "Other"
    # Free text that looks like instructions to the AI (or holds ID numbers) is dropped, as in v3.2's
    # "Neutralise Goal Text": the plan uses the goal type only.
    details, flagged = clean_goal_text(a.get("goal_details"), goal_type)
    details = "" if flagged else details
    d = {
        "user_key": email.lower(),
        "profile_source": "updated" if previous else "new",
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": {
            "user_name": str(a.get("name") or "").strip()[:80], "email": email.lower(),
            "age": int(str(a.get("age") or 0) or 0), "currency": cur,
            "annual_ctc": ctc, "estimated_monthly_in_hand": est, "current_monthly_salary": take_home,
            "in_hand_source": "estimated_from_ctc" if est and take_home and abs(take_home - est) < 1 else "user_confirmed",
            "risk_appetite": a.get("risk") if a.get("risk") in RISK_OPTIONS else "Medium",
        },
        "goal": {"goal_type": goal_type, "details": details,
                 "description": f"{goal_type} - {details}" if details else goal_type,
                 "target_amount": parse_amount(a.get("target_amount")), "target_date": str(a.get("target_date") or "")[:10],
                 "details_removed": flagged},
        "goals_extra": extra_goals_of(a),
        "liabilities": _liabilities(a),
        "savings_investments": savings,
        "insurance": insurance,
        "emergency_fund": {"current_amount": parse_optional(a.get("emergency")) or 0,
                           "monthly_essential_expenses": parse_amount(a.get("expenses")),
                           "monthly_topup": parse_optional(a.get("emergency_monthly")) or 0},   # user's own monthly top-up
        "answers": _tidy_amounts(copy.deepcopy(a)),   # answers for pre-filling "Update my answers" (spoken words -> 18L)
    }
    return compute_derived(d)


def sanity_fixes(d: dict) -> tuple[list[str], list[dict]]:
    """Numbers that can't all be true (from v3.2 'Check Profile Completeness'). Returns (notes, fields to re-ask)."""
    cur = d["profile"]["currency"]
    th = float(d["profile"].get("current_monthly_salary") or 0)
    ex = float(d["emergency_fund"].get("monthly_essential_expenses") or 0)
    emi = d["derived"]["totalEmi"]
    contrib = d["derived"]["monthlyContrib"]
    room = th - ex - emi
    notes, fields = [], []
    if th > 0 and ex + emi >= th:
        notes.append(f"Your essentials ({fmt_short(ex, cur)}) and EMIs ({fmt_short(emi, cur)}) come to more than your "
                     f"in-hand pay of {fmt_short(th, cur)}. Please check these figures.")
        fields += [{"key": "take_home", "label": "Monthly in-hand salary"},
                   {"key": "expenses", "label": "Monthly essential expenses (not EMIs)"}]
    elif th > 0 and contrib > room:
        notes.append(f"These don't add up yet: you'd be investing {fmt_short(contrib, cur)} a month, but after essentials "
                     f"and EMIs you have {fmt_short(room, cur)} left from your {fmt_short(th, cur)} in-hand pay. "
                     "If one of the monthly amounts below is really a one-time amount or a balance, set it to 0.")
        labels = dict(INVESTMENTS)
        for s in d["savings_investments"]:
            if s["monthly_contribution"] > 0:
                fields.append({"key": f"inv.{s['_key']}_monthly", "label": f"{labels.get(s['_key']) or s['type']} · monthly amount"})
    return notes, fields


# ------------------------------------------------------------------ chat "what if" changes
PLAN_CHANGE_KEYS = ["monthly_sip_total", "target_amount", "target_date", "risk_appetite", "take_home", "annual_ctc",
                    "expenses", "emergency_fund", "emergency_lumpsum", "emergency_monthly", "term_cover", "health_cover",
                    "remove_loan", "add_goal", "remove_goal"]


def apply_changes(saved: dict, changes: dict) -> tuple[dict | None, list[str], list[str]]:
    """Apply only the requested fields to a saved profile (ported from v3.2.3 'Apply Plan Changes').
    Works on the raw answers and rebuilds the profile, so every derived figure stays consistent."""
    a = copy.deepcopy(saved.get("answers") or {})
    if not a:
        return None, [], ["no saved answers to change"]
    cur = a.get("currency") or "INR"
    log, ignored = [], []

    def amt(k, v):
        n = parse_amount(v)
        if n is None or n < 0:
            ignored.append(f'{k} (could not read "{v}")')
        return n

    def set_amount(field, label, v, current):
        n = amt(label, v)
        if n is None:
            return
        if current is not None and abs(float(current) - n) < 0.5:
            ignored.append(f"{label} is already {fmt_short(n, cur)}")
            return
        log.append(f"{label} {fmt_short(current or 0, cur)} → {fmt_short(n, cur)}")
        a[field] = n

    for k, v in (changes or {}).items():
        if v is None or v == "":
            continue
        if k == "monthly_sip_total":
            n = amt("monthly investing", v)
            if n is None:
                continue
            inv = a.setdefault("inv", {})
            before = sum(parse_optional(inv.get(f"{key}_monthly")) or 0 for key, _ in INVESTMENTS)
            if abs(before - n) < 0.5:
                ignored.append(f"Monthly investing is already {fmt_short(n, cur)}")
                continue
            if n > before:                 # the extra goes to mutual funds (the plan's core)
                inv["mf_monthly"] = (parse_optional(inv.get("mf_monthly")) or 0) + (n - before)
            else:                          # scale every SIP down proportionally
                f = n / before if before else 0
                for key, _ in INVESTMENTS:
                    m = parse_optional(inv.get(f"{key}_monthly")) or 0
                    if m:
                        inv[f"{key}_monthly"] = round(m * f)
            log.append(f"Monthly investing {fmt_short(before, cur)} → {fmt_short(n, cur)}")
        elif k == "target_amount":
            n = amt("target", v)
            if n is not None and n >= 10000:
                set_amount("target_amount", "Target", n, parse_amount(a.get("target_amount")))
        elif k == "target_date":
            s = str(v)[:10]
            try:
                ok = date.fromisoformat(s) > date.today()
            except ValueError:
                ok = False
            if not ok:
                ignored.append("target_date (must be a future YYYY-MM-DD)")
            elif s == a.get("target_date"):
                ignored.append(f"Target date is already {s}")
            else:
                log.append(f"Target date {a.get('target_date')} → {s}")
                a["target_date"] = s
        elif k == "risk_appetite":
            r = str(v).strip().capitalize()
            if r not in RISK_OPTIONS:
                ignored.append("risk_appetite (Low, Medium or High)")
            elif r == a.get("risk"):
                ignored.append(f"Risk is already {r}")
            else:
                log.append(f"Risk {a.get('risk') or 'Medium'} → {r}")
                a["risk"] = r
        elif k == "take_home":
            set_amount("take_home", "In-hand pay", v, parse_amount(a.get("take_home")))
        elif k == "annual_ctc":
            set_amount("ctc", "CTC", v, parse_amount(a.get("ctc")))
        elif k == "expenses":
            set_amount("expenses", "Essentials", v, parse_amount(a.get("expenses")))
        elif k == "emergency_fund":
            set_amount("emergency", "Emergency fund", v, parse_optional(a.get("emergency")))
        elif k == "emergency_lumpsum":                   # "I'll move 50K to my emergency fund"
            n = amt("emergency deposit", v)
            if n:
                before = parse_optional(a.get("emergency")) or 0
                log.append(f"Emergency fund {fmt_short(before, cur)} → {fmt_short(before + n, cur)}")
                a["emergency"] = before + n
        elif k == "emergency_monthly":                   # "…and add 6K a month to it"
            set_amount("emergency_monthly", "Monthly emergency top-up", v, parse_optional(a.get("emergency_monthly")))
        elif k in ("term_cover", "health_cover"):
            set_amount(k, "Term cover" if k == "term_cover" else "Health cover", v, parse_optional(a.get(k)))
        elif k == "add_goal":                            # v1.7: "I also need 5L for a car in 2028"
            g = v if isinstance(v, dict) else {}
            goal_type = g.get("goal_type") if g.get("goal_type") in GOALS else "Other"
            n, s_date = parse_amount(g.get("target_amount")), str(g.get("target_date") or "")[:10]
            months = months_until(s_date)
            goals_now = [x for x in a.get("extra_goals") or [] if isinstance(x, dict) and x.get("goal_type")]
            if not n or n < 1000:
                ignored.append("add_goal (needs an amount)")
            elif not months or months < 1:
                ignored.append("add_goal (needs a future date)")
            elif len(goals_now) >= MAX_EXTRA_GOALS:
                ignored.append(f"add_goal (the plan already has {MAX_EXTRA_GOALS} extra goals - remove one first)")
            else:
                details = str(g.get("name") or g.get("details") or "").strip()[:60]
                if details.lower() == goal_type.lower():
                    details = ""
                pr = g.get("priority") if g.get("priority") in PRIORITIES else "Must-have"
                goals_now.append({"goal_type": goal_type, "details": details, "target_amount": n, "target_date": s_date,
                                  "priority": pr})
                a["extra_goals"] = goals_now
                label = details or goal_type
                log.append(f"Added goal: {label} - {fmt_short(n, cur)} by {month_year(s_date)} ({pr.lower()})")
        elif k == "remove_goal":
            want = str(v).lower().strip()
            goals_now = [x for x in a.get("extra_goals") or [] if isinstance(x, dict)]

            def names(x):              # "Buy a car - Family car", "Family car", "Buy a car"
                det, typ = str(x.get("details") or "").lower(), str(x.get("goal_type") or "").lower()
                return [n for n in (f"{typ} - {det}" if det else typ, det, typ) if n]
            hit = next((x for x in goals_now if want and any(want == n for n in names(x))), None) or \
                next((x for x in goals_now if want and any(want in n for n in names(x))), None)
            if not hit:
                ignored.append(f'remove_goal (no extra goal called "{v}")')
            else:
                a["extra_goals"] = [x for x in goals_now if x is not hit]
                log.append(f"Removed goal: {hit.get('details') or hit.get('goal_type')}")
        elif k == "remove_loan":
            t = next((x for x in a.get("loan_types") or [] if x.lower() == str(v).lower().strip()), None)
            if not t:
                ignored.append(f'remove_loan (no "{v}" on file)')
            else:
                a["loan_types"] = [x for x in a["loan_types"] if x != t]
                (a.get("loans") or {}).pop(t, None)
                log.append(f"Removed {t}")
        else:
            ignored.append(k)
    return (a if log else None), log, ignored
