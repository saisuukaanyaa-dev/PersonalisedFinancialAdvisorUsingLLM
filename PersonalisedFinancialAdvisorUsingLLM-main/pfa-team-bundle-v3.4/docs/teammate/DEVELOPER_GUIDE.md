# Developer's Guide — Deposit Formulas and the Optimal Deposit Search

This guide explains the financial formulas used by the Optimal Bank Deposit Finder
and shows where each one is implemented. The formulas come from
[`financial-formulas.tex`](financial-formulas.tex). For run commands (database
creation, LangGraph Studio, MCP server), see [`readme.md`](readme.md).

---

## 1. Where the formulas live

| Concept | File | Symbol |
| :--- | :--- | :--- |
| Fixed deposit maturity + inflation | [`StateActionState.py`](StateActionState.py) | `OptimalActionFixedDeposit._finalBalance` |
| Fixed deposit ranking | [`StateActionState.py`](StateActionState.py) | `OptimalActionFixedDeposit.sortBase` |
| Recurring deposit maturity + inflation | [`StateActionState.py`](StateActionState.py) | `OptimalActionRecurringDeposit._finalBalance` |
| Recurring deposit ranking | [`StateActionState.py`](StateActionState.py) | `OptimalActionRecurringDeposit.sortBase` |
| Goal search over deposits | [`GoalSearch.py`](GoalSearch.py) | `GoalSearch.BruteForce`, `GoalSearch.BestSearch` |
| Inflation rate source | [`OptimalBankDepositFinderAgent.py`](OptimalBankDepositFinderAgent.py) | `get_india_inflation` (World Bank CPI API) |
| LLM-facing tools | [`StateActionState.py`](StateActionState.py) | `OptimalActionFixedDepositTool`, `OptimalActionRecurringDepositTool` |

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
| $C_d$ (also $c_d$) | Compounding period (days) | `compoundingDuration` | `compoundingDuration` $= C_d / Y_d$ |
| $R_d$ | Recurring instalment period (days) | `recurringDuration` | `recurringDuration` $= R_d / Y_d$ |
| $p$ | Principal (FD) | `state.balance` | — |
| $I$ | Instalment (RD) | `stateR.balance` | — |
| $R_i$ | Inflation rate (%) | `inflation` | — |

Useful identities:

$$
\frac{r \cdot C_d}{100 \cdot Y_d} = \frac{r \cdot \texttt{compoundingDuration}}{100}
\qquad
\frac{T_d}{C_d} = \frac{\texttt{duration}}{\texttt{compoundingDuration}}
\qquad
\frac{Y_d}{R_d} = \frac{1}{\texttt{recurringDuration}}
$$

> **Note:** the `.tex` uses both $C_d$ and $c_d$ in the recurring-deposit formula.
> Both mean the compounding period.

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
\text{Amount} = I \left[ \left( \frac{Y_d}{R_d} + \frac{Y_d}{C_d} \right) \left( \frac{100}{r} - 0.5 \right) + \frac{C_d}{R_d} + 1 \right] \left[ \left( 1 + \frac{r \cdot C_d}{100 \cdot Y_d} \right)^{\frac{T_d}{C_d}} - 1 \right]
$$

| Symbol | Meaning |
| :--- | :--- |
| $I$ | Recurring instalment |
| $r$ | Annual interest rate (%) |
| $Y_d$ | Days in a year |
| $R_d$ | Days between instalments |
| $C_d$ | Compounding period in days |
| $T_d$ | Tenure in days |

### In code (years)

With $R$ = `recurringDuration`, $C$ = `compoundingDuration`, $T$ = `duration`:

$$
\text{Amount} = I \left[ \left( \frac{1}{R} + \frac{1}{C} \right) \left( \frac{100}{r} - 0.5 \right) + \frac{C}{R} + 1 \right] \left[ \left( 1 + \frac{r \cdot C}{100} \right)^{\frac{T}{C}} - 1 \right]
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
| `s.time <= sg.time` and `s.balance >= sg.balance` | `GOAL_REACHED` |
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

1. **RD $\frac{C_d}{R_d}$ term.** Both `sortBase` and `_finalBalance` in
   `OptimalActionRecurringDeposit` compute
   `compoundingDuration / compoundingDuration` (always `1`). The `.tex` specifies
   $C_d / R_d$, which in code would be `compoundingDuration / recurringDuration`.
2. **RD bracket grouping in `_finalBalance`.** In the `.tex`, the first bracket
   multiplies the second. In `_finalBalance`, the `(... - 1)` growth bracket
   multiplies only the `(C/C + 1)` part, and `** count` applies only to that
   product. `sortBase` groups the terms as the `.tex` does.
3. **Year length.** The code always uses 365 days, so leap years are ignored.
4. **Inflation is simple discounting**, which matches the `.tex`. Over long
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
   running the full agent: `python OptimalBankDepositFinderAgent.py`.
