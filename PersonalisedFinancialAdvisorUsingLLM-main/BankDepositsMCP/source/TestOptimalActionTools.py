"""Tests for OptimalActionFixedDepositTool and OptimalActionRecurringDepositTool.

Run from the source directory:
    python -m unittest TestOptimalActionTools -v

To also render the mermaid output of each test as diagrams for visual
verification, run the file directly with --diagrams:
    python TestOptimalActionTools.py --diagrams
This writes TestOptimalActionDiagrams.html in the "output" folder; open it in a
browser (it loads mermaid.js from a CDN).
"""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date

from StateActionState import (OUTPUT_DIR, OptimalActionFixedDepositTool,
                              OptimalActionRecurringDepositTool,
                              OptimalActionRecurringDeposit,
                              WriteMermaidDiagramPage, recurringDeposit,
                              state, stateR,
                              writeMermaidDiagramPage)

TODAY = date(2025, 1, 1)
GOAL_DATE = date(2030, 1, 1)


DIAGRAM_FILE = os.path.join(OUTPUT_DIR, "TestOptimalActionDiagrams.html")
SAVE_DIAGRAMS = False
DIAGRAMS = []


def recordDiagram(name, text):
    DIAGRAMS.append((name, text))


def tearDownModule():
    if SAVE_DIAGRAMS and DIAGRAMS:
        print(f"\nDiagrams written to {writeMermaidDiagramPage(DIAGRAMS, DIAGRAM_FILE)}")


def fixedDeposits():
    return [
        {"interestRate": 7.0, "duration": 1.0, "compoundingDuration": 0.25,
         "scheme_name": "FD1Y", "bank_name": "BankA"},
        {"interestRate": 7.5, "duration": 2.0, "compoundingDuration": 0.25,
         "scheme_name": "FD2Y", "bank_name": "BankB"},
    ]


def recurringDeposits():
    return [
        {"interestRate": 6.5, "duration": 1.0, "compoundingDuration": 0.25,
         "recurringDuration": 1, "scheme_name": "RD1Y",
         "bank_name": "BankA"},
        {"interestRate": 7.0, "duration": 2.0, "compoundingDuration": 0.25,
         "recurringDuration": 1, "scheme_name": "RD2Y",
         "bank_name": "BankB"},
    ]


class WriteMermaidDiagramPageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_tool_accepts_diagram_objects_and_pairs(self):
        out = os.path.join(self.dir, "d.html")
        result = WriteMermaidDiagramPage.invoke({
            "diagrams": [{"name": "a", "description": "graph TD; x-->y;"},
                         ["b", "graph TD; p-->q;"]],
            "path": out})
        self.assertEqual(result, out)
        with open(out, encoding="utf-8") as f:
            page = f.read()
        self.assertEqual(page.count('class="mermaid"'), 2)

    def test_folder_path_gets_default_file_name(self):
        result = WriteMermaidDiagramPage.invoke({
            "diagrams": [{"name": "a", "description": "graph TD; x-->y;"}],
            "path": self.dir})
        self.assertEqual(os.path.basename(result),
                         "OptimalActionDiagrams.html")
        self.assertTrue(os.path.isfile(result))


class FixesRegressionTest(unittest.TestCase):
    def test_non_html_output_path_rejected(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        target = os.path.join(d, "keep.py")
        with open(target, "w") as f:
            f.write("x = 1")
        with self.assertRaises(ValueError):
            WriteMermaidDiagramPage.invoke({
                "diagrams": [{"name": "a", "description": "graph TD;"}],
                "path": target})
        with open(target) as f:
            self.assertEqual(f.read(), "x = 1")

    def test_quote_in_scheme_name_does_not_break_label(self):
        fd = fixedDeposits()
        fd[1]["scheme_name"] = 'Tax "Saver"'
        text = OptimalActionFixedDepositTool.invoke({
            "s0": {"balance": 100000, "time": TODAY},
            "sg": {"balance": 200000, "time": GOAL_DATE},
            "deposits": fd})
        self.assertIn("Tax 'Saver'", text)
        for line in text.splitlines():
            if "-->|" in line:
                self.assertEqual(line.count('"'), 2)

    def test_repeated_recurring_action_ends_at_full_balance(self):
        rds = [recurringDeposit(**d) for d in recurringDeposits()]
        oA = OptimalActionRecurringDeposit(
            stateR(balance=5000, time=TODAY),
            state(balance=500000, time=GOAL_DATE), rds)
        graph, _ = oA.getActionList()
        for (dep, count), nextSt in oA.actionStateList:
            self.assertTrue(any(
                abs(v.balance - nextSt.balance) < 1e-6 and v.time == nextSt.time
                for _, v in graph.edges))
        # Edges chain: every edge start is the end of an earlier edge.
        ends = {(v.balance, v.time) for _, v in graph.edges}
        starts = [(u.balance, u.time) for u, _ in graph.edges]
        first = oA.s0
        for s in starts:
            self.assertTrue(s == (first.balance, first.time) or s in ends)

    def test_importing_agent_does_not_run_it(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "OptimalBankDepositFinderAgent.py"),
                  encoding="utf-8") as f:
            src = f.read()
        self.assertIn('if __name__ == "__main__":', src)
        self.assertNotRegex(src, r"(?m)^result = graph\.invoke")


class OptimalActionFixedDepositToolTest(unittest.TestCase):
    def invoke(self, balance=100000, goal=200000, deposits=None):
        return OptimalActionFixedDepositTool.invoke({
            "s0": {"balance": balance, "time": TODAY},
            "sg": {"balance": goal, "time": GOAL_DATE},
            "deposits": fixedDeposits() if deposits is None else deposits,
        })

    def test_returns_mermaid_text(self):
        result = self.invoke()
        text = result if isinstance(result, str) else result.graphInText
        self.assertIsInstance(text, str)
        self.assertTrue(text.strip())
        recordDiagram(self.id().split(".")[-2], text)

    def test_zero_balance_returns_empty_graph(self):
        # The tool short-circuits when there is nothing to invest.
        result = self.invoke(balance=0)
        text = result if isinstance(result, str) else result.graphInText
        self.assertIsInstance(text, str)

    def test_non_positive_goal_rejected(self):
        with self.assertRaises(AssertionError):
            self.invoke(goal=0)

    def test_invalid_interest_rate_rejected(self):
        bad = fixedDeposits()
        bad[0]["interestRate"] = 0
        with self.assertRaises(AssertionError):
            self.invoke(deposits=bad)

    def test_invalid_args_schema_rejected(self):
        with self.assertRaises(Exception):
            OptimalActionFixedDepositTool.invoke({"s0": {"balance": 1}})


class OptimalActionRecurringDepositToolTest(unittest.TestCase):
    def invoke(self, installment=5000, goal=500000, rds=None, fds=None):
        return OptimalActionRecurringDepositTool.invoke({
            "s0": {"balance": installment, "time": TODAY},
            "sg": {"balance": goal, "time": GOAL_DATE},
            "recurringDeposits": (recurringDeposits() if rds is None
                                  else rds),
            "fixedDeposits": fixedDeposits() if fds is None else fds,
        })

    def test_returns_mermaid_text(self):
        result = self.invoke()
        text = result if isinstance(result, str) else result.graphInText
        self.assertIsInstance(text, str)
        self.assertTrue(text.strip())
        recordDiagram(self.id().split(".")[-2], text)

    def test_zero_installment_returns_empty_graph(self):
        result = self.invoke(installment=0)
        text = result if isinstance(result, str) else result.graphInText
        self.assertIsInstance(text, str)

    def test_goal_not_above_installment_rejected(self):
        with self.assertRaises(AssertionError):
            self.invoke(installment=5000, goal=5000)

    def test_invalid_compounding_duration_rejected(self):
        bad = recurringDeposits()
        bad[0]["compoundingDuration"] = 0
        with self.assertRaises(AssertionError):
            self.invoke(rds=bad)

    def test_invalid_args_schema_rejected(self):
        with self.assertRaises(Exception):
            OptimalActionRecurringDepositTool.invoke({"s0": {"balance": 1}})


# if __name__ == "__main__":
#     if "--diagrams" in sys.argv:
#         sys.argv.remove("--diagrams")
#         SAVE_DIAGRAMS = True
#     unittest.main()
