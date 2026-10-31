"""Deterministic finance engine: every number in the report is computed here."""
from .allocation import allocation_and_risk
from .debt import debt_metrics
from .goals import new_goal_impact, plan_goals
from .projection import emergency_and_investable, projection


def compute(profile: dict) -> dict:
    """Profile -> all computed facts (pure, fast, unit-tested). v1.7: goals_plan shares money across all goals."""
    debt = debt_metrics(profile)
    alloc = allocation_and_risk(profile)
    gp = plan_goals(profile, alloc["total_value"], float(profile["derived"]["monthlyContrib"]),
                    emergency_and_investable(profile)["investable"])
    proj = projection(profile, alloc, debt, gp)
    return {"debt": debt, "allocation": alloc, "risk_plan": alloc["risk_plan"], "goals_plan": gp, **proj}


def goal_impact(profile: dict, new_goal: dict) -> dict:
    """What a new (often smaller, sooner) goal does to the plan - see goals.new_goal_impact."""
    alloc = allocation_and_risk(profile)
    return new_goal_impact(profile, new_goal, alloc["total_value"], float(profile["derived"]["monthlyContrib"]),
                           emergency_and_investable(profile)["investable"])
