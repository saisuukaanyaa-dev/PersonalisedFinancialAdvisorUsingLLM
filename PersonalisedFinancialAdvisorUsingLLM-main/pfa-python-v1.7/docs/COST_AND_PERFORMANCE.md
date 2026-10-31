# Cost and performance: Python edition v1.0

Measured on 28 Sep 2026 with the real OpenAI API.
- Models: gpt-5-mini (`reasoning_effort=low`) and text-embedding-3-small.
- Prices (OpenAI standard tier, per 1M tokens): gpt-5-mini $0.25 input / $0.025 cached input / $2.00 output (reasoning tokens bill as output); text-embedding-3-small $0.02.
- Rupee figures use $1 = ₹88 (`USD_TO_INR` in `.env`).

## Summary

| Item | Cost | Tokens | Time |
|---|---|---|---|
| One plan | ₹0.37-0.52 ($0.0043-0.0059) | ~7,000 | numbers + charts 0.01-0.02 s; AI text 11-19 s |
| One chat question | ₹0.10-0.11 ($0.0012) | ~2,900 | 4.5-6.5 s |
| Chat what-if | ≈ ₹0.56 (question ₹0.11 + new plan) | | 6.5 s to the link |
| Blocked by guardrail | ₹0 | 0 | ~1 ms |
| Knowledge base load (one-time) | ≈ $0.004 | ~195K | 21 s |

## One plan, per call (no cache hits)

| Call | Input | Output (reasoning) | Time | Cost |
|---|---|---|---|---|
| embeddings (3 queries) | 43 | - | 0.5 s | ₹0.0001 |
| report_story | 2,362 | 1,134 (128) | 12.3 s | ₹0.252 |
| report_details | 2,372 | 1,246 (512) | 13.1 s | ₹0.271 |
| **Total** (calls run in parallel) | 4,777 | 2,380 (640) | 13.7 s | **₹0.523** |

Output tokens are about 80% of the cost. The other measured plan cost ₹0.37 because prompt caching served 2,304 input tokens per call at a tenth of the price.

## Chat questions

| Question | Input | Output | Time | Cost |
|---|---|---|---|---|
| "What if I invest 40K a month with medium risk?" (updated plan) | 2,613 | 303 | 6.5 s | ₹0.111, plus the new plan |
| "Why keep an emergency fund in a liquid fund?" | 2,616 | 259 | 4.5 s | ₹0.103 |
| "My PAN is …" (blocked locally) | 0 | 0 | 0 s | ₹0 |

## Per user and at scale (₹0.45 per plan, ₹0.11 per question)

| Scenario | Cost |
|---|---|
| Light: 1 plan + 3 questions | ≈ ₹0.8 |
| Typical: 1 plan + 5 questions + 2 what-ifs | ≈ ₹2.1 |
| Heavy: 3 plans + 20 questions + 5 what-ifs | ≈ ₹6.3 |
| 1,000 typical users a month | ≈ ₹2,100 (≈ $24) |

## Speed vs the n8n v3.2 flow

| Step | n8n v3.2 | Python edition |
|---|---|---|
| Numbers and charts on screen | after all agents finished (1-3 min) | 0.01-0.02 s |
| AI explanation | 4 agents in a row + tool round trips + 2 guardrail calls | 1 search + 2 parallel calls, 11-19 s (the user is already reading) |
| Stock shortlist | agent tool loop | rules in code on one cached call, 7-13 ms |
| Chat answer | guardrail call + agent + sanitizer | local guard + 1 call, 4.5-6.5 s |
| Report page size | 34-44 KB (CSS inline) | 26 KB (CSS/JS cached) |

## Where to see it

- **In the app:**
  - each report's footer line
  - under each chat answer
  - the **Usage** page
- **Team report:** `./scripts/usage-report.sh`
- **Stored data:** in `advice_sessions.report_json->'usage'` and `chat_messages.usage`

## Ways to lower the cost

- Keep `OPENAI_REASONING_EFFORT=low`.
- Try `gpt-5-nano` for the chat (about 5× cheaper).
- Keep the shared facts block first in the prompts, so more of the input is served from cache.
