# Personal Finance Advisor v3.4: how the flow works, and how to demo it

**Demo in one line:** use the app like a real user, then open n8n's **Executions** tab to show what each request ran.
Test mode (`Execute workflow`, `scripts/test-step.sh`) is a debugging tool for one step at a time. You don't need it for a demo.

---

## 1. The big picture: one app, seven doors

The advisor is a **web app served by n8n**. Everything the user does in the browser calls one **webhook**, a starting node in the workflow. Each call is a separate run, listed in **Executions**.

| # | The user… | Webhook (starting node) | What happens |
|---|---|---|---|
| 1 | opens `localhost:5678/webhook/pfa` | **Advisor App** (GET) | n8n sends the app page |
| 2 | types their email | **Lookup API** (POST) | finds the saved profile and past plans |
| 3 | fills the 5 steps and presses **Submit** | **Submit API** (POST) ★ | **the main pipeline**, section 2 |
| 4 | sees "Building your plan…" | **Status API** (GET) | the page asks "is it ready?" every few seconds |
| 5 | sees the report open | **Report API** (GET) | loads the saved report and draws the charts |
| 6 | asks a question in the chat | **Chat API** (POST) ★ | **the chat agent**, section 3 |
| 7 | clicks **Yes / No** on a plan change | **Confirm API** (POST) | Yes runs the main pipeline again with the change |

---

## 2. The main pipeline (Submit API)

```
Submit API
 ├ Plan Request (form)            tidy the submitted answers
 ├ Build Financial Profile        "18L" → 1,800,000; pay, EMIs, surplus
 ├ Goal Text Guardrail (LLM)      blocks prompt injection in free text
 ├ Check Profile Completeness
 ├ Needs More Info? ── missing ──► Explain Fixes ► Respond: Fix These
 │       │ ok
 ├ Respond: Building              browser answered now; rest runs in background
 ├ Prepare User Storage ► Upsert User Profile (Postgres)
 ├ Restore User State
 │   ├─► Compute Debt Metrics       ► Debt Analysis Agent (LLM)      ┐ in
 │   └─► Compute Allocation Metrics ► Portfolio Analysis Agent (LLM) ┘ parallel
 ├ Sync Analyses (merge)
 ├ Compute Future Projection      goal reached at this saving rate?
 ├ Low risk → bank deposits? ── yes ──► Plan Bank Deposits
 │                                      ► Attach Deposit Plan
 ├ Investment Recommender Agent (LLM + tools)
 ├ Assemble Report Inputs
 ├ Report Generator Agent (LLM, structured JSON) ► Render Report Card
 └ Save Advice History (Postgres) report saved; Status API says "ready"
```

**Investment Recommender Agent tools:**
- Knowledge_Base_Search (RAG on pgvector)
- Historical_Market_Data
- Screen_NIFTY50_Stocks
- Company_Annual_Performance
- Plan_Bank_Deposits
- Get_Deposit_Rates

**Key design point:** the **numbers come from code nodes** (deterministic). The **LLM agents only explain and recommend**, using those numbers, and are told never to recalculate them. That's what keeps the report's maths reliable.

(The *Append to Google Sheets* node is switched off on purpose.)

---

## 3. The chat (Chat API, or n8n's "Open chat")

```
Chat API ► Chat Report Owner ► Chat Context ► Chat Input Guardrail
   ► Financial Q&A Agent
   ► Chat Output Sanitizer ► Chat Result
   ► Plan Change? ── yes ──► Yes / No buttons ► Confirm API
```

**Financial Q&A Agent tools:**

| Tool group | Tools |
|---|---|
| This user's data | the profile and latest report |
| Search | RAG search |
| Market data | market history, NIFTY50 screener, company results |
| Deposits | deposit planner and rates, India inflation |
| Teammate's service | Ask_Bank_Deposit_Schemes, Ask_Mutual_Funds |
| Plan changes | Propose_Plan_Change |

**Where the teammate's project fits:** questions about a bank's scheme rules or a specific mutual fund go to the teammate's container, which runs their Chroma RAG over bank and fund documents and is called as a tool.

---

## 4. Five-minute demo script

**Before the meeting**
- Run `./start.sh`, then `./healthcheck.sh`. Every line should say OK.
- Open two browser tabs:
  - the **app**: `localhost:5678/webhook/pfa`
  - **Executions**: `localhost:5678/workflow/pfaAdvisorV32App/executions`

**1. The app (2 min).** Enter a new email and fill the 5 steps with TESTING.md scenario A1:
- CTC 18L, goal *Buy a home*, 80L in about 5 years
- expenses 45K, car loan 3.2L at 9.2% with an 11K EMI
- MF 4.5L with a 15K SIP, FD 2L
- risk Medium

Press **Submit**. While "Building your plan…" shows, say: *"n8n has already answered the browser. The agents are running in the background."*

**2. n8n while it builds (1 min).** In Executions, open the **Submit API** run.
- Show the green path: guardrail, profile, **two agents in parallel**, the recommender with its tools, the report.
- Click **Investment Recommender Agent → Logs** to show the RAG search and the tool calls.

**3. The report (1 min).** Charts, the risk-profile card, "where to put your money each month", the safety-net meters.

**4. The chat (1 min).**
- Ask *"Which bank gives the best 1-year FD for me?"* to show tools at work.
- Then ask *"My expenses went up to 50K."* The **Yes / No plan-change** buttons appear. Open that run in Executions as well.

**Optional:** Phoenix at `localhost:6006`, project **pfa-n8n**, shows every LLM call with its prompt, tokens and cost.

---

## 5. Likely mentor questions

| Question | Answer |
|---|---|
| Why webhooks, not n8n's Form node? | A custom multi-step app: Back / Edit, pre-filled answers for returning users, live checks as you type. |
| How do you stop made-up numbers? | Code computes every number, agents only explain them, and outputs are sanitised. |
| How is it kept safe? | Guardrails on the goal text and on chat input, and a sanitiser on chat output. |
| Where is the data? | Postgres: profiles and report history, plus RAG embeddings in pgvector. |
| How do you see what the AI did? | n8n Executions → Logs on each agent, and Phoenix traces with tokens and cost. |
| Why does the report take 1-3 minutes? | Four LLM agents and tool calls. The page polls Status API, so the browser never times out. |
