"""Bank deposit planner: maths, the Low-risk hook, the chat router and parity with the n8n Code node.
Run:  python -m unittest discover -s tests   (from the bundle folder). Made-up amounts only."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("SESSION_SECRET", "x" * 40)

from pfa.ai import router                                           # noqa: E402
from pfa.engine import compute, deposits                            # noqa: E402
from pfa.profile import build_profile                               # noqa: E402

CASES = [
    {"initial_amount": 500000, "goal_amount": 520000, "goal_date": "2029-10-01", "start_date": "2026-10-01", "inflation_pct": 4},
    {"initial_amount": 300000, "monthly_installment": 15000, "goal_amount": 900000, "goal_date": "2030-10-01", "start_date": "2026-10-01", "inflation_pct": 5},
    {"initial_amount": 100000, "monthly_installment": 2000, "goal_amount": 5000000, "goal_date": "2028-10-01", "start_date": "2026-10-01", "inflation_pct": 5},
    {"initial_amount": 500000, "goal_amount": 2000000, "goal_date": "2036-10-01", "start_date": "2026-10-01", "inflation_pct": 4, "banks": "sbi", "senior": "yes"},
    {"monthly_installment": 5000, "goal_amount": 241163, "goal_date": "2030-04-01", "start_date": "2026-09-30", "inflation_pct": 0},
]


class DepositMaths(unittest.TestCase):
    def test_table_loaded(self):
        rows = deposits.load_rows()
        self.assertEqual(len(rows), 211)
        self.assertEqual(len({r["bank_name"] for r in rows}), 10)

    def test_rd_maturity_matches_banks(self):          # Rs 5,000 a month, 7%, 12 months ~ Rs 62,000
        self.assertTrue(61500 < deposits.rd_maturity(5000, 7, 12) < 62600)

    def test_inflation_over_whole_period(self):
        one = [{"bank": "Test", "scheme": "FD", "tenor": "2 years", "months": 24, "years": 2, "comp": 0.25, "rate": 7, "rate_source": "t"}]
        r = deposits.plan_fd(100000, date(2026, 10, 1), date(2036, 10, 3), 1e9, 5, one)
        nominal = 100000 * (1 + 7 * 0.25 / 100) ** 40
        self.assertEqual(r["steps"][0]["times"], 5)
        self.assertAlmostEqual(r["final_value_in_todays_money"], nominal / 1.05 ** 10, delta=50)

    def test_fd_reaches_modest_goal(self):
        r = deposits.plan_deposits(CASES[0])
        self.assertTrue(r["ok"] and r["fixed_deposit_plan"]["reached"])
        self.assertEqual(r["shortfall_todays_money"], 0)

    def test_rd_fills_the_whole_period(self):
        r = deposits.plan_deposits(CASES[1])
        best = r["recurring_deposit_plan"]["best"]
        self.assertTrue(r["recurring_deposit_plan"]["reached"])
        self.assertEqual(best["total_paid"], 15000 * best["months"])
        alts = r["recurring_deposit_plan"]["alternatives"]
        self.assertGreaterEqual(best["value_in_todays_money"], alts[0]["value_in_todays_money"])

    def test_out_of_reach_gives_shortfall(self):
        r = deposits.plan_deposits(CASES[2])
        self.assertGreater(r["shortfall_todays_money"], 0)
        self.assertGreater(r["recurring_deposit_plan"]["best"]["installment_needed_for_goal"], 2000)

    def test_nothing_fits_says_so(self):
        r = deposits.plan_deposits({"monthly_installment": 5000, "goal_amount": 100000, "goal_date": "2026-12-01",
                                    "start_date": "2026-10-01", "inflation_pct": 5})
        self.assertEqual(r["verdict"], deposits.NOT_POSSIBLE)

    def test_senior_and_bank_filter(self):
        g = deposits.plan_deposits({**CASES[3], "senior": "no"})
        s = deposits.plan_deposits(CASES[3])
        self.assertTrue(all(x["bank"] == "State Bank of India" for x in g["fixed_deposit_plan"]["steps"]))
        self.assertGreater(s["fixed_deposit_plan"]["final_value"], g["fixed_deposit_plan"]["final_value"])

    def test_bad_input(self):
        r = deposits.plan_deposits({"goal_amount": "abc", "goal_date": "2020-01-01", "inflation_pct": 5})
        self.assertFalse(r["ok"])
        self.assertGreaterEqual(len(r["errors"]), 2)

    def test_best_rates(self):
        rows = deposits.best_rates("Recurring Deposit", "HDFC")
        self.assertTrue(rows and all(x["bank"] == "HDFC Bank" and x["type"] == "RD" for x in rows))
        for name in ("SBI", "State Bank of India", "sbi bank", "Bank of Baroda", "bob", "PNB", "Punjab National Bank", "IDFC FIRST Bank"):
            rows = deposits.best_rates("Fixed Deposit", name)
            self.assertTrue(rows and len({x["bank"] for x in rows}) == 1, name)      # the full name works as well as the alias
        both = {x["bank"] for x in deposits.best_rates(None, "HDFC Bank,State Bank of India", limit=50)}
        self.assertEqual(both, {"HDFC Bank", "State Bank of India"})


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ParityWithN8n(unittest.TestCase):
    """The n8n Code node (tools/deposit_optimiser.js) and this module must give the same plan."""
    def test_same_plans(self):
        js = subprocess.run(["node", "-e", """
const { planDeposits } = require(process.argv[1]);
const fs = require('fs');
const lines = fs.readFileSync(process.argv[2], 'utf8').trim().split('\\n'); const head = lines.shift().split(',');
const rows = lines.map(l => { const c = l.match(/("([^"]|"")*"|[^,]*)(,|$)/g).map(x => x.replace(/,$/, '').replace(/^"|"$/g, '').replace(/""/g, '"'));
  const o = {}; head.forEach((h, i) => o[h] = c[i] === '' ? null : c[i]); return o; });
console.log(JSON.stringify(JSON.parse(process.argv[3]).map(p => planDeposits(rows, p))));
""", str(ROOT / "tools" / "deposit_optimiser.js"), str(deposits.CSV_PATH), json.dumps(CASES)], capture_output=True, text=True, check=True)
        for case, j in zip(CASES, json.loads(js.stdout)):
            p = deposits.plan_deposits(case)
            for k in ("verdict", "fixed_deposit_plan", "remaining_goal_after_fd_todays_money", "recurring_deposit_plan", "shortfall_todays_money"):
                self.assertEqual(json.loads(json.dumps(p[k])), j[k], msg=f"{k} differs for {case}")


def years_ahead(y: float) -> str:
    return (date.today() + timedelta(days=round(365.25 * y))).isoformat()


LOW = {"name": "Test Lowrisk", "age": "34", "currency": "INR", "ctc": "12L", "goal_type": "Buy a car", "goal_details": "",
       "target_amount": "8L", "target_date": years_ahead(3.5), "take_home": "88.5K", "expenses": "40K", "emergency": "2.4L",
       "term_cover": "1Cr", "health_cover": "10L", "loan_types": ["None - I'm debt-free"], "loans": {},
       "inv": {"mf_value": "1L", "mf_monthly": "5K", "fd_value": "50K", "pf_value": "2L", "pf_monthly": "3.6K"},
       "risk": "Low", "_loans_answered": True}


class LowRiskHook(unittest.TestCase):
    def facts(self, **over):
        prof = build_profile({**LOW, **over}, "lowrisk@test.local")
        return prof, compute(prof)

    def test_low_risk_gets_deposit_plan(self):
        prof, f = self.facts()
        dp = deposits.for_plan(f, 34)
        self.assertTrue(dp and dp["ok"] and dp["steps"], dp)
        fi = next(r for r in f["monthly_plan"]["rows"] if r["bucket"] == "Fixed income")
        self.assertTrue(fi["instrument"].startswith("Bank RD: "))
        self.assertIs(f["deposit_plan"], dp)

    def test_medium_long_goal_skips(self):
        _, f = self.facts(risk="Medium", target_date=years_ahead(6))
        self.assertIsNone(deposits.for_plan(f, 34))
        self.assertNotIn("deposit_plan", f)

    def test_short_goal_applies_even_if_high(self):
        _, f = self.facts(risk="High", target_date=years_ahead(2))
        self.assertTrue(deposits.applies(f))


class Router(unittest.TestCase):
    def test_deposit_questions_stay_local(self):
        for q in ("What are the best FD rates?", "Which bank gives the highest RD rate for 2 years?",
                  "Plan fixed deposits for 5 lakh till 2030", "current SBI fixed deposit rate", "suggest a recurring deposit"):
            self.assertEqual(router.decide(q).kind, "deposits", q)

    def test_other_rates_still_live(self):
        self.assertEqual(router.decide("What is the repo rate today?").kind, "live")


if __name__ == "__main__":
    unittest.main()
