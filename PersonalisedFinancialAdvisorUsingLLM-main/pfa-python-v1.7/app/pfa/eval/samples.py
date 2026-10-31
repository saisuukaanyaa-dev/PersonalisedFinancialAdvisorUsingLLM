"""Sample run: 10 made-up personas x 3 risk levels (Low, Medium, High) through the real plan pipeline.

    docker compose exec -T app python -m pfa.eval.samples --out /tmp/pfa-samples [--only 1,4] [--keep]
(./scripts/run-samples.sh does this, copies the files out and prints every report to PDF.)

For each plan it writes a standalone HTML report (stylesheets inlined, ready to print) and checks the rules:
Low risk -> Bank deposits section; no direct stocks at Low (Medium allows a 10% share, High 25%); a short goal
caps risk at Low. summary.json + summary.html list every run, its checks and its AI cost.
Uses the configured OpenAI key (about Rs 0.5 per plan with gpt-5-mini). Sample users are deleted afterwards unless --keep.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from .. import __version__, db, pipeline, report
from ..ai import llm

STATIC = Path(__file__).resolve().parents[1] / "static"
RISKS = ["Low", "Medium", "High"]


def ahead(years: float) -> str:
    return (date.today() + timedelta(days=round(365.25 * years))).isoformat()


def persona(n, name, age, ctc, take_home, expenses, goal, target, years, emergency, term, health, loans=None, inv=None, details=""):
    return {"n": n, "answers": {
        "name": name, "age": str(age), "currency": "INR", "ctc": ctc, "goal_type": goal, "goal_details": details,
        "target_amount": target, "target_date": ahead(years), "take_home": take_home, "expenses": expenses,
        "emergency": emergency, "term_cover": term, "health_cover": health,
        "loan_types": list(loans) if loans else ["None - I'm debt-free"], "loans": loans or {},
        "inv": inv or {}, "_loans_answered": True}}


# Made-up people covering short and long goals, loans, thin and complete safety nets, and a senior citizen.
PERSONAS = [
    persona(1, "Aarav Sample", 25, "6L", "42K", "22K", "Travel or sabbatical", "2L", 1.5, "30K", "0", "3L"),
    persona(2, "Meera Sample", 28, "12L", "88.5K", "40K", "Buy a car", "8L", 3.5, "2.4L", "1Cr", "10L",
            inv={"mf_value": "1L", "mf_monthly": "5K", "fd_value": "50K", "pf_value": "2L", "pf_monthly": "3.6K"}),
    persona(3, "Priya Sample", 32, "18L", "1.22L", "45K", "Buy a home", "80L", 8, "1.5L", "50L", "5L",
            loans={"Car loan": {"outstanding": "3.2L", "rate": "9.2", "emi": "11K"}},
            inv={"mf_value": "4.5L", "mf_monthly": "15K", "fd_value": "2L", "pf_value": "6.4L", "pf_monthly": "3K"}),
    persona(4, "Rahul Sample", 35, "25L", "1.6L", "60K", "Child's education", "30L", 12, "4L", "2Cr", "10L",
            loans={"Home loan": {"outstanding": "45L", "rate": "8.6", "emi": "42K"}},
            inv={"mf_value": "8L", "mf_monthly": "20K", "pf_value": "9L", "pf_monthly": "4K"}),
    persona(5, "Kavya Sample", 40, "30L", "1.85L", "70K", "Retirement", "3Cr", 20, "5L", "2.5Cr", "15L",
            inv={"mf_value": "25L", "mf_monthly": "30K", "stocks_value": "6L", "gold_value": "3L", "pf_value": "18L", "pf_monthly": "6K"}),
    persona(6, "Vikram Sample", 45, "40L", "2.4L", "1.1L", "Child's wedding", "40L", 6, "6L", "3Cr", "20L",
            loans={"Personal loan": {"outstanding": "4L", "rate": "13.5", "emi": "15K"}},
            inv={"mf_value": "15L", "mf_monthly": "25K", "fd_value": "10L", "pf_value": "22L", "pf_monthly": "8K"}),
    persona(7, "Neha Sample", 29, "9L", "65K", "35K", "Build long-term wealth", "25L", 10, "20K", "0", "0",
            loans={"Credit card dues": {"outstanding": "60K", "rate": "36", "emi": "8K"}},
            inv={"mf_value": "40K", "mf_monthly": "3K"}),
    persona(8, "Suresh Sample", 50, "35L", "2.1L", "90K", "Retirement", "2Cr", 10, "6L", "1Cr", "10L",
            inv={"mf_value": "30L", "mf_monthly": "40K", "fd_value": "15L", "pf_value": "35L", "pf_monthly": "7K"}),
    persona(9, "Ananya Sample", 38, "22L", "1.45L", "55K", "Start a business", "15L", 2, "3.5L", "1Cr", "10L",
            inv={"mf_value": "5L", "mf_monthly": "10K", "fd_value": "4L"}),
    persona(10, "Lakshmi Sample", 61, "15L", "1L", "45K", "Build long-term wealth", "20L", 5, "3L", "0", "10L",
            inv={"fd_value": "12L", "pf_value": "10L"}),
]


def checks(r: dict, risk: str) -> list[tuple[str, bool]]:
    plan, pr = r["risk_plan"], r["projection"]
    short = float(pr.get("years_remaining") or 99) < 3
    low = plan["effective_risk"] == "Low" or plan["stated_risk"] == "Low" or short
    fi = next((x for x in r["monthly_plan"]["rows"] if x["bucket"] == "Fixed income"), None)
    expect_dp = bool(low and fi and fi["amount"] > 0)
    out = [("risk recorded as chosen", plan["stated_risk"] == risk),
           ("never riskier than chosen", RISKS.index(plan["effective_risk"]) <= RISKS.index(risk)),
           ("short goal (<3 yrs) capped at Low", not short or plan["effective_risk"] == "Low"),
           ("bank deposits section when Low / short goal" if expect_dp else "no bank deposits section", bool(r.get("deposit_plan")) == expect_dp),
           ("no direct stocks at Low risk", not plan["direct_stocks_allowed"] or plan["effective_risk"] != "Low"),
           ("stock picks only when allowed", plan["direct_stocks_allowed"] or not r.get("picks")),
           ("AI explanation written", (r.get("ai") or {}).get("source") != "computed" and r.get("status") == "ready")]
    if r.get("deposit_plan"):
        dp = r["deposit_plan"]
        out.append(("deposit rows add up", not dp.get("ok") or abs(sum(s["value_at_end"] for s in dp["steps"]) + dp.get("cash_value", 0)
                                                                     - dp["value_on_goal_date"]) <= len(dp["steps"]) + 1))
    return out


def page(r: dict, rid: str, title: str, meta: str, chk: list[tuple[str, bool]]) -> str:
    from ..main import templates
    body = templates.env.get_template("_report_main.html").render(**report.view(r), report_id=rid)
    css = (STATIC / "app.css").read_text() + "\n" + (STATIC / "report.css").read_text()
    rows = "".join(f"<li class='{'ok' if ok else 'bad'}'>{'✓' if ok else '✗'} {html.escape(c)}</li>" for c, ok in chk)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{css}
.sample-head{{border:1px solid #c9c2e8;border-radius:12px;padding:12px 16px;margin:0 0 18px;background:#f6f4ff;color:#1d1640;font:14px/1.45 system-ui,sans-serif}}
.sample-head h1{{font-size:18px;margin:0 0 4px}} .sample-head ul{{margin:6px 0 0;padding-left:0;list-style:none;columns:2}}
.sample-head li.ok{{color:#1f7a3f}} .sample-head li.bad{{color:#b3261e;font-weight:600}}
@media print{{ .chat,.writing-note,button,.voice-row{{display:none!important}} h2{{break-after:avoid}} .card{{break-inside:auto}} .tile,.grid,tr,svg,.action,.meter,.sample-head{{break-inside:avoid}} }}
</style></head><body class="report-page"><div class="pfa"><div class="wrap">
<div class="sample-head"><h1>{html.escape(title)}</h1><div>{html.escape(meta)}</div><ul>{rows}</ul></div>
<main>{body}</main></div></div></body></html>"""


async def run(out: Path, only: set[int] | None, keep: bool) -> int:
    out.mkdir(parents=True, exist_ok=True)
    await db.open_pool()
    llm.open_client()
    summary, users = [], []
    try:
        for p in PERSONAS:
            if only and p["n"] not in only:
                continue
            for risk in RISKS:
                user = f"sample{p['n']:02d}-{risk.lower()}@example.test"
                users.append(user)
                answers = {**p["answers"], "risk": risk}
                from ..profile import build_profile
                profile = build_profile(answers, user)
                t0 = time.perf_counter()
                rid = await pipeline.create_plan(profile, f"sample run {p['n']} {risk}")
                for _ in range(120):
                    r = await db.load_report(rid, user)
                    if r.get("status") == "ready":
                        break
                    await asyncio.sleep(1)
                secs = time.perf_counter() - t0
                chk = checks(r, risk)
                a, plan, pr = p["answers"], r["risk_plan"], r["projection"]
                name = f"sample{p['n']:02d}-{risk.lower()}"
                title = f"Sample {p['n']} · {a['name']} · chose {risk} risk"
                meta = (f"Age {a['age']}, CTC {a['ctc']}, goal {a['goal_type']} {a['target_amount']} by {a['target_date']} · "
                        f"plan built at {plan['effective_risk']} · verdict {pr['verdict'].replace('_', ' ')} · "
                        f"generated {date.today().isoformat()} by PFA Python v{__version__} (made-up data)")
                (out / f"{name}.html").write_text(page(r, rid, title, meta, chk), encoding="utf-8")
                use = r.get("usage") or {}
                dp = r.get("deposit_plan") or {}
                summary.append({"file": f"{name}.pdf", "sample": p["n"], "name": a["name"], "age": a["age"], "goal": a["goal_type"],
                                "target": a["target_amount"], "years": round(float(pr["years_remaining"]), 1), "chosen": risk,
                                "effective": plan["effective_risk"], "verdict": pr["verdict"], "projected": round(pr["projected_value"]),
                                "target_amount": round(pr["target_amount"]), "stocks": bool(plan["direct_stocks_allowed"]),
                                "picks": len(r.get("picks") or []),
                                "deposits": " → ".join(f"{s['bank']} {s['term_months']}m @ {s['rate_pct']}%" for s in dp.get("steps", [])) or ("-" if not dp else "no plan"),
                                "cost_inr": use.get("cost_inr"), "seconds": round(secs, 1),
                                "checks_failed": [c for c, ok in chk if not ok]})
                s = summary[-1]
                print(f"{name:22} {s['effective']:6} {s['verdict']:10} stocks={'y' if s['stocks'] else 'n'} "
                      f"deposits={'y' if dp else 'n'} ₹{s['cost_inr'] or 0:.2f} {s['seconds']:5.1f}s "
                      f"{'OK' if not s['checks_failed'] else 'FAILED: ' + '; '.join(s['checks_failed'])}", flush=True)
    finally:
        if not keep:
            for u in users:
                for t in ("chat_messages", "chat_pending", "advice_sessions", "users"):
                    await db.execute(f"DELETE FROM {t} WHERE user_key = %s", u)
        await llm.close_client()
        await db.close_pool()
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    (out / "summary.html").write_text(summary_page(summary), encoding="utf-8")
    failed = sum(1 for s in summary if s["checks_failed"])
    print(f"{len(summary)} plans, {failed} with failed checks, AI cost ₹{sum(s['cost_inr'] or 0 for s in summary):.2f}")
    return 1 if failed else 0


def summary_page(rows: list[dict]) -> str:
    def tr(s):
        cls = "bad" if s["checks_failed"] else ""
        return (f"<tr class='{cls}'><td>{s['sample']}</td><td>{html.escape(s['name'])}, {s['age']}</td><td>{html.escape(s['goal'])} {s['target']} · {s['years']} yrs</td>"
                f"<td>{s['chosen']}</td><td>{s['effective']}</td><td>{s['verdict'].replace('_', ' ')}</td>"
                f"<td class='n'>₹{s['projected']:,} / ₹{s['target_amount']:,}</td><td>{'yes (' + str(s['picks']) + ')' if s['stocks'] else 'no'}</td>"
                f"<td>{html.escape(s['deposits'])}</td><td class='n'>₹{(s['cost_inr'] or 0):.2f}</td>"
                f"<td>{'✓' if not s['checks_failed'] else '✗ ' + html.escape('; '.join(s['checks_failed']))}</td><td>{s['file']}</td></tr>")
    total = sum(s["cost_inr"] or 0 for s in rows)
    failed = sum(1 for s in rows if s["checks_failed"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>PFA sample run</title><style>
@page{{size:A4 landscape;margin:12mm}} body{{font:11px/1.4 system-ui,sans-serif;color:#1d1640}} h1{{font-size:18px;margin:0 0 4px}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #ddd;padding:5px 6px;text-align:left;vertical-align:top}}
th{{background:#efeafd}} td.n{{text-align:right;white-space:nowrap}} tr.bad td{{background:#fdecea}}
</style></head><body><h1>PFA Python v{__version__} · sample run · {date.today().isoformat()}</h1>
<p>{len(rows)} plans (10 made-up personas × Low / Medium / High). Checks failed: <b>{failed}</b>. AI cost: <b>₹{total:.2f}</b> (gpt-5-mini).
Each row has its own PDF report. Verdicts compare the projection with the target at the plan's expected return.</p>
<table><tr><th>#</th><th>Person</th><th>Goal</th><th>Chose</th><th>Plan at</th><th>Verdict</th><th>Projected / target</th><th>Direct stocks</th>
<th>Bank deposits (fixed income)</th><th>AI cost</th><th>Checks</th><th>Report</th></tr>{''.join(tr(s) for s in rows)}</table></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/pfa-samples")
    ap.add_argument("--only", default="", help="persona numbers, e.g. 1,4")
    ap.add_argument("--keep", action="store_true", help="keep the sample users and reports in the database")
    a = ap.parse_args()
    sys.exit(asyncio.run(run(Path(a.out), {int(x) for x in a.only.split(",") if x.strip()} or None, a.keep)))
