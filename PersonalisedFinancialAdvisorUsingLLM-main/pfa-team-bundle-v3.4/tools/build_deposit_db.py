#!/usr/bin/env python3
"""Builds the bank-deposit database from the team's markdown documents - no AI, fully reproducible.

    python3 tools/build_deposit_db.py

Reads  deposits/source/detailed/*-deposit-schemes-v2.md  (9 banks) and the IndusInd summary, and writes:
  deposits/memory.db           SQLite, table deposit_schemes (same name the teammate's LangGraph agent reads)
  deposits/deposit_schemes.csv the same rows, for a quick look in a spreadsheet
  postgres/deposits.sql        the same rows for the n8n stack's Postgres (loaded by start.sh on every start)

Rows:
  - Fixed Deposit: every line of a bank's card-rate table (tenor | general | senior [| super senior]).
    A range like "5 years to 10 years" becomes two rows (60 and 120 months) - the same split the teammate
    did with prompt 1 in promptDictionary.txt - because the planner needs one fixed duration per row.
  - Recurring Deposit: the bank's own RD rate list when the document has one (Axis, HDFC, ICICI);
    otherwise the FD card rate for the same tenor (6-120 months), and rate_source says so.
Only standard retail schemes with a rate in a table/list are included; prose-only promotions are left out.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "deposits" / "source"
OUT_DB = ROOT / "deposits" / "memory.db"
OUT_CSV = ROOT / "deposits" / "deposit_schemes.csv"
OUT_SQL = ROOT / "postgres" / "deposits.sql"
AS_OF = "2026-09"
DAYS_PER_MONTH = 30.4375

BANKS = {"axis": "Axis Bank", "bob": "Bank of Baroda", "canara": "Canara Bank", "hdfc": "HDFC Bank", "icici": "ICICI Bank",
         "idfc-first": "IDFC FIRST Bank", "kotak": "Kotak Mahindra Bank", "pnb": "Punjab National Bank",
         "sbi": "State Bank of India", "indusind": "IndusInd Bank"}
COLUMNS = ["bank_name", "scheme_type", "scheme_name", "tenor_label", "duration_months", "duration_days",
           "interest_rate_general", "interest_rate_senior", "interest_rate_super_senior", "compounding_months",
           "installment_months", "rate_source", "source_file", "as_of"]


def pct(s: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s.replace("*", ""))
    return float(m.group(1)) if m else None


def tenor(label: str) -> tuple[list[float], str]:
    """"1 Year to less than 2 years" -> ([12.0], ...); "5 years to 10 years" -> ([60, 120]); months per row."""
    t = re.sub(r"[*()]", " ", label.lower())
    t = t.replace("upto", "up to")
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*(days?|months?|years?|yrs?)?", t)
    parts = [(float(n), u) for n, u in parts if n]
    if not parts:
        return [], "unreadable"
    # "6 to 9 Months" / "9 to 15 Months": the unit after the second number applies to both
    units = [u for _, u in parts]
    for i in range(len(parts) - 1, -1, -1):
        if not units[i] and i + 1 < len(units) and units[i + 1]:
            units[i] = units[i + 1]
    def months(n, u):
        u = u or "months"
        return round(n / DAYS_PER_MONTH, 2) if u.startswith("day") else n * 12 if u.startswith(("year", "yr")) else n
    vals = [months(n, u) for (n, _), u in zip(parts, units)]
    lo = vals[0]
    lo_exclusive = bool(re.match(r"\s*(above|more than|over)\b", t))
    if len(vals) == 1:
        if re.search(r"and above|or above|and more", t):
            return [lo], "open-ended (and above)"
        if re.match(r"\s*up to", t):
            return [lo], "up to"
        return [lo], "exact"
    hi = vals[1]
    hi_exclusive = bool(re.search(r"(less than|below|<)\s*\d", t))
    rows = []
    if not lo_exclusive:
        rows.append(lo)
    if not hi_exclusive and hi != lo:
        rows.append(hi)
    if not rows:                      # "above 1 year to less than 2 years" -> 18 months
        rows.append(round((lo + hi) / 2, 2))
    return rows, "range"


def read_card_table(md: str) -> list[dict]:
    """The first markdown table whose header mentions a rate: tenor | general | senior [| super senior]."""
    out, in_table = [], False
    for line in md.splitlines():
        if line.startswith("|") and re.search(r"(rate|%\s*p\.a|citizen)", line, re.I) and not in_table:
            in_table, header = True, [c.strip().lower() for c in line.strip("|").split("|")]
            continue
        if in_table:
            if not line.startswith("|"):
                if out:
                    break
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set(":- "):
                continue
            label = re.sub(r"\*+", "", cells[0]).strip()
            rates = [pct(c) for c in cells[1:]]
            if rates and rates[0] is not None:
                out.append({"label": label, "general": rates[0], "senior": rates[1] if len(rates) > 1 else None,
                            "super_senior": rates[2] if len(rates) > 2 else None})
    return out


def read_rd_list(md: str) -> list[dict]:
    """Bullets like '**6 Months:** **5.50% p.a.** (General) | **6.00% p.a.** (Senior)' inside the RD section."""
    m = re.search(r"^## [^\n]*Recurring Deposit[^\n]*$(.*?)(?=^## |\Z)", md, re.M | re.S)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        b = re.match(r"\s*\*\s+\*\*(.+?):\*\*\s*(.+)$", line)
        if not b:
            continue
        label, rest = b.group(1).strip(), b.group(2)
        g = re.search(r"(\d+(?:\.\d+)?)%[^|]*\(General", rest)
        sr = re.search(r"(\d+(?:\.\d+)?)%[^|]*\(Senior", rest)
        if g and re.search(r"\d", label) and re.search(r"(month|year|day)", label, re.I):
            out.append({"label": label, "general": float(g.group(1)), "senior": float(sr.group(1)) if sr else None,
                        "super_senior": None})
    return out


def build() -> list[dict]:
    rows = []
    files = sorted((SRC / "detailed").glob("*-deposit-schemes-v2.md")) + [SRC / "summaries" / "indusind-deposit-schemes.md"]
    for f in files:
        key = f.name.replace("-deposit-schemes-v2.md", "").replace("-deposit-schemes.md", "")
        bank = BANKS[key]
        md = f.read_text(encoding="utf-8")
        card = read_card_table(md)
        fd_rows = []
        for r in card:
            durations, kind = tenor(r["label"])
            special = re.search(r"(promo|special|peak)", r["label"], re.I)
            for months in durations:
                fd_rows.append({
                    "bank_name": bank, "scheme_type": "Fixed Deposit",
                    "scheme_name": f"{bank} {'Special Tenure ' if special else ''}Fixed Deposit".replace("  ", " "),
                    "tenor_label": r["label"], "duration_months": months, "duration_days": round(months * DAYS_PER_MONTH),
                    "interest_rate_general": r["general"], "interest_rate_senior": r["senior"],
                    "interest_rate_super_senior": r["super_senior"], "compounding_months": 3, "installment_months": None,
                    "rate_source": "card rate table", "source_file": f.name, "as_of": AS_OF})
        rows += fd_rows
        rd_list = read_rd_list(md)
        if rd_list:
            for r in rd_list:
                durations, _ = tenor(r["label"])
                for months in durations:
                    if 6 <= months <= 120:
                        rows.append({**{k: None for k in COLUMNS}, "bank_name": bank, "scheme_type": "Recurring Deposit",
                                     "scheme_name": f"{bank} Recurring Deposit", "tenor_label": r["label"],
                                     "duration_months": months, "duration_days": round(months * DAYS_PER_MONTH),
                                     "interest_rate_general": r["general"], "interest_rate_senior": r["senior"],
                                     "interest_rate_super_senior": None, "compounding_months": 3, "installment_months": 1,
                                     "rate_source": "RD rate list", "source_file": f.name, "as_of": AS_OF})
        else:
            for r in fd_rows:
                if 6 <= r["duration_months"] <= 120:
                    rows.append({**r, "scheme_type": "Recurring Deposit", "scheme_name": f"{bank} Recurring Deposit",
                                 "installment_months": 1,
                                 "rate_source": "FD card rate for the same tenor (no separate RD rate list in the document)"})
    # keep one row per (bank, type, duration) - the highest general rate wins (e.g. PNB's promo tenors)
    best = {}
    for r in rows:
        k = (r["bank_name"], r["scheme_type"], r["duration_months"])
        if k not in best or (r["interest_rate_general"] or 0) > (best[k]["interest_rate_general"] or 0):
            best[k] = r
    return sorted(best.values(), key=lambda r: (r["scheme_type"], r["bank_name"], r["duration_months"]))


def write(rows: list[dict]) -> None:
    OUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if OUT_DB.exists():
        OUT_DB.unlink()
    con = sqlite3.connect(OUT_DB)
    con.execute("""CREATE TABLE deposit_schemes (
        id INTEGER PRIMARY KEY, bank_name TEXT, scheme_type TEXT, scheme_name TEXT, tenor_label TEXT,
        duration_months REAL, duration_days INTEGER, interest_rate_general REAL, interest_rate_senior REAL,
        interest_rate_super_senior REAL, compounding_months INTEGER, installment_months INTEGER,
        rate_source TEXT, source_file TEXT, as_of TEXT)""")
    con.executemany(f"INSERT INTO deposit_schemes ({','.join(COLUMNS)}) VALUES ({','.join('?' * len(COLUMNS))})",
                    [[r[c] for c in COLUMNS] for r in rows])
    con.commit()
    con.close()
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({c: r[c] for c in COLUMNS} for r in rows)

    def lit(v):
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            return repr(v)
        return "'" + str(v).replace("'", "''") + "'"
    sql = ["-- Generated by tools/build_deposit_db.py - do not edit by hand. Loaded by start.sh on every start.", "SET client_min_messages = warning;",
           "CREATE TABLE IF NOT EXISTS deposit_schemes (",
           "  id SERIAL PRIMARY KEY, bank_name TEXT, scheme_type TEXT, scheme_name TEXT, tenor_label TEXT,",
           "  duration_months NUMERIC, duration_days INTEGER, interest_rate_general NUMERIC, interest_rate_senior NUMERIC,",
           "  interest_rate_super_senior NUMERIC, compounding_months INTEGER, installment_months INTEGER,",
           "  rate_source TEXT, source_file TEXT, as_of TEXT);",
           "BEGIN;", "TRUNCATE deposit_schemes RESTART IDENTITY;"]
    for r in rows:
        sql.append(f"INSERT INTO deposit_schemes ({','.join(COLUMNS)}) VALUES ({','.join(lit(r[c]) for c in COLUMNS)});")
    sql.append("COMMIT;")
    OUT_SQL.write_text("\n".join(sql) + "\n", encoding="utf-8")


if __name__ == "__main__":
    rows = build()
    write(rows)
    by = {}
    for r in rows:
        by.setdefault((r["bank_name"], r["scheme_type"]), 0)
        by[(r["bank_name"], r["scheme_type"])] += 1
    print(f"{len(rows)} rows -> {OUT_DB.relative_to(ROOT)}, {OUT_CSV.relative_to(ROOT)}, {OUT_SQL.relative_to(ROOT)}")
    for (b, t), n in sorted(by.items()):
        print(f"  {b:22} {t:18} {n}")
