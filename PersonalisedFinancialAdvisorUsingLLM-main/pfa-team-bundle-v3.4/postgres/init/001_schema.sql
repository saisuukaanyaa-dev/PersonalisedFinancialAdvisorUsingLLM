-- Personal Finance Advisor - application schema
-- Uses the same PostgreSQL instance that also hosts the PGVector/RAG store.

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    user_key TEXT NOT NULL UNIQUE,
    email TEXT,
    display_name TEXT,
    profile_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS advice_sessions (
    session_id TEXT PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    user_key TEXT NOT NULL,
    question TEXT,
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_advice_user_created
    ON advice_sessions(user_key, created_at DESC);

-- Safe migration for an existing local project.
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE advice_sessions ADD COLUMN IF NOT EXISTS user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE;
ALTER TABLE advice_sessions ADD COLUMN IF NOT EXISTS user_key TEXT;
ALTER TABLE advice_sessions ADD COLUMN IF NOT EXISTS question TEXT;
ALTER TABLE advice_sessions ADD COLUMN IF NOT EXISTS report_json JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE advice_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
