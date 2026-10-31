# What changed in v3.4

v3.4 brings the n8n edition in line with the Python v1.5 app. v3.3 is unchanged in its own folder.

## 1. A real step form, with Back

The five n8n Form pages are replaced by one page that the workflow serves itself: **http://localhost:5678/webhook/pfa**.

- **Start page:** enter your email. A returning user sees **See my latest plan · Update my answers · Start fresh** and the list of their plans. Plans changed in the chat say "updated in chat: …".
- **Step form:** 5 steps with **Back** and **Continue**, and answers are kept when you go back. Returning users get every answer pre-filled.
- **Checks as you type:** amounts are read with the same `parseAmount` the server uses, so "1Cr 35L" is caught on the spot ("I couldn't read…"), not after the last page. Step 2 pre-fills in-hand pay from the CTC (FY 2026-27 new regime).
- **Review page with Edit:** each section has **Edit**, which jumps to that step, then **Save and return to review**. Then **Build my plan**.
- **Server-side checks:** the Goal Text Guardrail and the completeness check ("these don't add up…") still run. Anything they flag is sent back to the step it belongs to, instead of n8n's "Nearly there" page.
- **Building page:** shows progress while the agents work (about 1-2 minutes), then opens the report.

## 2. Report page with the chat beside it, and editing the plan from the chat

`/webhook/pfa/report?id=…` shows the report with a chat panel. It's the same assistant as the hosted chat page.

- Ask anything: plan questions, bank FD/RD rates and plans, and the teammate's bank-scheme and mutual-fund documents.
- **Plan changes are confirmed first.** For example: "What if I invest 30K a month?", "my salary is now 1.6L", "move my goal to 2030", "I closed my car loan", "make it Low risk".
  - The agent calls **Propose_Plan_Change**.
  - The workflow previews the change on the saved answers and stores it as *pending*.
  - The page shows a **Yes / No** card.
- **Yes:** the change is applied to the saved answers and the same pipeline runs again. A new plan opens, marked **Updated plan** with the list of changes and a link to the previous version.
- **No:** nothing changes.

The hosted chat page shows text only, so there a proposed change comes back with a link to the report page, where you press Yes.

## 3. Bank deposits inside the main flow

The deposit planner used to be a separate workflow (*PFA · Bank deposit planner*) with its own chat. Now:

- Its nodes are part of the advisor workflow. The Low-risk report step, the chat tools (Plan_Bank_Deposits, Get_Deposit_Rates, Get_India_Inflation) and the `/mcp/bank-deposits` MCP server all live in one workflow.
- **One chat for everything.** The separate deposit chat link is gone.
- On an upgraded install, the old workflow is switched off automatically (`n8n/bootstrap/setup.sh` and `postgres/v34.sql`).

## 4. Sturdier teammate integration

The teammate's knowledge tools are now called as **HTTP tools** (`/ask/<tool>` on the teammate service, with the same bearer token).

**Why:** n8n's MCP client connects when the agent starts, so in v3.3 a stopped teammate container made *every* chat fail. Now the chat keeps working, and says when the teammate's documents can't be reached. The same tools are still published over MCP at `:8090/mcp`.

## 5. Phoenix

- Form submissions and chat changes are grouped per user (session `plans-<email>`).
- Report-page chats are grouped per conversation.
- The building page's status checks are not traced.

## New endpoints (all in the advisor workflow)

| Method | Path | What it does |
|---|---|---|
| GET | `/webhook/pfa` | The app: start page, step form, building view |
| POST | `/webhook/pfa/lookup` | Pre-filled answers and plan history for an email |
| POST | `/webhook/pfa/submit` | Build a plan from the form, or say what to fix |
| GET | `/webhook/pfa/status?id=` | Is the plan ready? |
| GET | `/webhook/pfa/report?id=` | Report + chat page |
| POST | `/webhook/pfa/chat` | Chat message, from the report page |
| POST | `/webhook/pfa/confirm` | Yes / No on a proposed change |

## How the workflow is built

The workflow JSON is generated:

```bash
python3 tools/build_v34.py
```

It reads `n8n/v33_source/*.json` and the readable sources in `n8n/src/` (the page, the chat and the Code nodes). Offline checks for the Code nodes:

```bash
node tools/test/test_v34_nodes.js
```

These run 26 checks with no n8n and no AI: profile building, the "fix this" replies, pre-fill, propose / confirm / decline, and both pages render.

## Tested on an isolated copy (5 Oct 2026, made-up user)

| Step | Result |
|---|---|
| Start page | Welcome back, plan history listed |
| Update my answers | Every step pre-filled; Back and Continue work |
| Edit from review | Changed expenses, returned to review |
| CTC "1Cr 35L" | Caught on the step ("I couldn't read…") |
| Build my plan | Report opened after **108 s**, with the bank-deposit section (Low risk) |
| Chat: Parag Parikh exit load | Answered from the teammate's documents |
| Chat: "What if I invest 30K a month?" | Yes / No card: "Monthly investing ₹18K → ₹30K" |
| Yes | New plan after **91 s**, "Updated plan" banner, link to the previous version |
| Plan history | "updated in chat: Monthly investing ₹18K → ₹30K" |
| Chat with the teammate container stopped | Still answers; says the teammate's documents are unavailable |
| Chat: "Which bank pays most on a 3-year FD?" | Answered from the rate table |
| `/mcp/bank-deposits` | 3 tools, served by the advisor workflow |

Screenshots are in `docs/screenshots-v3.4/`.

## Known limits

- **No password:** the email is still the only key (pilot). Report links use unguessable ids.
- **Browser support:** n8n serves the pages under a sandbox policy. They work in Chrome, Edge and Safari, but the Claude desktop app's built-in browser blocks their requests. Use a normal browser.
- **Execution history:** each status check while a plan builds is one small n8n execution (about 15-20 per plan). n8n prunes old executions automatically.
