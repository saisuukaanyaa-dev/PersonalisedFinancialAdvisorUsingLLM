"""Chat router: answer from the local knowledge base, or fetch live data via SerpAPI?

Three layers, cheapest first:
  1. Rules (free, instant). Words about *now* (today, current, latest…) and topics that change daily
     (share prices, NIFTY level, index changes, FD/repo rates, news) -> LIVE. Concept and plan questions
     ("what is", "explain", "my plan", ELSS, drawdown…) -> LOCAL.
  2. If the rules can't tell, the chat's own AI call returns needs_live_data (no extra call); only then a
     search and a short second call happen.
  (v1.5) Bank FD / RD questions go to the DEPOSITS route: rates and plans come from the team's deposit table and
     planner (engine/deposits.py), free and instant - not from a web search.
  3. Local first even for LIVE: if today's startup refresh already holds the answer (a fresh quote, the
     index level, index changes), no search is spent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from .. import db
from ..config import settings
from ..live import serpapi

LIVE_TIME = re.compile(r"\b(today'?s?|right now|now|currently|current|latest|recent(ly)?|this (week|month|year)|yesterday|as of|live|at the moment)\b", re.I)
LIVE_TOPICS = {
    "price": re.compile(r"\b(share|stock) price|\bprice of\b|\btrading at\b|\bquote\b|\bnav\b|\bhow much is .* (share|stock)\b", re.I),
    "index": re.compile(r"\b(nifty|sensex)\b[^?]*\b(level|today|now|close[ds]?|closing|points|trading)\b|\bmarket (today|now)\b", re.I),
    "constituents": re.compile(r"\b(nifty|sensex|index)\b[^?]*\b(added|removed|excluded|included|dropped|entr(y|ies)|exits?)\b|"
                              r"\b(added|removed|excluded|included|dropped)\b[^?]*\b(nifty|sensex|index)\b|\brebalanc\w*|\breconstitut\w*|\bconstituents?\b", re.I),
    "rates": re.compile(r"\b(fd|deposit|rd|savings?|saving schemes?|repo|interest|lending|ppf|nsc|scss|kvp|sukanya)( account)? rates?\b|"
                        r"\brepo\b|\binflation( rate)?\b[^?]*\b(now|today|current|latest)\b|\b(current|latest)\b[^?]*\binflation\b", re.I),
    "news": re.compile(r"\bnews\b|\bannounc\w*\b|\bheadlines?\b", re.I),
}
# Definitions ("what is a repo rate?") are concepts; "what is the repo rate?" asks for today's value.
CONCEPT = re.compile(r"^\s*(what is an?|what's an?|what does|explain|define|meaning of|how does|how do|how is|why|difference between)\b", re.I)
# "Suggest 5 best stocks", "which shares should I buy", "top picks for me" -> watchlist with today's prices
PICKS = re.compile(r"\b(sug+e?s+t\w*|rec+om+end\w*|best|top|good|which|pick|picks|name|list|ideas?)\b[^?]*\b(stocks?|shares?|compan(y|ies)|equit(y|ies))\b|"
                   r"\bstock (picks?|ideas?|suggestions?)\b|\bwatchlist\b", re.I)
# FD / RD questions -> the team's deposit table and planner (v1.5)
DEPOSITS = re.compile(r"\b(fds?|rds?|fixed[- ]deposits?|recurring[- ]deposits?|bank deposits?|term deposits?|deposit (rates?|schemes?|plans?))\b", re.I)
# not in the bank table: RBI rates and post-office / small-savings schemes stay on the live route
NOT_BANK = re.compile(r"\b(repo|reverse repo|post[- ]?office|nsc|kvp|scss|ppf|sukanya|corporate|company)\b", re.I)
LOCAL_TOPIC = re.compile(
    r"\b(my (plan|goal|emergency|loan|report|risk|sip|portfolio|allocation|stocks?)|emergency fund|term (cover|insurance)|"
    r"health (cover|insurance)|asset allocation|diversif\w*|drawdown|cagr|volatility|80c|tax saving|elss|ppf|epf|nps|"
    r"index fund|what if|(should|can|am|do|could) i)\b", re.I)


@dataclass
class Route:
    kind: str                         # local | live | ask_model | picks | deposits
    reason: str
    topics: list = field(default_factory=list)
    engine: str | None = None         # google_finance | google
    query: str | None = None
    symbol: str | None = None


_symbols: dict[str, str] = {}         # alias (lower) -> NSE symbol


async def load_symbols() -> dict[str, str]:
    """NIFTY 50 symbols and short company names, from the market API (cached for the process)."""
    if _symbols:
        return _symbols
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            rows = (await c.get(f"{settings.market_api_url}/constituents/latest")).json().get("results", [])
    except httpx.HTTPError:
        return _symbols
    stop = {"the", "bank", "india", "ltd", "limited", "and", "of", "industries", "company"}
    for r in rows:
        sym = r["symbol"]
        _symbols[sym.lower()] = sym
        first = re.sub(r"[^a-z&-]", "", str(r.get("company_name", "")).split(" ")[0].lower())
        if len(first) >= 4 and first not in stop:
            _symbols.setdefault(first, sym)
    return _symbols


def find_symbol(message: str, symbols: dict[str, str]) -> str | None:
    for tok in re.findall(r"[A-Za-z&-]{2,}", message):
        s = symbols.get(tok.lower())
        if s and (len(tok) >= 4 or tok.isupper()):          # "TCS", "ITC" only when typed as symbols
            return s
    return None


def decide(message: str, symbols: dict[str, str] | None = None) -> Route:
    m = message.strip()
    sym = find_symbol(m, symbols or {})
    time_word = bool(LIVE_TIME.search(m))
    topics = [k for k, rx in LIVE_TOPICS.items() if rx.search(m)]
    concept = bool(CONCEPT.search(m)) and not time_word
    if DEPOSITS.search(m) and not concept and not NOT_BANK.search(m):   # "explain FDs" stays local
        return Route("deposits", "bank FD / RD: the team's deposit table and planner", ["deposits"])
    if PICKS.search(m) and not concept and not sym and not topics:
        return Route("picks", "stock suggestions: watchlist with 5-year data and today's prices", ["picks"])
    if re.search(r"\bmy\b", m, re.I) and not time_word and not sym:
        return Route("local", "a question about the user's own plan", topics)       # "my loan's interest rate"
    if sym and time_word and "price" not in topics and "constituents" not in topics:
        topics.append("price")
    if topics and not concept:
        if "price" in topics and sym:
            return Route("live", f"share price of {sym}", topics, "google_finance", f"{sym}:NSE", sym)
        if "index" in topics:
            return Route("live", "NIFTY 50 level", topics, "google_finance", "NIFTY_50:INDEXNSE")
        if "constituents" in topics:
            return Route("live", "NIFTY 50 membership changes", topics, "google", f"NIFTY 50 {m}")
        return Route("live", f"time-sensitive topic ({', '.join(topics)})", topics, "google", f"{m} India")
    if concept or LOCAL_TOPIC.search(m):
        return Route("local", "concept or plan question", topics)
    if time_word:
        return Route("ask_model", "mentions time but the topic is unclear", topics)
    return Route("ask_model", "no clear signal - the model decides", topics)


def _age_ok(ts: datetime | None) -> bool:
    return bool(ts) and (datetime.now(timezone.utc) - ts).total_seconds() < settings.serpapi_cache_hours * 3600


async def fetch(route: Route) -> tuple[str, list[dict], str]:
    """Live context for a LIVE route: (text for the prompt, sources, how it was obtained)."""
    from ..live.refresh import last_done
    # 1. today's refresh already has it?
    if route.engine == "google_finance" and route.symbol:
        r = await db.fetchone("SELECT * FROM market_quotes WHERE symbol = %s", route.symbol)
        if r and _age_ok(r["fetched_at"]):
            when = r["fetched_at"].astimezone().strftime("%d %b %Y %H:%M")
            return (f"{r['symbol']} ({r['name']}): ₹{float(r['price']):,.2f}, {r['movement'] or ''} {r['change_pct'] or ''}% "
                    f"(Google Finance, fetched {when}).", [{"source": "Google Finance", "date": when}], "knowledge base (today's refresh)")
    last = await last_done()
    if last and _age_ok(last["finished_at"]):
        s = last["summary"] or {}
        when = last["finished_at"].astimezone().strftime("%d %b %Y %H:%M")
        if route.query == "NIFTY_50:INDEXNSE" and s.get("index"):
            i = s["index"]
            return (f"NIFTY 50: {i['price']:,} ({i.get('movement') or ''} {i.get('change_pct') or ''}%), reported {i.get('time') or when}.",
                    [{"source": "Google Finance", "date": when}], "knowledge base (today's refresh)")
        if "constituents" in route.topics and (s.get("changes") or {}).get("checked"):
            c = s["changes"]
            txt = (f"Checked {when}. Added: {', '.join(a['symbol'] for a in c.get('added', [])) or 'none reported'}. "
                   f"Removed: {', '.join(x['symbol'] for x in c.get('removed', [])) or 'none reported'}. {c.get('summary', '')}")
            return txt, [{"source": x, "date": when} for x in c.get("sources", [])[:3]], "knowledge base (today's refresh)"
    # 2. SerpAPI (cached for SERPAPI_CACHE_HOURS)
    if not settings.live_enabled:
        return "Live data is not available (SerpAPI is off).", [], "unavailable"
    try:
        data, info = await serpapi.search(route.engine or "google", route.query or "", "chat")
    except serpapi.BudgetExceeded:
        return "Live data is not available right now (monthly search budget used).", [], "unavailable"
    except httpx.HTTPError as e:
        return f"Live data is not available right now ({str(e)[:80]}).", [], "unavailable"
    how = "SerpAPI (cached)" if info["cached"] else "SerpAPI"
    fetched = datetime.fromisoformat(info["fetched_at"]).astimezone().strftime("%d %b %Y %H:%M")
    if route.engine == "google_finance":
        q = serpapi.quote(data)
        if q:
            if route.symbol:
                await db.execute(
                    """INSERT INTO market_quotes (symbol, name, price, change_pct, movement, quote_time, fetched_at)
                       VALUES (%s, %s, %s, %s, %s, %s, now()) ON CONFLICT (symbol) DO UPDATE SET price = EXCLUDED.price,
                       change_pct = EXCLUDED.change_pct, movement = EXCLUDED.movement, quote_time = EXCLUDED.quote_time, fetched_at = now()""",
                    route.symbol, q.get("title"), q["price"], q.get("change_pct"), q.get("movement"), q.get("time"))
            return (f"{q.get('title') or route.query}: {q['currency']} {q['price']:,} ({q.get('movement') or ''} {q.get('change_pct') or ''}%), "
                    f"reported {q.get('time') or fetched}.", [{"source": "Google Finance", "date": fetched}], how)
    items = serpapi.snippets(data, limit=5)
    if not items:
        return "The live search found nothing relevant.", [], how
    text = "\n".join(f"[W{i + 1}] {x['title']} ({x['source']}{', ' + x['date'] if x['date'] else ''}"
                     f"{'' if x['trusted'] else ', unverified source'}): {x['text']}" for i, x in enumerate(items))
    return text, [{"source": x["source"], "date": x["date"] or fetched, "trusted": x["trusted"]} for x in items[:3]], how


async def prices(symbols: list[str]) -> tuple[dict, list[dict], str]:
    """Today's price for each watchlist stock: from today's refresh when fresh, otherwise SerpAPI (cached)."""
    out, used_serp, used_kb = {}, False, False
    for sym in symbols:
        r = await db.fetchone("SELECT * FROM market_quotes WHERE symbol = %s", sym)
        if r and _age_ok(r["fetched_at"]):
            used_kb = True
        elif settings.live_enabled:
            try:
                data, _ = await serpapi.search("google_finance", f"{sym}:NSE", "chat")
                q = serpapi.quote(data)
                if q:
                    await db.execute(
                        """INSERT INTO market_quotes (symbol, name, price, change_pct, movement, quote_time, fetched_at)
                           VALUES (%s, %s, %s, %s, %s, %s, now()) ON CONFLICT (symbol) DO UPDATE SET price = EXCLUDED.price,
                           change_pct = EXCLUDED.change_pct, movement = EXCLUDED.movement, quote_time = EXCLUDED.quote_time, fetched_at = now()""",
                        sym, q.get("title"), q["price"], q.get("change_pct"), q.get("movement"), q.get("time"))
                    used_serp = True
                    r = await db.fetchone("SELECT * FROM market_quotes WHERE symbol = %s", sym)
            except (serpapi.BudgetExceeded, httpx.HTTPError):
                pass
        if r:
            out[sym] = {"price": float(r["price"]), "change_pct": float(r["change_pct"]) if r["change_pct"] is not None else None,
                        "movement": r["movement"], "as_of": r["fetched_at"].astimezone().strftime("%d %b %Y %H:%M")}
    how = " + ".join(x for x, used in (("knowledge base (today's refresh)", used_kb), ("SerpAPI", used_serp)) if used)
    sources = [{"source": "Google Finance", "date": next(iter(out.values()))["as_of"]}] if out else []
    return out, sources, how or "no live prices (5-year data only)"
