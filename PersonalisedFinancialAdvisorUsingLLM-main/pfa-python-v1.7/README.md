# Personal Finance Advisor: Python edition (v1.7, from the n8n v3.2 flow)

> **New in v1.7: more than one goal, and "what if a smaller goal comes up in between?"** (mentor feedback)
> - **Up to 4 goals:** the main goal plus 3 more, each with an amount, a date and a priority (Must-have / Nice-to-have). Add them on step 1 of the form, from the report, or by telling Arth ("I also need 6L for a car in 2028").
> - **How the money is shared (all in code, no AI):** Must-have before Nice-to-have, then the nearest date first. Savings you already have are set aside in that order, each goal getting what it needs today at its own expected return; anything left stays with the main goal. Monthly money is shared the same way. Each goal gets **its own risk level for its own date** (a car in 2 years sits in FD / RD; a home in 8 years can hold equity), using the same rulebook as the main goal.
> - **Report → Your goals:** every goal's share of savings, the SIP it needs, what the plan gives it, its projected value and status (On track · Funded by the plan · Partly funded · Not funded yet, with the date it becomes reachable). A timeline chart shows all goal money over time, dropping as each goal is paid out. The monthly plan adds every goal's SIP, each split by its own mix.
> - **"What if a new goal comes up?"** An instant calculator on the report (no AI, no cost) shows three ways to pay for a new goal:
>   **A. Save for it separately.** Its true monthly cost is the change in what *all* goals need, because savings set aside for it leave the others. You see what every other goal gets afterwards.
>   **B. Use the main goal's savings.** No new SIP; the main goal loses the amount *plus its growth* (`amount × (1 + r)^(months between the two goals)`), with the monthly top-up or the delay that makes up for it, and a market-risk warning.
>   **C. Wait.** When your spare money alone reaches it; nothing else changes.
>   It recommends one, and **Add it to my plan** rebuilds the plan (also for the later date from C). Arth shows the same numbers, computed in code, before you press Yes.
> - With one goal, every number is the same as v1.6, except that plan SIPs are now rounded **up** to ₹100 when the money allows (no more "your goal needs ₹36 more").
> - Details and the maths: [docs/MULTI_GOAL.md](docs/MULTI_GOAL.md). v1.6.4 is unchanged in `../pfa-python-v1.6.4`.
>
> **New in v1.6: start with a conversation, not a form.**
> - **First screen after sign-in:** a chat with Arth. The user describes themselves, their goal and their money in their own words (typed or spoken). The profile panel beside the chat fills in as Arth understands.
> - **One AI read per message, not per answer:** one structured-output call extracts every field it can, and never guesses a value the user didn't say. Whatever is missing is asked in **one grouped message** of short inputs and buttons, read by code at no cost. The review offers **Build my plan** or **Edit my plan** (editing is code only).
> - **Returning users** see their saved profile with the same two buttons, or can just say what changed ("my salary is now 22 lakh and I closed the car loan").
> - **Cost:** one read is about ₹0.05-0.12 (gpt-5-mini, minimal reasoning, measured), with at most 3 per intake. That's against about ₹1.40 if every answer went through the AI. Reads appear on the Usage page and in Phoenix ("Intake extract"); the messages themselves are not stored.
> - **The 5-step form** is still there: "Prefer a form?" in the chat, or **Update answers** in the top bar. v1.5 is unchanged.
>
> **New in v1.5: the team's bank deposit planner.** It's the FD/RD optimiser from *PersonalisedFinancialAdvisorUsingLLM*, the same maths as the n8n bundle.
> - **Low risk (or a goal under 3 years):** the report always gets a **Bank deposits** section. It shows the recurring-deposit sequence for the fixed-income money (bank, tenure, rate, dates, maturity value), whether it covers that share of the goal, and the monthly amount needed if not. The *Fixed income* row names the banks.
> - **Chat:** FD/RD questions are answered from the team's rate table (10 banks, 211 rates), which is free and needs no web search. Ask for a plan ("I have 3L now and 10K a month, I need 8L by 2030") and Arth runs the planner and presents the FD and RD sequence. Inflation comes from the World Bank when you don't give it.
> - **Cost:** the planner itself uses no AI. A plan request in chat makes one extra AI call.
> - Details: [docs/BANK_DEPOSITS.md](docs/BANK_DEPOSITS.md). v1.4 is unchanged.
>
> **New in v1.4: the deck's look and voice everywhere.**
> - **Theme:** the form pages and the chat use the mentor deck's theme: lavender background, deep purple panels, violet highlight letters, black pill buttons and the orange→pink→purple gradient, with a matching dark mode.
> - **Voice in and out for the whole intake form:** "🎙 Answer this step by voice" reads each question, listens, fills the answer and moves on. You can say "eighteen lakh", "June 2034", "car loan" or "skip".
> - **Chat:** the same voice as before.
> - **Cost:** free with the browser voice; the natural voice is optional. v1.3 is unchanged.
>
> **New in v1.3: a chat that feels human, voice, and clearer numbers.**
> - **Arth**, the chat advisor, answers what you ask, with real numbers.
> - Stock requests get a **watchlist** with 5-year data and today's prices.
> - Plan changes are **shown and confirmed** before anything changes.
> - **Voice** is on request only: free browser voice, or an optional natural voice.
> - The report adds a **monthly SIP pie** and a **"Your SIPs now vs the plan"** table.
> - The intake columns are clearer.
> - A **conversation evaluation** scores the chat.
>
> v1.2 is unchanged in `../pfa-python-v1.2`.
>
> **New in v1.2: live data and a clearer allocation.**
> - **SerpAPI** updates the knowledge base when the app starts: today's date, the NIFTY 50 level, recent index additions and removals, and the latest share prices.
> - **A router** decides, question by question, whether the chat answers from the local knowledge base or fetches live data.
> - **A "What you own today" pie** sits next to the target mix.
> - **A 30-question evaluation** compares local, web and router answers.
>
> v1.1 (observability) and v1.0 are unchanged in their own folders.

The v3.2 advisor rebuilt as a small modular Python web app, following the mentors' feedback:

| Mentor feedback | What changed |
|---|---|
| "n8n takes too long to respond" | The report's **numbers and charts open in about 0.05 s**. The AI explanation is written in the background and appears on the same page a few seconds later. The four agents that v3.2 ran one after another are now **two AI calls in parallel**. Stock screening is done in code instead of an agent tool loop. Guardrails are local rules instead of extra model calls. |
| "The application is HTML heavy" | The report is a **~26 KB page** rendered on the server. The CSS and JS are separate, cached files (~42 KB, loaded once), and the charts are small inline SVGs. |
| "Show Goal projection at the top" | The report now **opens with the goal projection**: verdict, progress ring, target vs projected, and the projection chart. The other sections follow in the same order as before. |
| Also requested | **Sign-in** with Google (optional) or email + password, the **Bank Deposits MCP removed**, and the **chat at the end of the report**. The chat can change the plan and gives a link to the updated report. |

Everything else is the v3.2 logic, ported line for line:
- in-hand pay from CTC (FY 2026-27 new regime)
- the risk plan (horizon caps, safety-net blockers for stocks)
- the Low / Medium / High target mixes
- the projection maths and the monthly plan by instrument
- the colour-blind-checked chart palette
- the conversational intake with its reactions

The n8n bundles (v3.2 and v3.2.3) are **unchanged**.

## Start it

You need Docker Desktop. An OpenAI key is optional but needed for the AI text and chat.

```bash
./start.sh
```

Then open **http://localhost:8080**, create an account, and follow the five short steps. `start.sh`:
- creates `.env` with random secrets
- asks for your OpenAI key
- builds and starts three containers
- loads the knowledge base (1,632 chunks, about 20 s)

| Command | Does |
|---|---|
| `./start.sh` | Start or restart. Run it again after changing `.env` or the code. |
| `./healthcheck.sh` | Service status, AI/Google on or off, knowledge-base chunks, number of accounts and plans. |
| `./stop.sh` | Stop. Data is kept. |
| `./reset.sh` | Delete all local data. |
| `./scripts/ingest-rag.sh [--force]` | Load or reload the knowledge base. It's resumable. |
| `./scripts/usage-report.sh` | AI cost per user: plans, ₹/plan, questions, ₹/question. |

Default ports are app **8080** and Postgres **5434**, both bound to localhost only. They don't clash with the n8n bundle (5678 / 5433 / 8000), so both can run at once.

## Sign-in

- **Email + password** always works. Passwords are hashed with scrypt, and repeated failed logins are throttled.
- **Google** is enabled when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in `.env`. To set it up once (about 10 minutes):
  1. In [Google Cloud Console](https://console.cloud.google.com/), create a project, then go to **APIs & Services → OAuth consent screen**. Choose **External**, add your app name and email, and add each tester's Gmail under **Test users**.
  2. Go to **Credentials → Create credentials → OAuth client ID → Web application**.
  3. Add the **Authorised redirect URI** `http://localhost:8080/auth/google/callback`. If you changed `APP_PORT` or `PUBLIC_BASE_URL`, match them.
  4. Put the client ID and secret in `.env`, then run `./start.sh`. The sign-in page shows **Continue with Google**.

  If a Google user already has a password account with the same email, the two are linked. The old password stops working, because Google has proved who owns the address.

**Other simple options we considered:**

| Option | Verdict |
|---|---|
| Email one-time code (passwordless) | Simple for users, but needs an SMTP account (e.g. a Gmail app password) to send codes. |
| Reverse-proxy sign-in (e.g. Cloudflare Access) | Zero code, good for a hosted demo, but needs a domain. |

Email + password plus Google covers local team testing without any extra service.

> Note: email + password sign-up does not verify that the person owns the address. That's fine for local testing. For a public deployment, use Google only, or add email verification.

## How it works

```text
Browser ──► FastAPI app (app/pfa)                                        Postgres + pgvector
  sign-in      auth.py        email+password (scrypt) · Google OAuth      accounts
  intake       profile.py     5 steps, per-step checks + reactions        users (profile per email)
  plan         pipeline.py ─► engine/  debt · allocation (risk plan) ·    advice_sessions (reports)
                                        projection (FV maths, monthly plan)
                          ─► engine/stocks.py ── market-analyzer (NIFTY 50 history, cached)
                          ─► save report ──► page opens now (numbers + charts)
                          ─► background: ai/rag.py (1 embeddings call) ─► finance_kb_embeddings
                                         ai/narrative.py (2 AI calls in parallel) ─► report updated
  report       report.py + charts.py (server-side SVG) + templates/_report_main.html
  chat         ai/chat.py     guard ─► 1 AI call: on-topic? + reply + plan changes
                              changes ─► profile.apply_changes ─► pipeline ─► link to the updated report
```

| v3.2 n8n nodes | Python module |
|---|---|
| Intake Form, Chat 1-5, Read … nodes, Any Loans? | `templates/intake.html`, `static/intake.js`, `profile.check_step` / `reaction` |
| Build Financial Profile, Check Profile Completeness, Ask For Missing Details | `profile.build_profile`, `profile.sanity_fixes` (the "Nearly there" step) |
| Goal Text Guardrail, Chat Input Guardrail, Chat Output Sanitizer | `ai/guard.py`: local rules. The topic check is part of the chat's single AI call. |
| Prepare User Storage, Upsert User Profile | `db.save_profile` (parameterised SQL, so no base64 workaround is needed) |
| Compute Debt / Allocation Metrics, Compute Future Projection | `engine/debt.py`, `engine/allocation.py`, `engine/projection.py` |
| Debt, Portfolio, Recommender and Report agents, and their LLMs | `ai/narrative.py`: two parallel structured-output calls, plus computed fallback text |
| Screen_NIFTY50_Stocks, Historical_Market_Data tools | `engine/stocks.py`: one call to the market API, rules applied in code |
| Knowledge_Base_Search (PGVector) | `ai/rag.py`: the same table, model and cosine search |
| Render Report Card | `report.py`, `charts.py`, `templates/_report_main.html`, `static/report.css` |
| Save Advice History, Show Report | `db.save_report`, `GET /report/{id}` |
| Financial Q&A Agent, Chat Memory, Update_My_Plan (3.2.3) | `ai/chat.py`, the `chat_messages` table, `profile.apply_changes` |
| RAG ingestion workflow | `pfa/ingest.py` (`./scripts/ingest-rag.sh`) |

**Why it's faster.** Almost all of v3.2's waiting was sequential AI work: 4 agents in a row, plus several tool round trips in the recommender, plus a guardrail model call on the way in and out. Here:
1. The numbers never wait for AI.
2. The two AI calls overlap.
3. Retrieval is one batched embeddings request.
4. Stock screening and guardrails take microseconds in code.
5. The model runs with `reasoning_effort=low`. Set `OPENAI_REASONING_EFFORT=medium` in `.env` for more thorough, slower text.

If OpenAI is slow or down, the report still shows a complete explanation written from the numbers.

**Privacy and safety:**
- Reports are only visible to the account that owns them.
- Sessions are signed, HTTP-only cookies.
- Every write API needs an anti-CSRF header.
- A strict Content-Security-Policy allows no external scripts.
- ID numbers typed into the chat are refused, and masked in any AI output.

## Files

| Path | What |
|---|---|
| `app/pfa/` | The application. Every module has a docstring explaining its job. |
| `app/pfa/templates`, `app/pfa/static` | Pages, the report layout, CSS and JS (no frameworks, no CDNs). |
| `docs/ARCHITECTURE.html` | Architecture diagrams, module guide, key code, speed and cost (open in a browser; diagrams need internet). |
| `app/pfa/live/serpapi.py`, `live/refresh.py`, `ai/router.py` | v1.2 live data: SerpAPI client (cache, budget, trusted sources), startup knowledge-base update, chat router. |
| `app/pfa/eval/` · `scripts/run-eval.sh` | 30-question evaluation of local vs web vs router. |
| `tools/mock_serpapi.py` | Stand-in for SerpAPI (labelled test data) for testing without credits. |
| `app/pfa/ai/chat.py` · `ai/voice.py` · `static/report.js` | v1.3 chat (Arth, confirm-before-change, watchlist, streaming) and voice. |
| `app/pfa/eval/conversations.json` · `scripts/run-conversation-eval.sh` | Conversation evaluation. |
| `app/pfa/tracing.py` | Observability: OpenTelemetry spans with OpenInference attributes, exported to Phoenix. |
| `docs/build_mentor_deck.js` | Rebuilds the v1.1 mentor deck (13 slides with speaker notes): `node docs/build_mentor_deck.js` (needs `pptxgenjs`, `sharp`, `react-icons`). |
| `docs/COST_AND_PERFORMANCE.md` | Measured cost per plan and per chat question, per-call breakdown, speed vs n8n. |
| `tests/test_goals.py` | 12 tests for v1.7: sharing money across goals, one goal = v1.6 numbers, priorities, the timeline, the three new-goal options, form checks, chat add / remove, the report section. |
| `tests/test_engine.py` | 36 unit tests (including spoken amounts) (including 20 router questions, emergency changes that never cut SIPs, the watchlist, fund types, the pie and web-result parsing): parsing, tax, intake checks, risk plan, projection, stock rules, chat changes, guardrails, passwords, cost maths and tracing. |
| `tools/mock_openai.py` | A stand-in for OpenAI, for testing without a key (see TESTING.md). |
| `market-analyzer/` | The v3.2 NIFTY 50 API, plus `/five-year/all` for the one-call screen. |
| `knowledge-base/`, `data/` | The same 830 documents and NIFTY 50 dataset as v3.2. |

## Voice-guided form and deck theme (new in v1.4)

**Voice for the form**, on the intake page. Voice starts only when the user presses a button.
- **🎙 Answer this step by voice:** Arth reads Arth's message and each question aloud, listens, fills the field and confirms ("Got it: eighteen lakh"). At the end of the step, saying *"next"* continues, and the next step starts the same way.
- **Answers it understands:**
  - amounts in words or shorthand ("eighteen lakh", "fifty thousand", "2 lakh 50 thousand", "1.5 crore")
  - dates ("June 2034", "in 8 years")
  - choices ("buying a house" → Buy a home, "rupees" → INR, "high" → High risk)
  - loans ("car loan and credit card", "no loans")
  - "skip" for optional fields, and "keep" for a pre-filled answer
- **Every field** also has its own small 🎙 to dictate just that answer.
- **Read questions aloud** reads Arth's reactions between steps, and any errors.
- **Voice engines:** the browser voice by default (free), or the natural voice if `VOICE_ENGINE=openai` and the user ticks it. The chat and the form share the same code (`static/voice.js`).
- **Saved neatly:** spoken amounts are stored as shorthand ("18L") so "Update my answers" pre-fills neatly.

**Theme:** the tokens `--t-*` in `static/app.css` come from the mentor deck, and the chat panel on the report page uses the same tokens. Static files are versioned (`?v=1.4.0`), so browsers pick up new styles right after an upgrade.

## The chat, rebuilt (new in v1.3)

v1.2's chat was correct but robotic:
- it led with "no" and repeated the same blocker three times
- it couldn't answer stock questions because it had no data
- it once cut a user's SIPs when they asked to add money to the emergency fund

v1.3 fixes each of these:

| Problem | v1.3 |
|---|---|
| Refusals, repeated | **Arth** (a named advisor) follows *acknowledge → answer → one next step → one question*, uses the first name, and mentions a limit **once** with the exact unlock ("stocks wait until your emergency fund reaches ₹1.95L, about 13 months at ₹6K a month"). |
| No data for stock questions | A **watchlist** is screened even while stocks are paused: the best 5-year NIFTY 50 names within your risk limits, with **today's prices** from the startup refresh (or SerpAPI, cached). Mutual funds are given as categories with **₹ amounts from your monthly plan**. Fund houses and schemes aren't named; that needs a SEBI-registered adviser, and Arth says so once. |
| Silent, wrong plan changes | Changes are **previewed**: *"I'll change: Emergency fund ₹0 → ₹50K · Monthly emergency top-up ₹0 → ₹6K"* with **Yes / No**. There are new fields for a one-time emergency deposit and a monthly top-up, so SIPs are never cut unless you say so. |
| A wall of text | Short paragraphs, bullets and **bold**, follow-up suggestion chips, and progress stages while it works ("Checking today's prices…"). One disclaimer sits under the chat instead of at the end of every message, and the cost moves behind an ⓘ. |

**Voice:** nothing listens or speaks unless the user presses 🎙 or 🔊, or turns on *Read replies aloud*.

| | `VOICE_ENGINE=browser` (default) | `VOICE_ENGINE=openai` |
|---|---|---|
| Speak a question | Browser speech recognition (Chrome, Edge, Safari), **free** | + OpenAI gpt-4o-mini-transcribe if the browser can't: **≈ ₹0.04** per 10-second question |
| Hear an answer | The device's own voice, **free** | + a *Natural voice* option (gpt-4o-mini-tts): **≈ ₹1 per reply** (estimate) |

OpenAI voice is capped per user per day (`VOICE_DAILY_LIMIT_PER_USER`) and appears on the Usage page. Audio is never stored. Browsers only allow the microphone on `localhost` or https.

**Evidence:** `./scripts/run-conversation-eval.sh` runs 8 scripted conversations, including the real one that prompted this rebuild. Each is scored on:
- **Automatic checks:** names the watchlist, asks before changing the plan, leaves SIPs untouched, shows a dated live source, refuses ID numbers locally, declining keeps the plan.
- **An AI judge** (1–5): warmth, whether it answered the question, and how specific it was.
- **Repeated refusals.**

It writes `docs/CONVERSATION_EVAL.md`; a run costs about ₹3–5.

## Clearer numbers (new in v1.3)
- **"Where your monthly investing goes now"** is a pie of your SIPs beside *What you own today*. Before, SIPs with no invested value yet were invisible, so a beginner saw "100% fixed income".
- **"Your SIPs now vs the plan"** is a table with one row per bucket: what you invest now, what the plan suggests, and **why**. For example: *Direct stocks ₹2,000 → ₹0: paused until your emergency fund reaches 3 months*.
- **Clearer intake:** the columns are now *Already invested (value today)* and *SIP / added every month*, and the labels stay visible on phones. The review card shows both amounts per row. If PPF/EPF is your biggest SIP, a gentle nudge asks whether it was meant for mutual funds.
- **An optional monthly emergency top-up** in the intake. The plan then says how many months until you reach 6 months of essentials.

## Live data with SerpAPI (new in v1.2)

**Why both RAG and SerpAPI:**

| Layer | Used for |
|---|---|
| Code | Every number and chart |
| Knowledge base (RAG) | Trusted, stable knowledge: 830 curated documents plus today's live documents |
| SerpAPI | Only what changes daily |

The router picks the right layer for each question.

### Knowledge-base update at start
The app isn't hosted, so there is no nightly job. Instead, each time the container starts (**at most once every 24 h**; a restart within that window skips it), the app updates the knowledge base. Every page shows *"Updating the knowledge base…"* with the step, and `start.sh` prints the same progress.

| Step | Source | Searches |
|---|---|---|
| Today's date and the NIFTY 50 level | Google Finance | 1 |
| Stocks added to or removed from the NIFTY 50 | Google News + niftyindices / nseindia | 2 |
| Latest prices of 6 NIFTY 50 stocks | Google Finance, oldest first; all 50 are covered over about a week | 6 |
| Index changes read from the news by the AI, kept only if consistent with the dataset's list (removed ⊂ list, added ∉ list) | - | 0 |
| Three dated documents replace the previous live documents in the knowledge base | - | 0 |

The free SerpAPI plan has **250 searches a month (50/hour)**. The app counts every search and never lets the refresh use the last 60, so the chat always has some left. Cached results are free.

### The router (chat)
1. **Rules, free and instant.**
   - **Live:** time words ("today", "current", "latest"…) or time-sensitive topics:
     - share prices
     - the NIFTY level
     - index changes
     - FD, repo and other rates
     - news
   - **Local:** concept questions ("what is a…", "explain", "why"), and personal "my… / should I…" questions.
2. **If the rules can't tell**, the chat's single AI call also returns `needs_live_data`. Only then are a search and a short second call made.
3. **Local first even for live questions.** If today's refresh already has the answer (a fresh quote, the index level, the index changes), no search is spent. Otherwise SerpAPI is called, with results cached for 12 h.

Live answers end with the source and date, e.g. *"Live data: rbi.org.in · 29 Sep 2026 · via SerpAPI"*. Trusted sources (RBI, SEBI, NSE, AMFI, the Income Tax department and the main banks) come first; anything else is labelled unverified. Web text is treated as data, never instructions, and ID numbers are masked.

**Measured cost:** a chat question answered locally costs about ₹0.11. A live search costs about **₹2.2 extra on the paid Starter plan** ($0.025), or ₹0 on the free plan. That price gap is why the knowledge-base-first router matters. Set `PRICE_SERPAPI_SEARCH=0` in `.env` if you are on the free plan.

### Setup
Put your key in `.env` (`SERPAPI_API_KEY=...`) and run `./start.sh`. Budget settings (`SERPAPI_REFRESH_BUDGET`, `SERPAPI_QUOTES_PER_REFRESH`, `SERPAPI_REFRESH_HOURS`, `SERPAPI_CHAT_RESERVE`) are in `.env.example`. Without a key, the app works as v1.1.

### Evaluation (evidence for the mentor)
`./scripts/run-eval.sh` asks 30 fixed questions (12 concepts, 12 needing today's data, 6 about the user's plan) three ways:
- **local knowledge base only**
- **web only**
- **the router**

It writes `docs/EVALUATION.md`: route accuracy, grounded answers, dated sources, time, cost and searches per mode, plus every router decision with its reason. All answers go to `docs/eval_answers.json`. A full run costs about ₹10 of OpenAI and about 30 SerpAPI searches; `--modes hybrid` runs just the router.

## "What you own today" pie (new in v1.2)
The report now shows, after *Where you stand today*:
- **A pie of everything you own:** equity, fixed income, gold, savings and cash, and the emergency fund, with % on the slices and ₹ in the legend.
- **A pie of the target mix** for your risk level.
- **One plain sentence**, e.g. *"69% of your money is in fixed income. Of your investments, 15% are in equity; your Medium-risk plan aims for 50%, so new money leans towards equity."*

The intake now asks what kind of mutual funds you hold:
- **Equity funds** count as equity.
- **Debt funds** count as fixed income.
- **Hybrid funds** count half and half.
- **"Not sure"** counts as equity.

Before v1.2, every mutual fund counted as equity.

## Observability (new in v1.1)

The team's n8n bundle added **Phoenix** plus a small telemetry API: workflow nodes were meant to POST `{session_id, node_name, state}` events, and the API turned them into OpenTelemetry spans. In that bundle the workflow didn't call it yet.

In Python the app **traces itself**, so the separate telemetry service isn't needed. Every step becomes an OpenInference span that Phoenix understands:

```text
Build plan (CHAIN)                        Chat message (CHAIN)
├─ Compute numbers (CHAIN)                ├─ Guardrail check (GUARDRAIL)
├─ Screen NIFTY 50 (TOOL)                 ├─ Knowledge-base search (RETRIEVER)
└─ Write explanation (CHAIN)              │   └─ embeddings (EMBEDDING)
   ├─ Knowledge-base search (RETRIEVER)   ├─ chat_reply (LLM)
   │   └─ embeddings (EMBEDDING)          └─ Build plan ... (when the chat changes the plan)
   ├─ report_story (LLM)
   └─ report_details (LLM)
```

Open **http://localhost:6006** and choose project **pfa-python**:

- **Traces:** each plan and chat question, with the timing of every step. The two AI calls run side by side.
- **LLM spans:**
  - model and invocation settings
  - the prompt and the answer
  - token counts (input, cached, output, reasoning)
  - cost (`pfa.cost_usd`)
- **Retriever spans:** the knowledge-base passages found, with their scores.
- **Sessions:** all of one user's plans and chat questions grouped together, so you can follow a user's journey and its total tokens.

**Privacy:**
- Users appear as `user-<hash>`. Their email is never sent.
- ID numbers are masked before anything is exported.
- `PFA_TRACE_CONTENT=false` sends only timings, token counts and costs: no prompts, answers or figures.
- Phoenix listens on localhost only.

**Safe by design:**
- Spans are exported in the background, so requests never wait for Phoenix. With Phoenix stopped, plans still build in ~20 ms; the only effect is warning lines in the app log.
- Setting `PHOENIX_COLLECTOR_ENDPOINT=` (empty) in `.env` switches tracing off completely.

| Setting (`.env`) | Default | Meaning |
|---|---|---|
| `PHOENIX_PORT` | 6006 | Dashboard port. Change it if the n8n bundle's Phoenix is also running. |
| `PHOENIX_PROJECT` | pfa-python | Project name in Phoenix |
| `PFA_TRACE_CONTENT` | true | Include prompts, answers and figures in traces |
| `PHOENIX_COLLECTOR_ENDPOINT` | (bundled Phoenix) | Set empty to disable tracing, or point to another OpenTelemetry collector |

## Upgrading from v1.5

This folder has a copy of your v1.5 `.env`. Everything carries over, and the new `intake_reads` table is created automatically at start.

1. Run `./stop.sh` in `../pfa-python-v1.5`.
2. Run `./start.sh` here.

## Upgrading from v1.4

This folder has a copy of your v1.4 `.env`. The database, reports and knowledge base carry over, and nothing new needs to be loaded.

1. Run `./stop.sh` in `../pfa-python-v1.4`.
2. Run `./start.sh` here.

Existing reports keep their content. Build a new plan (or change one from the chat) to get the Bank deposits section.

## Upgrading from v1.3

This folder has a copy of your v1.3 `.env`.

1. Run `./stop.sh` in `../pfa-python-v1.3`.
2. Run `./start.sh` here.

## Upgrading from v1.2

This folder has a copy of your v1.2 `.env` (same data).

1. Run `./stop.sh` in `../pfa-python-v1.2`.
2. Run `./start.sh` here.
3. Optionally set `VOICE_ENGINE=openai` in `.env` for the natural voice.

## Upgrading from v1.1

This folder has a copy of your v1.1 `.env`: same database, accounts, plans and knowledge base.

1. Run `./stop.sh` in `../pfa-python-v1.1`.
2. Add `SERPAPI_API_KEY=` to this folder's `.env`.
3. Run `./start.sh` here.

The first start updates the knowledge base with live data.

## Upgrading from v1.0

This folder already has a copy of your v1 `.env`, so the same database password is used and your accounts, plans and knowledge base carry over. Both versions use Docker project `pfapy`.

```bash
cd ../pfa-python-v1 && ./stop.sh
cd ../pfa-python-v1.1 && ./start.sh
```

The first start downloads the Phoenix image (about 1.6 GB on disk).

## AI cost per plan and per chat question

Every OpenAI call is metered (tokens in, cached, out, reasoning; time) and priced at the rates in `.env`:

- **Each report** ends with a line such as *"AI cost of this plan ₹0.37 ($0.0043) · 2 AI calls + 1 search · 6,778 tokens"*.
- **Each chat answer** shows its cost, tokens and time. Questions blocked by the guardrails cost ₹0.
- **Usage page** (top bar, **Usage**): your average cost per plan and per question, and every plan and question with its cost.
- **Team report:** `./scripts/usage-report.sh` lists plans, ₹ per plan, questions and ₹ per question for every user.

Measured with gpt-5-mini on 28 Sep 2026:

| Item | Cost | Tokens |
|---|---|---|
| One plan | ₹0.37-0.52 ($0.004-0.006) | ~7,000 |
| One chat question | ₹0.10-0.11 ($0.0012) | ~2,900 |

A what-if costs one question plus one new plan. Output tokens are about 80% of the cost. Prices and `USD_TO_INR` are settings in `.env`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Knowledge-base loading says **"Cannot reach api.openai.com from inside the app container"** or **"Name or service not known"** | Docker's DNS is stale. This usually happens after the Mac changes Wi-Fi or VPN, or wakes from sleep. **Colima:** `colima restart` (to make it stick: `colima start --dns 1.1.1.1 --dns 8.8.8.8`). **Docker Desktop:** restart it. Then run `./scripts/ingest-rag.sh`, which resumes. |
| `Cannot connect to the Docker daemon` | Docker isn't running: `colima start`, or open Docker Desktop. |
| The report never shows the AI text ("written from your numbers") | Check `OPENAI_API_KEY` in `.env`, then `docker compose logs app --tail 50`. The plan itself is unaffected. |
| `port is already allocated` | Change `APP_PORT`, `POSTGRES_PORT` or `PHOENIX_PORT` in `.env`, then run `./start.sh`. The n8n bundle's Phoenix also uses 6006. |
| No traces in Phoenix | Check `curl localhost:8080/healthz` shows `"tracing": true`, and see `docker compose logs phoenix`. Phoenix takes ~20 s to start after the app. |

## Please remember

- Use **made-up data** when testing.
- The advice is educational, not licensed financial advice. Market figures are historical (period ending 26 Aug 2026).
- The app is for local testing. Before putting it online:
  - serve it over https and set `COOKIE_SECURE=true`
  - update `PUBLIC_BASE_URL`
  - see the sign-up note above
