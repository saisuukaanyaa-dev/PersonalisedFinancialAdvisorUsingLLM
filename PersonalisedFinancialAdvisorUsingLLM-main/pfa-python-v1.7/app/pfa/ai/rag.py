"""Knowledge-base retrieval over pgvector (the same table and format as the v3.2 bundle)."""
from __future__ import annotations

import logging

from .. import db, tracing
from ..config import settings
from . import llm

log = logging.getLogger("pfa.rag")


def vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


async def search(queries: list[str], k: int = 3) -> list[dict]:
    """All queries embedded in ONE request, then one nearest-neighbour query each. Returns numbered sources."""
    if not settings.ai_enabled or not queries:
        return []
    with tracing.span("Knowledge-base search", "RETRIEVER", pfa__queries=len(queries), pfa__top_k=k) as s:
        out = await _search(queries, k)
        tracing.retrieved(s, queries, out)
        return out


async def _search(queries: list[str], k: int) -> list[dict]:
    try:
        vectors = await llm.embed(queries)
        seen, out = set(), []
        for v in vectors:
            rows = await db.fetchall(
                f"""SELECT text, metadata->>'file' AS file, 1 - (embedding <=> %s::vector) AS score
                      FROM {settings.kb_table} ORDER BY embedding <=> %s::vector LIMIT %s""", vec(v), vec(v), k)
            for r in rows:
                key = r["text"][:120]
                if key in seen:
                    continue
                seen.add(key)
                out.append({"n": len(out) + 1, "file": r["file"] or "knowledge base",
                            "text": " ".join(r["text"].split())[:700], "score": round(float(r["score"]), 3)})
        return out
    except Exception as e:                       # a missing table or embeddings error must not break the report
        log.warning("RAG search skipped: %s", e)
        return []


def as_prompt(sources: list[dict]) -> str:
    if not sources:
        return "(no knowledge-base passages available)"
    return "\n".join(f"[{s['n']}] ({s['file']}) {s['text']}" for s in sources)
