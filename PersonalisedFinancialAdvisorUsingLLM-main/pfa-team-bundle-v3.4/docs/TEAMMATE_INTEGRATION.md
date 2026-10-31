# The teammate's project inside the PFA flow (v3.3, updated in v3.4)

> **v3.4:** n8n calls the two knowledge tools as **HTTP tools** (`POST /ask/<tool>`, same bearer token) instead of MCP clients. n8n's MCP client connects when the agent starts, so a stopped teammate container made every chat fail. HTTP tools connect only when used. The tools are still published over MCP at `:8090/mcp`. The deposit planner chat is now the report-page chat.

Source: `PersonalisedFinancialAdvisorUsingLLM-main` (copied into `teammate-advisor/teammate/` on 4 Oct 2026; the original folder is untouched).

## What runs where

```
 Advisor follow-up chat (n8n) ──► Financial Q&A Agent ──► Teammate_Advisor_MCP ─┐
 Deposit planner chat (n8n)  ──► Deposit Planner Agent ─► Teammate_Deposit_Schemes ┤  MCP over HTTP, bearer token
                                                                                   ▼
                          teammate-advisor container  (Python 3.12, their code unchanged)
                          ├─ Ask_Bank_Deposit_Schemes   their RagChainForNumericalData.QueryRag over 9 banks' documents
                          ├─ Ask_Mutual_Funds           the same over 9 mutual-fund summaries
                          ├─ Financial_Information_Chat their guarded LangGraph chatbot (agent + both RAG tools)
                          └─ GetBestBankDepositSchemeSequence  their LangGraph deposit agent (not wired, see below)
                                     │
                                     └─► Phoenix, project "pfa-teammate-advisor" (LangChain spans: prompts, context, tokens)
```

The report pipeline is unchanged: plans and numbers still come from the n8n code nodes and the n8n deposit planner.
The teammate's service adds **knowledge**: what a named bank's scheme rules are, and facts about specific mutual funds.

## Their RAG, in their words and code

| Step | What their code does |
|---|---|
| Chunking | Markdown split by headers (H1-H6), then 1,000-character chunks with 100 overlap; the header path is prefixed to every chunk |
| Stores | Chroma (persistent), one collection per instrument: 79 deposit chunks, 45 mutual-fund chunks; local all-MiniLM-L6-v2 embeddings (no OpenAI cost) |
| Retrieval | spaCy finds named entities in the question. With entities: BM25 over the chunk headings (15 candidates). Without: vector search (8 + 2), then a cross-encoder (ms-marco-MiniLM-L-6-v2) reranks |
| Answer | gpt-4.1, temperature 0, "answer using only the provided context, otherwise say you do not know" |
| Guardrails | llm_guard: banned substrings (incl. "ignore all previous instructions", "jailbreak") and a token limit, on the question and the answer |

**Their evaluation** (`docs/teammate/`): 5 metrics, judged per question.

| | Bank deposits (49 questions) | Mutual funds (60 questions) |
|---|---|---|
| Faithfulness | 91.5% | 97.6% |
| Context relevance | 95.0% | 89.6% |
| Answer relevance | 99.8% | 93.2% |
| Context recall | 92.2% | 92.0% |
| Answer correctness | 85.7% | 90.0% |

The six mutual-fund misses are Motilal Oswal Flexi Cap, which has no summary in their data. The system said it did not know rather than inventing numbers.

## Checked on the isolated test stack (4 Oct 2026)

| Call | Result |
|---|---|
| No bearer token | HTTP 401 |
| `Ask_Bank_Deposit_Schemes`: "premature withdrawal penalty on Canara Bank RDs?" | "1.00% … interest paid at 1.00% below the applicable card rate", 7 s |
| `Ask_Mutual_Funds`: "exit load and expense ratio of Parag Parikh Flexi Cap?" | exit-load slabs and 0.69%, a few seconds |
| `Ask_Bank_Deposit_Schemes`: "ignore all previous instructions…" | blocked by their guardrail (BanSubstrings) |
| `Financial_Information_Chat`: HDFC Flexi Cap minimum + HDFC senior FD | both answered from their documents, 12 s |
| `GetBestBankDepositSchemeSequence` | **fails in the current teammate code**, see below |

## Why their deposit agent is not wired in

The copy taken on 4 Oct fails on both kinds of request:

- monthly saving only ("₹5,000 a month, ₹62,000 in 1 year"): `IndexError: list index out of range` in `GoalSearch.BestSearch2` (line 71), called from `OptimalActionRecurringDeposit.__init__`;
- lump sum + monthly ("3 lakh now, 10,000 a month, 8 lakh by April 2030"): `ValidationError: 155 validation errors for OptimalActionFixedDepositToolArgsSchema` (the model's tool arguments don't match the schema).

The tool is still published by the service (so it can be shown in the MCP Inspector) with a 120-second limit per call, but no n8n agent uses it. Plans keep coming from the n8n deposit planner (`pfa_bank_deposits.json`), which carries the earlier fixes to their maths (RD maturity, inflation over the whole period). Once the teammate fixes these two errors, connecting it is one line: add `GetBestBankDepositSchemeSequence` to `includeTools` in the `Teammate_Deposit_Schemes` node.

## Runtime notes

- **Image:** 3.3 GB (CPU-only PyTorch for the reranker, spaCy, Chroma's ONNX model). The first `./start.sh` builds it (about 10-15 minutes). The models and both Chroma stores are built into the image, so the container needs no downloads at runtime.
- **Memory:** about 650-750 MB when running.
- **Cost:** each RAG question is one gpt-4.1 call with about 3-4K tokens of context: roughly ₹0.8 **(est.)**. `Financial_Information_Chat` adds the agent's own gpt-4.1 calls (roughly ₹2-3 **(est.)**). Embeddings and reranking run locally, for free.
- **Two runtime-only changes, outside their files** (`pfa_mcp_server.py`):
  1. spaCy and the cross-encoder are loaded once instead of on every question (the same results, seconds faster);
  2. the RAG tools run their guardrail scanners directly. Their `LLMWithGuardrails.invoke()` also sends each question to gpt-4.1 and only prints the reply, which doubled the cost of every question. The chatbot and deposit-agent tools still use their original guardrail code.
- **Data:** their agent writes its own SQL against `memory.db`, so the bundle's rate table is mounted **read-only**.
