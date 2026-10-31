SET client_min_messages = warning;
-- v3.4: plan changes proposed in the chat wait here until the user presses Yes or No on the report page.
-- Loaded by start.sh on every start (idempotent).
CREATE TABLE IF NOT EXISTS pfa_chat_pending (
    id          TEXT PRIMARY KEY,
    user_key    TEXT NOT NULL,
    report_id   TEXT,
    changes     JSONB NOT NULL DEFAULT '{}'::jsonb,
    preview     JSONB NOT NULL DEFAULT '[]'::jsonb,
    message     TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | applied | declined | stale
    new_report  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pfa_chat_pending_user ON pfa_chat_pending (user_key, created_at DESC);

-- v3.4 upgrade from v3.2/v3.3: the deposit planner moved into the advisor workflow. Retire the old separate
-- workflow and free its webhook paths (/mcp/bank-deposits and its chat), which n8n's CLI leaves registered.
DO $$
BEGIN
  IF to_regclass('public.webhook_entity') IS NOT NULL THEN
    DELETE FROM webhook_entity WHERE "workflowId" = 'pfaBankDepositsV1';
  END IF;
  IF to_regclass('public.workflow_entity') IS NOT NULL THEN
    UPDATE workflow_entity SET active = false WHERE id = 'pfaBankDepositsV1';
  END IF;
END $$;
