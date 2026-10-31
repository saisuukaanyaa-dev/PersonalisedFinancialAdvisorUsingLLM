# Personal Finance Advisor v3: conversational intake and colourful report

> Historical design notes (v3 to v3.2). In v3.4 the n8n Form pages were replaced by the app page at `/webhook/pfa`; see [V34_CHANGES.md](V34_CHANGES.md).

**Workflow:** `pfa_v3_23092026.json` (built from `pfa_v2_22092026.json`; nothing in the project root was changed)
**Runtime:** n8n `2.36.8`, the same Postgres, market-analyzer and credentials as v2
**Samples:** `sample_report.html` (user with loans and a clarification step), `sample_report_debtfree.html` (debt-free user with a 32-year retirement goal) and `sample_report_overspend.html` (monthly plans that exceed pay, kept after the warning). All three use mock LLM prose; every number and chart comes from the real Code nodes.

---

## What changed from v2

| Request | v3 |
|---|---|
| Ask for name, email, age, current CTC, goal and target date | Email is on the first page. Name, age, **annual CTC**, goal (dropdown plus optional details), target amount and target date are on chat step 1. |
| Collect debt, insurance, emergency fund, gold, stocks and MFs with a human touch | Four more short chat steps. Each opens with an advisor bubble that **reacts to the previous answers**, for example "Essentials take 37% of your pay, leaving about ₹77K a month" or "Your credit card dues at 42% are expensive money". |
| First form: *new user* or *update profile* | The radio button is now **I'm new here / Update my existing profile**. |
| Colourful charts in the final output | 8 charts are drawn as inline SVG/CSS (list below). |
| Don't edit existing files | Everything is in `pfa_v3_23092026/`. The node IDs, webhook IDs and form path (`personal-finance-advisor-v3`) are new, so v2 and v3 can run side by side. |

## The conversation

```
Intake Form ── "I'm new here / Update my existing profile" + email
  → Lookup User Profile → Evaluate Journey        (email found ⇒ pre-fill every page)
  → Chat 1 · About You & Goal     name, age, currency, annual CTC, goal, target amount, target date
  → Read Goal & Income            estimates in-hand pay from CTC
  → Chat 2 · Cash Flow            "A CTC of ₹18L usually lands around ₹1.22L a month… sound right?"
  → Read Cash Flow                in-hand (pre-filled with the estimate) + essential expenses
  → Chat 3 · Safety Net           emergency fund, term cover + premium, health cover + premium
  → Read Safety Net
  → Chat 4 · Loan Types           tick: Home / Car / Personal / Education / Credit card / Gold / Other / None
  → Read Loan Types → Any Loans?
        ├─ yes → Chat 4b · Loan Details (only the ticked loans: outstanding, rate, EMI) → Read Loan Details ─┐
        └─ no  ─────────────────────────────────────────────────────────────────────────────────────────────┤
  → Prepare Investments Chat → Chat 5 · Investments   MF, stocks, gold, FD/RD, PPF/EPF/VPF, cash, other
  → Build Financial Profile  → Check Profile Completeness → (only if something was unreadable) Ask / Apply
  → …the v2 pipeline, unchanged: storage, agents, projection, report
```

**New user vs update.**
- Update users see every page pre-filled. If they change nothing and click through, the saved profile comes back unchanged. The harness checks this.
- The email lookup decides the journey. If someone ticks "new" but their email is already saved, they get the pre-filled update flow with a "looks like we've met before" note. If someone ticks "update" but no profile is found, they are set up as a new user.
- Profiles saved by v2 also pre-fill. Their free-text loans and savings are mapped to the new loan types and investment buckets.

**CTC to in-hand estimate** (INR, FY 2026-27 new regime). The assumptions are basic pay = 40% of CTC, 12% PF from both employer and employee, 4.81% gratuity, a ₹75K standard deduction, the §87A rebate up to ₹12L taxable income, surcharge, 4% cess and ₹2,500 professional tax. The estimate is only a pre-filled default: the user confirms or corrects it, and the report labels it "(estimated)" if it was left unchanged. For non-INR currencies the default is a rough 72% of CTC.

**Unreadable input.** If a user types something like "about fifty k", the node records exactly which field it came from. The clarification page asks only for those fields, in the same chat style, and writes each answer back to the right place.

## The report's charts

1. **Goal progress ring** in the gradient header, coloured by verdict.
2. **Where your monthly pay goes**: a stacked bar of essentials, EMIs, investing and free cash, with a legend showing ₹ and %.
3. **Goal projection line chart**: the corpus at today's SIP vs at the SIP needed to reach the goal, with a dashed target line and year-by-year hover tooltips.
4. **Own vs owe**: assets by class alongside loans. Loans above 12% interest are red.
5. **Allocation donut**: current holdings by asset class.
6. **Now vs suggested bars**: one per asset class (faded bar = now, solid = the adviser's suggestion). The table view is kept underneath.
7. **Safety-net meters**: emergency fund against 6 months, term cover against 10× income, health cover against ₹10L, and EMIs against take-home. Each meter has a ✓ / ! / ✕ badge.
8. **Loan bars** sorted by interest rate, with a "pay first" flag. The equity shortlist also gets mini CAGR bars.

All charts use a colour-blind-checked palette. Every colour also has a text label, and dark mode is supported. There is **no JavaScript and no CDN**, so the report renders inside n8n's sandboxed completion page, works offline, and stores intact in `advice_sessions.report_json.html`. A "Show the numbers behind the charts" section lists the projection as a table.

## Smaller changes carried along

- **Net worth now includes the emergency fund**, which v2 left out.
- `Compute Allocation Metrics` checks **gold before equity**. Before this, "Gold ETF" was counted as equity.
- The snapshot gains `annual_ctc`, `term_cover`, `recommended_term_cover`, `health_cover`, `emergency_fund_target`, `monthly_investing` and a year-by-year `series`. All of them are computed in code. The Recommender prompt now points at the insurance and emergency-fund figures.
- Google Sheets gets new columns (`annual_ctc`, `in_hand_source`, `emergency_fund`, `term_cover`, `health_cover`, `monthly_investing`, `goal_type`). `handlingExtraData: insertInNewColumn` adds them to the header row automatically.
- The chat assistant's prompt points users to "Update my existing profile" when their details change.

## Import and test

1. In n8n, go to **Workflows → Import from file** and choose `pfa_v3_23092026.json`.
2. Open each credential-bearing node once (Postgres, OpenAI, Google Sheets) and confirm the credential is selected. The IDs are the same as v2.
3. Open the **Intake Form** node, then use its test URL or activate the workflow. The production path is `/form/personal-finance-advisor-v3`.
4. No schema change is needed. v3 writes a superset of the v2 profile JSON into the same `users.profile_json` column.

**Verified:** every Code node was run locally in an n8n-style harness for three cases: a new user with loans and one unreadable value, a debt-free user, and an update user who clicks through unchanged. The code tested is the code embedded in this JSON. **Not verified:** a live run inside n8n. The form, LLM and Sheets steps need your credentials, so do one test submission before you share the link.

## Fixes after the first live run

| Reported | Cause | Fix |
|---|---|---|
| "In-hand is ₹1.5L, so how can I invest ₹3L?" | The *FD / RD · monthly deposit* box was saved as `3L`, probably the FD balance typed into the monthly box. Nothing checked that the monthly figures were possible. The chart then took its percentages from the ₹3.35L outflow, not from pay. | `Check Profile Completeness` now adds up essentials, EMIs and planned monthly investing. If the total is more than in-hand pay, it asks the user to check each monthly amount, pre-filled with what they typed. If they keep the figure, the cash-flow chart is still measured against **in-hand pay**: a dashed "in-hand pay" line, percentages of pay, and the excess shown as a red **Shortfall**. |
| "I have no debt, but it shows Debt ₹5L" | "Debt" was the finance-jargon name for the **asset class** (FDs, PPF, EPF, bonds), and ₹5L was the user's FD. | Every chart and table now calls it **Fixed income (FD/PPF)**. The Portfolio, Recommender and Report agents and the report schema are told to do the same. The "Total debt" tile is now **Loans outstanding**. |
| "What is Max Drawdown? Why negative?" | It is the biggest fall from a high to a later low over the 5 years. It is a loss, so the convention is to write it as a negative number. | The column is now **Worst fall (max drawdown)**, shown as ▼ 33.4%. Every column has a sub-caption, and a "How to read this" note explains it with a ₹1,00,000 example. |

Also re-checked by running the reported inputs through the built workflow code. With the monthly FD set to 0: surplus ₹1.15L, free cash ₹1.15L (77% of pay), investing ₹0, fixed income ₹5L (FD), no loans.

## Risk-taking ability (Low / Medium / High)

**Asking the question.** Chat step 5 ends with a gut check: *"You invested ₹1,00,000 and after a bad year it shows ₹80,000. What would you do?"*

- **Low**: I'd sell to stop the loss (FDs, PPF)
- **Medium**: I'd wait for it to recover (mostly mutual funds)
- **High**: I'd invest more while it's cheap (funds + stocks)

The answer is saved as `profile.risk_appetite` and pre-filled when the user updates their profile. Profiles saved before this change default to Medium.

**Turning it into a plan.** The plan is built in code, in `Compute Allocation Metrics`, so every agent works from the same rules.

| | Low | Medium | High |
|---|---|---|---|
| Target mix (equity / fixed income / gold / cash) | 15 / 70 / 10 / 5 | 50 / 35 / 10 / 5 | 70 / 20 / 7 / 3 |
| Equity through | Nifty 50 index fund | Index + large/flexi-cap MFs | Flexi/mid-cap MFs + index |
| Fixed income through | FD / RD, PPF, short-term debt funds | PPF, FD / RD | PPF / short-duration debt funds |
| Direct stocks (share of monthly goal money) | none | up to 10% | up to 25% |
| Stock limits | none | worst fall ≤ ▼35%, swing ≤ 30% | worst fall ≤ ▼35% (▼45% if 10+ yrs), swing ≤ 38% |
| Expected return used in the projection | 7.55% | 8.95% | 9.78% |

- **The chosen risk is capped by the goal date.** Under 3 years always means Low, with no shares at all (85% fixed income). Between 3 and 5 years the most allowed is Medium. When the plan level ends up lower than what the user chose, the report says why.
- **Direct stocks also need a safety net.** They only unlock when all of these are true:
  - the goal is at least 5 years away
  - the emergency fund covers 3 months or more
  - health cover is in place
  - there is no loan above 12% interest
- **Until then, the report shows "Direct stocks · not yet".** It lists exactly what to fix, and the stocks the market screen found are held back.
- **Every stock the AI proposes is checked in code** against the limits above. Stocks must also grow by at least half their yearly swing, with a maximum of 2 per sector. Anything that fails is removed, and the report says which stock and why. The saved report keeps the filtered list.
- **The monthly plan comes out in ₹ per instrument.** The emergency fund is topped up first: it aims for 6 months within about a year, using at most 40% of the money left after essentials and EMIs. The goal amount is then split using the target mix. If the goal needs more than the user can spare, the report says so.

**What the report adds.** A *Your risk profile* card showing what the user chose and what the plan uses. A *Where to put your money each month* chart and table. "Suggested" allocation now always equals the plan's target. The Assumptions line and the stock-sleeve sentence are also built from code, so they can't contradict the charts.

**Samples.** `sample_risk_low.html`, `sample_risk_medium.html` and `sample_risk_high.html` use the inputs from the reported live run, with the equity shortlist from that run as the AI's proposal. The High sample assumes a 4L emergency fund and 5L health cover.

With those inputs:
- **Low and Medium:** no stocks. Your current emergency fund (1.4 months) and missing health cover block them.
- **High, once the safety net is fixed:** keeps MARUTI, EICHERMOT and BEL.
  - HINDALCO is removed: its worst fall of ▼49.9% is past the ▼35% limit.
  - BAJFINANCE is removed: 8.2% growth is too low for 28.3% swings.
- **Medium, once the safety net is fixed:** BEL is also removed, because its 31.4% swing is over the 30% limit.

## v3.2: AI guardrails and MCP

| Added | Where | What it does |
|---|---|---|
| **Goal Text Guardrail** (Guardrails node, jailbreak + topical alignment) | After `Build Financial Profile` | Screens the free text a user types (goal details, name of an "other" investment), which reaches three LLM prompts. **Pass** → `Keep Goal Text`. **Fail** → `Neutralise Goal Text`, which drops the text and keeps only the chosen goal type. |
| **Guardrail LLM** (gpt-5-mini) | Sub-node | Runs the two LLM-based guardrail checks. |
| **Chat Input Guardrail** | Chat Trigger → agent | Blocks jailbreaks, off-topic requests, secret keys, and card / PAN / Aadhaar / passport / voter / bank numbers. **Fail** → `Polite Refusal`. |
| **Chat Output Sanitizer** (Guardrails, sanitize) | Agent → `Chat Reply` | Redacts ID, card and phone numbers and keys from the agent's answer. |
| **PFA MCP Server** (MCP Server Trigger, Bearer auth) | `/mcp/pfa-finance-tools` | Publishes the 4 read-only tools (Knowledge_Base_Search RAG + 3 market tools) to any MCP client: Claude Desktop, Cursor, other n8n workflows. User-profile tools are deliberately **not** exposed. |

**Wiring change:** the Guardrails node outputs only its check result. So `Financial Q&A Agent` now reads `$('Chat Trigger').first().json.chatInput`, and `Chat Memory` uses a custom session key from the Chat Trigger.

**After import:**
1. Open `PFA MCP Server` and create a **Bearer Auth** credential. Its token is what MCP clients send.
2. Check that `Guardrail LLM` has your OpenAI credential. Its ID is the same as the other LLM nodes.

**Architecture deck:** `PFA_Architecture_v3.2.pptx` has 20 slides:
- the AI capability map
- the tech stack
- the end-to-end diagram
- a node-by-node table for every stage
- RAG, guardrails, MCP and the risk engine
- data storage
- the roadmap to a production app
