"""SerpAPI client: live Google / Google News / Google Finance results, used carefully.

- Cache first: the same query within SERPAPI_CACHE_HOURS is served from Postgres (SerpAPI doesn't
  charge for it either way, but we don't even make the call).
- Monthly budget: every paid search is logged; the startup refresh stops SERPAPI_CHAT_RESERVE searches
  short of SERPAPI_MONTHLY_LIMIT so the chat always has some left.
- Web text is untrusted: results are reduced to title / source / date / snippet, ID numbers are masked,
  and callers pass them to the model as quoted data only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .. import db, tracing, usage
from ..ai.guard import sanitize
from ..config import settings

log = logging.getLogger("pfa.serpapi")

# Sites we treat as authoritative for Indian personal finance and markets.
TRUSTED = ("rbi.org.in", "sebi.gov.in", "nseindia.com", "niftyindices.com", "bseindia.com", "amfiindia.com",
           "incometax.gov.in", "indiapost.gov.in", "npstrust.org.in", "pib.gov.in", "sbi.co.in", "hdfcbank.com",
           "icicibank.com", "axisbank.com", "kotak.com")


class BudgetExceeded(Exception):
    pass


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _key(engine: str, q: str, params: dict) -> str:
    raw = json.dumps({"e": engine, "q": q.strip().lower(), "p": params}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


async def used_this_month() -> int:
    row = await db.fetchone("SELECT count(*) AS n FROM serp_usage WHERE month = %s", _month())
    return int(row["n"])


async def remaining(purpose: str) -> int:
    left = settings.serpapi_monthly_limit - await used_this_month()
    return max(0, left - (settings.serpapi_chat_reserve if purpose == "refresh" else 0))


async def search(engine: str, q: str, purpose: str, cache_hours: float | None = None, **params) -> tuple[dict, dict]:
    """Returns (response json, info{cached, fetched_at, ms}). Raises BudgetExceeded or httpx errors."""
    if not settings.live_enabled:
        raise BudgetExceeded("SerpAPI is not configured")
    cache_hours = settings.serpapi_cache_hours if cache_hours is None else cache_hours
    key = _key(engine, q, params)
    t0 = time.perf_counter()
    with tracing.span(f"SerpAPI {engine}", "TOOL", tool__name=f"serpapi.{engine}", pfa__purpose=purpose) as s:
        tracing.io(s, input=q)
        row = await db.fetchone(
            "SELECT response, fetched_at FROM serp_cache WHERE key = %s AND fetched_at > now() - make_interval(secs => %s)",
            key, cache_hours * 3600)
        if row:
            info = {"cached": True, "fetched_at": row["fetched_at"].isoformat(), "ms": round((time.perf_counter() - t0) * 1000)}
            _meter(engine, q, True, t0)
            if s.is_recording():
                s.set_attribute("pfa.cached", True)
            return row["response"], info
        if await remaining(purpose) <= 0:
            raise BudgetExceeded(f"monthly SerpAPI budget reached for {purpose}")
        p = {"engine": engine, "q": q, "api_key": settings.serpapi_key, "hl": "en", **params}
        if engine in ("google", "google_news"):
            p.setdefault("gl", "in")
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(settings.serpapi_base_url + "/search.json", params=p)
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(f"SerpAPI {r.status_code}: {r.text[:200]}", request=r.request, response=r)
        data = r.json()
        if data.get("error"):
            raise httpx.HTTPError(f"SerpAPI error: {str(data['error'])[:200]}")
        data.pop("search_metadata", None)
        data.pop("search_parameters", None)          # never store the api_key echo
        await db.execute("INSERT INTO serp_usage (month, purpose, engine, query) VALUES (%s, %s, %s, %s)",
                         _month(), purpose, engine, q[:300])
        await db.execute(
            """INSERT INTO serp_cache (key, engine, query, response, fetched_at) VALUES (%s, %s, %s, %s::jsonb, now())
               ON CONFLICT (key) DO UPDATE SET response = EXCLUDED.response, fetched_at = now()""",
            key, engine, q[:300], json.dumps(data))
        _meter(engine, q, False, t0)
        if s.is_recording():
            s.set_attribute("pfa.cached", False)
        return data, {"cached": False, "fetched_at": datetime.now(timezone.utc).isoformat(),
                      "ms": round((time.perf_counter() - t0) * 1000)}


def _meter(engine: str, q: str, cached: bool, t0: float) -> None:
    m = usage.current()
    if m is not None:
        m.record_serp(engine, q, cached, (time.perf_counter() - t0) * 1000)


def domain(url: str) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def trusted(url: str) -> bool:
    d = domain(url)
    return any(d == t or d.endswith("." + t) for t in TRUSTED)


def snippets(data: dict, limit: int = 5) -> list[dict]:
    """Organic / news / answer-box results reduced to plain, masked text. Trusted sources first."""
    out = []
    ab = data.get("answer_box") or {}
    if ab.get("answer") or ab.get("snippet"):
        out.append({"title": ab.get("title") or "Answer box", "source": domain(ab.get("link", "")) or "google",
                    "date": ab.get("date", ""), "text": ab.get("answer") or ab.get("snippet"), "link": ab.get("link", ""),
                    "trusted": trusted(ab.get("link", "")) or not ab.get("link")})
    for r in (data.get("news_results") or []) + (data.get("organic_results") or []):
        link = r.get("link", "")
        src = r.get("source")
        src = src.get("name") if isinstance(src, dict) else src
        out.append({"title": r.get("title", ""), "source": domain(link) or src or "", "date": r.get("date", ""),
                    "text": r.get("snippet") or "", "link": link, "trusted": trusted(link)})
    out.sort(key=lambda x: not x["trusted"])            # stable: trusted first, rank kept otherwise
    clean = []
    for x in out:
        if not (x["text"] or x["title"]):
            continue
        x["text"] = sanitize(" ".join(str(x["text"]).split()))[:400]
        x["title"] = sanitize(" ".join(str(x["title"]).split()))[:160]
        clean.append(x)
        if len(clean) >= limit:
            break
    return clean


def quote(data: dict) -> dict | None:
    """Google Finance summary -> {price, change_pct, movement, time, title}."""
    s = data.get("summary") or {}
    price = s.get("extracted_price")
    if price is None:
        return None
    pm = s.get("price_movement") or {}
    return {"title": s.get("title"), "price": price, "currency": s.get("currency") or "INR",
            "change_pct": pm.get("percentage"), "movement": pm.get("movement"), "time": s.get("date") or ""}
