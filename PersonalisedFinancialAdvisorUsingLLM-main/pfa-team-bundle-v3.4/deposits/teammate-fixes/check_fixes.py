"""python3 deposits/teammate-fixes/check_fixes.py
Runs the teammate's ORIGINAL optimiser and the FIXED copy side by side (made-up amounts).
Needs no installs: pydantic / langchain are replaced by tiny stand-ins, only the maths is exercised."""
import importlib.util, json, subprocess, sys, types
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIG = HERE.parents[2] / "PersonalisedFinancialAdvisorUsingLLM-main"   # read only
BUNDLE = HERE.parents[1]

class BaseModel:                      # stand-in: keyword fields become attributes
    def __init__(self, **kw): self.__dict__.update(kw)
    def __repr__(self): return f"{type(self).__name__}({self.__dict__})"
pyd = types.ModuleType("pydantic"); pyd.BaseModel = BaseModel; pyd.Field = lambda *a, **k: None
tools = types.ModuleType("langchain_core.tools"); tools.tool = lambda *a, **k: (lambda f: f)
sys.modules.update({"pydantic": pyd, "langchain_core": types.ModuleType("langchain_core"), "langchain_core.tools": tools})

def load(folder, tag):
    for name in ("GoalSearch", "StateActionState"):
        spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
        mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return sys.modules["StateActionState"]

orig, fixed = load(ORIG, "original"), load(HERE, "fixed")
rupees = lambda x: f"Rs {x:,.0f}"
ok = True
def check(label, cond):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + label)

# 1. RD maturity: Rs 5,000 a month, 7%, 12 months, quarterly compounding (bank calculators: ~Rs 62,000)
def rd(mod):
    s0 = mod.stateR(balance=5000, time=date(2026, 10, 1)); sg = mod.state(balance=10**9, time=date(2027, 10, 5))
    d = mod.recurringDeposit(interestRate=7, duration=1, compoundingDuration=0.25, recurringDuration=1/12, scheme_name="RD", bank_name="Test")
    return mod.OptimalActionRecurringDeposit(s0, sg, 0, [d]).actionStateList[0][1].balance
o, f = rd(orig), rd(fixed)
print(f"\nRD 5,000/month, 7%, 1 year, no inflation: original {rupees(o)}  fixed {rupees(f)}")
check("fixed RD maturity is Rs 61,500-62,600", 61500 < f < 62600)

# 2. Inflation: one 2-year FD at 7% renewed 5 times (10 years), inflation 5%, Rs 1,00,000
def fd(mod, goal=10**9):
    s0 = mod.state(balance=100000, time=date(2026, 10, 1)); sg = mod.state(balance=goal, time=date(2036, 10, 3))
    d = mod.deposit(interestRate=7, duration=2, compoundingDuration=0.25, scheme_name="FD", bank_name="Test")
    return mod.OptimalActionFixedDeposit(s0, sg, 5, [d]).actionStateList
o, f = fd(orig)[0], fd(fixed)[0]
nominal = 100000 * (1 + 7 * 0.25 / 100) ** 40
print(f"\nFD 2y x{f[0][1]}, 7%, 10 years, inflation 5%: nominal {rupees(nominal)}")
print(f"  in today's money - original {rupees(o[1].balance)} (deflated 2 years)  fixed {rupees(f[1].balance)} (deflated 10 years)")
check("fixed FD = nominal / 1.05^10", abs(f[1].balance - nominal / 1.05 ** 10) < 1)

js = subprocess.run(["node", "-e", """
const { planDeposits } = require(process.argv[1]);
const rows = [{ bank_name: 'Test', scheme_type: 'Fixed Deposit', scheme_name: 'FD', tenor_label: '2 years', duration_months: 24,
                interest_rate_general: 7, compounding_months: 3, rate_source: 't', as_of: 't' }];
const r = planDeposits(rows, { initial_amount: 100000, goal_amount: 1e9, goal_date: '2036-10-03', start_date: '2026-10-01', inflation_pct: 5 });
console.log(JSON.stringify(r.fixed_deposit_plan.final_value_in_todays_money));""", str(BUNDLE / "tools" / "deposit_optimiser.js")],
    capture_output=True, text=True)
check(f"n8n Code node (JS port) agrees: {rupees(float(js.stdout or 0))}", abs(float(js.stdout or 0) - f[1].balance) < 50)

# 3. Nothing fits before the goal date: original crashed (unset aM / zip(*[])), fixed returns empty lists
for name, mod in (("original", orig), ("fixed", fixed)):
    try:
        s0 = mod.state(balance=100000, time=date(2026, 10, 1)); sg = mod.state(balance=10**9, time=date(2026, 11, 1))
        d = mod.deposit(interestRate=7, duration=1, compoundingDuration=0.25, scheme_name="FD", bank_name="Test")
        out = mod.OptimalActionFixedDepositTool(s0, sg, 5, [d]); res = f"returned {out}"
    except Exception as e:
        out, res = None, f"crashed: {type(e).__name__}: {e}"
    print(f"\nGoal date before any FD ends - {name}: {res}")
check("fixed returns ([], []) instead of crashing", out == ([], []))

print("\nALL PASSED" if ok else "\nSOME CHECKS FAILED"); sys.exit(0 if ok else 1)
