"""Thin OpenAI client: structured JSON answers and embeddings, over one shared HTTP connection pool."""
from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from .. import tracing, usage
from ..config import settings

log = logging.getLogger("pfa.llm")
client: httpx.AsyncClient | None = None


def open_client() -> None:
    global client
    client = httpx.AsyncClient(timeout=settings.llm_timeout_s,
                               limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))


async def close_client() -> None:
    if client:
        await client.aclose()


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}


async def _post(path: str, payload: dict, name: str = "") -> dict:
    t0 = time.perf_counter()
    for attempt in range(3):
        try:
            r = await client.post(settings.openai_base_url + path, headers=_headers(), json=payload)
        except httpx.TransportError as e:
            if attempt == 2:
                raise
            log.warning("OpenAI network error (%r), retrying", e)
            await asyncio.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503) and attempt < 2 and "insufficient_quota" not in r.text:
            await asyncio.sleep(float(r.headers.get("retry-after") or 1.5 * (attempt + 1)))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:300]}")
        j = r.json()
        meter = usage.current()
        if meter is not None:                 # attribute tokens + cost to the plan / chat question in progress
            meter.record(name or path.strip("/"), j.get("usage"), (time.perf_counter() - t0) * 1000,
                         embedding=path == "/embeddings")
        return j
    raise RuntimeError("OpenAI: retries exhausted")


async def json_call(system: str, user: str, name: str, schema: dict, max_tokens: int = 3000, reasoning_effort: str | None = None) -> dict:
    """One chat completion whose answer must match `schema` (OpenAI structured outputs, strict)."""
    payload = {
        "model": settings.chat_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
        "max_completion_tokens": max_tokens,
    }
    effort = reasoning_effort or settings.reasoning_effort
    if effort and settings.chat_model.startswith(("gpt-5", "o")):
        payload["reasoning_effort"] = effort      # "low" keeps answers fast; simple extraction can use "minimal"
    params = {k: payload[k] for k in ("max_completion_tokens", "reasoning_effort") if k in payload}
    params["response_format"] = name
    with tracing.span(name, "LLM") as s:
        j = await _post("/chat/completions", payload, name)
        content = j["choices"][0]["message"].get("content") or ""
        tracing.llm_call(s, model=j.get("model") or settings.chat_model, name=name, system=system, user_msg=user,
                         output=content, usage=j.get("usage"), cost_usd=usage.call_cost_usd(j.get("usage")), params=params)
        return json.loads(content)


async def embed(texts: list[str]) -> list[list[float]]:
    with tracing.span("embeddings", "EMBEDDING", embedding__model_name=settings.embed_model) as s:
        j = await _post("/embeddings", {"model": settings.embed_model, "input": [t.replace("\n", " ") for t in texts]}, "embeddings")
        if s.is_recording():
            u = j.get("usage") or {}
            s.set_attribute("llm.token_count.prompt", int(u.get("prompt_tokens") or 0))
            s.set_attribute("llm.token_count.total", int(u.get("total_tokens") or u.get("prompt_tokens") or 0))
            s.set_attribute("pfa.cost_usd", round(usage.call_cost_usd(u, embedding=True), 8))
            if tracing.CAPTURE and len(texts) <= 10:          # query texts only, never the bulk ingestion
                for i, t in enumerate(texts):
                    s.set_attribute(f"embedding.embeddings.{i}.embedding.text", t[:1000])
        return [d["embedding"] for d in sorted(j["data"], key=lambda d: d["index"])]


def obj(props: dict, required: list[str] | None = None) -> dict:
    """Strict JSON-schema object helper: every property required, no extras."""
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


STR = {"type": "string"}
STR_LIST = {"type": "array", "items": {"type": "string"}}
