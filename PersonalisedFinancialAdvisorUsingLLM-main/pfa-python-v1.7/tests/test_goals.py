"""v1.7: several goals - how savings and monthly money are shared, the "new goal in between" options, the profile and
chat changes, and the report section.  Run:  python -m unittest discover -s tests   (from the bundle folder)"""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("SESSION_SECRET", "x" * 40)

from jinja2 import Environment, FileSystemLoader            # noqa: E402

from pfa.ai import narrative                                # noqa: E402
from pfa.ai.chat import impact_lines                        # noqa: E402
from pfa.engine import compute, goal_impact                 # noqa: E402
from pfa.engine.goals import fv, months_to_reach, required_pmt  # noqa: E402
from pfa.profile import apply_changes, build_profile, check_step, new_goal_from  # noqa: E402
from pfa.report import view                                 # noqa: E402
from test_engine import PRIYA, years_ahead                  # noqa: E402

CAR = {"goal_type": "Buy a car", "details": "Family car", "target_amount": "6L", "target_date": years_ahead(2), "priority": "Must-have"}


def profile(**extra):
    return build_profile({**PRIYA, **extra}, "priya@example.com")


class Maths(unittest.TestCase):
    def test_required_monthly_reaches_target(self):
        r = 0.09 / 12
        pmt = required_pmt(800000, 100000, r, 36)
        self.assertAlmostEqual(fv(100000, pmt, r, 36), 800000, delta=1)
        self.assertEqual(required_pmt(100000, 500000, r, 36), 0)           # savings alone get there
        self.assertEqual(months_to_reach(800000, 100000, pmt, r), 36)


class SharingMoney(unittest.TestCase):
    def test_one_goal_gives_v16_numbers(self):
        f = compute(profile())
        gp, pr, mp = f["goals_plan"], f["projection"], f["monthly_plan"]
        self.assertEqual(gp["count"], 1)
        main = gp["goals"][0]
        self.assertAlmostEqual(main["corpus"], f["allocation"]["total_value"], delta=1)
        self.assertEqual(main["funded_monthly"], mp["goal_investment"])
        need_up = -(-pr["required_monthly"] // 100) * 100        # rounded up to ₹100 when the money allows
        self.assertEqual(mp["goal_investment"], need_up if need_up <= gp["investable"] else gp["investable"] // 100 * 100)
        self.assertEqual(mp["goal_underfunded_by"], 0)
        self.assertEqual(main["risk"], f["risk_plan"]["effective_risk"])

    def test_near_goal_first_with_its_own_risk(self):
        f = compute(profile(extra_goals=[CAR]))
        gp = f["goals_plan"]
        home, car = gp["goals"]
        self.assertEqual(gp["count"], 2)
        self.assertEqual(car["funded_order"], 1)                          # nearest must-have first
        self.assertEqual(car["risk"], "Low")                              # 2 years away
        self.assertEqual(car["mix"]["equity"], 0)
        self.assertEqual(home["risk"], "High")
        self.assertAlmostEqual(home["corpus"] + car["corpus"], f["allocation"]["total_value"], delta=2)
        self.assertLessEqual(gp["funded_total"], gp["investable"])
        # the main goal's projection now uses only its share of the savings
        self.assertAlmostEqual(f["projection"]["current_corpus"], home["corpus"], delta=1)
        self.assertEqual(f["monthly_plan"]["goal_investment"], gp["funded_total"])

    def test_not_enough_money_and_nice_to_have_waits(self):
        trip = {"goal_type": "Travel or sabbatical", "details": "World trip", "target_amount": "40L",
                "target_date": years_ahead(1.5), "priority": "Nice-to-have"}
        f = compute(profile(extra_goals=[trip]))
        home, t = f["goals_plan"]["goals"]
        self.assertEqual(t["funded_order"], 2)                            # nearer, but only nice-to-have
        self.assertIn(t["status"], ("partly", "not_funded"))
        self.assertFalse(f["goals_plan"]["all_funded"])
        self.assertGreater(f["goals_plan"]["underfunded_total"], 0)
        self.assertTrue(narrative.fallback(profile(extra_goals=[trip]), f, [])["summary"].count("goals"))

    def test_timeline_pays_each_goal_on_its_date(self):
        f = compute(profile(extra_goals=[CAR]))
        tl = f["goals_plan"]["timeline"]
        car_ev = next(e for e in tl["events"] if e["id"] == "g1")
        self.assertAlmostEqual(car_ev["month"], f["goals_plan"]["goals"][1]["months"])
        before = next(p for p in tl["points"] if p["month"] == car_ev["month"] and not p.get("after_payout"))
        after = next(p for p in tl["points"] if p["month"] == car_ev["month"] and p.get("after_payout"))
        self.assertAlmostEqual(before["total"] - after["total"], car_ev["paid"], delta=2)


class NewGoalInBetween(unittest.TestCase):
    def test_three_options(self):
        p = profile()
        goal, err = new_goal_from({"goal_type": "Buy a car", "target_amount": "6L", "target_date": years_ahead(2)})
        self.assertIsNone(err)
        imp = goal_impact(p, goal)
        a, b, c = imp["option_a"], imp["option_b"], imp["option_c"]
        base, after = compute(p)["goals_plan"], compute(profile(extra_goals=[CAR]))["goals_plan"]
        # A: true monthly cost = what all goals need afterwards minus before (savings moved to the car raise the home SIP)
        self.assertAlmostEqual(a["monthly_cost"], after["total_required"] - base["total_required"], delta=2)
        self.assertGreater(a["set_aside_now"], 0)
        self.assertGreater(a["others_monthly_change"], 0)
        # B: the withdrawal loses its growth until the main goal's date
        home = base["goals"][0]
        r = home["expected_return_pct"] / 1200
        self.assertTrue(b["applies"])
        self.assertAlmostEqual(b["main_loses_at_goal"], 600000 * (1 + r) ** (home["months"] - imp["new_goal"]["months"]), delta=2)
        self.assertIsNotNone(b["risk_note"])                              # home money sits in equity until then
        # C: spare money alone, never before the wanted date
        self.assertGreaterEqual(c["reachable_months"], imp["new_goal"]["months"])
        self.assertIn(imp["recommended"], "ABC")
        self.assertTrue(impact_lines(p, {"goal_type": "Buy a car", "name": "Car", "target_amount": 600000,
                                         "target_date": years_ahead(2)}))

    def test_goal_after_main_cannot_borrow(self):
        goal, _ = new_goal_from({"goal_type": "Retirement", "target_amount": "2Cr", "target_date": years_ahead(20)})
        self.assertFalse(goal_impact(profile(), goal)["option_b"]["applies"])

    def test_bad_input(self):
        self.assertIsNotNone(new_goal_from({"goal_type": "Buy a car", "target_amount": "lots", "target_date": years_ahead(2)})[1])
        self.assertIsNotNone(new_goal_from({"goal_type": "Buy a car", "target_amount": "6L", "target_date": "2001-01-01"})[1])


class ProfileAndChat(unittest.TestCase):
    def test_form_checks(self):
        e = check_step(1, {**PRIYA, "extra_goals": [{"goal_type": "Buy a car", "target_amount": "lots", "target_date": ""},
                                                    {"goal_type": "", "target_amount": "", "target_date": ""}]})
        self.assertIn("extra_goals.0.target_amount", e)
        self.assertIn("extra_goals.0.target_date", e)
        self.assertNotIn("extra_goals.1.goal_type", e)                    # a blank row is ignored
        self.assertNotIn("target_amount", e)                              # the main goal's field is untouched

    def test_profile_keeps_goals(self):
        p = profile(extra_goals=[CAR])
        self.assertEqual(p["goals_extra"][0]["name"], "Buy a car - Family car")
        self.assertEqual(p["goals_extra"][0]["target_amount"], 600000)
        self.assertEqual(p["answers"]["extra_goals"][0]["target_amount"], "6L")

    def test_chat_add_and_remove(self):
        saved = profile()
        a, log, ignored = apply_changes(saved, {"add_goal": {"goal_type": "Buy a car", "name": "Family car",
                                                             "target_amount": 600000, "target_date": years_ahead(2)}})
        self.assertTrue(log and log[0].startswith("Added goal: Family car"))
        p2 = build_profile(a, "priya@example.com", previous=saved)
        self.assertEqual(len(p2["goals_extra"]), 1)
        a3, log3, _ = apply_changes(p2, {"remove_goal": "Buy a car - Family car"})
        self.assertEqual(log3, ["Removed goal: Family car"])
        self.assertEqual(build_profile(a3, "priya@example.com")["goals_extra"], [])
        full = profile(extra_goals=[CAR, CAR, CAR])
        _, log4, ign4 = apply_changes(full, {"add_goal": {"goal_type": "Other", "target_amount": 100000, "target_date": years_ahead(1)}})
        self.assertFalse(log4)
        self.assertTrue(any("already has 3" in x for x in ign4))


class ReportSection(unittest.TestCase):
    def test_goals_section_renders(self):
        p = profile(extra_goals=[CAR])
        f = compute(p)
        r = {"profile": p, **f, "ai": narrative.fallback(p, f, []), "picks": [], "screen": {}, "status": "ready",
             "started_at": time.time(), "change_log": [], "parent": None}
        v = view(r)
        self.assertEqual(len(v["goals"]["rows"]), 2)
        env = Environment(loader=FileSystemLoader(str(Path(__file__).resolve().parents[1] / "app/pfa/templates")))
        html = env.get_template("_report_main.html").render(**v, report_id="x")
        self.assertIn("Your goals (2)", html)
        self.assertIn("What if a new goal comes up?", html)
        self.assertIn("goal-mark", html)                                  # payout markers on the timeline
        imp = goal_impact(profile(), new_goal_from({"goal_type": "Buy a car", "target_amount": "6L", "target_date": years_ahead(2)})[0])
        part = env.get_template("_goal_impact.html").render(imp=imp, mo=v["mo"], sh=v["sh"], month_text=v["month_text"])
        self.assertIn("A · Save for it separately", part)
        self.assertIn("data-add-goal", part)


if __name__ == "__main__":
    unittest.main()
