# Several goals, and a smaller goal in between (v1.7)

Mentor feedback: *"Use more than one goal, and show how we calculate it when a smaller goal comes up in between."*

All of this is computed in code (`app/pfa/engine/goals.py`). The AI only explains the numbers; it never calculates them.

## 1. Goals

- The **main goal** is the one from v1.0: `profile["goal"]`. Its projection still opens the report.
- **Up to 3 more goals:** `profile["goals_extra"]`, each with a type, an optional name, an amount, a date and a priority (**Must-have** or **Nice-to-have**).
- Goals can be added in three places:
  - step 1 of the form;
  - the report's **What if a new goal comes up?** calculator, then **Add it to my plan**;
  - the chat ("I also need 6L for a car in 2028"), always confirmed with Yes / No.
- Goals are removed with **Remove** in the goals table, or by asking Arth.

## 2. How the money is shared

| Step | Rule |
|---|---|
| Order | Must-have before Nice-to-have, then the nearest date first. Money needed sooner has the least time to grow, so it is secured first. |
| Risk per goal | Each goal gets its own risk level and mix from its own horizon, with the same rulebook as the main goal (`allocation.goal_mix`): under 3 years → Low (85% fixed income, no equity); under 5 years → at most Medium; otherwise the user's stated risk. Expected return = the mix's blend of 11% equity, 7% fixed income, 8% gold, 4% cash. |
| Savings you already have | Set aside in that order. Each goal gets what it needs **today**: `target ÷ (1 + r)^months`, at its own monthly rate r, until the savings run out. Anything left stays with the main goal. |
| SIP each goal needs | `PMT = (target − set_aside × (1+r)^n) ÷ (((1+r)^n − 1) ÷ r)`, or 0 if the savings alone get there. |
| Today's pace | Today's SIPs are shared in the same order (anything beyond the needs stays with the main goal). This gives "projected at today's pace". |
| The plan | The money free each month (after essentials, EMIs and the emergency top-up) is shared in the same order, in round ₹100s. A SIP is rounded up when the money allows, and down when it doesn't. Whatever no goal needs is "left over". |
| Status | **On track** (today's pace already reaches it) · **Funded by the plan** · **Partly funded** · **Not funded yet**. The last two show the date the goal becomes reachable at the plan's SIP. |
| Monthly plan | Every goal's SIP is split by its own mix and added up by bucket. Direct stocks apply only to the main goal's equity share. The bank deposit planner still uses the main goal's fixed-income part. |
| Timeline | Month by month, each goal's pot grows at its own rate with its plan SIP and pays out on its date. The chart shows the total, with a drop at each payout. |

With one goal this gives the same numbers as v1.6 (unit-tested), apart from rounding the plan SIP up to ₹100 when there's room.

## 3. A smaller goal comes up in between: three ways to pay

`new_goal_impact()` runs the plan without and with the new goal and compares them.

| Option | What it calculates |
|---|---|
| **A. Save for it separately** | **True monthly cost = total SIP all goals need afterwards − before.** This is more than the new goal's own SIP: the savings set aside for it leave the other goals, so their SIPs go up. Shows what every other goal gets and projects afterwards, and whether the spare money covers it. |
| **B. Use the main goal's savings** | No new SIP. The amount is taken from the main goal's pot on the new goal's date, so the main goal loses it **plus its growth**: `loss = amount × (1 + r_main)^(n_main − n_new)`. The make-up is `loss ÷ (((1+r)^n − 1) ÷ r)` per month over the main goal's horizon, or the extra months until the main goal still reaches its target. The money stays in the main goal's mix until then, so a market-risk note is shown when that mix holds equity. Not offered when the new goal comes after the main goal. |
| **C. Wait** | When the spare money alone (what the plan leaves over each month) reaches the new goal, at the mix for that horizon. Nothing else changes. |

**Recommendation rules:**
1. If A fits in the spare money with no other goal losing out → **A**.
2. Otherwise, if waiting costs at most 12 months → **C**.
3. Otherwise, if B's make-up fits in the spare money → **B**.
4. Otherwise **A**, with the trade-off shown.

## 4. Worked example (made-up profile from the tests)

Priya: in-hand ₹1.22L a month, essentials ₹45K, car-loan EMI ₹11K, ₹12.9L invested, ₹18K SIPs today, High risk. Main goal: **home, ₹80L in 8 years** (High risk, 9.78% a year). After the emergency top-up, **₹56,000** a month is free to invest.

- **One goal:** the home needs **₹35,839** a month. The plan gives ₹35,900, and ₹20,100 a month is left over.
- **A ₹6L car in 2 years comes up** (Low risk, 6.75% a year):

| Option | Result |
|---|---|
| A. Save separately | **₹5,24,428** of today's savings is set aside for the car, which then needs ₹0 a month. The home loses those savings, so its SIP rises from ₹35,900 to **₹43,800**. **True cost: ₹7,897 a month.** The spare ₹20,100 covers it, leaving ₹12,200 → **recommended.** |
| B. Use the home's savings | Taking ₹6L out in 2 years costs the home ₹6L × (1.00815)^72 = **₹10.76L** by its date. Making it up needs **₹7,436 a month**, or a **12-month** delay. Cheaper per month than A, but the car money sits in the home's 70%-equity mix for 2 years. |
| C. Wait | ₹20,100 a month alone reaches ₹6L in **28 months**, 4 months later than wanted. |

The lesson for the mentors: a "free" near goal (₹0 a month) still has a cost, because it moves today's savings away from the long goal, and the long goal loses the growth on them.

## 5. Where it lives

| File | What |
|---|---|
| `app/pfa/engine/goals.py` | `plan_goals`, `timeline`, `new_goal_impact` (pure functions) |
| `app/pfa/engine/allocation.py` | `goal_mix`: one risk rulebook for every goal |
| `app/pfa/engine/projection.py` | Main goal uses its share; monthly plan adds all goals |
| `app/pfa/profile.py` | Form rows → `goals_extra`; checks; chat `add_goal` / `remove_goal`; `new_goal_from` |
| `app/pfa/main.py` | `POST /api/goals/impact` · `/api/goals/add` · `/api/goals/remove` |
| `app/pfa/templates/_report_main.html`, `_goal_impact.html`, `static/goals.js` | Report section and calculator |
| `app/pfa/ai/chat.py` | Arth: add / remove goals; the preview shows code-computed costs only |
| `tests/test_goals.py` | 12 tests |
