"""Token and cost metering for every OpenAI call.

Each unit of work - writing one plan's explanation, or answering one chat question - starts a Meter.
llm._post() records every call's tokens into the current meter (a context variable, so concurrent plans
and chats never mix). The summary is saved with the report or the chat message, which lets us answer
"what does one plan cost?" and "what does one chat question cost?" from the database.

Prices are USD per 1M tokens (OpenAI standard tier, checked 28 Sep 2026) and can be changed in .env.
Reasoning tokens are billed as output tokens and are already included in completion_tokens.
"""
from __future__ import annotations

import contextvars
import os
import time
from dataclasses import dataclass, field


def _price(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


PRICES = {
    "chat_input": _price("PRICE_CHAT_INPUT_PER_M", 0.25),      # gpt-5-mini
    "chat_cached": _price("PRICE_CHAT_CACHED_PER_M", 0.025),
    "chat_output": _price("PRICE_CHAT_OUTPUT_PER_M", 2.00),
    "embed": _price("PRICE_EMBED_PER_M", 0.02),                # text-embedding-3-small
    "serp_search": _price("PRICE_SERPAPI_SEARCH", 0.025),     # per paid search (Starter plan $25 / 1,000); free plan = $0
}
USD_TO_INR = _price("USD_TO_INR", 88.0)


@dataclass
class Meter:
    started: float = field(default_factory=time.perf_counter)
    calls: list = field(default_factory=list)

    def record(self, name: str, usage: dict | None, ms: float, embedding: bool = False) -> None:
        u = usage or {}
        if embedding:
            self.calls.append({"name": name, "embed_tokens": int(u.get("prompt_tokens") or u.get("total_tokens") or 0),
                               "ms": round(ms)})
            return
        details_in = u.get("prompt_tokens_details") or {}
        details_out = u.get("completion_tokens_details") or {}
        self.calls.append({
            "name": name,
            "input_tokens": int(u.get("prompt_tokens") or 0),
            "cached_tokens": int(details_in.get("cached_tokens") or 0),
            "output_tokens": int(u.get("completion_tokens") or 0),
            "reasoning_tokens": int(details_out.get("reasoning_tokens") or 0),
            "ms": round(ms),
        })

    def record_serp(self, engine: str, query: str, cached: bool, ms: float) -> None:
        self.calls.append({"name": f"serpapi:{engine}", "serp_searches": 0 if cached else 1, "cached": cached,
                           "query": query[:120], "ms": round(ms)})

    def summary(self) -> dict:
        tot = {k: sum(c.get(k, 0) for c in self.calls)
               for k in ("input_tokens", "cached_tokens", "output_tokens", "reasoning_tokens", "embed_tokens", "serp_searches")}
        usd = ((tot["input_tokens"] - tot["cached_tokens"]) * PRICES["chat_input"]
               + tot["cached_tokens"] * PRICES["chat_cached"]
               + tot["output_tokens"] * PRICES["chat_output"]
               + tot["embed_tokens"] * PRICES["embed"]) / 1e6 + tot["serp_searches"] * PRICES["serp_search"]
        return {
            **tot,
            "ai_calls": sum(1 for c in self.calls if "input_tokens" in c),
            "embed_calls": sum(1 for c in self.calls if "embed_tokens" in c),
            "cost_usd": round(usd, 6),
            "cost_inr": round(usd * USD_TO_INR, 4),
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000),
            "calls": self.calls,
            "prices_usd_per_m": PRICES, "usd_to_inr": USD_TO_INR,
        }


def call_cost_usd(u: dict | None, embedding: bool = False) -> float:
    """Price of one API response's `usage` block."""
    u = u or {}
    if embedding:
        return int(u.get("prompt_tokens") or u.get("total_tokens") or 0) * PRICES["embed"] / 1e6
    cached = int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    prompt, out = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
    return ((prompt - cached) * PRICES["chat_input"] + cached * PRICES["chat_cached"] + out * PRICES["chat_output"]) / 1e6


_current: contextvars.ContextVar[Meter | None] = contextvars.ContextVar("pfa_meter", default=None)


def start() -> Meter:
    """Begin metering a unit of work in the current task (replaces any inherited meter)."""
    m = Meter()
    _current.set(m)
    return m


def current() -> Meter | None:
    return _current.get()


def fmt_inr(v: float) -> str:
    return f"₹{v:.2f}" if v >= 0.1 else f"₹{v:.3f}"
