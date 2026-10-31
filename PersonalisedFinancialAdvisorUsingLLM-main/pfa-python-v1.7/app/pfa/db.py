"""Postgres access (async pool). Tables are created on startup, so a fresh database just works."""
from __future__ import annotations

import json
import os

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from .config import settings

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS accounts (
    id            BIGSERIAL PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    name          TEXT,
    password_hash TEXT,
    google_sub    TEXT UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- Same shape as the v3.2 n8n bundle: one profile per user_key (the lower-cased email).
CREATE TABLE IF NOT EXISTS users (
    user_id      BIGSERIAL PRIMARY KEY,
    user_key     TEXT NOT NULL UNIQUE,
    email        TEXT,
    display_name TEXT,
    profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per report. session_id is a random, unguessable id; reports are only shown to their owner.
CREATE TABLE IF NOT EXISTS advice_sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    user_key    TEXT NOT NULL,
    question    TEXT,
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_advice_user_created ON advice_sessions(user_key, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         BIGSERIAL PRIMARY KEY,
    user_key   TEXT NOT NULL,
    report_id  TEXT,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_user_created ON chat_messages(user_key, created_at DESC);
-- tokens, cost and time for each answered chat question (on the assistant row)
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS usage JSONB;

-- v1.3: plan changes proposed in the chat wait here until the user presses Yes / No
CREATE TABLE IF NOT EXISTS chat_pending (
    id         TEXT PRIMARY KEY,
    user_key   TEXT NOT NULL,
    report_id  TEXT,
    changes    JSONB NOT NULL,
    preview    JSONB NOT NULL,
    message    TEXT,
    status     TEXT NOT NULL DEFAULT 'pending',   -- pending | applied | declined | stale
    new_report TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- v1.3: optional OpenAI voice (speech to text / text to speech), metered
CREATE TABLE IF NOT EXISTS voice_usage (
    id         BIGSERIAL PRIMARY KEY,
    user_key   TEXT NOT NULL,
    kind       TEXT NOT NULL,                      -- stt | tts
    seconds    NUMERIC,
    chars      INT,
    cost_usd   NUMERIC NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- v1.2: live data from SerpAPI
CREATE TABLE IF NOT EXISTS serp_cache (
    key        TEXT PRIMARY KEY,               -- engine + query + params
    engine     TEXT NOT NULL,
    query      TEXT NOT NULL,
    response   JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS serp_usage (       -- one row per paid search (cache hits are free and not logged)
    id         BIGSERIAL PRIMARY KEY,
    month      TEXT NOT NULL,                 -- YYYY-MM, for the monthly quota
    purpose    TEXT NOT NULL,                 -- refresh | chat | eval
    engine     TEXT NOT NULL,
    query      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_serp_usage_month ON serp_usage(month);
CREATE TABLE IF NOT EXISTS market_quotes (     -- latest known quote per symbol (rotating refresh fills all 50 over time)
    symbol     TEXT PRIMARY KEY,
    name       TEXT,
    price      NUMERIC,
    change_pct NUMERIC,
    movement   TEXT,
    quote_time TEXT,                          -- as reported by Google Finance
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS intake_reads (       -- v1.6: one row per AI read of the intake chat (the message itself is not stored)
    id            BIGSERIAL PRIMARY KEY,
    user_key      TEXT NOT NULL,
    cost_usd      NUMERIC NOT NULL DEFAULT 0,
    input_tokens  INT,
    output_tokens INT,
    elapsed_ms    INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS kb_refresh (
    id          BIGSERIAL PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status      TEXT NOT NULL,                -- running | done | partial | error
    summary     JSONB NOT NULL DEFAULT '{}'::jsonb
);
"""

pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    global pool
    pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=10, open=False,
                               kwargs={"row_factory": dict_row, "autocommit": True,
                                       "options": f"-c timezone={os.environ.get('TZ') or 'UTC'}"})
    await pool.open(wait=True, timeout=60)
    async with pool.connection() as c:
        await c.execute(SCHEMA)


async def close_pool() -> None:
    if pool:
        await pool.close()


async def fetchone(sql: str, *args):
    async with pool.connection() as c:
        cur = await c.execute(sql, args)
        return await cur.fetchone()


async def fetchall(sql: str, *args):
    async with pool.connection() as c:
        cur = await c.execute(sql, args)
        return await cur.fetchall()


async def execute(sql: str, *args) -> None:
    async with pool.connection() as c:
        await c.execute(sql, args)


# ------------------------------------------------------------------ profiles and reports
async def load_profile(user_key: str) -> dict | None:
    row = await fetchone("SELECT profile_json FROM users WHERE user_key = %s", user_key)
    return row["profile_json"] if row and row["profile_json"] else None


async def save_profile(profile: dict) -> int:
    row = await fetchone(
        """INSERT INTO users (user_key, email, display_name, profile_json, updated_at)
           VALUES (%s, %s, %s, %s, now())
           ON CONFLICT (user_key) DO UPDATE SET email = EXCLUDED.email, display_name = EXCLUDED.display_name,
             profile_json = EXCLUDED.profile_json, updated_at = now()
           RETURNING user_id""",
        profile["user_key"], profile["profile"]["email"], profile["profile"]["user_name"], Jsonb(profile))
    return row["user_id"]


async def save_report(report_id: str, user_id: int, user_key: str, question: str, report: dict) -> None:
    await execute(
        """INSERT INTO advice_sessions (session_id, user_id, user_key, question, report_json)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (session_id) DO UPDATE SET report_json = EXCLUDED.report_json""",
        report_id, user_id, user_key, question, Jsonb(report))


async def update_report_ai(report_id: str, ai: dict, status: str, timings: dict, usage: dict | None = None) -> None:
    await execute(
        """UPDATE advice_sessions
              SET report_json = report_json || jsonb_build_object('ai', %s::jsonb, 'status', %s::text,
                                  'timings', COALESCE(report_json->'timings', '{}'::jsonb) || %s::jsonb)
                                || CASE WHEN %s::jsonb IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('usage', %s::jsonb) END
            WHERE session_id = %s""",
        json.dumps(ai), status, json.dumps(timings), json.dumps(usage) if usage else None,
        json.dumps(usage) if usage else None, report_id)


async def load_report(report_id: str, user_key: str) -> dict | None:
    row = await fetchone(
        "SELECT report_json, created_at FROM advice_sessions WHERE session_id = %s AND user_key = %s",
        report_id, user_key)
    if not row:
        return None
    return {**row["report_json"], "created_at": row["created_at"].isoformat()}


async def latest_report_id(user_key: str) -> str | None:
    row = await fetchone(
        "SELECT session_id FROM advice_sessions WHERE user_key = %s ORDER BY created_at DESC LIMIT 1", user_key)
    return row["session_id"] if row else None


async def list_reports(user_key: str, limit: int = 10) -> list[dict]:
    return await fetchall(
        """SELECT session_id, created_at, report_json->'projection'->>'verdict' AS verdict,
                  report_json->'change_log' AS change_log
             FROM advice_sessions WHERE user_key = %s ORDER BY created_at DESC LIMIT %s""", user_key, limit)


async def usage_for(user_key: str) -> dict:
    """Per-plan and per-question costs for one user (newest first) plus totals."""
    plans = await fetchall(
        """SELECT session_id, created_at, question,
                  (report_json->'usage'->>'cost_usd')::float AS usd, (report_json->'usage'->>'cost_inr')::float AS inr,
                  (report_json->'usage'->>'input_tokens')::int + (report_json->'usage'->>'output_tokens')::int AS tokens,
                  (report_json->'timings'->>'total_ms')::int AS ms
             FROM advice_sessions WHERE user_key = %s ORDER BY created_at DESC LIMIT 50""", user_key)
    chats = await fetchall(
        """SELECT a.created_at,
                  (SELECT q.content FROM chat_messages q WHERE q.user_key = a.user_key AND q.role = 'user' AND q.id < a.id
                    ORDER BY q.id DESC LIMIT 1) AS question,
                  (a.usage->>'cost_usd')::float AS usd, (a.usage->>'cost_inr')::float AS inr,
                  (a.usage->>'input_tokens')::int + (a.usage->>'output_tokens')::int AS tokens,
                  (a.usage->>'elapsed_ms')::int AS ms, a.usage->>'kind' AS kind
             FROM chat_messages a WHERE a.user_key = %s AND a.role = 'assistant' AND a.usage IS NOT NULL
            ORDER BY a.id DESC LIMIT 50""", user_key)
    voice = await fetchone(
        """SELECT count(*) FILTER (WHERE kind = 'stt') AS stt, count(*) FILTER (WHERE kind = 'tts') AS tts,
                  coalesce(sum(cost_usd), 0)::float AS usd FROM voice_usage WHERE user_key = %s""", user_key)
    intake = await fetchone(
        """SELECT count(*) AS reads, coalesce(sum(cost_usd), 0)::float AS usd FROM intake_reads WHERE user_key = %s""", user_key)
    return {"plans": plans, "chats": chats, "voice": voice, "intake": intake}


async def usage_by_user() -> list[dict]:
    """Team-wide summary for the usage report script."""
    return await fetchall(
        """WITH p AS (SELECT user_key, count(*) AS plans, count(report_json->'usage') AS metered_plans,
                           sum((report_json->'usage'->>'cost_usd')::float) AS plan_usd
                        FROM advice_sessions GROUP BY 1),
                c AS (SELECT user_key, count(*) AS questions, sum((usage->>'cost_usd')::float) AS chat_usd
                        FROM chat_messages WHERE role = 'assistant' AND usage IS NOT NULL GROUP BY 1)
           SELECT COALESCE(p.user_key, c.user_key) AS user_key, COALESCE(plans, 0) AS plans,
                  COALESCE(metered_plans, 0) AS metered_plans, COALESCE(plan_usd, 0) AS plan_usd,
                  COALESCE(questions, 0) AS questions, COALESCE(chat_usd, 0) AS chat_usd
             FROM p FULL JOIN c ON p.user_key = c.user_key ORDER BY 1""")
