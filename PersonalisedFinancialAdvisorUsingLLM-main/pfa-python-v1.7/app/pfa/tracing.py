"""Observability: OpenTelemetry traces to Arize Phoenix (ported from the team's n8n telemetry service).

In the n8n bundle, workflow nodes were meant to POST {session_id, node_name, state} to a small telemetry
API that turned each event into a span. Here the app is Python, so it traces itself directly - no extra
service - and every span carries the OpenInference attributes Phoenix understands:

  Build plan (CHAIN)                       Chat message (CHAIN)
  ├─ Compute numbers (CHAIN)               ├─ Guardrail check (GUARDRAIL)
  ├─ Screen NIFTY 50 (TOOL)                ├─ Knowledge-base search (RETRIEVER) ─ embeddings (EMBEDDING)
  └─ Write explanation (CHAIN)             ├─ chat_reply (LLM: messages, tokens, cost)
     ├─ Knowledge-base search (RETRIEVER)  └─ Build plan … (when the chat changes the plan)
     ├─ report_story (LLM)
     └─ report_details (LLM)

All of one user's plans and chat messages share a session id (a hash of their email, never the email),
so Phoenix's Sessions view shows each user's journey with its total tokens and cost.

Settings: PHOENIX_COLLECTOR_ENDPOINT (empty = tracing off, zero overhead), PHOENIX_PROJECT,
PFA_TRACE_CONTENT=false to send only timings, token counts and costs - no prompts, answers or figures.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

log = logging.getLogger("pfa.tracing")
tracer = trace.get_tracer("pfa")                  # a proxy: becomes real once init() sets the provider
_provider = None
CAPTURE = (os.environ.get("PFA_TRACE_CONTENT") or "true").lower() != "false"
MAX_TEXT = 8000


def init(version: str = "") -> bool:
    """Start exporting spans to Phoenix if PHOENIX_COLLECTOR_ENDPOINT is set."""
    global _provider
    endpoint = (os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") or "").strip()
    if not endpoint or _provider is not None:
        return _provider is not None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({
        "service.name": "pfa-python-app",
        "service.version": version,
        "openinference.project.name": os.environ.get("PHOENIX_PROJECT") or "pfa-python",
    })
    _provider = TracerProvider(resource=resource)
    # Batched and exported in a background thread: requests never wait for Phoenix, and a stopped
    # Phoenix only produces a log line.
    _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5)))
    trace.set_tracer_provider(_provider)
    log.info("Tracing to Phoenix at %s (content capture %s)", endpoint, "on" if CAPTURE else "off")
    return True


def shutdown() -> None:
    if _provider is not None:
        _provider.shutdown()                     # flushes spans still in the batch


def enabled() -> bool:
    return _provider is not None


def user_hash(email: str) -> str:
    """A stable, non-reversible id for a user - Phoenix never sees the email address."""
    return "user-" + hashlib.sha256(email.lower().encode()).hexdigest()[:12]


def _text(v) -> str:
    from .ai.guard import sanitize             # ID numbers are masked before anything leaves the app
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return sanitize(s)[:MAX_TEXT]


def _set(s, key: str, value) -> None:
    if value is None:
        return
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    s.set_attribute(key, value)


@contextmanager
def span(name: str, kind: str, **attrs):
    """A span with an OpenInference kind (CHAIN, LLM, RETRIEVER, EMBEDDING, TOOL, GUARDRAIL)."""
    with tracer.start_as_current_span(name) as s:
        if s.is_recording():
            s.set_attribute("openinference.span.kind", kind)
            for k, v in attrs.items():
                _set(s, k.replace("__", "."), v)
        try:
            yield s
        except Exception as e:
            if s.is_recording():
                s.record_exception(e)
                s.set_status(Status(StatusCode.ERROR, str(e)[:200]))
            raise
        else:
            if s.is_recording():
                s.set_status(Status(StatusCode.OK))


def io(s, input=None, output=None) -> None:
    """input.value / output.value - only when content capture is on."""
    if not CAPTURE or not s.is_recording():
        return
    for key, v in (("input", input), ("output", output)):
        if v is None:
            continue
        s.set_attribute(f"{key}.value", _text(v))
        s.set_attribute(f"{key}.mime_type", "text/plain" if isinstance(v, str) else "application/json")


def user(s, email: str) -> None:
    if s.is_recording():
        uid = user_hash(email)
        s.set_attribute("user.id", uid)
        s.set_attribute("session.id", uid)       # one Phoenix session per user: all their plans and chats


def llm_call(s, *, model: str, name: str, system: str, user_msg: str, output: str | None,
             usage: dict | None, cost_usd: float | None, params: dict) -> None:
    """OpenInference LLM attributes: model, messages, token counts, cost."""
    if not s.is_recording():
        return
    s.set_attribute("llm.model_name", model)
    s.set_attribute("llm.provider", "openai")
    s.set_attribute("llm.system", "openai")
    s.set_attribute("llm.invocation_parameters", json.dumps(params))
    s.set_attribute("pfa.call", name)
    if CAPTURE:
        for i, (role, content) in enumerate((("system", system), ("user", user_msg))):
            s.set_attribute(f"llm.input_messages.{i}.message.role", role)
            s.set_attribute(f"llm.input_messages.{i}.message.content", _text(content))
        if output is not None:
            s.set_attribute("llm.output_messages.0.message.role", "assistant")
            s.set_attribute("llm.output_messages.0.message.content", _text(output))
        io(s, user_msg, output)
    u = usage or {}
    prompt, completion = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
    s.set_attribute("llm.token_count.prompt", prompt)
    s.set_attribute("llm.token_count.completion", completion)
    s.set_attribute("llm.token_count.total", prompt + completion)
    cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens")
    reasoning = (u.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if cached is not None:
        s.set_attribute("llm.token_count.prompt_details.cache_read", int(cached))
    if reasoning is not None:
        s.set_attribute("llm.token_count.completion_details.reasoning", int(reasoning))
    if cost_usd is not None:
        s.set_attribute("pfa.cost_usd", round(cost_usd, 6))


def retrieved(s, queries: list[str], docs: list[dict]) -> None:
    """OpenInference RETRIEVER attributes: the query and the passages found, with scores."""
    if not s.is_recording():
        return
    s.set_attribute("pfa.documents", len(docs))
    if not CAPTURE:
        return
    s.set_attribute("input.value", _text(" | ".join(queries)))
    for i, d in enumerate(docs):
        s.set_attribute(f"retrieval.documents.{i}.document.id", str(d.get("file")))
        s.set_attribute(f"retrieval.documents.{i}.document.score", float(d.get("score") or 0))
        s.set_attribute(f"retrieval.documents.{i}.document.content", _text(d.get("text", "")))
