"""Load the knowledge base into pgvector:  python -m pfa.ingest [--force] [--dry-run] [--batch 96] [--concurrency 4]

Same table and format as the v3.2 bundle (id uuid, text, metadata jsonb, embedding vector(1536), cosine).
Chunks of 800 characters with 100 overlap (recursive split on paragraphs, lines, words). Resumable:
files already loaded with the same content hash are skipped; each batch commits whole files.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg

from .ai import llm
from .ai.rag import vec
from .config import settings

CHUNK, OVERLAP, SEPS = 800, 100, ["\n\n", "\n", " ", ""]


def split(text: str, seps=SEPS) -> list[str]:
    """Recursive character splitter (LangChain-style, as used by n8n)."""
    sep = next((s for s in seps if s == "" or s in text), "")
    rest = seps[seps.index(sep) + 1:] if sep in seps else []
    parts = list(text) if sep == "" else text.split(sep)
    docs, cur, total = [], [], 0
    for part in parts:
        if len(part) > CHUNK and rest:
            if cur:
                docs.append(sep.join(cur).strip()); cur, total = [], 0
            docs.extend(split(part, rest))
            continue
        add = len(part) + (len(sep) if cur else 0)
        if total + add > CHUNK and cur:
            d = sep.join(cur).strip()
            if d:
                docs.append(d)
            while cur and (total > OVERLAP or total + add > CHUNK):
                total -= len(cur[0]) + (len(sep) if len(cur) > 1 else 0)
                cur.pop(0)
        cur.append(part)
        total += len(part) + (len(sep) if len(cur) > 1 else 0)
    d = sep.join(cur).strip()
    if d:
        docs.append(d)
    return [x for x in docs if x]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="wipe and reload everything")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch", type=int, default=96)
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    files = sorted(Path(settings.kb_dir).glob("*.md"))
    if not files:
        print(f"No .md files in {settings.kb_dir}", file=sys.stderr)
        return 1
    table = settings.kb_table
    conn = await psycopg.AsyncConnection.connect(settings.database_url, autocommit=True)
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ("id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY, '
                       f'"text" text, "metadata" jsonb, "embedding" vector(1536))')
    await conn.execute(f"CREATE INDEX IF NOT EXISTS {table}_hnsw ON {table} USING hnsw (embedding vector_cosine_ops)")
    if args.force and not args.dry_run:
        await conn.execute(f"TRUNCATE {table}")
    loaded = dict(await (await conn.execute(
        f"SELECT metadata->>'file', min(metadata->>'sha') FROM {table} GROUP BY 1")).fetchall())

    todo = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        sha = hashlib.sha1(text.encode()).hexdigest()[:16]
        if loaded.get(f.name) == sha:
            continue
        todo.append((f.name, sha, split(text)))
    n_chunks = sum(len(c) for _, _, c in todo)
    print(f"{len(files)} files: {len(files) - len(todo)} already loaded, {len(todo)} to embed ({n_chunks} chunks). "
          f"Model {settings.embed_model} · {args.batch} chunks/request · {args.concurrency} in parallel")
    if args.dry_run or not todo:
        await conn.close()
        return 0
    if not settings.ai_enabled:
        print("OPENAI_API_KEY is not set - cannot embed.", file=sys.stderr)
        return 1
    host = urlparse(settings.openai_base_url).hostname or ""
    try:
        socket.getaddrinfo(host, 443)
    except OSError as e:
        print(f"\nCannot reach {host} from inside the app container ({e.strerror or e}).\n"
              "Docker's network or DNS is not working. Usually one of these fixes it:\n"
              "  - Colima:          colima restart     (or: colima start --dns 1.1.1.1 --dns 8.8.8.8)\n"
              "  - Docker Desktop:  restart Docker Desktop\n"
              "  - VPN / proxy:     reconnect, or check that containers may reach the internet\n"
              "Then run ./scripts/ingest-rag.sh - it resumes where it stopped.", file=sys.stderr)
        await conn.close()
        return 2

    jobs, cur = [], []
    for item in todo:                                   # pack whole files into ~batch-sized jobs
        if cur and sum(len(x[2]) for x in cur) + len(item[2]) > args.batch:
            jobs.append(cur); cur = []
        cur.append(item)
    if cur:
        jobs.append(cur)

    llm.open_client()
    sem = asyncio.Semaphore(args.concurrency)
    done, t0, tokens = [0], time.time(), [0.0]

    async def run(job):
        async with sem:
            texts = [c for _, _, chunks in job for c in chunks]
            vectors = await llm.embed(texts)
            tokens[0] += sum(len(t) for t in texts) / 4                      # ~4 characters per token
            async with await psycopg.AsyncConnection.connect(settings.database_url) as c:
                async with c.transaction():
                    i = 0
                    for name, sha, chunks in job:
                        await c.execute(f"DELETE FROM {table} WHERE metadata->>'file' = %s", (name,))
                        for k, chunk in enumerate(chunks):
                            meta = {"source": f"{settings.kb_dir}/{name}", "file": name, "sha": sha, "chunk": k,
                                    "chunks": len(chunks), "loader": "pfa.ingest"}
                            await c.execute(f'INSERT INTO {table} ("text", "metadata", "embedding") VALUES (%s, %s, %s::vector)',
                                            (chunk, json.dumps(meta), vec(vectors[i])))
                            i += 1
            done[0] += len(texts)
            print(f"\r  {done[0]}/{n_chunks} chunks · {time.time() - t0:.1f}s", end="", flush=True)

    try:
        await asyncio.gather(*(run(j) for j in jobs))
    except Exception as e:                  # keep the output readable; what was committed stays loaded
        print(f"\nStopped: {e!r}\nWhat finished is saved - run ./scripts/ingest-rag.sh again to resume.", file=sys.stderr)
        return 1
    finally:
        await llm.close_client()
    total = (await (await conn.execute(f"SELECT count(*) FROM {table}")).fetchone())[0]
    await conn.close()
    from .usage import PRICES, USD_TO_INR
    usd = tokens[0] * PRICES["embed"] / 1e6
    print(f"\nDone in {time.time() - t0:.1f}s - {total} chunks in {table}. "
          f"One-time embedding cost about ${usd:.4f} (₹{usd * USD_TO_INR:.2f}) for ~{tokens[0]:,.0f} tokens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
