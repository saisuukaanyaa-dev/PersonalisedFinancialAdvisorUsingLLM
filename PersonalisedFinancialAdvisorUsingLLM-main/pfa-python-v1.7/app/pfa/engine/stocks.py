"""NIFTY 50 shortlist, screened in code.

In v3.2 the Investment Recommender agent discovered stocks through several tool calls in a row
(screen -> five-year data per name -> knowledge base), and the renderer then removed names that broke
the risk rules. Here the same rules select the names directly from one market-analyzer call, which
takes milliseconds; the AI only writes the one-line "why" for each name.
"""
from __future__ import annotations

import time

import httpx

from ..config import settings

_cache: dict = {"at": 0.0, "rows": [], "period": {}}


async def five_year_all(client: httpx.AsyncClient) -> tuple[list[dict], dict]:
    """All companies' five-year figures; the dataset is static, so keep it for an hour."""
    if _cache["rows"] and time.time() - _cache["at"] < 3600:
        return _cache["rows"], _cache["period"]
    r = await client.get(f"{settings.market_api_url}/five-year/all", timeout=10)
    r.raise_for_status()
    j = r.json()
    _cache.update(at=time.time(), rows=j.get("results", []), period=j.get("dataset_period", {}))
    return _cache["rows"], _cache["period"]


def screen(rows: list[dict], rules: dict | None, limit: int = 5) -> dict:
    if not rules:
        return {"picks": [], "screened": len(rows), "passed": 0}
    passed = []
    for s in rows:
        dd, vol, cagr = s.get("max_drawdown_pct"), s.get("annualized_volatility_pct"), s.get("cagr_pct")
        if not all(isinstance(x, (int, float)) for x in (dd, vol, cagr)):
            continue
        if -abs(dd) < rules["max_drawdown_pct"] or vol > rules["max_volatility_pct"]:
            continue
        if cagr < vol * rules["min_cagr_to_volatility"]:
            continue
        passed.append(s)
    # best growth per unit of swing first; never more than N per sector
    passed.sort(key=lambda s: s["cagr_pct"] / max(s["annualized_volatility_pct"], 1), reverse=True)
    picks, per_sector = [], {}
    for s in passed:
        sec = str(s.get("sector") or "").lower()
        if per_sector.get(sec, 0) >= rules["max_per_sector"]:
            continue
        per_sector[sec] = per_sector.get(sec, 0) + 1
        picks.append({
            "symbol": s["symbol"], "company_name": s.get("company_name"), "sector": s.get("sector"),
            "five_year_cagr_pct": round(s["cagr_pct"], 1),
            "annualized_volatility_pct": round(s["annualized_volatility_pct"], 1),
            "max_drawdown_pct": round(s["max_drawdown_pct"], 1),
            "rationale": (f"Grew about {s['cagr_pct']:.0f}% a year with {s['annualized_volatility_pct']:.0f}% yearly swings; "
                          f"its worst fall (▼{abs(s['max_drawdown_pct']):.0f}%) is within your limit."),
        })
        if len(picks) >= limit:
            break
    return {"picks": picks, "screened": len(rows), "passed": len(passed)}
