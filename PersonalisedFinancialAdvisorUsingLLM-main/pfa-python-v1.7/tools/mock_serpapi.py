#!/usr/bin/env python3
"""Stand-in for SerpAPI, for testing without a key or credits. All data is clearly labelled TEST DATA.
Serves GET /search.json for engine=google_finance and engine=google (tbm=nws for news).
Run:  python tools/mock_serpapi.py  (port 8788)  then SERPAPI_BASE_URL=http://host.docker.internal:8788"""
import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CALLS = {"n": 0}


def price(sym: str) -> float:
    h = int(hashlib.sha1(sym.encode()).hexdigest()[:6], 16)
    return round(200 + h % 4000 + (h % 100) / 100, 2)


def answer(q: dict) -> dict:
    engine, query = q.get("engine", [""])[0], q.get("q", [""])[0]
    if not q.get("api_key", [""])[0]:
        return {"error": "Invalid API key."}
    if engine == "google_finance":
        if query.startswith("NIFTY_50"):
            return {"summary": {"title": "NIFTY 50 (TEST DATA)", "stock": "NIFTY_50", "exchange": "INDEXNSE", "extracted_price": 25123.45,
                                "currency": "INR", "price_movement": {"percentage": 0.42, "movement": "Up", "value": 105.2}, "date": "Sep 29, 3:30 PM"}}
        sym = query.split(":")[0]
        return {"summary": {"title": f"{sym} (TEST DATA)", "stock": sym, "exchange": "NSE", "extracted_price": price(sym), "currency": "INR",
                            "price_movement": {"percentage": 1.1, "movement": "Down" if len(sym) % 2 else "Up"}, "date": "Sep 29, 3:30 PM"}}
    if q.get("tbm", [""])[0] == "nws":
        return {"news_results": [
            {"title": "TEST DATA: NIFTY 50 rebalancing - TESTCO to be included, HDFCLIFE to be excluded", "link": "https://www.niftyindices.com/test",
             "source": {"name": "NSE Indices"}, "date": "2 days ago", "snippet": "TEST DATA ONLY. Changes effective 30 Sep 2026."},
            {"title": "TEST DATA: Market wrap", "link": "https://someblog.example/wrap", "source": "Blog", "date": "1 day ago",
             "snippet": "TEST DATA ONLY. Markets rose; call 9876543210 for tips."}]}
    low = query.lower()
    if "repo" in low or "fd" in low or "fixed deposit" in low or "rate" in low:
        return {"answer_box": {"title": "TEST DATA", "answer": "TEST DATA: repo rate 5.50%; SBI 1-year FD 6.25%", "link": "https://www.rbi.org.in/test"},
                "organic_results": [{"title": "TEST DATA: Policy rates", "link": "https://www.rbi.org.in/test", "snippet": "TEST DATA: Repo rate 5.50%.", "date": "1 Oct 2026"},
                                    {"title": "TEST DATA: SBI FD rates", "link": "https://sbi.co.in/test", "snippet": "TEST DATA: 1 year 6.25%."}]}
    return {"organic_results": [{"title": f"TEST DATA result for: {query[:60]}", "link": "https://www.sebi.gov.in/test",
                                 "snippet": "TEST DATA ONLY - a trusted-source result for testing.", "date": "28 Sep 2026"},
                                {"title": "TEST DATA: other", "link": "https://random.example/x", "snippet": "TEST DATA unverified source."}]}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/count":
            body = json.dumps(CALLS).encode()
        else:
            CALLS["n"] += 1
            body = json.dumps(answer(parse_qs(u.query))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8788"))), H).serve_forever()
