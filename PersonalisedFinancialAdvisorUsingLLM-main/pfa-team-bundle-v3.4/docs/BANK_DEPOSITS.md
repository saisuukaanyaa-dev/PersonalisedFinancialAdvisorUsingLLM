# Bank deposit planner: the teammate's MCP rebuilt in n8n

Source project: `PersonalisedFinancialAdvisorUsingLLM-main` (LangGraph agent `OptimalBankDepositFinderAgent`, FastMCP server `DocumentMCP`, SQLite `memory.db`). That folder is only read; nothing in it is changed.

## What maps to what

| Teammate's project | This bundle |
|---|---|
| `memory.db`, built by hand by chatting with the admin agent in LangGraph Studio | `tools/build_deposit_db.py` builds it from the same bank markdown files. No AI; the same output every run |
| SQLite on the laptop | The same rows go into the stack's Postgres (`deposit_schemes`), loaded by `start.sh` on every start. `deposits/memory.db` is still produced for the Python code |
| LangGraph agent, gpt-4o | **Deposit Planner Agent** node, gpt-5-mini |
| `GetSqlLiteTablesStructure` + `GetSqlLiteTableData` (model writes any SQL) | **Get_Deposit_Rates**: one fixed, read-only query with a bank-name parameter |
| `OptimalActionFixedDepositTool` / `OptimalActionRecurringDepositTool` | **Plan_Bank_Deposits**: a sub-workflow that reads the rates, then runs the **Optimise FD & RD Plan** Code node (port of `GoalSearch.py` + `StateActionState.py`) |
| `get_india_inflation` | **Get_India_Inflation** tool. The planner also fetches the rate itself when the user gives none |
| `LLMWithGuardrails` (llm_guard + an extra gpt-4.1 call) | **Deposit Question Guardrail** (jailbreak, topic, PII, secrets) and **Deposit Output Sanitizer** |
| FastMCP `DocumentMCP` on 127.0.0.1:8090, no auth, tool `GetBestBankDepositSchemeSequence(request)` | **Bank Deposits MCP Server** at `/mcp/bank-deposits` with bearer auth, exposing `GetBestBankDepositSchemeSequence` (same name) plus `Plan_Bank_Deposits` and `Get_Deposit_Rates` |
| LangGraph Studio chat | Hosted **Chat Trigger** (link printed by `start.sh`) |

## The rate table (`deposit_schemes`)

The table has 211 rows from 10 banks: 9 detailed v2 documents plus the IndusInd summary.

- **Fixed Deposit**: every row of the bank's card-rate table.
  - A range like "5 years to 10 years" becomes two rows (60 and 120 months), the same split as `promptDictionary.txt` prompt 1.
  - "Above/more than X" excludes X, and "less than/below Y" excludes Y. When both ends are excluded, the midpoint is used.
- **Recurring Deposit**:
  - Axis, HDFC, ICICI and SBI have their own RD rate lists; `rate_source = 'RD rate list'`.
  - The other banks don't publish separate RD rates, so they use the FD card rate for the same 6–120-month tenor, and `rate_source` says so.
- Compounding is quarterly. Rates are marked `as_of = 2026-09`.
- **To refresh:** edit the markdown in `deposits/source/`, run `python3 tools/build_deposit_db.py`, then run `./start.sh`.

## The optimiser: kept vs fixed

**Kept from the original:**

- the state/action model
- the rate-sorted depth-first goal search (`BruteForce`)
- the FD formula (quarterly compounding; the same FD renewed `count` times)
- the FD sort key
- the agent's flow: FD for the lump sum first, then RD for what's left, then show both
- the "Not possible with current fixed/recurring deposits interest rates." message

**Fixed:**

1. **RD maturity (bug).** The original expression overstates maturity about 18×. For ₹5,000/month at 7% for 1 year with no inflation, it gives **₹11,03,576**; banks pay about **₹62,000**.
   - The fix is the standard Indian bank formula: each monthly installment compounds quarterly from the month it's paid until maturity, `M = Σₖ P·(1 + r/400)^((n−k+1)/3)`.
   - The fixed code gives **₹62,311**.
   - The RD sort key used the same wrong expression; it now ranks by what ₹1 a month grows to.
2. **Inflation (bug).** The original divides by `(1 + term × inflation)` once per step, even when the FD is renewed `count` times in that step. So inflation covered only one term.
   - Example: ₹1,00,000 in a 2-year FD at 7%, renewed 5 times (10 years), at 5% inflation. The nominal value is ₹2,00,160.
   - The original reports **₹1,81,963** in today's money, deflated for 2 years. The correct figure is **₹1,22,881**, deflated for 10 years (÷ 1.05¹⁰).
   - Now inflation compounds over the whole time elapsed, from the start to each maturity.
3. **Crashes.** When nothing fits, the original hit `zip(*[])` and an unset `aM`. Now the result is a clear verdict.
4. **Out-of-reach goals.** The original returned one step. Now it returns the best sequence found, the shortfall, and the monthly installment needed.
5. **RD plan.** It fills every month to the goal date with the best mix of back-to-back RDs (a small dynamic programme). Chaining RDs was the original's idea too.
6. **Speed.** A memo and a search budget keep it fast. A 20-year goal takes about 10 ms.

### Fixed copy of the teammate's Python

The teammate's folder is left as it is. `deposits/teammate-fixes/` holds `GoalSearch.py` and `StateActionState.py` with the same fixes. They are drop-in replacements with the same classes, tools and CRLF line endings, so the team can copy them into their project.

- **What changed:**
  - FD: inflation is compounded over `duration × count` years.
  - RD: standard maturity formula and sort key. The monthly installment is kept apart from the money saved, so a second RD step no longer treats the first RD's maturity amount as its installment. Matured RDs are deflated from the start date.
  - Both tools return `([], [])` instead of crashing when nothing fits.
  - `BestSearch` no longer crashes when no deposit ends before the goal date.
- **What stays the same:** the search itself.
- **Review:** the exact changes are in `*.py.diff`.
- **Check:** `python3 deposits/teammate-fixes/check_fixes.py` runs the original and fixed code side by side and compares them with the n8n Code node. It needs no installs; pydantic and langchain are stubbed. It prints the before/after figures above, and all checks pass.

The goal amount is compared **in today's money**, as in the original. The result also shows the goal's nominal value on the goal date.

Tests: `node tools/test/test_optimiser.js`. It uses made-up amounts and needs no Docker or OpenAI.

## How the v3.2 advisor uses it

### Low risk always goes through the deposit planner

The advisor doesn't leave this to the AI. Three nodes sit between **Compute Future Projection** and the **Investment Recommender**:

1. **Low risk → bank deposits?** (If). It's true when the chosen or applied risk is Low, or the goal is under 3 years away, and the monthly plan has a fixed-income amount. Otherwise the run goes straight to the Recommender as before.
2. **Plan Bank Deposits** (Execute Workflow → *PFA · Bank deposit planner*, plan branch, no AI). It sends:
   - the monthly fixed-income amount as the RD installment;
   - the goal date;
   - the fixed-income share of what the monthly saving must build: (target − today's investments grown at the plan's return) × fixed-income %;
   - inflation 0 (the advisor's target is a nominal amount);
   - senior rates for age 60+.
3. **Attach Deposit Plan** (Code). It adds `deposit_plan` to the data and rewrites the monthly plan's *Fixed income* row. For example, "Bank RD: IDFC FIRST Bank 6m @ 6.5%, then HDFC Bank 36m @ 7.1%".

The results reach the user in two ways:

- The **Recommender** receives the plan and is told to present those banks, tenures and rates exactly.
- The report card gets a new section, **Bank deposits for your fixed-income part**. It shows the RD sequence, amount paid in, value by the goal date, whether it covers the share, the monthly amount needed if not, and single-bank alternatives.

If the planner fails, the report still completes. The section then says the planner couldn't build a plan.

Tested on an isolated stack with a Low-risk profile: ₹12L CTC, a car goal of ₹8L by April 2030, ₹3.5L already invested. The fixed-income amount was ₹5,000/month. The report showed IDFC FIRST 6 months → HDFC 36 months, reaching ₹2.32L against a ₹2.41L share, with about ₹5,207/month needed.

### MCP tools for the agents

The advisor also has one MCP node, **Bank_Deposits_MCP** (MCP Client). It calls `http://localhost:5678/mcp/bank-deposits` with the same bearer credential.

- The node is attached to the **Investment Recommender** and the **Financial Q&A** agents.
- It exposes only `Plan_Bank_Deposits` and `Get_Deposit_Rates`, so the advisor doesn't pay for a second agent.
- The two agent prompts gain a "BANK DEPOSITS" rule. Bank names and rates from these tools may be named; that's the one exception to the no-brands rule.

## Cost

- **Plan_Bank_Deposits and Get_Deposit_Rates:** no AI, free.
- **Asking the planner (chat or `GetBestBankDepositSchemeSequence`):** 1 guardrail call plus 1–3 agent turns on gpt-5-mini. That's typically under ₹1 per question, versus roughly ₹5–15 with the original gpt-4o plus a gpt-4.1 guardrail.

## Limits

- **Rates are card rates** from the team's documents, not live. Confirm them with the bank.
- **Tax isn't modelled:** interest is shown before TDS and income tax.
- **Idle money:** matured RDs and FD money after the last step are held, not reinvested (a conservative choice).
