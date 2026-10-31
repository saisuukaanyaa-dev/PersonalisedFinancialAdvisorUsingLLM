# Personal Finance Advisor: team bundle v3.4 (final)

> **Start here: http://localhost:5678/webhook/pfa** (after `./start.sh`). Use Chrome, Edge or Safari.
>
> **New in v3.4** (details: [docs/V34_CHANGES.md](docs/V34_CHANGES.md))
> - **A real step form:** Back / Continue, a review page with Edit, checks as you type, a start page with your plan history.
> - **Report + chat on one page.** Ask for a change ("What if I invest 30K a month?"), press **Yes**, and a new **Updated plan** is built.
> - **Bank deposits inside the main flow:** one workflow and one chat. The separate deposit workflow and its chat are retired.
> - The teammate's tools are called as HTTP tools, so the chat keeps working even if that container is down.
>
> v3.3 and v3.2 are unchanged in their own folders.

## v3.3 notes

> **New in v3.3**
> - **The teammate's project runs inside the flow.** `PersonalisedFinancialAdvisorUsingLLM` (Python, LangGraph, Chroma hybrid RAG, llm_guard) is the `teammate-advisor` container, published as an MCP server. The advisor's follow-up chat and the deposit planner chat call it for bank-scheme rules and mutual-fund facts. Details: [docs/TEAMMATE_INTEGRATION.md](docs/TEAMMATE_INTEGRATION.md).
> - **Phoenix now shows every run.** The telemetry service reads each n8n run and sends it to Phoenix as a trace: agents, every LLM call with prompt, tokens and cost, retrieved chunks, tools and errors, grouped into sessions. Traces survive restarts. Details: [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md).
> - The first `./start.sh` builds the teammate image once: about 10-15 minutes and 3.3 GB. Give Docker at least **4 GB RAM**.
>
> Built on v3.2-obs-deposits, which is unchanged in its own folder. Earlier notes follow.

## v3.2 notes: observability + bank deposits

> **This version adds the team's bank deposit planner** (the LangGraph / MCP project), rebuilt as n8n nodes on gpt-5-mini.
> **Low risk (or a goal under 3 years) always runs the deposit planner.** The report gets a *Bank deposits* section with the exact RD sequence for the fixed-income money.
> The advisor's Investment Recommender and follow-up chat can also name concrete FD / RD options through MCP.
> Details: [docs/BANK_DEPOSITS.md](docs/BANK_DEPOSITS.md). The original v3.2 bundle is unchanged.
>
> - Deposit planner chat: retired in v3.4. Ask in the report-page chat instead.
> - Deposit MCP server: `http://localhost:5678/mcp/bank-deposits` (Bearer = `MCP_BEARER_TOKEN`)
> - Rate table: `deposits/memory.db` (SQLite) and Postgres table `deposit_schemes`, built by `python3 tools/build_deposit_db.py`

This is a self-contained local stack for testing the AI Personal Finance Advisor. One command starts everything:

- **n8n**, which runs the workflows: a conversational intake, 5 AI agents, RAG, guardrails, an MCP server and follow-up chat
- **Postgres 16 + pgvector**, which stores profiles, reports, chat memory and the knowledge-base vectors
- **market-analyzer**, a small Python API over the historical NIFTY 50 data

Everything runs on your machine, and all ports are bound to `localhost` only.

## Observability (Phoenix)

This bundle also runs **Phoenix** (http://localhost:6006), an LLM/OpenTelemetry dashboard, and a small **Telemetry API** (http://localhost:8001/health). The Telemetry API takes `POST /trace` with `session_id`, `node_name`, `step` and `state`, and forwards it to Phoenix as a span. In v3.3 the telemetry service also exports every n8n run automatically (see above).

Ports used: 5678 (n8n), 5433 (Postgres), 8000 (market API), 6006 (Phoenix), 8001 (Telemetry API), 8090 (teammate MCP service). Each can be changed in `.env` (`N8N_PORT`, `POSTGRES_PORT`, `MARKET_API_PORT`, `PHOENIX_PORT`, `TELEMETRY_PORT`, `TEAMMATE_MCP_PORT`).

## Before you start

| You need | Notes |
|---|---|
| Docker Desktop (or Docker Engine + Compose v2) | Give Docker at least **4 GB RAM**. |
| An **OpenAI API key** | Use your own key. Each full report makes about 6-10 `gpt-5-mini` calls (a few cents). |
| Free ports **5678, 5433, 8000** | If one is taken, change `N8N_PORT`, `POSTGRES_PORT` or `MARKET_API_PORT` in `.env`. |
| macOS or Linux terminal | On Windows, use **WSL 2** or **Git Bash**. |

## Start it (about 5 minutes the first time)

```bash
./start.sh
```

`start.sh`:
- creates `.env` with random secrets
- asks for your OpenAI key (hidden input)
- starts the containers
- sets up n8n automatically: credentials, workflows and activation
- loads the 830-document knowledge base into pgvector

When it finishes, it prints these links:

| What | Link |
|---|---|
| **Advisor app** (start here) | http://localhost:5678/webhook/pfa |
| Hosted chat (same assistant as the report page) | http://localhost:5678/webhook/5b46aa0d-dea0-4fee-9081-a432d5d484ce/chat |
| n8n editor (to inspect runs) | http://localhost:5678, where you create a local owner account on first visit |
| MCP endpoint | http://localhost:5678/mcp/pfa-finance-tools, using the Bearer token `MCP_BEARER_TOKEN` from `.env` |

Next, follow **[TESTING.md](TESTING.md)**.

## Everyday commands

| Command | Does |
|---|---|
| `./start.sh` | Start or restart. Re-run it after changing `.env`. |
| `./healthcheck.sh` | Status of every service, saved users and reports, RAG chunk count, OpenAI key. |
| `./stop.sh` | Stop the stack. Your data is kept. |
| `./reset.sh` | Delete **all** local data and start clean. It asks you to confirm. |
| `./scripts/ingest-rag.sh` | Load the knowledge base. It's resumable: it skips files already loaded and reloads changed ones. |
| `./scripts/ingest-rag.sh --force` | Wipe and reload the whole knowledge base. |
| `docker compose logs -f n8n` | Live n8n logs. |

To see exactly what each AI step did, open the n8n editor and go to **Executions**.

## What's inside

```text
pfa-team-bundle-v3.2/
├── start.sh  stop.sh  reset.sh  healthcheck.sh
├── docker-compose.yml         postgres, market-analyzer, n8n-setup (one-shot), n8n
├── .env.example               copied to .env by start.sh (never share your .env)
├── n8n/
│   ├── pfa_advisor_v3.4.json      the whole advisor: app pages, pipeline, chat, deposit planner, MCP servers (generated by tools/build_v34.py)
│   ├── src/                       readable sources of the app page, chat and Code nodes
│   ├── v33_source/                the v3.3 workflows the builder starts from
│   ├── pfa_rag_ingestion.json     knowledge-base loader (run by start.sh)
│   └── bootstrap/                 credential + import script used by n8n-setup
├── postgres/init/001_schema.sql   users, advice_sessions tables
├── postgres/deposits.sql          bank FD/RD rates (reloaded by start.sh on every start)
├── deposits/                      memory.db, deposit_schemes.csv, source/ bank markdown files,
│                                  teammate-fixes/ (their Python with the RD + inflation bugs fixed)
├── tools/                         build_deposit_db.py, build_deposits_workflow.py, deposit_optimiser.js, test/
├── market-analyzer/               historical NIFTY 50 API (Python, no dependencies)
├── teammate-advisor/              the teammate's project (teammate/, unchanged) + pfa_mcp_server.py (MCP wrapper)
├── telemetry/                     n8n runs -> Phoenix exporter (+ POST /trace)
├── data/                          NIFTY 50 CSVs (period ending 26 Aug 2026)
├── knowledge-base/                830 markdown documents for RAG
├── scripts/                       ingest-rag.sh, dataset helpers
└── docs/
    ├── PFA_Architecture_v3.2.pptx  architecture deck: every node explained
    ├── WORKFLOW_DESIGN.md          design notes and change history
    ├── ARCHITECTURE.md             data-store decisions
    └── sample-reports/             example reports (open in a browser)
```

## How n8n is set up for you

The `n8n-setup` container runs before n8n on every `./start.sh`. It:
1. Creates three credentials from `.env`: **Postgres account**, **OpenAI account** and **PFA MCP bearer token**.
2. Imports the three workflows and **activates** the deposit planner and the advisor.

It's safe to re-run: it overwrites the same credential and workflow IDs. If you change your OpenAI key in `.env`, run `./start.sh` again.

## Differences from the author's setup

- **Google Sheets logging is disabled.** It needs each person's Google OAuth. Reports are still saved in Postgres. To turn it on, open the editor, enable `Append to Google Sheets`, then pick your own credential and sheet.
- **RAG ingestion is a separate workflow**, *PFA · RAG ingestion (run once)*, so it can run from the command line.
- **The follow-up chat is a public hosted page on localhost**, so you can test it without the editor.

## Knowledge-base loading (RAG)

`scripts/rag-ingest.mjs` embeds the 830 documents (about 1,600 chunks) with `text-embedding-3-small`:

- It sends **96 chunks per request** and runs **4 requests in parallel**. That's about 20 API calls in total, instead of the 830 one-file-at-a-time calls the n8n node makes.
- Each request has a 60-second timeout. Rate limits (429) and network errors are retried with back-off, and `Retry-After` is honoured.
- Each group of files is committed in one transaction. If it stops for any reason, **run it again and it resumes**, with no duplicates and no half-loaded files.
- It writes the same table and format that n8n's `Knowledge_Base_Search` reads. Retrieval uses the same pinned model.

Tuning:

| Situation | Command |
|---|---|
| Faster (paid OpenAI tier) | `./scripts/ingest-rag.sh --concurrency 8 --batch 128` |
| Hitting rate limits (free / new account) | `./scripts/ingest-rag.sh --concurrency 2 --batch 48` |
| See what would be loaded, without calling OpenAI | `./scripts/ingest-rag.sh --dry-run` |

A full load normally takes **well under a minute** and costs about **$0.004** (~195K tokens). The workflow *PFA · RAG ingestion (run once)* is still in n8n for reference, but it's much slower. Use the script.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` | Change the port in `.env`, then `./start.sh`. |
| Form shows "Problem loading form" / 404 | `./healthcheck.sh`. If the form isn't OK, check `docker compose logs n8n-setup`. |
| Report never appears / AI step errors | Check that `OPENAI_API_KEY` in `.env` is valid, then `./start.sh`. Look in the editor under **Executions** for the red node. |
| Chat or recommender says it can't find knowledge | `./healthcheck.sh` shows *RAG chunks*. If it's 0, run `./scripts/ingest-rag.sh`. |
| Ingestion stopped part-way | Run `./scripts/ingest-rag.sh` again. It resumes. For repeated 429s, use `--concurrency 2 --batch 48`. |
| Updated files in this folder don't take effect | `./start.sh`. It always re-imports the workflows and restarts n8n. |
| `n8n-setup` fails with *Mismatching encryption keys* | Your `.env` was replaced after the first install. Put your original `.env` back. Or, if you don't need the data, run `docker compose -p pfa down -v` and then `./start.sh`. **Keep your `.env`** whenever you update the bundle folder. |
| Anything else | `./reset.sh` then `./start.sh`, which gives a clean install. |

## Please remember

- Use **made-up financial data** when testing. Real profiles are stored in the local database.
- The advice is **educational and not licensed financial advice**. The market data is historical, not live.
- Don't expose these ports to the internet. The bundle is for local testing only.
