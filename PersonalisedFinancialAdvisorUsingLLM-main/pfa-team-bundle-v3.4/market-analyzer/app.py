#!/usr/bin/env python3
"""Zero-dependency historical NIFTY 50 analysis API for the PFA demo."""
import csv, json, os, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/data"))

def read_csv(name):
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

annual = read_csv("nifty50_annual_performance.csv")
final_annual = read_csv("nifty50_final_annual_performance.csv")
five = read_csv("nifty50_5year_performance.csv")
corporate = read_csv("nifty50_corporate_actions.csv")
constituents = read_csv("nifty50_yearly_constituents.csv")


def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def clean(row):
    out = {}
    for k, v in row.items():
        n = num(v)
        out[k] = n if n is not None and k not in ("year", "symbol", "company_name", "sector", "period_type", "price_data_status", "membership_start", "membership_end", "price_start_date", "price_end_date", "member_from", "member_to", "full_year_member", "observations", "start_date", "end_date", "event_date", "event_type", "description", "valid_from", "valid_to") else v
    return out

def company_summary(symbol):
    symbol = symbol.upper()
    rows = [r for r in five if r.get("symbol", "").upper() == symbol]
    if not rows:
        return {"status":"unavailable", "symbol":symbol, "reason":"No five-year record in supplied dataset."}
    r = clean(rows[0])
    return {"status":"ok", "data_type":"historical", "dataset_period":{"start":r.get("start_date"),"end":r.get("end_date")}, "company":r}

def annual_summary(symbol, year):
    symbol = symbol.upper(); year = str(year)
    rows = [r for r in annual if r.get("symbol", "").upper() == symbol and r.get("year") == year]
    if not rows:
        return {"status":"unavailable", "symbol":symbol, "year":year, "reason":"No annual record in supplied dataset."}
    return {"status":"ok", "data_type":"historical", "company":clean(rows[0])}

def ranking(year, metric, limit=5, order="desc"):
    rows = [clean(r) for r in final_annual if r.get("year") == str(year)]
    key = {"return":"annual_return_pct", "volatility":"annualized_volatility_pct", "drawdown":"max_drawdown_pct"}.get(metric)
    if not key: return {"status":"error", "reason":"metric must be return, volatility, or drawdown"}
    rows = [r for r in rows if isinstance(r.get(key), (int,float))]
    reverse = order != "asc"
    rows.sort(key=lambda x:x[key], reverse=reverse)
    return {"status":"ok", "data_type":"historical", "year":str(year), "metric":metric, "results":rows[:max(1,min(int(limit),20))]}

def handler(path, query):
    parts = [p for p in path.split("/") if p]
    if path == "/health":
        return {"status":"ok","dataset":"NIFTY50 historical bundle","files":{"annual":len(annual),"final_annual":len(final_annual),"five_year":len(five),"corporate_actions":len(corporate),"constituents":len(constituents)}}
    if len(parts) >= 3 and parts[0]=="company" and parts[2]=="five-year": return company_summary(parts[1])
    if len(parts) >= 4 and parts[0]=="company" and parts[2]=="annual": return annual_summary(parts[1], parts[3])
    if len(parts) >= 2 and parts[0]=="ranking":
        year=parts[1]; metric=query.get("metric",["return"])[0]; limit=query.get("limit",["5"])[0]; order=query.get("order",["desc"])[0]
        return ranking(year, metric, limit, order)
    if len(parts)>=2 and parts[0]=="company" and parts[1] and query.get("info"):
        return {"status":"ok","symbol":parts[1],"corporate_actions":[clean(r) for r in corporate if r.get("symbol","").upper()==parts[1].upper()],"membership":[clean(r) for r in constituents if r.get("symbol","").upper()==parts[1].upper()]}
    return {"status":"error","reason":"Unknown endpoint"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urllib.parse.urlparse(self.path)
        try: result=handler(parsed.path, urllib.parse.parse_qs(parsed.query))
        except Exception as e: result={"status":"error","reason":str(e)}
        body=json.dumps(result, ensure_ascii=False).encode()
        self.send_response(200 if result.get("status") != "error" else 400)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, fmt, *args): print(fmt % args)

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT","8000"))), Handler).serve_forever()
