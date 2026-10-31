"""Reading and writing money the way people type it (ported from the v3.2 n8n shared helpers).

parse_amount returns None for anything it cannot understand - never 0 - so the intake can ask
the user again instead of silently planning with a wrong number.
"""
from __future__ import annotations

import math
import re
from datetime import date

_SUFFIX = [
    (re.compile(r"^(c|cr|crs|crore|crores)$"), 1e7),
    (re.compile(r"^(l|lk|lac|lacs|lakh|lakhs)$"), 1e5),
    (re.compile(r"^(k|th|thousand|thousands)$"), 1e3),
    (re.compile(r"^(m|mn|million|millions)$"), 1e6),
    (re.compile(r"^(b|bn|billion|billions)$"), 1e9),
    (re.compile(r"^(pa|pm|permonth|peryear|month|year|yr|mo)$"), 1),
]


_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                     "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALE = {"hundred": 100, "thousand": 1e3, "k": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
          "crore": 1e7, "crores": 1e7, "cr": 1e7, "million": 1e6, "billion": 1e9}


def words_to_number(text: str) -> float | None:
    """Spoken amounts: "eighteen lakh", "one crore twenty lakh", "fifty thousand", "2 lakh 50 thousand",
    "one point five crore", "one and a half lakh". None if the words aren't a number."""
    t = re.sub(r"(?<=\d),(?=\d)", "", str(text).lower())                 # 85,000 -> 85000
    t = re.sub(r"[₹,]|rupees?|\brs\.?", " ", t).replace("-", " ")
    t = re.sub(r"\band a half\b", " point five", t)
    total, current, seen = 0.0, 0.0, False
    tokens = t.split()
    i = 0
    while i < len(tokens):
        w = tokens[i]
        if w in ("and", "a", "only"):
            i += 1
            continue
        if w == "point" and i + 1 < len(tokens):                     # "one point five"
            digits = []
            while i + 1 < len(tokens) and (tokens[i + 1] in _ONES or tokens[i + 1].isdigit()):
                i += 1
                digits.append(str(_ONES.get(tokens[i], tokens[i])))
            current += float("0." + "".join(digits)) if digits else 0
            i += 1
            continue
        if re.fullmatch(r"\d+(\.\d+)?", w):
            current += float(w); seen = True
        elif w in _ONES:
            current += _ONES[w]; seen = True
        elif w in _TENS:
            current += _TENS[w]; seen = True
        elif w == "hundred":
            current = (current or 1) * 100; seen = True
        elif w in _SCALE:
            total += (current or 1) * _SCALE[w]; current = 0; seen = True
        else:
            return None
        i += 1
    return total + current if seen else None


def parse_amount(v) -> float | None:
    """85000, "85,000", "85K", "1.2L", "2.5 lakh", "3Cr", "Rs 12,00,000" -> number; unreadable -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if math.isfinite(v) else None
    s = str(v).lower().strip()
    if not s:
        return None
    s = re.sub(r"[₹$€£¥,\s_]", "", s)
    s = re.sub(r"^(rupees?|rs\.?|inr|usd|eur|gbp|aed|sgd)", "", s)
    m = re.match(r"^(-?\d+(?:\.\d+)?)(.*)$", s)
    if not m:
        return words_to_number(v)                       # spoken: "eighteen lakh", "fifty thousand"
    n = float(m.group(1))
    suffix = re.sub(r"[^a-z]", "", m.group(2))
    if suffix == "":
        return n
    if re.search(r"\d", m.group(2)) or len(suffix) > 12:          # "2 lakh 50 thousand"
        return words_to_number(v)
    for pattern, mult in _SUFFIX:
        if pattern.match(suffix):
            return n * mult
    return None


def parse_optional(v) -> float | None:
    """Blank means 0; anything typed but unreadable means None."""
    if v is None or str(v).strip() == "":
        return 0.0
    return parse_amount(v)


def parse_rate(v) -> float | None:
    """Interest rates are never scaled: "8.5%", "8.5 % p.a." and "8.5" all mean 8.5."""
    if v is None or str(v).strip() == "":
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))      # first number, like JavaScript's parseFloat
    if not m:
        return None
    n = float(m.group())
    return n if math.isfinite(n) and 0 <= n <= 60 else None


def trim2(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s


def fmt_short(n, cur: str = "INR") -> str:
    """₹1.22L, ₹80L, ₹1.5Cr - the Indian way people talk about money."""
    v = float(n or 0)
    sign = "-" if v < 0 else ""
    a = abs(v)
    if not cur or cur == "INR":
        if a >= 1e7:
            return f"{sign}₹{trim2(a / 1e7)}Cr"
        if a >= 1e5:
            return f"{sign}₹{trim2(a / 1e5)}L"
        if a >= 1e3:
            return f"{sign}₹{trim2(a / 1e3)}K"
        return f"{sign}₹{round(a)}"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SGD": "S$"}.get(cur, cur + " ")
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}{sym}{trim2(round(a / div, 1))}{suf}"
    return f"{sign}{sym}{round(a)}"


def shorthand(n, cur: str = "INR") -> str:
    """A number written back the way the user would type it (for pre-filling forms)."""
    if n is None or n == "":
        return ""
    try:
        v = float(n)
    except (TypeError, ValueError):
        return str(n)
    if v == 0:
        return "0"
    if not cur or cur == "INR":
        for div, suf in ((1e7, "Cr"), (1e5, "L"), (1e3, "K")):
            if abs(v) >= div and abs(round(v / div * 100) / 100 * div - v) < 0.5:
                return trim2(v / div) + suf
    return trim2(round(v, 2))


def money(n, cur: str = "INR") -> str:
    """Full amount with grouping: ₹12,40,000 (Indian lakh grouping for INR)."""
    v = round(float(n or 0))
    sign = "-" if v < 0 else ""
    a = str(abs(v))
    if not cur or cur == "INR":
        if len(a) > 3:
            head, tail = a[:-3], a[-3:]
            head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
            a = head + "," + tail
        return f"{sign}₹{a}"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SGD": "S$"}.get(cur, cur + " ")
    return f"{sign}{sym}{abs(v):,}"


def first_name(name: str | None) -> str:
    parts = str(name or "").strip().split()
    return parts[0].capitalize() if parts else "there"


def months_until(d: str | date | None) -> int | None:
    if not d:
        return None
    try:
        t = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    except ValueError:
        return None
    today = date.today()
    return round((t - today).days / 30.44)


def month_year(d: str | None) -> str:
    try:
        return date.fromisoformat(str(d)[:10]).strftime("%b %Y")
    except (TypeError, ValueError):
        return str(d or "")


def estimate_in_hand(ctc, cur: str = "INR") -> float | None:
    """Annual CTC -> monthly in-hand pay. India: FY 2026-27 new regime (87A rebate, marginal relief,
    surcharge, 4% cess), basic 40% of CTC, 12% PF each side, gratuity 4.81%, professional tax."""
    c = float(ctc or 0)
    if c <= 0:
        return None
    if cur and cur != "INR":
        return round(c * 0.72 / 12 / 100) * 100          # generic rough cut
    basic = c * 0.40
    employer_pf, gratuity, employee_pf = basic * 0.12, basic * 0.0481, basic * 0.12
    gross = c - employer_pf - gratuity
    taxable = max(0.0, gross - 75000)
    slabs = [(400000, 0), (800000, 0.05), (1200000, 0.10), (1600000, 0.15),
             (2000000, 0.20), (2400000, 0.25), (math.inf, 0.30)]
    tax, prev = 0.0, 0.0
    for upto, rate in slabs:
        if taxable > prev:
            tax += (min(taxable, upto) - prev) * rate
        prev = upto
    if taxable <= 1200000:
        tax = 0.0                                            # 87A rebate
    else:
        tax = min(tax, taxable - 1200000)                    # marginal relief
    surcharge = 0.25 if taxable > 2e7 else 0.15 if taxable > 1e7 else 0.10 if taxable > 5e6 else 0
    tax = tax * (1 + surcharge) * 1.04
    net = gross - employee_pf - tax - 2500
    return round(net / 12 / 500) * 500
