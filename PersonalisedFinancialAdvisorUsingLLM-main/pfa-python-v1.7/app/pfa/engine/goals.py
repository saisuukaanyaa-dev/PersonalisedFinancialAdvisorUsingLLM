"""Several goals at once (v1.7, mentor feedback: "allow more than one goal, and show what happens when a smaller
goal comes up in between").

How the money is shared - all in code, no AI:
1. Order. Must-have goals before Nice-to-have ones, then the nearest date first: money needed sooner has the least
   time to grow, so it is secured first.
2. Savings you already have are set aside ("earmarked") in that order. Each goal gets what it needs today - its
   target discounted at its own expected return - until the savings run out. Anything left stays with the main goal.
3. Monthly money is shared the same way: each goal gets the SIP it needs, in order, until the money runs out.
   Today's SIPs are shared for "at today's pace"; the money free after essentials, EMIs and the emergency top-up is
   shared for the plan.
4. Every goal has its own horizon, so its own risk level and mix (a car in 2 years sits in FD / RD; a home in
   8 years can hold equity) - the same rulebook as the main goal (allocation.goal_mix).

new_goal_impact() answers "a smaller goal has come up before my main goal - what does it cost me?" with three ways
to pay for it and their effect on every other goal.
"""
from __future__ import annotations

import copy
from datetime import date

from .allocation import goal_mix, months_to

PRIORITIES = ["Must-have", "Nice-to-have"]
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}
MAX_EXTRA_GOALS = 3
MAX_MONTHS = 600          # 50 years: beyond this a goal is treated as out of reach


def _rate(pct: float) -> float:
    return pct / 100 / 12


def _r100(x: float) -> int:
    return max(0, int(round(x / 100) * 100))


def fv(corpus: float, pmt: float, r: float, m: int) -> float:
    """Future value of savings `corpus` plus a monthly `pmt` after m months at monthly rate r."""
    g = (1 + r) ** m
    return corpus * g + (pmt * ((g - 1) / r) if r else pmt * m)


def required_pmt(target: float, corpus: float, r: float, m: int) -> float:
    """Monthly amount that grows `corpus` to `target` in m months (0 if the savings alone get there)."""
    g = (1 + r) ** m
    annuity = (g - 1) / r if r else m
    return max(0.0, (target - corpus * g) / annuity) if annuity else 0.0


def months_to_reach(target: float, corpus: float, pmt: float, r: float, start: int = 1) -> int | None:
    """First month (>= start) when savings + monthly pmt reach target; None if not within 50 years."""
    for m in range(max(1, start), MAX_MONTHS + 1):
        if fv(corpus, pmt, r, m) >= target - 0.5:
            return m
    return None


def date_after(months: int) -> str:
    t = date.today()
    y, mo = divmod(t.month - 1 + int(months), 12)
    return date(t.year + y, mo + 1, 1).isoformat()


def goal_list(d: dict) -> list[dict]:
    """The main goal (profile["goal"], unchanged since v1.0) followed by the extra goals (profile["goals_extra"])."""
    main = d.get("goal") or {}
    goals = [{"id": "main", "name": main.get("description") or main.get("goal_type") or "Main goal",
              "goal_type": main.get("goal_type"), "target_amount": float(main.get("target_amount") or 0),
              "target_date": main.get("target_date"), "is_main": True,
              "priority": main.get("priority") if main.get("priority") in PRIORITY_RANK else "Must-have"}]
    for i, g in enumerate((d.get("goals_extra") or [])[:MAX_EXTRA_GOALS]):
        if not float(g.get("target_amount") or 0) or not g.get("target_date"):
            continue
        goals.append({"id": g.get("id") or f"g{i + 1}", "name": g.get("name") or g.get("goal_type") or f"Goal {i + 2}",
                      "goal_type": g.get("goal_type"), "target_amount": float(g["target_amount"]),
                      "target_date": g["target_date"], "is_main": False,
                      "priority": g.get("priority") if g.get("priority") in PRIORITY_RANK else "Must-have"})
    return goals


def plan_goals(d: dict, corpus: float, current_monthly: float, investable: float) -> dict:
    """Share savings and monthly money across all goals. With one goal this gives exactly the v1.6 numbers."""
    goals = goal_list(d)
    stated = d.get("profile", {}).get("risk_appetite")
    for g in goals:
        g["months"] = months_to(g["target_date"])
        g["years"] = round(g["months"] / 12, 1)
        mix = goal_mix(stated, g["months"] / 12)
        g.update(risk=mix["effective"], mix=mix["target"], instruments=mix["instruments"],
                 expected_return_pct=mix["expected_return_pct"], _r=_rate(mix["expected_return_pct"]))
    order = sorted(goals, key=lambda g: (PRIORITY_RANK[g["priority"]], g["months"], not g["is_main"]))
    main = goals[0]

    # 1. earmark today's savings: what each goal needs today, in funding order
    left = float(corpus or 0)
    for g in order:
        give = min(left, g["target_amount"] / (1 + g["_r"]) ** g["months"])
        g["corpus"], left = give, left - give
    main["corpus"] += left
    for g in goals:
        g["required_monthly"] = required_pmt(g["target_amount"], g["corpus"], g["_r"], g["months"])

    # 2. today's SIPs, shared in the same order (anything beyond the needs stays with the main goal)
    left = float(current_monthly or 0)
    for g in order:
        give = min(left, g["required_monthly"])
        g["current_monthly"], left = give, left - give
    main["current_monthly"] += left

    # 3. the plan: money free each month, shared in order; what no goal needs stays unallocated
    # SIPs in round ₹100s: rounded UP when the money allows (so a goal is never "₹36 short"), down when it doesn't
    left = float(investable or 0)
    for g in order:
        need_up = -(-g["required_monthly"] // 100) * 100
        give = int(need_up) if need_up <= left else int(left // 100) * 100
        g["funded_monthly"], left = give, max(0.0, left - give)

    for g in goals:
        r, m, t = g["_r"], g["months"], g["target_amount"]
        g["projected_now"] = round(fv(g["corpus"], g["current_monthly"], r, m))
        g["projected_plan"] = round(fv(g["corpus"], g["funded_monthly"], r, m))
        g["on_track_now"] = g["projected_now"] >= t - 0.5
        g["underfunded_monthly"] = max(0, round(g["required_monthly"] - g["funded_monthly"]))
        g["status"] = ("on_track" if g["on_track_now"] else "funded" if g["underfunded_monthly"] <= 100
                       else "partly" if g["funded_monthly"] > 0 else "not_funded")
        reach = months_to_reach(t, g["corpus"], g["funded_monthly"], r, m) if g["status"] in ("partly", "not_funded") else m
        g["reachable_date"] = date_after(reach) if reach else None
        g["delay_months"] = (reach - m) if reach else None
        g["shortfall_plan"] = max(0, round(t - g["projected_plan"]))
        g["progress_pct"] = round(min(100.0, g["projected_plan"] / t * 100), 1) if t else 0
        g["corpus"] = round(g["corpus"])
        g["required_monthly"] = round(g["required_monthly"])
        g["current_monthly"] = round(g["current_monthly"])
        g["funded_order"] = order.index(g) + 1

    funded = sum(g["funded_monthly"] for g in goals)
    out = {
        "goals": [{k: v for k, v in g.items() if not k.startswith("_")} for g in goals],
        "count": len(goals),
        "investable": round(float(investable or 0)),
        "total_required": sum(g["required_monthly"] for g in goals),
        "funded_total": funded,
        "unallocated": max(0, round(float(investable or 0) - funded)),
        "underfunded_total": sum(g["underfunded_monthly"] for g in goals),
        "all_funded": all(g["status"] in ("on_track", "funded") for g in goals),
        "rule": "Must-have before Nice-to-have, then the nearest date first.",
    }
    out["timeline"] = timeline(goals)
    return out


def timeline(goals: list[dict]) -> dict:
    """Month-by-month: every goal's pot grows at its own rate with the plan's SIP and pays out on its date.
    Money left in a pot after paying its goal keeps growing (at the main goal's rate). Yearly points + goal events."""
    horizon = max(g["months"] for g in goals)
    pots = {g["id"]: float(g["corpus"]) for g in goals}
    main_r = goals[0]["_r"]
    spare, points, events = 0.0, [], []
    by_month: dict[int, list[dict]] = {}
    for g in goals:
        by_month.setdefault(g["months"], []).append(g)
    points.append({"month": 0, "total": round(sum(pots.values()))})
    for m in range(1, horizon + 1):
        spare *= 1 + main_r
        for g in goals:
            if g["months"] >= m:
                pots[g["id"]] = pots[g["id"]] * (1 + g["_r"]) + g["funded_monthly"]
        if m in by_month:      # the value just before the payout, so the chart can draw the drop
            points.append({"month": m, "total": round(spare + sum(v for k, v in pots.items() if _alive(goals, k, m - 1)))})
        for g in by_month.get(m, []):
            pot = pots[g["id"]]
            paid = min(pot, g["target_amount"])
            gap = max(0, round(g["target_amount"] - pot))
            events.append({"month": m, "id": g["id"], "name": g["name"], "target": round(g["target_amount"]),
                           # rounding SIPs to ₹100 can leave a few rupees; under 0.5% of the target is not "short"
                           "paid": round(paid), "short": gap if gap > g["target_amount"] * 0.005 else 0})
            spare += pot - paid
            pots[g["id"]] = 0.0
        if m % 12 == 0 or m in by_month or m == horizon:
            points.append({"month": m, "total": round(spare + sum(v for k, v in pots.items() if _alive(goals, k, m))),
                           **({"after_payout": True} if m in by_month else {})})
    return {"points": points, "events": events, "horizon": horizon}


def _alive(goals: list[dict], gid: str, m: int) -> bool:
    return next(g for g in goals if g["id"] == gid)["months"] > m


def new_goal_impact(d: dict, new_goal: dict, corpus: float, current_monthly: float, investable: float) -> dict:
    """"A smaller goal has come up" - what it costs, three ways:
    A. save for it each month (the plan's normal rule: it is funded in order, so later goals may get less),
    B. pay for it from the main goal's savings when it falls due (no new SIP; the main goal pays the price),
    C. push it out until the money you have spare each month can reach it (nothing else changes)."""
    base = plan_goals(d, corpus, current_monthly, investable)
    d2 = copy.deepcopy(d)
    ng_in = {**new_goal, "id": "new"}
    d2["goals_extra"] = (d2.get("goals_extra") or [])[:MAX_EXTRA_GOALS - 1] + [ng_in]
    after = plan_goals(d2, corpus, current_monthly, investable)
    ng = next(g for g in after["goals"] if g["id"] == "new")
    bmain = base["goals"][0]
    stated = d.get("profile", {}).get("risk_appetite")
    spare = base["unallocated"]

    # A. save separately: the new goal enters the funding order; show what every existing goal gets afterwards
    effects = []
    for b in base["goals"]:
        a = next(g for g in after["goals"] if g["id"] == b["id"])
        effects.append({"id": b["id"], "name": b["name"], "funded_before": b["funded_monthly"], "funded_after": a["funded_monthly"],
                        "projected_before": b["projected_plan"], "projected_after": a["projected_plan"],
                        "target": b["target_amount"], "status_after": a["status"],
                        "corpus_before": b["corpus"], "corpus_after": a["corpus"],
                        "reachable_after": a["reachable_date"], "delay_after": a["delay_months"]})
    # a goal is "hurt" when its projected value falls by more than 0.5% of its target (not by rounding)
    hurt = [e for e in effects if e["projected_before"] - e["projected_after"] > max(1000, e["target"] * 0.005)]
    # The true monthly cost is the change in what ALL goals need: savings set aside for the new goal leave the
    # others, so their SIPs rise even when the new goal itself needs little or nothing each month.
    cost = max(0, after["total_required"] - base["total_required"])
    option_a = {"monthly_cost": cost, "new_goal_monthly": ng["required_monthly"], "funded": ng["funded_monthly"],
                "set_aside_now": ng["corpus"], "others_monthly_change": cost - ng["required_monthly"],
                "covered_by_spare": after["underfunded_total"] <= base["underfunded_total"] + 100 and not hurt,
                "spare_after": after["unallocated"],
                "new_goal_status": ng["status"], "new_goal_reachable": ng["reachable_date"], "effects": effects, "hurts": hurt}

    # B. take it from the main goal's pot on the new goal's date (only if it comes before the main goal)
    n_new, n_main, r_main = ng["months"], bmain["months"], _rate(bmain["expected_return_pct"])
    if n_new < n_main:
        t_new = float(new_goal["target_amount"])
        loss = t_new * (1 + r_main) ** (n_main - n_new)
        projected_b = bmain["projected_plan"] - loss
        g = (1 + r_main) ** n_main
        extra = loss / ((g - 1) / r_main) if r_main else loss / n_main
        delay = None
        for m in range(n_main, MAX_MONTHS + 1):
            if fv(bmain["corpus"], bmain["funded_monthly"], r_main, m) - t_new * (1 + r_main) ** (m - n_new) >= bmain["target_amount"] - 0.5:
                delay = m - n_main
                break
        option_b = {"applies": True, "withdrawal": round(t_new), "main_loses_at_goal": round(loss),
                    "risk_note": (f"The {new_goal.get('name') or 'new goal'} money stays in your main goal's "
                                  f"{bmain['risk']}-risk mix until it is needed, so a market fall just before could leave it short."
                                  if bmain["mix"]["equity"] > 0 else None),
                    "main_projected_after": round(projected_b), "main_target": bmain["target_amount"],
                    "main_short_after": max(0, round(bmain["target_amount"] - projected_b)),
                    "extra_monthly_to_recover": round(extra), "delay_months": delay,
                    "main_new_date": date_after(n_main + delay) if delay is not None else None}
    else:
        option_b = {"applies": False, "why": "The new goal comes after your main goal, so there is no main-goal money to borrow from."}

    # C. wait: the spare money each month (what the plan leaves unallocated) - when can it reach the new goal alone?
    wait_m = None
    if spare > 0:
        for m in range(n_new, MAX_MONTHS + 1):
            if fv(0, spare, _rate(goal_mix(stated, m / 12)["expected_return_pct"]), m) >= float(new_goal["target_amount"]) - 0.5:
                wait_m = m
                break
    option_c = {"spare_monthly": spare, "reachable_months": wait_m,
                "reachable_date": date_after(wait_m) if wait_m else None,
                "delay_months": (wait_m - n_new) if wait_m else None}

    # recommendation, in plain rules
    if option_a["covered_by_spare"]:
        rec = ("A", "Save for it separately: your spare money covers its full monthly cost, every goal stays funded, "
                    "and its money sits in a mix suited to its own date.")
    elif option_c["delay_months"] is not None and option_c["delay_months"] <= 12:
        rec = ("C", f"Waiting about {option_c['delay_months']} months lets your spare money pay for it, and keeps every other goal as planned.")
    elif option_b.get("applies") and option_b["extra_monthly_to_recover"] <= spare + 100:
        rec = ("B", "Pay it from your main goal's savings, then let your spare money top the main goal back up - "
                    "it fits within what you have spare each month (mind the market-risk note).")
    else:
        rec = ("A", "Saving for it separately keeps the trade-off visible: the goals funded last get less, as shown.")
    return {"new_goal": {k: ng[k] for k in ("name", "target_amount", "target_date", "months", "years", "risk",
                                            "expected_return_pct", "instruments", "priority", "required_monthly", "corpus")},
            "base": {"unallocated": spare, "all_funded": base["all_funded"]},
            "option_a": option_a, "option_b": option_b, "option_c": option_c,
            "recommended": rec[0], "recommendation": rec[1]}
