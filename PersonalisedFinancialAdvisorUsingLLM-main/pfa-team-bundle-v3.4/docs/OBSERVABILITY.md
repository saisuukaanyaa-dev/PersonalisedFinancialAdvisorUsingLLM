# Observability with Phoenix (v3.3, updated in v3.4)

> **v3.4:** form submissions and confirmed chat changes are grouped per user (session `plans-<email>`), and report-page chats per conversation. Segments are named "build report", "plan change", "open report", "chat message". The building page's status checks are skipped.

Open **http://localhost:6006**. Two projects:

| Project | What's in it |
|---|---|
| `pfa-n8n` | every n8n run: the advisor form journey, the report build, each follow-up chat message, the deposit planner, its MCP calls |
| `pfa-teammate-advisor` | every call to the teammate's service: their RAG chains and LangGraph agents |

## What was wrong before v3.3

1. **No workflow ever sent a trace.** The telemetry API only accepted manual `POST /trace` calls, and no node made them, so Phoenix stayed empty during real use.
2. **Every event became its own trace,** with no grouping by user or run.
3. **FastAPI traced itself:** each manual event added "POST /trace", "fastapi.serialization" and similar spans, because the telemetry service set the *global* tracer provider and FastAPI picked it up.
4. **Traces were lost on every restart:** Phoenix had no volume.
5. **`image: latest`:** a new Phoenix release could change the dashboard on demo day.

## How it works now

```
n8n ──(runs saved in Postgres: execution_data)──► telemetry exporter ──OTLP──► Phoenix  (project pfa-n8n)
teammate service ──OpenInference LangChain instrumentation──OTLP──────────────► Phoenix  (project pfa-teammate-advisor)
```

- **No workflow changes.** n8n already stores, for every node: start time, duration, status, output, and for AI nodes the prompt and **token usage**. The telemetry service polls Postgres every 5 seconds and converts each new run segment into one trace.
- **One trace per segment.** A form journey pauses at every page, so each page is a short trace, and the report build is one trace with all four agents. Each chat message is one trace.
- **Sessions.** All traces of one advisor journey share `session.id = n8n-exec-<execution id>`, and each chat conversation shares `chat-<sessionId>`. Phoenix's **Sessions** tab shows a whole journey or conversation in order. `user.id` is the email from the intake form.
- **Span kinds** (OpenInference), so Phoenix shows the right icons and panels:

| n8n node | Phoenix span |
|---|---|
| AI Agent nodes | AGENT |
| OpenAI chat model sub-nodes | **LLM**: prompt messages, answer, `llm.model_name`, token counts, `pfa.cost_usd` |
| Knowledge_Base_Search | RETRIEVER, with the retrieved chunks |
| Embeddings | EMBEDDING (query text; the vector itself is not stored) |
| Market tools, MCP clients, sub-workflows | TOOL |
| Guardrails nodes | GUARDRAIL |
| Code, If, Postgres, forms | CHAIN, with the node's output |

  Sub-nodes are nested under their agent: an LLM call sits under the agent that made it, and an embedding under its retrieval.
- **Errors:** a failed node is a red span with n8n's error message, and the run's root span turns red.
- **No duplicates:** what has been sent is recorded in the table `pfa_trace_export` (execution id → node runs sent), so restarts don't resend anything. On first start, runs from the last 24 hours are sent (`TRACE_BACKFILL_HOURS` in `.env`).
- **Cost:** `pfa.cost_usd` per LLM span, and summed on each root span, uses the list prices in `telemetry/main.py` (gpt-5-mini $0.25 / $2.00 per 1M tokens).
- `POST /trace` still works for custom events, now grouped by `session_id`.
- Phoenix is pinned to v20.16.0 and stores its data in the volume `pfa_phoenix_data`.

## What to show in the demo

1. Run one advisor journey. In `pfa-n8n`, open the **"build report"** trace. The timeline shows Debt and Portfolio agents in parallel, then the Recommender's tool calls (Knowledge_Base_Search with the retrieved chunks), then the Report agent. Click an LLM span to see the exact prompt, the answer, the tokens and the cost.
2. Open **Sessions** and pick `n8n-exec-<id>`: the whole journey, page by page.
3. Ask the follow-up chat about a bank scheme ("What is the premature withdrawal penalty on Canara Bank RDs?"). The chat trace shows the `Teammate_Advisor_MCP` tool. Then open `pfa-teammate-advisor`: the same question inside the teammate's service, with the reranked context sent to gpt-4.1.

## Check it's working

```bash
curl -s localhost:8001/health
```

This prints `executions_exported`, `spans_exported`, `last_poll` and `last_error`. `./healthcheck.sh` shows the same in one line.

## Next steps

- Phoenix **evaluations** on the stored LLM spans: faithfulness of chat answers against the retrieved chunks.
- Alerts on red traces: failed agents, MCP timeouts.
- n8n 2.36 also has built-in OpenTelemetry (`N8N_OTEL_*`). It gives timings only, with no prompts or tokens, which is why the exporter reads n8n's own run data instead.
