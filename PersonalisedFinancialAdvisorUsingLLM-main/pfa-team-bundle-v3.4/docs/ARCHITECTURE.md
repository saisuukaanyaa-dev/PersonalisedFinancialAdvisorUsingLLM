# Architecture Decision Record

## Decision

Use one PostgreSQL instance for both application persistence and PGVector RAG. Do not introduce MySQL for the current project. Use the supplied historical NIFTY 50 datasets instead of a live market API.

## Why

The project is a sophisticated prototype/demo rather than a high-volume financial production platform. PostgreSQL is already required for PGVector, and the user dataset is small enough for JSONB-backed persistence. Adding MySQL would create another service, credentials, backups, networking, and operational surface without solving a current requirement.

## Data responsibilities

### PostgreSQL application tables

`users` stores identity and the latest normalized financial profile.

`advice_sessions` stores generated advice/report snapshots.

### PGVector

`finance_kb_embeddings` stores financial knowledge and historical-market RAG documents.

### Historical market service

The local market analyzer is the source of truth for exact historical NIFTY 50 metrics. It reads the supplied CSVs and returns deterministic results to n8n.

## RAG vs deterministic retrieval

Use deterministic retrieval for exact numbers:

- CAGR
- annual return
- volatility
- maximum drawdown
- rankings
- membership

Use RAG for:

- methodology
- financial concepts
- explanations
- interpretation guidance
- corporate-action/missing-data context

## Future scaling path

If the project becomes a production application, migrate application data from JSONB snapshots to normalized relational tables and consider a dedicated API/service layer. The agent contracts should remain unchanged.
