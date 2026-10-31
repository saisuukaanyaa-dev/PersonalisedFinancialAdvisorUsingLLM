"""Guardrails, done locally in microseconds instead of one LLM round trip each (v3.2 used the n8n
Guardrails node with its own model call on the way in and again on the way out).

- Inputs: prompt-injection patterns and personal identifiers are caught with rules before any AI call.
- Topic: the chat model itself returns an `on_topic` flag in the same call that answers (no extra call).
- Outputs: identifiers are masked before anything is shown or stored.
"""
from __future__ import annotations

import re

INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+|your\s+|previous\s+|above\s+|prior\s+)*(instructions|rules|prompts?)"
    r"|system\s*prompt|you\s+are\s+now|act\s+as\s+(an?\s+)?(different|new|unrestricted)|developer\s+mode|jailbreak"
    r"|pretend\s+(to\s+be|you)|reveal\s+(your|the)\s+(prompt|instructions)|<\s*/?\s*(system|assistant)\s*>",
    re.I)

PII = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "Aadhaar": re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)"),
    "passport": re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b"),
    "IFSC": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
}
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn(digits: str) -> bool:
    s, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        s, alt = s + d, not alt
    return s % 10 == 0


def find_pii(text: str) -> list[str]:
    found = [name for name, rx in PII.items() if rx.search(text or "")]
    for m in CARD.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            found.append("card number")
            break
    return found


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION.search(text or ""))


def clean_goal_text(text: str, goal_type: str) -> tuple[str, bool]:
    """Free-text goal details go into AI prompts; if they look like instructions, use the goal type only."""
    t = " ".join(str(text or "").split())[:200]
    if looks_like_injection(t) or find_pii(t):
        return goal_type, True
    return t, False


def check_chat_input(message: str) -> str | None:
    """None if the message may go to the AI; otherwise a kind refusal."""
    m = str(message or "").strip()
    if not m:
        return "Ask me anything about your plan - for example \"What if I invest 30K a month?\""
    if len(m) > 1500:
        return "That's a long message - could you ask it in a sentence or two?"
    pii = find_pii(m)
    if pii:
        return (f"Please don't share ID or account numbers here (I spotted what looks like a {pii[0]}). "
                "I don't need them to help with your plan.")
    if looks_like_injection(m):
        return "I can only help with your personal finance plan - ask me about your goal, savings, loans or investments."
    return None


def sanitize(text: str) -> str:
    out = text or ""
    for name, rx in PII.items():
        out = rx.sub(f"[{name} hidden]", out)

    def card(m):
        d = re.sub(r"\D", "", m.group())
        return "[card number hidden]" if 13 <= len(d) <= 19 and _luhn(d) else m.group()
    return CARD.sub(card, out)
