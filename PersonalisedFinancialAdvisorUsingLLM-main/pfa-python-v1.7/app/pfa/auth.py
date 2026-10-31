"""Sign-in: email + password (always on) and Google (on when GOOGLE_CLIENT_ID/SECRET are set).

- Passwords: scrypt from the standard library, per-user salt, constant-time compare.
- Sessions: a signed cookie (Starlette SessionMiddleware) holding only the account id.
- Google: OAuth 2.0 authorization-code flow with a random `state`; we accept only verified emails.
- CSRF: every state-changing API call must send the header `X-PFA: 1`. Browsers cannot add a custom
  header cross-site without a CORS preflight, and this app allows no cross-origin requests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import db
from .config import settings

router = APIRouter()
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


# ------------------------------------------------------------------ passwords
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str | None) -> bool:
    try:
        _, n, r, p, salt, dk = (stored or "").split("$")
        test = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(test, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ throttle login attempts
_attempts: dict[str, deque] = defaultdict(deque)


def _throttled(key: str, limit: int = 8, window: int = 900, record: bool = True) -> bool:
    """True if `key` already has `limit` recorded attempts in the window; otherwise records one (if asked)."""
    q, now = _attempts[key], time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    if record:
        q.append(now)
    return False


# ------------------------------------------------------------------ helpers used by other routes
async def current_account(request: Request) -> dict | None:
    aid = request.session.get("account_id")
    if not aid:
        return None
    return await db.fetchone("SELECT id, email, name FROM accounts WHERE id = %s", aid)


def require_csrf(request: Request) -> None:
    if request.headers.get("x-pfa") != "1":
        raise HTTPException(403, "Missing request header.")


def _login(request: Request, account_id: int) -> None:
    request.session.clear()
    request.session["account_id"] = account_id


# ------------------------------------------------------------------ email + password
@router.post("/auth/signup")
async def signup(request: Request):
    require_csrf(request)
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    name = str(body.get("name") or "").strip()[:80]
    pw = str(body.get("password") or "")
    if not EMAIL_RE.match(email):
        return JSONResponse({"error": "Please enter a valid email address."}, 400)
    if len(pw) < 8:
        return JSONResponse({"error": "Use at least 8 characters for your password."}, 400)
    if _throttled("signup:" + (request.client.host if request.client else "?"), limit=20):
        return JSONResponse({"error": "Too many attempts. Please wait a few minutes."}, 429)
    existing = await db.fetchone("SELECT id, password_hash FROM accounts WHERE email = %s", email)
    if existing:
        msg = ("An account with this email already exists. Sign in instead." if existing["password_hash"]
               else "This email is registered with Google. Use \"Continue with Google\".")
        return JSONResponse({"error": msg}, 409)
    row = await db.fetchone(
        "INSERT INTO accounts (email, name, password_hash, last_login_at) VALUES (%s, %s, %s, now()) RETURNING id",
        email, name or None, hash_password(pw))
    _login(request, row["id"])
    return {"ok": True, "next": "/start"}


@router.post("/auth/login")
async def login(request: Request):
    require_csrf(request)
    body = await request.json()
    email = str(body.get("email") or "").strip().lower()
    pw = str(body.get("password") or "")
    ip = request.client.host if request.client else "?"
    key = f"login:{email}:{ip}"
    if _throttled(key, record=False):                    # only failed attempts count
        return JSONResponse({"error": "Too many attempts. Please wait 15 minutes and try again."}, 429)
    row = await db.fetchone("SELECT id, password_hash FROM accounts WHERE email = %s", email)
    if not row or not verify_password(pw, row["password_hash"]):
        _throttled(key)
        return JSONResponse({"error": "That email and password don't match."}, 401)
    await db.execute("UPDATE accounts SET last_login_at = now() WHERE id = %s", row["id"])
    _login(request, row["id"])
    return {"ok": True, "next": "/start"}


@router.post("/auth/logout")
async def logout(request: Request):
    require_csrf(request)
    request.session.clear()
    return {"ok": True, "next": "/login"}


# ------------------------------------------------------------------ Google
def _redirect_uri() -> str:
    return settings.public_base_url + "/auth/google/callback"


@router.get("/auth/google")
async def google_start(request: Request):
    if not settings.google_enabled:
        return RedirectResponse("/login?error=google_off", 303)
    state = secrets.token_urlsafe(24)
    request.session["oauth_state"] = state
    q = urlencode({"client_id": settings.google_client_id, "redirect_uri": _redirect_uri(), "response_type": "code",
                   "scope": "openid email profile", "state": state, "prompt": "select_account"})
    return RedirectResponse(f"{GOOGLE_AUTH}?{q}", 303)


@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    expected = request.session.pop("oauth_state", None)
    if error or not code or not expected or not hmac.compare_digest(state, expected):
        return RedirectResponse("/login?error=google_failed", 303)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            tok = await client.post(GOOGLE_TOKEN, data={
                "code": code, "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
                "redirect_uri": _redirect_uri(), "grant_type": "authorization_code"})
            tok.raise_for_status()
            info = await client.get(GOOGLE_USERINFO, headers={"Authorization": f"Bearer {tok.json()['access_token']}"})
            info.raise_for_status()
            u = info.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return RedirectResponse("/login?error=google_failed", 303)
    email = str(u.get("email") or "").lower()
    if not u.get("sub") or not email or not u.get("email_verified"):
        return RedirectResponse("/login?error=google_unverified", 303)
    row = await db.fetchone("SELECT id FROM accounts WHERE google_sub = %s", u["sub"])
    if not row:
        # Link to an existing email account, or create one. Password sign-ups don't prove the person owns
        # the address, but Google does - so on linking, the Google owner takes over and any password
        # set by whoever registered the address first stops working.
        row = await db.fetchone(
            """INSERT INTO accounts (email, name, google_sub, last_login_at) VALUES (%s, %s, %s, now())
               ON CONFLICT (email) DO UPDATE SET google_sub = EXCLUDED.google_sub, password_hash = NULL,
                 name = COALESCE(accounts.name, EXCLUDED.name), last_login_at = now()
               RETURNING id""", email, (u.get("name") or "")[:80] or None, u["sub"])
    else:
        await db.execute("UPDATE accounts SET last_login_at = now() WHERE id = %s", row["id"])
    _login(request, row["id"])
    return RedirectResponse("/start", 303)
