"""Server-side SVG/HTML charts (ported from the v3.2 'Render Report Card' node). No chart library,
no scripts: each chart is a few hundred bytes of markup styled by /static/report.css."""
from __future__ import annotations

import math
from datetime import date

from markupsafe import Markup, escape

from .money import fmt_short, money

STATUS = {
    "good": ("var(--good)", "✓", "Healthy"),
    "warning": ("var(--warning)", "!", "Build up"),
    "critical": ("var(--critical)", "✕", "Missing"),
}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def year_at(m: int) -> str:
    if m == 0:
        return "Now"
    t = date.today()
    y, mo = divmod(t.month - 1 + m, 12)
    return str(t.year + y)


def ring(p: float, status: str) -> Markup:
    R, v = 52, clamp(float(p or 0), 0, 100)
    C = 2 * math.pi * R
    return Markup(
        f'<svg class="ring" viewBox="0 0 128 128" role="img" aria-label="{v:.0f}% of goal projected">'
        f'<circle cx="64" cy="64" r="{R}" class="ring-track"/>'
        f'<circle cx="64" cy="64" r="{R}" class="ring-fill" style="stroke:{STATUS[status][0]}" '
        f'stroke-dasharray="{C * v / 100:.1f} {C:.1f}" transform="rotate(-90 64 64)"><title>{v:.1f}% of target projected</title></circle>'
        f'<text x="64" y="62" class="ring-num">{v:.0f}%</text><text x="64" y="82" class="ring-sub">of goal</text></svg>')


def stack_bar(segs: list[dict], total: float | None = None, cur="INR") -> Markup:
    t = total or sum(s["value"] for s in segs) or 1
    spans = "".join(
        f'<span style="width:{s["value"] / t * 100:.2f}%;background:{s["color"]}" '
        f'title="{escape(s["key"])}: {escape(money(s["value"], cur))} ({s["value"] / t * 100:.0f}%)"></span>'
        for s in segs if s["value"] > 0)
    return Markup(f'<div class="stack">{spans}</div>')


def legend(segs: list[dict], total: float, cur="INR") -> Markup:
    items = "".join(
        f'<li><i style="background:{s["color"]}"></i><span class="lg-key">{escape(s["key"])}</span>'
        f'<span class="lg-val">{escape(money(s["value"], cur))}</span>'
        f'<span class="lg-pct">{f"{s["value"] / total * 100:.0f}%" if total > 0 else ""}</span></li>' for s in segs)
    return Markup(f'<ul class="legend">{items}</ul>')


def donut(parts: list[dict], top: str, bottom: str, cur="INR") -> Markup:
    R = 70
    C = 2 * math.pi * R
    total = sum(p["value"] for p in parts)
    if not total:
        return Markup('<div class="empty">No investments recorded yet</div>')
    live = [p for p in parts if p["value"] > 0]
    gap = 2 if len(live) > 1 else 0
    off, arcs = 0.0, []
    for p in live:
        ln = p["value"] / total * C
        arcs.append(f'<circle cx="90" cy="90" r="{R}" class="donut-seg" style="stroke:{p["color"]}" '
                    f'stroke-dasharray="{max(0.1, ln - gap):.2f} {C:.2f}" stroke-dashoffset="{-off:.2f}" transform="rotate(-90 90 90)">'
                    f'<title>{escape(p["key"])}: {escape(money(p["value"], cur))} ({p["value"] / total * 100:.1f}%)</title></circle>')
        off += ln
    return Markup(f'<svg class="donut" viewBox="0 0 180 180" role="img" aria-label="Current asset allocation">'
                  f'<circle cx="90" cy="90" r="{R}" class="donut-track"/>{"".join(arcs)}'
                  f'<text x="90" y="86" class="donut-num">{escape(top)}</text>'
                  f'<text x="90" y="106" class="donut-sub">{escape(bottom)}</text></svg>')


def projection_chart(proj: dict, cur="INR") -> Markup:
    s = proj.get("series") or []
    if len(s) < 2:
        return Markup("")
    W, H, L, R, T, B = 720, 300, 64, 160, 18, 36
    max_y = max([proj["target_amount"]] + [max(p["current_path"], p["required_path"]) for p in s]) * 1.1 or 1
    max_m = s[-1]["month"] or 1
    x = lambda m: L + m / max_m * (W - L - R)
    y = lambda v: T + (1 - v / max_y) * (H - T - B)
    grid = "".join(
        f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
        f'<text x="{L - 8}" y="{y(v) + 4:.1f}" class="axis" text-anchor="end">{escape(fmt_short(v, cur))}</text>'
        for v in (f * max_y for f in (0, 0.25, 0.5, 0.75, 1)))
    step = max(1, math.ceil(len(s) / 8))
    shown = list(range(0, len(s), step))
    if shown[-1] != len(s) - 1:
        if len(s) - 1 - shown[-1] < step * 0.75:
            shown[-1] = len(s) - 1
        else:
            shown.append(len(s) - 1)
    xl = "".join(f'<text x="{x(s[i]["month"]):.1f}" y="{H - 12}" class="axis" text-anchor="middle">{year_at(s[i]["month"])}</text>'
                 for i in shown)
    path = lambda k: " ".join(f'{"L" if i else "M"}{x(p["month"]):.1f},{y(p[k]):.1f}' for i, p in enumerate(s))
    area = f'{path("current_path")} L{x(max_m):.1f},{y(0):.1f} L{x(0):.1f},{y(0):.1f} Z'
    dense = len(s) > 12

    def dots(k):
        color = "var(--s1)" if k == "current_path" else "var(--s3)"
        lab = "At your current SIP" if k == "current_path" else "At the required SIP"
        return "".join(f'<circle cx="{x(p["month"]):.1f}" cy="{y(p[k]):.1f}" r="{6 if dense else 4}" class="dot{" hit" if dense else ""}" '
                       f'style="fill:{color}"><title>{year_at(p["month"])} · {lab}: {escape(money(p[k], cur))}</title></circle>'
                       for p in s)
    last = s[-1]
    labels = sorted([
        (last["current_path"], fmt_short(last["current_path"], cur) + " today's pace", "var(--s1)"),
        (last["required_path"], fmt_short(last["required_path"], cur) + " needed pace", "var(--s3)"),
        (proj["target_amount"], "Target " + fmt_short(proj["target_amount"], cur), "var(--muted)"),
    ], key=lambda t: -t[0])
    prev, ends = -1e9, []
    for v, text, color in labels:
        yy = max(y(v), prev + 16)
        prev = yy
        ends.append(f'<text x="{W - R + 8}" y="{yy + 4:.1f}" class="end-label"><tspan style="fill:{color}">●</tspan> {escape(text)}</text>')
    return Markup(
        f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Projected savings path versus target">{grid}'
        f'<line x1="{L}" x2="{W - R}" y1="{y(proj["target_amount"]):.1f}" y2="{y(proj["target_amount"]):.1f}" class="target-line"/>'
        f'<path d="{area}" class="area"/><path d="{path("required_path")}" class="line" style="stroke:var(--s3)"/>'
        f'<path d="{path("current_path")}" class="line" style="stroke:var(--s1)"/>{dots("required_path")}{dots("current_path")}'
        f'{xl}{"".join(ends)}</svg>')


def meter(title, value_text, ratio, status, note, label=None) -> Markup:
    color, icon, default = STATUS[status]
    return Markup(
        f'<div class="meter"><div class="meter-head"><span class="meter-title">{escape(title)}</span>'
        f'<span class="badge" style="--b:{color}"><b>{icon}</b> {escape(label or default)}</span></div>'
        f'<div class="meter-value">{escape(value_text)}</div>'
        f'<div class="meter-track"><span style="width:{clamp(ratio, 0, 1) * 100:.1f}%;background:{color}"></span></div>'
        f'<div class="meter-note">{escape(note)}</div></div>')


def pie(parts: list[dict], label: str, size: int = 220, cur: str = "INR", show_money: bool = True) -> Markup:
    """Pie with % labels inside slices of 7% or more; slices under 3% are merged into "Other".
    parts: [{key, value, color}]. The legend next to it carries every value, so nothing depends on colour alone."""
    live = [p for p in parts if p["value"] > 0]
    total = sum(p["value"] for p in live)
    if total <= 0:
        return Markup('<div class="empty">Nothing recorded yet</div>')
    small = [p for p in live if p["value"] / total < 0.03]
    if len(small) > 1:
        live = [p for p in live if p not in small] + [{"key": "Other", "value": sum(p["value"] for p in small), "color": "var(--neutral)"}]
    r, c = size / 2 - 4, size / 2
    ang, paths, labels = -math.pi / 2, [], []
    for p in live:
        frac = p["value"] / total
        a2 = ang + frac * 2 * math.pi
        tip = f'{escape(p["key"])}: {frac * 100:.0f}%' + (f' ({escape(money(p["value"], cur))})' if show_money else "")
        if frac >= 0.9999:
            paths.append(f'<circle cx="{c}" cy="{c}" r="{r}" style="fill:{p["color"]}"><title>{tip}</title></circle>')
        else:
            x1, y1 = c + r * math.cos(ang), c + r * math.sin(ang)
            x2, y2 = c + r * math.cos(a2), c + r * math.sin(a2)
            large = 1 if frac > 0.5 else 0
            paths.append(f'<path d="M{c},{c} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large} 1 {x2:.2f},{y2:.2f} Z" class="pie-seg" '
                         f'style="fill:{p["color"]}"><title>{tip}</title></path>')
        if frac >= 0.07:
            mid = (ang + a2) / 2
            lx, ly = c + r * 0.62 * math.cos(mid), c + r * 0.62 * math.sin(mid)
            labels.append(f'<text x="{lx:.1f}" y="{ly + 5:.1f}" class="pie-pct">{frac * 100:.0f}%</text>')
        ang = a2
    svg = (f'<svg class="pie" viewBox="0 0 {size} {size}" role="img" aria-label="{escape(label)}">'
           f'{"".join(paths)}{"".join(labels)}</svg>')
    rows = "".join(
        f'<li><i style="background:{p["color"]}"></i><span class="lg-key">{escape(p["key"])}</span>'
        + (f'<span class="lg-val">{escape(money(p["value"], cur))}</span>' if show_money else "")
        + f'<span class="lg-pct">{p["value"] / total * 100:.0f}%</span></li>' for p in live)
    return Markup(f'<div class="pie-wrap">{svg}<ul class="legend pie-legend">{rows}</ul></div>')


GOAL_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"]


def goals_timeline(tl: dict, goals: list[dict], cur="INR") -> Markup:
    """v1.7: all your goal money over time at the plan's SIPs. The line drops when a goal is paid; each payout has a
    marker with the goal's name and whether its pot covered it."""
    pts = tl.get("points") or []
    if len(pts) < 2:
        return Markup("")
    W, H, L, R, T, B = 720, 300, 64, 24, 46, 36
    max_y = max(p["total"] for p in pts) * 1.12 or 1
    max_m = tl.get("horizon") or pts[-1]["month"] or 1
    x = lambda m: L + m / max_m * (W - L - R)
    y = lambda v: T + (1 - v / max_y) * (H - T - B)
    grid = "".join(
        f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
        f'<text x="{L - 8}" y="{y(v) + 4:.1f}" class="axis" text-anchor="end">{escape(fmt_short(v, cur))}</text>'
        for v in (f * max_y for f in (0, 0.25, 0.5, 0.75, 1)))
    years = sorted({p["month"] for p in pts if p["month"] % 12 == 0})
    step = max(1, math.ceil(len(years) / 8))
    xl = "".join(f'<text x="{x(m):.1f}" y="{H - 12}" class="axis" text-anchor="middle">{year_at(m)}</text>'
                 for i, m in enumerate(years) if i % step == 0)
    path = " ".join(f'{"L" if i else "M"}{x(p["month"]):.1f},{y(p["total"]):.1f}' for i, p in enumerate(pts))
    area = f'{path} L{x(pts[-1]["month"]):.1f},{y(0):.1f} L{x(0):.1f},{y(0):.1f} Z'
    color = {g["id"]: GOAL_COLORS[i % len(GOAL_COLORS)] for i, g in enumerate(goals)}
    marks = []
    for i, e in enumerate(tl.get("events") or []):
        xx = x(e["month"])
        ok = e["short"] <= 0
        short_name = e["name"].split(" - ", 1)[-1]          # the person's own words ("Europe trip") over the category
        label = f'{short_name} {fmt_short(e["target"], cur)}' + ("" if ok else " (short)")
        anchor = "end" if xx > W - 140 else "start"
        dx = -6 if anchor == "end" else 6
        ty = 14 + (i % 2) * 16
        marks.append(
            f'<line x1="{xx:.1f}" x2="{xx:.1f}" y1="{ty + 4}" y2="{y(0):.1f}" class="goal-mark" style="stroke:{color.get(e["id"], "var(--muted)")}"/>'
            f'<text x="{xx + dx:.1f}" y="{ty + 4}" class="goal-label" text-anchor="{anchor}">'
            f'<tspan style="fill:{color.get(e["id"], "var(--muted)")}">●</tspan> {escape(label)}'
            f'<title>{year_at(e["month"])} · {escape(e["name"])}: pays {escape(money(e["paid"], cur))} of {escape(money(e["target"], cur))}'
            f'{"" if ok else " - short by " + escape(money(e["short"], cur))}</title></text>')
    dots = "".join(f'<circle cx="{x(p["month"]):.1f}" cy="{y(p["total"]):.1f}" r="4" class="dot" style="fill:var(--s1)">'
                   f'<title>{year_at(p["month"])}{" (after payout)" if p.get("after_payout") else ""}: {escape(money(p["total"], cur))}</title></circle>'
                   for p in pts if p["month"] % 12 == 0 or p.get("after_payout"))
    return Markup(
        f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="All goal savings over time, with goal payouts">{grid}'
        f'<path d="{area}" class="area"/><path d="{path}" class="line" style="stroke:var(--s1)"/>{"".join(marks)}{dots}{xl}</svg>')
