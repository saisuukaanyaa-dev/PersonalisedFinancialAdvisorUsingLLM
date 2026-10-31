"""Voice for the chat - only when the user asks for it.

Default VOICE_ENGINE=browser: the page uses the browser's own speech recognition and speech synthesis.
That costs nothing and this module is not used at all.

VOICE_ENGINE=openai adds natural-sounding voice through OpenAI, still only on a button press:
  - speech to text: gpt-4o-mini-transcribe, $0.003 per minute  (≈ ₹0.04 for a 10-second question)
  - text to speech: gpt-4o-mini-tts, about $0.015 per minute of audio (≈ ₹1 per 120-word answer, an estimate:
    the API bills audio tokens and doesn't return them, so we estimate from the text length)
Audio is never stored. Every call is metered in voice_usage and shown on the Usage page. Each user gets a
daily cap so a stuck button can't run up a bill.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque

from .. import db, tracing
from ..config import settings
from . import llm

ENGINE = (os.environ.get("VOICE_ENGINE") or "browser").strip().lower()
STT_MODEL = os.environ.get("OPENAI_STT_MODEL") or "gpt-4o-mini-transcribe"
TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL") or "gpt-4o-mini-tts"
TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE") or "sage"
PRICE_STT_PER_MIN = float(os.environ.get("PRICE_STT_PER_MIN") or 0.003)
PRICE_TTS_PER_MIN = float(os.environ.get("PRICE_TTS_PER_MIN") or 0.015)
DAILY_LIMIT = int(os.environ.get("VOICE_DAILY_LIMIT_PER_USER") or 60)
MAX_AUDIO_BYTES = 3_000_000                      # ~1 minute of compressed audio
MAX_TTS_CHARS = 1500
CHARS_PER_SECOND = 15                            # typical speaking rate, for the TTS cost estimate

_calls: dict[str, deque] = defaultdict(deque)


def enabled() -> bool:
    return ENGINE == "openai" and settings.ai_enabled


def _allow(user_key: str) -> bool:
    q, now = _calls[user_key], time.time()
    while q and now - q[0] > 86400:
        q.popleft()
    if len(q) >= DAILY_LIMIT:
        return False
    q.append(now)
    return True


async def _meter(user_key: str, kind: str, seconds: float | None, chars: int | None, usd: float) -> None:
    await db.execute("INSERT INTO voice_usage (user_key, kind, seconds, chars, cost_usd) VALUES (%s, %s, %s, %s, %s)",
                     user_key, kind, seconds, chars, round(usd, 6))


async def transcribe(user_key: str, audio: bytes, mime: str, seconds: float) -> str:
    if not enabled():
        raise PermissionError("OpenAI voice is off")
    if not _allow(user_key):
        raise PermissionError("Daily voice limit reached")
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("Recording too long - please keep questions under a minute")
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(mime.split(";")[0], "webm")
    with tracing.span("speech to text", "LLM", llm__model_name=STT_MODEL, pfa__seconds=round(seconds, 1)):
        r = await llm.client.post(
            settings.openai_base_url + "/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            data={"model": STT_MODEL, "response_format": "json",
                  "prompt": "Indian personal finance: SIP, PPF, EPF, NPS, ELSS, NIFTY 50, FD, RD, lakh, crore, EMI."},
            files={"file": (f"question.{ext}", audio, mime.split(";")[0])})
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:200]}")
        text = (r.json().get("text") or "").strip()
    await _meter(user_key, "stt", seconds, None, max(seconds, 1) / 60 * PRICE_STT_PER_MIN)
    return text


async def speak(user_key: str, text: str) -> bytes:
    if not enabled():
        raise PermissionError("OpenAI voice is off")
    if not _allow(user_key):
        raise PermissionError("Daily voice limit reached")
    text = " ".join(text.replace("**", "").replace("- ", "").split())[:MAX_TTS_CHARS]
    with tracing.span("text to speech", "LLM", llm__model_name=TTS_MODEL, pfa__chars=len(text)):
        r = await llm.client.post(
            settings.openai_base_url + "/audio/speech",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={"model": TTS_MODEL, "voice": TTS_VOICE, "input": text, "response_format": "mp3",
                  **({"instructions": "Speak in warm, friendly Indian English, like a helpful friend explaining money. "
                                      "Read ₹ as rupees."} if TTS_MODEL.startswith("gpt-4o") else {})})
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:200]}")
    await _meter(user_key, "tts", len(text) / CHARS_PER_SECOND, len(text), len(text) / CHARS_PER_SECOND / 60 * PRICE_TTS_PER_MIN)
    return r.content
