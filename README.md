# Personalised Financial Advisor using LLM

An AI financial advisor for Indian users, built by our team as the capstone project for the
**TalentSprint Certification Program in Applied Generative AI and Agentic AI**.

A user describes their income, savings, loans, goals and risk level. The advisor searches trusted data
(NIFTY 50 history, Indian tax rules, bank deposit schemes and mutual fund documents) and returns a
goal-based plan with charts, then answers follow-up questions in a chat. Wherever possible the numbers come
from plain code, and the AI is used to explain them and to answer questions from retrieved documents.

> **Educational project only.** Nothing here is certified financial advice. Always check rates and scheme
> terms with the bank or a licensed advisor before investing.

---

## What is in this repository

This repository holds three projects that share the same idea. They are three stages of the same system,
not three separate products.

| Folder | What it is | Stack |
|---|---|---|
| [`BankDepositsMCP`](#1-bankdepositsmcp) | The bank-deposit and mutual-fund agent: finds the best FD/RD plan for a goal, answers questions from RAG, and is published as an MCP server | Python, LangGraph, ChromaDB, llm-guard, MCP |
| [`pfa-team-bundle-v3.4`](#2-pfa-team-bundle-v34-n8n--docker) | The advisor built as n8n workflows: conversational intake, AI agents, RAG, guardrails, MCP servers, follow-up chat | n8n, Docker, Postgres + pgvector, Phoenix, OpenAI |
| [`pfa-python-v1.7`](#3-pfa-python-v17-python-web-app) | The advisor rebuilt as a fast Python web app, following mentor feedback | FastAPI, Postgres + pgvector, Phoenix, OpenAI |

```text
BankDepositsMCP/          bank-deposit agent + MCP server (standalone, uv)
pfa-team-bundle-v3.4/     n8n + Docker edition (start.sh)
pfa-python-v1.7/          Python web app edition (start.sh)
```

### How the pieces fit together

```text
                         ┌────────────────────────────────────────────┐
                         │  Shared data                               │
                         │  NIFTY 50 history · 830-document knowledge │
                         │  base · tax rules · bank FD/RD rate table  │
                         └───────────────┬────────────────────────────┘
                                         │
        ┌────────────────────────────────┼─────────────────────────────────┐
        │                                │                                 │
┌───────▼───────────┐          ┌─────────▼──────────┐           ┌──────────▼─────────┐
│ BankDepositsMCP   │  MCP /   │ pfa-team-bundle    │  same     │ pfa-python-v1.7    │
│ LangGraph agent,  │◄─ HTTP ──┤ v3.4 (n8n)         │  logic    │ FastAPI web app    │
│ RAG, guardrails   │  tools   │ 5 AI agents, chat  │ ported ──►│ numbers in ~0.05 s │
└───────────────────┘          └────────────────────┘           └────────────────────┘
```

The bank-deposit agent is used inside both advisors: the n8n bundle runs it as a container
(`teammate-advisor`) and calls it as tools, and the Python app uses the same deposit maths and rate table.

### Which one should I run?

| I want to... | Run |
|---|---|
| See the full advisor quickly, with sign-in, voice and multi-goal planning | `pfa-python-v1.7` |
| See the n8n workflow, agents and MCP servers, and inspect every run | `pfa-team-bundle-v3.4` |
| Study the bank-deposit search, RAG and guardrails code, or run the MCP server alone | `BankDepositsMCP` |

---

## Requirements

| You need | Notes |
|---|---|
| Docker Desktop (or Docker Engine + Compose v2) | Give Docker at least **4 GB RAM**. |
| An **OpenAI API key** | Use your own. A full report costs a few cents. |
| macOS, Linux, or Windows with **WSL 2 / Git Bash** | The `start.sh` scripts are bash scripts. |
| `uv` and Python 3.13 | Only for running `BankDepositsMCP` without Docker. |

**Never commit a `.env` file.** It holds your API key and generated secrets. Each project ships a
`.env.example` to copy from.

### Default ports

| Port | Used by |
|---|---|
| 5678 | n8n (bundle) |
| 5433 | Postgres (bundle) |
| 8000 | Market API (bundle and Python app) |
| 6006 | Phoenix dashboard |
| 8001 | Telemetry API (bundle) |
| 8090 | Bank-deposit MCP service (bundle's `teammate-advisor`, and `BankDepositsMCP` when run through Docker) |
| 8080 | Python web app |
| 5434 | Postgres (Python app) |

The Python app and the n8n bundle use different ports, so both can run at once. Two things use port 8090,
so do not run the bundle and the standalone `BankDepositsMCP` Docker setup together, or change `MCP_PORT`.

---

## 1. BankDepositsMCP

The bank-deposit and mutual-fund agent. It answers "which bank deposit should I use to reach my goal?" and
general questions about deposit schemes and mutual funds, using only the documents it has stored.

### What it does

- **Optimal Bank Deposit Finder agent** (LangGraph). Given savings, monthly money, a target amount and a
  date, it searches combinations of fixed deposits (FD) and recurring deposits (RD) across banks and returns
  the sequence that reaches the goal, adjusted for inflation.
- **Financial General Information chatbot.** Answers questions about bank deposit schemes and mutual funds
  from RAG databases that are built on first run.
- **MCP server.** Publishes the finder as a `GetBestBankDepositScheme` tool, so other agents (for example the
  n8n workflow) can call it.
- **Guardrails** (`GaurdRails.py`, using `llm-guard`). Input scanners block known prompt-injection phrases and
  over-long prompts. An output scanner checks the reply before it is shown.
- **RAG evaluation.** Test scripts and metrics for the retrieval quality (`RagEvaluationTest.py`,
  `testsScriptForNumericalRag.py`, and the write-up in `Documentation/`).

### Data

| Folder | Contents |
|---|---|
| `IndianBankDeposits/` | Detailed and summary scheme documents for 10 banks: SBI, HDFC, ICICI, Axis, Kotak, PNB, Canara, Bank of Baroda, IDFC FIRST and IndusInd, plus test cases |
| `IndianMutualFunds/` | Summaries of 9 mutual funds (large-cap, flexi-cap, small-cap and focused), plus test cases |
| `memory.db` | SQLite table of deposit rates, built by `source/DatabaseCreator.py` |
| `chroma_dbBankDeposit/`, `chroma_dbMutualFund/` | ChromaDB vector stores for retrieval |

### How the search works

The finder treats the goal as a state-space search. Each state holds the money so far, the date and the
deposits already opened. Each action opens a deposit, and a result is accepted when the final balance, after
inflation, reaches the target. The FD and RD maturity formulas, the inflation adjustment, and the places where
the code and the written formulas differ are documented in `DEVELOPER_GUIDE.md`. The LaTeX write-ups are in
`Documentation/`.

### Run it

```bash
cd BankDepositsMCP
cp .env.example .env          # add your OPENAI_API_KEY (and any optional keys)
uv sync                       # creates .venv with the locked dependencies
```

| Task | Command |
|---|---|
| Build the deposit database | `uv run python source/DatabaseCreator.py` |
| Run the optimal deposit finder on a test prompt | `uv run python source/OptimalBankDepositFinderAgent.py` |
| Run the deposit and mutual-fund chatbot | `uv run python source/FinancialGeneralInformationChatBot.py` |
| Open LangGraph Studio | `uv run python -m langgraph_cli dev` |
| Start the MCP server | `uv run mcp run source/MCPServerForOptimalBankDepositFinderAgent.py` |
| Debug the MCP server in the Inspector | `uv run mcp dev source/MCPServerForOptimalBankDepositFinderAgent.py` |

Or run the MCP service with Docker: `docker compose up bank-deposit-mcp` (serves on port 8090).

Optional environment keys: `SERPAPI_API_KEY`, `ALPHA_VANTAGE_KEY`, and the `LANGSMITH_*` variables to see
traces in LangSmith.

---

## 2. pfa-team-bundle-v3.4 (n8n + Docker)

A self-contained local stack that runs the whole advisor as n8n workflows. One command starts everything.

### What is inside

| Service | What it does |
|---|---|
| **n8n** | Runs the workflows: conversational intake, 5 AI agents, RAG, guardrails, MCP servers and the follow-up chat |
| **Postgres 16 + pgvector** | Stores profiles, reports, chat memory and the knowledge-base vectors |
| **market-analyzer** | Small Python API over the historical NIFTY 50 data |
| **teammate-advisor** | The `BankDepositsMCP` project, running as a container and exposed as an MCP server and HTTP tools |
| **Phoenix** | LLM and OpenTelemetry dashboard at http://localhost:6006 |
| **telemetry** | Reads each n8n run and sends it to Phoenix as a trace (agents, every LLM call, retrieved chunks, tools, errors) |

### Features (v3.4)

- **A real step form.** Back and Continue buttons, checks as you type, a review page with Edit, and a start
  page with your plan history.
- **Report and chat on one page.** Ask "What if I invest 30K a month?" and press **Yes** to build an
  **Updated plan**. Changes are always previewed and confirmed before anything is applied.
- **Bank deposits inside the main flow.** Low risk, or a goal under 3 years, always runs the deposit planner
  and adds a *Bank deposits* section with the exact RD sequence.
- **RAG over an 830-document knowledge base** (NIFTY 50 analysis and Indian tax rules, about 1,600 chunks,
  embedded with `text-embedding-3-small` into pgvector).
- **Guardrails.** A goal-text guardrail neutralises prompt-injection attempts before the text reaches an
  agent. The chat refuses off-topic requests, refuses ID numbers (for example PAN) and never predicts
  stock prices.
- **MCP servers.** `/mcp/pfa-finance-tools` and `/mcp/bank-deposits` (Bearer token from `.env`).
- **Observability.** Every run appears in Phoenix, grouped into sessions.
- **Resilient tools.** The teammate service is called as HTTP tools, so the chat keeps working even if that
  container is down.

### Run it

```bash
cd pfa-team-bundle-v3.4
./start.sh
```

`start.sh` creates `.env` with random secrets, asks for your OpenAI key (hidden input), starts the
containers, sets up n8n (credentials, workflows, activation) and loads the knowledge base. The first run
builds the `teammate-advisor` image once, which takes about 10 to 15 minutes and 3.3 GB.

| Link | What |
|---|---|
| http://localhost:5678/webhook/pfa | **The advisor app. Start here.** Use Chrome, Edge or Safari |
| http://localhost:5678 | n8n editor (create a local owner account on first visit) |
| http://localhost:6006 | Phoenix dashboard |
| http://localhost:5678/mcp/pfa-finance-tools | MCP endpoint (Bearer token `MCP_BEARER_TOKEN` from `.env`) |

| Command | Does |
|---|---|
| `./start.sh` | Start or restart. Run it again after changing `.env` |
| `./healthcheck.sh` | Status of every service, saved users and reports, RAG chunk count, OpenAI key |
| `./stop.sh` | Stop. Your data is kept |
| `./reset.sh` | Delete all local data and start clean (asks first) |
| `./scripts/ingest-rag.sh [--force]` | Load or reload the knowledge base. Resumable |

Notes: Google Sheets logging is disabled by default because it needs each person's own Google OAuth. Reports
are still saved in Postgres. If you see "No `.env` found, but data from an earlier install exists", either
restore your old `.env` or wipe the old data (see the message `start.sh` prints).

### Where to read more

`README.md` and `TESTING.md` inside the folder, and `docs/` (architecture, workflow design, bank deposits,
observability, teammate integration, demo flow, step-by-step node testing, and sample reports).
`TESTING.md` has a full test plan with scenarios for the form, the chat and the guardrails.

---

## 3. pfa-python-v1.7 (Python web app)

The advisor rebuilt as a small, modular Python web app. It keeps the same logic as the n8n version but is much
faster: the numbers and charts open in about 0.05 seconds, and the AI explanation is written in the
background and appears a few seconds later.

### Features

- **Conversational start.** A chat with **Arth**, the advisor. Describe yourself, your goal and your money in
  your own words, typed or spoken, and the profile panel fills in. The 5-step form is still there.
- **Up to 4 goals.** Each has an amount, a date and a priority (must-have or nice-to-have). Money is shared
  in code: must-have first, then the nearest date. Each goal gets its own risk level for its own date.
- **"What if a new goal comes up?"** An instant calculator compares three options: save for it separately,
  use the main goal's savings, or wait.
- **Report that opens with the goal projection.** Verdict, progress ring, target vs projected, a
  projection chart, then the monthly plan, risk profile and safety-net meters.
- **Bank deposit planner.** For low-risk or short goals, with the FD/RD sequence and the banks named.
- **Chat that can change the plan.** Changes are shown and confirmed first, then a link to the updated report
  is given.
- **Voice.** Optional voice for the form and chat (free browser voice, or an optional natural voice).
- **Sign-in.** Email and password (hashed with scrypt, failed logins throttled), and optional Google sign-in.
- **Live data (optional).** SerpAPI refreshes the knowledge base with today's NIFTY 50 level and recent
  prices, with a cache and a monthly budget.
- **Evaluation and cost tracking.** A 30-question retrieval evaluation, a conversation evaluation, and a
  per-user AI cost report.
- **Observability.** OpenTelemetry traces exported to Phoenix.

### Privacy and safety

Reports are visible only to the account that owns them. Sessions use signed, HTTP-only cookies. Write APIs
need an anti-CSRF header. A strict Content-Security-Policy allows no external scripts. ID numbers typed into the
chat are refused and masked in any AI output.

### Run it

```bash
cd pfa-python-v1.7
./start.sh
```

Then open **http://localhost:8080**, create an account and follow the five short steps. `start.sh` creates
`.env`, asks for your OpenAI key (optional, but needed for the AI text and chat), builds three containers and
loads the knowledge base (1,632 chunks, about 20 seconds).

| Command | Does |
|---|---|
| `./start.sh` | Start or restart |
| `./healthcheck.sh` | Service status, AI and Google on or off, knowledge-base chunks, accounts and plans |
| `./stop.sh` | Stop. Data is kept |
| `./reset.sh` | Delete all local data |
| `./scripts/usage-report.sh` | AI cost per user and per question |

Email and password sign-up does not verify that the person owns the address. That is fine for local testing.
For a public deployment, use Google sign-in only or add email verification.

### Where to read more

`README.md` and `TESTING.md` inside the folder, `docs/ARCHITECTURE.html`, `docs/MULTI_GOAL.md` and
`docs/COST_AND_PERFORMANCE.md`. Unit tests are in `tests/`.

---

## Data

- **NIFTY 50 history.** Daily prices, annual return, volatility and drawdown for the index constituents
  (period ending August 2026). Companies with no price data are marked unavailable rather than filled in.
- **Knowledge base.** 830 markdown documents generated from that dataset, plus Indian tax rules.
- **Bank deposits.** Scheme documents and a rate table for 10 banks.
- **Mutual funds.** Summaries of 9 funds.

## Tech stack

Python 3.13, FastAPI, LangGraph, LangChain, n8n, Model Context Protocol (MCP), ChromaDB, Postgres with
pgvector, sentence-transformers and cross-encoder reranking, BM25 hybrid retrieval, llm-guard, Arize Phoenix
and OpenTelemetry, LangSmith, Docker and OpenAI models.

## Credits

Built by the project team as part of the TalentSprint Applied Generative AI and Agentic AI program.
