"""PFA Telemetry: turns n8n workflow runs into Phoenix traces.

Every few seconds it reads finished (or paused) n8n executions from Postgres and sends one trace per run
segment to Phoenix, in the OpenInference format Phoenix understands:

  root span      one per segment (a form step, the report build, one chat message, one deposit plan)
  AGENT spans    the AI Agent nodes (Debt, Portfolio, Recommender, Report, Q&A, Deposit Planner)
  LLM spans      each gpt-5-mini call, with the prompt, the answer, token counts, model and cost
  RETRIEVER      Knowledge_Base_Search (pgvector), with the retrieved chunks
  TOOL           market tools, MCP tools (bank deposits, the teammate's service), sub-workflows
  GUARDRAIL      the Guardrails nodes
  CHAIN          every other node (Code, If, Postgres, forms), with its output

All spans of one advisor journey share session.id = "n8n-exec-<id>" and each chat conversation shares
session.id = "chat-<sessionId>", so Phoenix's Sessions tab shows a whole journey or conversation together.

No workflow changes are needed: n8n already stores every node's start time, duration, output, prompt and
token usage in execution_data. What has been sent is remembered in the table pfa_trace_export, so nothing
is sent twice, even after a restart.

POST /trace (session_id, node_name, step, state) still works for custom events.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import psycopg
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

log = logging.getLogger("pfa-telemetry")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://phoenix:6006/v1/traces")
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "pfa-n8n")
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "5"))
BACKFILL_HOURS = int(os.getenv("BACKFILL_HOURS", "24"))
EXPORT_N8N = os.getenv("EXPORT_N8N_EXECUTIONS", "true").lower() == "true"
MAX_ATTR = int(os.getenv("MAX_ATTRIBUTE_CHARS", "8000"))
DSN = (f"host={os.getenv('PGHOST', 'postgres')} port={os.getenv('PGPORT', '5432')} dbname={os.getenv('PGDATABASE', 'finance_advisor')} "
       f"user={os.getenv('PGUSER', 'pfa')} password={os.getenv('PGPASSWORD', '')}")

# USD per 1M tokens (input, output). Used for the pfa.cost_usd attribute; Phoenix also prices known models itself.
PRICES = {"gpt-5-mini": (0.25, 2.00), "gpt-5": (1.25, 10.0), "gpt-4.1": (2.0, 8.0), "gpt-4.1-mini": (0.40, 1.60),
          "gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.0), "text-embedding-3-small": (0.02, 0.0)}

# A provider of our own, NOT the global one: FastAPI picks up a global tracer provider and would trace its own
# request handling (the "POST /trace", "fastapi.serialization" noise seen in Phoenix before).
provider = TracerProvider(resource=Resource.create({
    "service.name": "pfa-n8n", "service.version": "3.3", "openinference.project.name": PROJECT}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=PHOENIX_ENDPOINT)))
tracer = provider.get_tracer("pfa-n8n")

app = FastAPI(title="PFA Telemetry API")
stats: dict[str, Any] = {"exporter": "on" if EXPORT_N8N else "off", "executions_exported": 0, "segments_exported": 0,
                         "spans_exported": 0, "last_poll": None, "last_error": None}


# ============================================================== helpers
def parse_flatted(text: str) -> Any:
    """n8n stores execution data in the 'flatted' format: one JSON array where strings inside objects and
    arrays are indexes of other entries."""
    arr = json.loads(text)
    out: list[Any] = [None] * len(arr)
    done = [False] * len(arr)

    def rev(i: int) -> Any:
        if done[i]:
            return out[i]
        v = arr[i]
        if isinstance(v, list):
            res: list = []
            out[i], done[i] = res, True
            res.extend(rev(int(x)) if isinstance(x, str) else x for x in v)
            return res
        if isinstance(v, dict):
            res2: dict = {}
            out[i], done[i] = res2, True
            for k, x in v.items():
                res2[k] = rev(int(x)) if isinstance(x, str) else x
            return res2
        out[i], done[i] = v, True
        return v
    return rev(0)


def clip(v: Any) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= MAX_ATTR else s[:MAX_ATTR] + f"… [{len(s) - MAX_ATTR} more characters]"


def ns(ms: float) -> int:
    return int(ms * 1_000_000)


def first_json(items: Any) -> Any:
    """First item's json from a node output like [[{json: …}]]."""
    try:
        return items[0][0]["json"]
    except (IndexError, KeyError, TypeError):
        return None


def kind_of(node_type: str, data_keys: list[str]) -> str:
    t = node_type.lower()
    if "guardrails" in t:
        return "GUARDRAIL"
    if t.endswith(".agent") or "agent" in t.split(".")[-1]:
        return "AGENT"
    if "lmchat" in t or "ai_languageModel" in data_keys:
        return "LLM"
    if "embeddings" in t or "ai_embedding" in data_keys:
        return "EMBEDDING"
    if "vectorstore" in t:
        return "RETRIEVER"
    if "ai_tool" in data_keys or t.endswith("tool") or "mcpclient" in t or "executeworkflow" in t:
        return "TOOL"
    return "CHAIN"


def model_of(node: dict) -> str | None:
    m = (node or {}).get("parameters", {}).get("model")
    if isinstance(m, dict):
        m = m.get("value")
    return m if isinstance(m, str) and m else None


# ============================================================== one run segment -> one trace
def node_attrs(name: str, run: dict, node: dict, ctx: dict) -> tuple[dict, str, float, float]:
    """OpenInference attributes for one node run. Returns (attributes, kind, prompt_tokens, completion_tokens)."""
    data = run.get("data") or {}
    keys = list(data.keys())
    ntype = (node or {}).get("type", "")
    kind = kind_of(ntype, keys)
    a: dict[str, Any] = {"openinference.span.kind": kind, "n8n.node.name": name, "n8n.node.type": ntype,
                         "n8n.execution.id": ctx["execution_id"], "n8n.workflow.name": ctx["workflow_name"],
                         "session.id": ctx["session"]}
    if ctx.get("user"):
        a["user.id"] = ctx["user"]
    override = (run.get("inputOverride") or {})
    pin = pout = 0.0

    if kind == "LLM":
        model = model_of(node)
        payload = first_json(data.get("ai_languageModel")) or {}
        usage = payload.get("tokenUsage") or payload.get("tokenUsageEstimate") or {}
        pin, pout = float(usage.get("promptTokens") or 0), float(usage.get("completionTokens") or 0)
        msgs = (first_json(override.get("ai_languageModel")) or {}).get("messages") or []
        gens = ((payload.get("response") or {}).get("generations") or [[]])
        answer = " ".join(g.get("text", "") for g in (gens[0] if gens else []) if isinstance(g, dict))
        a.update({"llm.provider": "openai", "llm.system": "openai", "llm.token_count.prompt": int(pin),
                  "llm.token_count.completion": int(pout), "llm.token_count.total": int(pin + pout),
                  "input.value": clip("\n\n".join(m if isinstance(m, str) else json.dumps(m) for m in msgs)),
                  "output.value": clip(answer)})
        if model:
            a["llm.model_name"] = model
            price = PRICES.get(model)
            if price:
                a["pfa.cost_usd"] = round(pin / 1e6 * price[0] + pout / 1e6 * price[1], 6)
        for i, m in enumerate(msgs[:20]):
            text = m if isinstance(m, str) else json.dumps(m)
            role = "system" if text.startswith("System:") else "user" if text.startswith("Human:") else "user"
            a[f"llm.input_messages.{i}.message.role"] = role
            a[f"llm.input_messages.{i}.message.content"] = clip(text)
        a["llm.output_messages.0.message.role"] = "assistant"
        a["llm.output_messages.0.message.content"] = clip(answer)
    elif kind == "EMBEDDING":
        q = first_json(override.get("ai_embedding")) or {}
        a.update({"embedding.model_name": model_of(node) or "", "input.value": clip(q.get("query") or q),
                  "output.value": "embedding vector (not stored in the trace)"})
    elif kind in ("RETRIEVER", "TOOL") and ("ai_tool" in keys or "ai_tool" in override):
        q = first_json(override.get("ai_tool")) or {}
        resp = (first_json(data.get("ai_tool")) or {}).get("response", first_json(data.get("ai_tool")))
        a.update({"input.value": clip(q.get("query", q)), "output.value": clip(resp)})
        if kind == "RETRIEVER" and isinstance(resp, list):
            for i, doc in enumerate(resp[:10]):
                text = doc.get("text") if isinstance(doc, dict) else doc
                try:
                    content = json.loads(text).get("pageContent", text)
                except (TypeError, ValueError, AttributeError):
                    content = text
                a[f"retrieval.documents.{i}.document.content"] = clip(content)
        a["tool.name"] = name
    else:
        out = first_json(data.get("main")) if "main" in data else first_json(next(iter(data.values()), None))
        if out is not None:
            a["output.value"] = clip(out)
            a["output.mime_type"] = "application/json" if not isinstance(out, str) else "text/plain"
        src = run.get("source") or []
        if src and isinstance(src[0], dict) and src[0].get("previousNode"):
            a["input.value"] = f"from {src[0]['previousNode']}"
    meta = run.get("metadata") or {}
    if isinstance(meta.get("subExecution"), dict):
        a["n8n.sub_execution.id"] = str(meta["subExecution"].get("executionId"))
    if run.get("executionStatus") == "waiting":
        a["n8n.waiting_for"] = "the user (form page shown)"
    return a, kind, pin, pout


def export_segment(ctx: dict, runs: list[tuple[str, int, dict]], nodes: dict, final_status: str) -> int:
    """runs: (node name, run index, run data) sorted by start time. Sends one trace; returns spans sent."""
    starts = [r["startTime"] for _, _, r in runs]
    ends = [r["startTime"] + (r.get("executionTime") or 0) for _, _, r in runs]
    main_runs = [(n, i, r) for n, i, r in runs if not (r.get("metadata") or {}).get("subRun")]
    last = main_runs[-1][0] if main_runs else runs[-1][0]
    first = main_runs[0] if main_runs else runs[0]
    wf_short = ctx["workflow_name"].split(" + ")[0]
    names = [n for n, _, _ in runs]
    segment = ("build report" if "Render Report Card" in names
               else "plan change" if "Apply Plan Change" in names
               else "open report" if "Render Report Page" in names
               else "app page" if "Render App Page" in names
               else "look up user" if "Lookup Result" in names
               else "chat message" if ctx["session"].startswith("chat-") else last)
    root = tracer.start_span(f"{wf_short} · {segment}", start_time=ns(min(starts)), attributes={
        "openinference.span.kind": "AGENT" if ctx["session"].startswith("chat-") else "CHAIN",
        "session.id": ctx["session"], "n8n.execution.id": ctx["execution_id"], "n8n.workflow.name": ctx["workflow_name"],
        "n8n.execution.mode": ctx["mode"], "n8n.execution.status": final_status, "n8n.nodes_in_segment": len(runs),
        **({"user.id": ctx["user"]} if ctx.get("user") else {}),
        "input.value": clip(ctx.get("input") or f"{first[0]}"), "output.value": clip(
            first_json((main_runs[-1][2].get("data") or {}).get("main")) if main_runs else "")})
    spans: dict[tuple[str, int], Any] = {}
    sent, cost, tokens = 1, 0.0, 0.0
    root_ctx = trace.set_span_in_context(root)
    for name, idx, run in runs:
        src = (run.get("source") or [{}])[0] or {}
        parent = spans.get((src.get("previousNode"), src.get("previousNodeRun", 0))) if (run.get("metadata") or {}).get("subRun") else None
        attrs, kind, pin, pout = node_attrs(name, run, nodes.get(name, {}), ctx)
        attrs["n8n.run_index"] = idx
        span = tracer.start_span(name, context=trace.set_span_in_context(parent) if parent else root_ctx,
                                 start_time=ns(run["startTime"]), attributes=attrs)
        err = run.get("error")
        if err or run.get("executionStatus") == "error":
            msg = (err or {}).get("message", "node failed") if isinstance(err, dict) else str(err)
            span.set_status(Status(StatusCode.ERROR, msg))
            span.add_event("exception", {"exception.message": msg})
        else:
            span.set_status(Status(StatusCode.OK))
        span.end(end_time=ns(run["startTime"] + (run.get("executionTime") or 0)))
        spans[(name, idx)] = span
        cost += attrs.get("pfa.cost_usd", 0.0)
        tokens += pin + pout
        sent += 1
    root.set_attribute("pfa.cost_usd", round(cost, 6))
    root.set_attribute("pfa.tokens.total", int(tokens))
    root.set_status(Status(StatusCode.ERROR, "execution failed") if final_status in ("error", "crashed")
                    else Status(StatusCode.OK))
    root.end(end_time=ns(max(ends)))
    return sent


# ============================================================== polling n8n's executions
SQL_CANDIDATES = """
SELECT e.id, e.status, e.mode, w.name, d.data, x.keys, x.sig,
       e.status || ':' || pg_column_size(d.data) AS new_sig
FROM execution_entity e
JOIN execution_data d ON d."executionId" = e.id
LEFT JOIN workflow_entity w ON w.id = e."workflowId"
LEFT JOIN pfa_trace_export x ON x.execution_id = e.id
WHERE e."deletedAt" IS NULL AND e.status NOT IN ('running', 'new')
  AND e."startedAt" > now() - make_interval(hours => %s)
  AND (x.sig IS NULL OR x.sig <> e.status || ':' || pg_column_size(d.data))
ORDER BY e.id
LIMIT 25
"""


def session_and_user(eid: int, d: dict, run_data: dict) -> tuple[str, str | None, str | None]:
    # v3.4: both chat doors (report page and hosted chat) go through "Chat Context"
    ctx = first_json((run_data.get("Chat Context") or [{}])[0].get("data", {}).get("main")) if "Chat Context" in run_data else None
    if isinstance(ctx, dict) and ctx.get("sessionId"):
        return f"chat-{ctx['sessionId']}", ctx.get("user_key") or None, ctx.get("chatInput")
    # v3.4: a plan built from the step form or a confirmed chat change - one session per user
    prof = first_json((run_data.get("Build Financial Profile") or [{}])[0].get("data", {}).get("main")) if "Build Financial Profile" in run_data else None
    if isinstance(prof, dict) and prof.get("user_key"):
        return f"plans-{prof['user_key']}", prof["user_key"], None
    chat = first_json((run_data.get("Chat Trigger") or [{}])[0].get("data", {}).get("main")) if "Chat Trigger" in run_data else None
    if isinstance(chat, dict) and chat.get("sessionId"):
        return f"chat-{chat['sessionId']}", None, chat.get("chatInput")
    form = first_json((run_data.get("Intake Form") or [{}])[0].get("data", {}).get("main")) if "Intake Form" in run_data else None
    user = form.get("Your email") if isinstance(form, dict) else None
    parent = d.get("parentExecution") or {}
    if parent.get("executionId"):
        return f"n8n-exec-{parent['executionId']}", user, None
    return f"n8n-exec-{eid}", user, None


def poll_once(conn: psycopg.Connection) -> None:
    rows = conn.execute(SQL_CANDIDATES, (BACKFILL_HOURS,)).fetchall()
    for eid, status, mode, wf_name, raw, keys, _sig, new_sig in rows:
        done = set(keys or [])
        try:
            d = parse_flatted(raw)
            run_data = (d.get("resultData") or {}).get("runData") or {}
            wf = conn.execute('SELECT "workflowData" FROM execution_data WHERE "executionId" = %s', (eid,)).fetchone()[0]
            nodes = {n["name"]: n for n in (wf or {}).get("nodes", [])}
            new = sorted(((n, i, r) for n, rl in run_data.items() for i, r in enumerate(rl)
                          if f"{n}#{i}" not in done and r.get("startTime")), key=lambda x: (x[2]["startTime"], x[2].get("executionIndex", 0)))
            if "Report Status" in run_data:          # the building page's status polls: not worth a trace each
                new = []
            if new:
                session, user, chat_input = session_and_user(eid, d, run_data)
                ctx = {"execution_id": str(eid), "workflow_name": wf_name or "n8n workflow", "session": session,
                       "user": user, "mode": mode, "input": chat_input}
                stats["spans_exported"] += export_segment(ctx, new, nodes, status)
                stats["segments_exported"] += 1
                done.update(f"{n}#{i}" for n, i, _ in new)
            first_time = keys is None
            conn.execute("""INSERT INTO pfa_trace_export (execution_id, sig, keys) VALUES (%s, %s, %s)
                            ON CONFLICT (execution_id) DO UPDATE SET sig = EXCLUDED.sig, keys = EXCLUDED.keys, exported_at = now()""",
                         (eid, new_sig, json.dumps(sorted(done))))
            conn.commit()
            if first_time:
                stats["executions_exported"] += 1
        except Exception as exc:                                    # one bad execution must not stop the others
            conn.rollback()
            stats["last_error"] = f"execution {eid}: {type(exc).__name__}: {exc}"
            log.exception("could not export execution %s", eid)
            conn.execute("""INSERT INTO pfa_trace_export (execution_id, sig, keys) VALUES (%s, %s, %s)
                            ON CONFLICT (execution_id) DO UPDATE SET sig = EXCLUDED.sig""", (eid, new_sig, json.dumps(sorted(done))))
            conn.commit()


def exporter_loop() -> None:
    while True:
        try:
            with psycopg.connect(DSN, autocommit=False) as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS pfa_trace_export (
                                  execution_id integer PRIMARY KEY, sig text, keys jsonb NOT NULL DEFAULT '[]',
                                  exported_at timestamptz NOT NULL DEFAULT now())""")
                conn.commit()
                log.info("exporting n8n executions to %s (project %s)", PHOENIX_ENDPOINT, PROJECT)
                while True:
                    has_tables = conn.execute("SELECT to_regclass('execution_entity') IS NOT NULL").fetchone()[0]
                    if has_tables:
                        poll_once(conn)
                    stats["last_poll"] = datetime.now(timezone.utc).isoformat()
                    provider.force_flush(5000)
                    time.sleep(POLL_SECONDS)
        except Exception as exc:                                    # database not ready yet, or restarted: retry
            stats["last_error"] = f"{type(exc).__name__}: {exc}"
            log.warning("exporter: %s - retrying in 10 s", exc)
            time.sleep(10)


@app.on_event("startup")
def start_exporter() -> None:
    if EXPORT_N8N:
        threading.Thread(target=exporter_loop, name="n8n-exporter", daemon=True).start()


# ============================================================== API
class StateEvent(BaseModel):
    session_id: str
    node_name: str
    step: int | None = None
    state: dict[str, Any] | None = None


@app.get("/health")
def health():
    return {"status": "ok", "phoenix_endpoint": PHOENIX_ENDPOINT, "project": PROJECT, **stats}


@app.post("/trace")
def trace_state(event: StateEvent):
    """A custom event from anywhere (e.g. an n8n HTTP Request node). Grouped by session in Phoenix."""
    state_json = json.dumps(event.state, ensure_ascii=False, default=str) if event.state is not None else ""
    attrs = {"openinference.span.kind": "CHAIN", "session.id": event.session_id, "pfa.node_name": event.node_name,
             "input.value": event.node_name, "output.value": clip(state_json), "output.mime_type": "application/json"}
    if event.step is not None:
        attrs["pfa.step"] = event.step
    span = tracer.start_span(f"PFA - {event.node_name}", attributes=attrs)
    span.set_status(Status(StatusCode.OK))
    span.end()
    return {"status": "ok", "session_id": event.session_id, "node_name": event.node_name,
            "trace_id": format(span.get_span_context().trace_id, "032x"),
            "recorded_at": datetime.now(timezone.utc).isoformat()}
