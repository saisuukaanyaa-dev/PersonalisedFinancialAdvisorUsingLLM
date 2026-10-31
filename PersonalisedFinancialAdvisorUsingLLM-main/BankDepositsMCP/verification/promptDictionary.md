# Prompt Dictionary — Personalised Financial Advisor Using LLM

## Contents

| Part | Section | IDs | Count |
|---|---|---|---|
| A | [Data Preparation Prompts](#part-a-data-preparation-prompts) | DP-01 – DP-04 | 4 |
| B | [Test Prompts — General Public (age < 60)](#part-b-test-prompts--general-public-age--60) | GP-01 – GP-09 | 9 |
| C | [Test Prompts — Senior Citizen (age 60–79)](#part-c-test-prompts--senior-citizen-age-6079) | SC-01 – SC-10 | 10 |
| D | [Test Prompts — Super Senior Citizen (age 80+)](#part-d-test-prompts--super-senior-citizen-age-80) | SSC-01 – SSC-09 | 9 |
| E | [Test Matrix](#part-e-test-matrix) | all 28 test prompts | — |

**ID scheme:** every prompt has a unique ID. The scenario number (S1–S9) is the same across the three age groups, so GP-03, SC-03 and SSC-03 test the same scenario for different ages.

### Scenarios

| Scenario | Description |
|---|---|
| S1 | Fixed deposit (lump sum), target goal, inflation 0, FD tool named |
| S2 | Recurring deposit, target goal, 10 yrs, inflation 0, RD-only, RD tool named |
| S3 | Same as S2 with age + 1 (age-boundary check) |
| S4 | Recurring deposit, 9 yrs, inflation 0, RD tool named (no "RD-only" line) |
| S5 | Recurring deposit, 8 yrs, inflation 0, no tool named |
| S6 | Monthly installment, target goal, no inflation, no product type, no tool named |
| S7 | Lump sum + monthly installment, target goal, no tool named |
| S8 | Lump sum + monthly installment, time horizon only (no target amount) |
| S9 | Same as S8 with a longer time horizon |

---

## Part A. Data Preparation Prompts

### DP-01 — Split interest-rate / duration ranges into separate rows

```text
For the rows having:
interest_rate_general : (r"^-?\d+(\.\d+)?$") - (r"^-?\d+(\.\d+)?$")
interest_rate_senior : (r"^-?\d+(\.\d+)?$") - (r"^-?\d+(\.\d+)?$")
duration_months_min (r"\d") months
duration_months_max (r"\d") months

Add one more column duration_months

Add a 2 new rows:
if
1.
interest_rate_general : \1
interest_rate_senior : \3
duration_months \5 months
2.
interest_rate_general : \2
interest_rate_senior : \4
duration_months \6 months

Add one row:
if \1 and \2 are the same

and remove the original rows
```

### DP-02 — Collapse equal min/max duration into `duration_months`

```text
For the rows having:
duration_months_min (r"\d") months and
duration_months_max (r"\d") months

if \1 and \2 are equal,
duration_months_min NA
duration_months_max NA
duration_months \1 months
```

### DP-03 — Add `installment_time_period` for recurring schemes

```text
Add a new column called installment_time_period.
For the rows having:
scheme_name containing the word "Recurring"
extract the installment time period in months from the column maximum_deposit_amount:
example :
if the text in the maximum_deposit_amount contains the patterns "/month" or "per month" or "monthly", then installment_time_period = 1 month
for the rest of the empty cells of the column installment_time_period should be made NA
```

### DP-04 — Strip "% p.a." from interest-rate columns

```text
make the columns having  "(^-?\d+(\.\d+)?$)% p.a." in interest_rate_general or interest_rate_senior, replace with \1
```

---

## Part B. Test Prompts — General Public (age < 60)

### GP-01 — S1 · Age 35 · Fixed deposit · `OptimalActionFixedDepositTool`

```text
My age is 35 years. My present bank balance is 100000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal deposit actions to meet the goal.
Please consider only fixed deposit products.
please use the tool 'OptimalActionFixedDepositTool'
```

### GP-02 — S2 · Age 40 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 40 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### GP-03 — S3 · Age 41 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 41 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### GP-04 — S4 · Age 42 · Recurring deposit, 9 yrs · `OptimalActionRecurringDepositTool`

```text
My age is 42 years. My installment amount is 1000 rs and it should be 150000 rs after 9 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
please use the tool 'OptimalActionRecurringDepositTool'
```

### GP-05 — S5 · Age 43 · Recurring deposit, 8 yrs · No tool named

```text
My age is 43 years. My installment amount is 1000 rs and it should be 150000 rs after 8 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
```

### GP-06 — S6 · Age 44 · Monthly installment, goal · No tool named

```text
My age is 44 years. My installment amount is 1000 rs per month and it should be 150000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### GP-07 — S7 · Age 45 · Balance + monthly installment, goal · No tool named

```text
My age is 45 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month and it should be 300000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### GP-08 — S8 · Age 48 · Balance + monthly installment, 13-yr horizon · No tool named

```text
My age is 48 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 13 years from now.
```

### GP-09 — S9 · Age 48 · Balance + monthly installment, 20-yr horizon · No tool named

```text
My age is 48 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 20 years from now.
```

---

## Part C. Test Prompts — Senior Citizen (age 60–79)

### SC-01 — S1 · Age 63 · Fixed deposit · `OptimalActionFixedDepositTool`

```text
My age is 63 years. My present bank balance is 100000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal deposit actions to meet the goal.
Please consider only fixed deposit products.
please use the tool 'OptimalActionFixedDepositTool'
```

### SC-02 — S2 · Age 64 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 64 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SC-03 — S3 · Age 65 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 65 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SC-04 — S4 · Age 66 · Recurring deposit, 9 yrs · `OptimalActionRecurringDepositTool`

```text
My age is 66 years. My installment amount is 1000 rs and it should be 150000 rs after 9 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SC-05 — S5 · Age 67 · Recurring deposit, 8 yrs · No tool named

```text
My age is 67 years. My installment amount is 1000 rs and it should be 150000 rs after 8 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
```

### SC-06 — S6 · Age 68 · Monthly installment, goal · No tool named

```text
My age is 68 years. My installment amount is 1000 rs per month and it should be 150000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### SC-07 — S7 · Age 69 · Balance + monthly installment, goal · No tool named

```text
My age is 69 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month and it should be 300000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### SC-08 — S8 · Age 70 · Balance + monthly installment, 8-yr horizon · No tool named

```text
My age is 70 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 8 years from now.
```

### SC-09 — S9 · Age 70 · Balance + monthly installment, 14-yr horizon · No tool named

```text
My age is 70 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 14 years from now.
```

### SC-10 — S9 · Age 65 · Balance + monthly installment, 20-yr horizon · No tool named

```text
My age is 65 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 20 years from now.
```

---

## Part D. Test Prompts — Super Senior Citizen (age 80+)

### SSC-01 — S1 · Age 81 · Fixed deposit · `OptimalActionFixedDepositTool`

```text
My age is 81 years. My present bank balance is 100000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal deposit actions to meet the goal.
Please consider only fixed deposit products.
please use the tool 'OptimalActionFixedDepositTool'
```

### SSC-02 — S2 · Age 82 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 82 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SSC-03 — S3 · Age 83 · Recurring deposit · `OptimalActionRecurringDepositTool`

```text
My age is 83 years. My installment amount is 1000 rs and it should be 150000 rs after 10 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
Please consider only recurring deposit products.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SSC-04 — S4 · Age 84 · Recurring deposit, 9 yrs · `OptimalActionRecurringDepositTool`

```text
My age is 84 years. My installment amount is 1000 rs and it should be 150000 rs after 9 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
please use the tool 'OptimalActionRecurringDepositTool'
```

### SSC-05 — S5 · Age 85 · Recurring deposit, 8 yrs · No tool named

```text
My age is 85 years. My installment amount is 1000 rs and it should be 150000 rs after 8 years.
Please consider the inflation as 0.
Please give the optimal recurring deposit actions to meet the goal.
```

### SSC-06 — S6 · Age 86 · Monthly installment, goal · No tool named

```text
My age is 86 years. My installment amount is 1000 rs per month and it should be 150000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### SSC-07 — S7 · Age 87 · Balance + monthly installment, goal · No tool named

```text
My age is 87 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month and it should be 300000 rs after 8 years.
Please give the optimal deposit actions to meet the goal.
```

### SSC-08 — S8 · Age 88 · Balance + monthly installment, 10-yr horizon · No tool named

```text
My age is 88 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 10 years from now.
```

### SSC-09 — S9 · Age 85 · Balance + monthly installment, 15-yr horizon · No tool named

```text
My age is 85 years. My bank balance is 100000 rs. My installment amount is 1000 rs per month.
Please give the optimal deposit actions to for a period of 15 years from now.
```

---

## Part E. Test Matrix

**Legend:** Bal = present bank balance (rs) · Inst = installment (rs) · Target = goal amount (rs) · Infl 0 = "inflation as 0" stated · FD = `OptimalActionFixedDepositTool` · RD = `OptimalActionRecurringDepositTool` · – = not given/not named · Old # = number in the original file

| ID | Old # | Scen | Age | Bal | Inst | Target | Yrs | Infl 0 | Product | Tool |
|---|---|---|---|---|---|---|---|---|---|---|
| GP-01 | 4 | S1 | 35 | 100000 | – | 150000 | 10 | Yes | FD only | FD |
| GP-02 | 5 | S2 | 40 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| GP-03 | 6 | S3 | 41 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| GP-04 | 7 | S4 | 42 | – | 1000 | 150000 | 9 | Yes | RD | RD |
| GP-05 | 8 | S5 | 43 | – | 1000 | 150000 | 8 | Yes | RD | – |
| GP-06 | 9 | S6 | 44 | – | 1000/month | 150000 | 8 | No | Any | – |
| GP-07 | 10 | S7 | 45 | 100000 | 1000/month | 300000 | 8 | No | Any | – |
| GP-08 | 11 | S8 | 48 | 100000 | 1000/month | – | 13 | No | Any | – |
| GP-09 | 12 | S9 | 48 | 100000 | 1000/month | – | 20 | No | Any | – |
| SC-01 | 4 | S1 | 63 | 100000 | – | 150000 | 10 | Yes | FD only | FD |
| SC-02 | 5 | S2 | 64 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| SC-03 | 6 | S3 | 65 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| SC-04 | 7 | S4 | 66 | – | 1000 | 150000 | 9 | Yes | RD | RD |
| SC-05 | 8 | S5 | 67 | – | 1000 | 150000 | 8 | Yes | RD | – |
| SC-06 | 9 | S6 | 68 | – | 1000/month | 150000 | 8 | No | Any | – |
| SC-07 | 10 | S7 | 69 | 100000 | 1000/month | 300000 | 8 | No | Any | – |
| SC-08 | 11 | S8 | 70 | 100000 | 1000/month | – | 8 | No | Any | – |
| SC-09 | 12 | S9 | 70 | 100000 | 1000/month | – | 14 | No | Any | – |
| SC-10 | 12\* | S9 | 65 | 100000 | 1000/month | – | 20 | No | Any | – |
| SSC-01 | 4 | S1 | 81 | 100000 | – | 150000 | 10 | Yes | FD only | FD |
| SSC-02 | 5 | S2 | 82 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| SSC-03 | 6 | S3 | 83 | – | 1000 | 150000 | 10 | Yes | RD only | RD |
| SSC-04 | 7 | S4 | 84 | – | 1000 | 150000 | 9 | Yes | RD | RD |
| SSC-05 | 8 | S5 | 85 | – | 1000 | 150000 | 8 | Yes | RD | – |
| SSC-06 | 9 | S6 | 86 | – | 1000/month | 150000 | 8 | No | Any | – |
| SSC-07 | 10 | S7 | 87 | 100000 | 1000/month | 300000 | 8 | No | Any | – |
| SSC-08 | 11 | S8 | 88 | 100000 | 1000/month | – | 10 | No | Any | – |
| SSC-09 | 12 | S9 | 85 | 100000 | 1000/month | – | 15 | No | Any | – |

\* "test prompt 12" appeared twice in the Senior Citizen section of the original file; the second occurrence is now SC-10.

### Numbering changes from the original file

- "prompt3" was used twice in the data-preparation section; the second one is now **DP-04**.
- Test prompts 4–12 were repeated in each age section; they now carry unique group-prefixed IDs (**GP / SC / SSC**) so results can be logged without ambiguity.
- Prompt text itself is unchanged, so test inputs stay reproducible.
