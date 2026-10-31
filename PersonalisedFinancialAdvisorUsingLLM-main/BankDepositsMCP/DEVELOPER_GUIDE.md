# Developer's Guide — Deposit Formulas and the Optimal Deposit Search

This guide explains the financial formulas used by the Optimal Bank Deposit Finder
and shows where each one is implemented. The formulas come from
[`financial-formulas.tex`](financial-formulas.tex). For run commands (database
creation, LangGraph Studio, MCP server), see [`readme.md`](readme.md).

---

## 1. Where the formulas live

| Concept | File | Symbol |
| :--- | :--- | :--- |
| Fixed deposit maturity + inflation | [`StateActionState.py`](source/StateActionState.py) | `OptimalActionFixedDeposit._finalBalance` |
| Fixed deposit ranking | [`StateActionState.py`](source/StateActionState.py) | `OptimalActionFixedDeposit.sortBase` |
| Recurring deposit maturity + inflation | [`StateActionState.py`](source/StateActionState.py) | `OptimalActionRecurringDeposit._finalBalance` |
| Recurring deposit ranking | [`StateActionState.py`](source/StateActionState.py) | `OptimalActionRecurringDeposit.sortBase` |
| Goal search over deposits | [`GoalSearch.py`](source/GoalSearch.py) | `GoalSearch.BruteForce`, `GoalSearch.BestSearch` |
| Inflation rate source | [`OptimalBankDepositFinderAgent.py`](source/OptimalBankDepositFinderAgent.py) | `get_india_inflation` (World Bank CPI API) |
| LLM-facing tools | [`StateActionState.py`](source/StateActionState.py) | `OptimalActionFixedDepositTool`, `OptimalActionRecurringDepositTool` |
| Mermaid diagram page (HTML, rendered with mermaid.js) | [`StateActionState.py`](source/StateActionState.py) | `writeMermaidDiagramPage` (function), `WriteMermaidDiagramPage` (LLM tool) |

`WriteMermaidDiagramPage` takes a list of diagrams (name + mermaid text) and an
output path. It writes one HTML page that renders every diagram with mermaid.js
(loaded from a CDN, so open the page in a browser) and returns the path written.
A relative path is placed in the project's `output` folder; a folder path gets the
default file name `OptimalActionDiagrams.html`; any path that is not `.html` is
rejected. `TestOptimalActionTools.py --diagrams` uses the same function to write
`output/TestOptimalActionDiagrams.html`.

---

## 2. Units: days in the formulas, years in the code

`financial-formulas.tex` writes every period in **days**. The Pydantic models
(`deposit`, `recurringDeposit`) store every period in **years**. The two forms are
the same once you divide each day count by $Y_d$:

| `.tex` symbol | Meaning | Code field (years) | Relation |
| :--- | :--- | :--- | :--- |
| $r$ | Annual interest rate (%) | `interestRate` | $r$ |
| $Y_d$ | Days in a year | hard-coded `365` | — |
| $T_d$ | Total tenure (days) | `duration` | `duration` $= T_d / Y_d$ |
| $C_d$ | Compounding period (days) | `compoundingDuration` | `compoundingDuration` $= C_d / Y_d$ |
| $R_d$ | Recurring instalment period (days) | `recurringDuration` (**months**) | `recurringDuration` $= 12 \cdot R_d / Y_d$ |
| $p$ | Principal (FD) | `state.balance` | — |
| $I$ | Installment (RD) | `stateR.balance` | — |
| $R_i$ | Inflation rate (%) | `inflation` | — |

Useful identities:

$$
\frac{r \cdot C_d}{100 \cdot Y_d} = \frac{r \cdot \texttt{compoundingDuration}}{100}
\qquad
\frac{T_d}{C_d} = \frac{\texttt{duration}}{\texttt{compoundingDuration}}
\qquad
\frac{R_d}{C_d} = \frac{\texttt{recurringDuration} / 12}{\texttt{compoundingDuration}}
\qquad
\frac{Y_d}{T_d} = \frac{1}{\texttt{duration}}
$$

---

## 3. Fixed Deposit (FD)

### Formula

$$
A = p \left( 1 + \frac{r \cdot C_d}{100 \cdot Y_d} \right)^{\frac{T_d}{C_d}}
$$

| Symbol | Meaning |
| :--- | :--- |
| $A$ | Maturity amount |
| $p$ | Principal deposited |
| $r$ | Annual interest rate (%) |
| $C_d$ | Compounding period in days |
| $Y_d$ | Days in a year |
| $T_d$ | Tenure in days |

### In code (years)

$$
A = p \left( 1 + \frac{r \cdot \texttt{compoundingDuration}}{100} \right)^{\frac{\texttt{duration}}{\texttt{compoundingDuration}}}
$$

**Worked example:** ₹1,00,000 at 7% compounded quarterly (`compoundingDuration = 0.25`)
for 1 year:

$$
A = 100000 \times (1 + 0.0175)^{4} \approx 1{,}07{,}186
$$

---

## 4. Recurring Deposit (RD)

### Formula

$$
\text{Value} = \frac{Y_d}{T_d} \cdot I \cdot \frac{\left[ 1 - \left(1 + \frac{C_d \cdot r}{100 \cdot Y_d}\right)^{\frac{T_d}{C_d}} \right] \left(1 + \frac{C_d \cdot r}{100 \cdot Y_d}\right)^{\frac{R_d}{C_d}}}{1 - \left(1 + \frac{C_d \cdot r}{100 \cdot Y_d}\right)^{\frac{R_d}{C_d}}}
$$

The derivation is in [`recurring-deposit-proof.tex`](recurring-deposit-proof.tex).

| Symbol | Meaning |
| :--- | :--- |
| $I$ | Instalment deposited at the end of every period $R_d$ |
| $r$ | Annual interest rate (%) |
| $Y_d$ | Days in a year |
| $R_d$ | Days between instalments |
| $C_d$ | Compounding period in days |
| $T_d$ | Tenure in days |

### In code (years)

With $R$ = `recurringDuration / 12`, $C$ = `compoundingDuration`, $T$ = `duration`:

$$
\text{Value} = \frac{1}{T} \cdot I \cdot \frac{\left[ 1 - \left(1 + \frac{r \cdot C}{100}\right)^{\frac{T}{C}} \right] \left(1 + \frac{r \cdot C}{100}\right)^{\frac{R}{C}}}{1 - \left(1 + \frac{r \cdot C}{100}\right)^{\frac{R}{C}}}
$$

---

## 5. Inflation adjustment (value at the end of $n$ years)

### Formula

$$
A(n) = \frac{A}{1 + \frac{n \cdot R_i}{100}}
$$

| Symbol | Meaning |
| :--- | :--- |
| $A(n)$ | Value of $A$ in today's money after $n$ years |
| $A$ | Nominal amount |
| $n$ | Number of years |
| $R_i$ | Annual inflation (discount) rate (%) |

This is **simple** (not compound) discounting.

### In code

`_finalBalance` applies the discount with $n = \texttt{duration} \times \texttt{count}$,
where $R_i$ is `self.inflation`, fetched live by `get_india_inflation` from the
World Bank CPI indicator `FP.CPI.TOTL.ZG` (latest non-null year).

---

## 6. How the formulas drive the search

The agent treats deposit planning as a **state → action → state** search.

- **State** (`state` / `stateR`): `balance` and `time` (a `date`).
- **Action**: a deposit scheme, plus `count` = how many times it is renewed back-to-back.
- **Goal** (`sg`): a target `balance` by a target `time`.

### 6.1 Transition — `_finalBalance(s, deposit)`

1. The number of whole renewals that fit before the goal date:

$$
\texttt{count} = \max\left(1,\ \left\lfloor \frac{(\texttt{sg.time} - \texttt{s.time})_{\text{days}}}{365 \cdot \texttt{duration}} \right\rfloor \right)
$$

2. The new balance, for a fixed deposit:

$$
\texttt{balance}' = \frac{\texttt{balance}}{1 + \frac{\texttt{duration}\cdot\texttt{count}\cdot R_i}{100}} \cdot \left(1 + \frac{r \cdot C}{100}\right)^{\frac{T}{C}\cdot\texttt{count}}
$$

   that is, the FD formula (§3) compounded over `count` renewals, then discounted
   by inflation (§5) over the same span. For a recurring deposit, the RD growth
   factor (§4) takes the place of the FD factor.

3. The new time: `s.time + timedelta(days = duration × count × 365)`.

### 6.2 Goal test — `_reached(s, sg)`

| Condition | Result |
| :--- | :--- |
| `s.time <= sg.time` and `s.balance < sg.balance` | `GOAL_NOT_YET_REACHED` |
| `s.time > sg.time` | `GOAL_NOT_REACHABLE` |

### 6.3 Ranking — `sortBase(deposit)`

Before searching, the deposits are sorted in descending order by their growth
factor over the whole horizon (the FD or RD factor raised to the number of
renewals that fit between `s0` and `sg`). This makes the depth-first search try
the most profitable schemes first.

### 6.4 Search — `GoalSearch`

- `BruteForce(s)`: depth-first search. It applies each deposit in ranked order and
  returns the first sequence that reaches the goal. The path is stored in
  `pathList` as `((deposit, count), nextState)` tuples.
- `BestSearch(s)`: calls `BruteForce`. If the goal cannot be reached, it falls back
  to the single deposit with the highest resulting balance that still ends before
  the goal date.
- The tools return two lists: `actionList` (`(deposit, count)` pairs) and
  `stateList` (states after each step).

---

## 7. Known discrepancies between `.tex` and code

Check these before changing any formula:

1. **RD $\frac{Y_d}{T_d}$ factor.** `sortBase` and `_finalBalance` in
   `OptimalActionRecurringDeposit` compute the growth factor `w` without the
   leading $\frac{Y_d}{T_d}$ (`1 / duration`) of the `.tex` formula. Otherwise `w`
   matches §4 exactly. `_finalBalance` then multiplies `w` by `count`.
2. **Year length.** The code always uses 365 days, so leap years are ignored.
3. **Inflation is simple discounting**, which matches the `.tex`. Over long
   horizons it understates inflation compared with compound discounting
   $A / (1 + R_i/100)^n$.

---

## 8. Changing or adding a formula

1. Update `financial-formulas.tex` so the documentation stays the source of truth.
2. Change the growth factor in **both** `sortBase` and `_finalBalance` of the
   relevant class. Ranking and transition must use the same formula, or the search
   order will not match the outcome.
3. For a new deposit type, add a Pydantic model and a class with `sortBase`,
   `_finalBalance` and `_reached`. Wrap it in an `@tool` as the existing tools do,
   and register it in `OptimalBankDepositFinderAgent.py`.
4. Check the result against a hand calculation (like §3's worked example) before
   running the full agent: `uv run python source/OptimalBankDepositFinderAgent.py`.

---

## 9. Why the tools use `assert` to catch LLM mistakes

The deposit tools are called by an LLM, which fills in the arguments
(`interestRate`, `duration`, `compoundingDuration`, ...) from the scheme text it
retrieved. The Pydantic models only check the **type** (a `float` is a `float`).
They do not check that the value is **sensible**. The LLM can still extract
`0`, a negative number, or a value in the wrong unit (months instead of years,
or `0.0` because a field was missing from the document).

Left unchecked, such a value does not usually fail loudly:

- A zero or negative `duration` or `compoundingDuration` raises a bare
  `ZeroDivisionError` deep inside the formula, with no hint of which scheme or
  field was wrong.
- A zero `interestRate` makes `qw1` in the recurring-deposit formula zero, which
  divides by zero.
- Some bad values do not crash at all. A negative rate silently produces a
  *shrinking* balance, and the search happily ranks that scheme and returns a
  wrong answer that looks plausible.

An `assert` at the top of the function turns each of these into an immediate,
descriptive error that names the field, the bad value and the scheme. This is a
cheap, local check that stops bad input before it reaches the maths, and it makes
a wrong LLM extraction easy to diagnose in test runs and traces.

Note that `ToolsNode` in `OptimalBankDepositFinderAgent.py` does not catch
exceptions from `invoke_tool`, so a failed assertion currently stops the run
rather than being fed back to the LLM. To let the agent self-correct, catch
`AssertionError` in `ToolsNode` and return `str(e)` as the `ToolMessage`
content.

### Example: `_finalBalance` in `StateActionState.py`

Both `fixedDeposit._finalBalance` and `recurringDeposit._finalBalance` start with
the same three checks:

```python
def _finalBalance(self, s, deposit):
    assert deposit.interestRate > 0, (
        f"interestRate must be positive, got {deposit.interestRate} "
        f"for {deposit.bank_name} {deposit.scheme_name}")
    assert deposit.duration > 0, (
        f"duration must be positive, got {deposit.duration} "
        f"for {deposit.bank_name} {deposit.scheme_name}")
    assert deposit.compoundingDuration > 0, (
        f"compoundingDuration must be positive, got "
        f"{deposit.compoundingDuration} "
        f"for {deposit.bank_name} {deposit.scheme_name}")
    count = math.floor((self.sg.time - s.time).days / (365 * deposit.duration))
    ...
```

Each assertion guards a specific later operation:

| Assertion | What it protects |
|---|---|
| `interestRate > 0` | In the RD version, `qw1 = ar**exp1 - 1` is zero for a zero rate, and `w = qw3 * qw2 / qw1` divides by zero. A negative rate would shrink the balance. |
| `duration > 0` | `count` divides by `365 * deposit.duration`. |
| `compoundingDuration > 0` | `exp1` and `exp2` divide by `compoundingDuration`. |

Without the first assertion, an LLM that extracted `interestRate = 0` for an RD
would produce `ZeroDivisionError: float division by zero`, which says nothing
about the cause. With it, the error reads
`interestRate must be positive, got 0.0 for <bank> <scheme>`, which points
directly at the bad argument.

### Guidelines

- **Put the assertion where the value is first used**, and name the bank and
  scheme in the message so the LLM knows which call was wrong.
- **State the rule and the offending value** (`must be positive, got ...`).
- **Assert on LLM-supplied inputs only.** Do not assert on values the code
  itself computed. A failure there is a bug in our code and should surface as
  one.
- **Do not run Python with `-O`.** It strips `assert` statements, and the guards
  silently disappear. If the tools must run under `-O`, replace these with
  explicit `raise ValueError(...)`.
- When you add a new deposit type (§8), add the same guards for every input that
  appears as a divisor, an exponent base or a rate.

## 10. Adjusting the LangGraph recursion limit

Every compiled graph is built with a recursion limit of 50:

```python
app = workflow.compile().with_config({"recursion_limit": 50})
```

This is set in `DatabaseCreator.py`, `FinancialGeneralInformationChatBot.py`,
`OptimalBankDepositFinderAgent.py` and `TestDatabaseUpdateAgent.py`. The limit
caps the number of super-steps (node executions) in one run. Each LLM call,
tool call and guardrail check counts as a step, so a long tool-calling loop can
hit it.

### When to adjust it

If a run fails with `GraphRecursionError: Recursion limit of 50 reached
without hitting a stop condition`, first check that the agent is not looping
(for example, repeatedly calling a tool that keeps returning an error). Raise
the limit only if the run is making real progress and just needs more steps.

### Scale the limit with the time span of the goal

As the time span of the goal grows, raise the recursion limit as well. A longer
horizon fits more renewals and more deposit combinations (§6), so the search
tree gets bigger, and the agent may need more tool-calling rounds to plan,
compare and explain the result. Treat 50 as the default for short and
medium-term goals, and increase it in steps for long-horizon goals.

Note that `GoalSearch.BestSearch` is iterative and runs inside a single tool
call, so the search itself counts as one graph step. The limit is consumed by
the agent's LLM, tool and guardrail rounds around it, not by the size of the
search tree directly. Verify with a long-horizon goal before settling on a
value.

### How to adjust it

- **For all runs of a graph:** change the `50` in the `with_config` call of that
  graph's `compile()` line.
- **For a single run:** pass it in the config and it overrides the default:

  ```python
  graph.invoke({"messages": [...]}, config={"recursion_limit": 100})
  ```

### Guidelines

- Raise it in small steps (for example 50 → 75 → 100). A very large value
  hides infinite loops and burns LLM tokens before the error appears.
- Keep the value the same across the four graphs unless one has a clear need
  for more, and update this section if you change the default.
