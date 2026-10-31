"""FastAPI app: pages, intake API, plan API, report pages and the follow-up chat."""
from __future__ import annotations

import asyncio
import json as _json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import __version__, auth, db, pipeline, tracing
from .ai import chat, intake_chat, llm, voice
from .live import refresh as kb_refresh
from .config import settings
from .engine import goal_impact as engine_goal_impact
from .engine.goals import MAX_EXTRA_GOALS, PRIORITIES
from .money import fmt_short, money
from .profile import (CURRENCIES, GOALS, LOAN_TYPES, RISK_OPTIONS, apply_changes, build_profile, check_step, intro_bubble,
                      new_goal_from, reaction, sanity_fixes)
from .report import _month_text as month_text, view

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
HERE = Path(__file__).parent
log = logging.getLogger("pfa.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.open_pool()
    llm.open_client()
    tracing.init(version=__version__)
    kb_refresh.start_in_background()          # updates the knowledge base with live data (at most once a day)
    yield
    await llm.close_client()
    await db.close_pool()
    tracing.shutdown()


if not settings.session_secret or len(settings.session_secret) < 32:
    raise SystemExit("SESSION_SECRET must be set to a random string of at least 32 characters (./start.sh creates one).")

app = FastAPI(title="Personal Finance Advisor", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, session_cookie="pfa_session",
                   max_age=7 * 24 * 3600, same_site="lax", https_only=settings.cookie_secure)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.include_router(auth.router)
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.globals["v"] = __version__          # cache-busting for /static files after upgrades


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("Content-Security-Policy",
                            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                            "script-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; form-action 'self' https://accounts.google.com")
    resp.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    if request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


def page(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, {"google": settings.google_enabled, **ctx})


async def signed_in(request: Request):
    return await auth.current_account(request)


# ------------------------------------------------------------------ pages
@app.get("/")
async def home(request: Request):
    return RedirectResponse("/start" if await signed_in(request) else "/login", 303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if await signed_in(request):
        return RedirectResponse("/start", 303)
    messages = {"google_failed": "Google sign-in didn't complete. Please try again.",
                "google_unverified": "Your Google account's email isn't verified.",
                "google_off": "Google sign-in isn't set up on this server. Use email and password."}
    return page(request, "login.html", error=messages.get(error, ""))


@app.get("/start", response_class=HTMLResponse)
async def start(request: Request, fresh: int = 0):
    """v1.6: the first screen after sign-in is a chat with Arth that fills the intake (the form stays at /intake)."""
    acct = await signed_in(request)
    if not acct:
        return RedirectResponse("/login", 303)
    profile = None if fresh else await db.load_profile(acct["email"])
    reports = await db.list_reports(acct["email"]) if profile else []
    answers = dict((profile or {}).get("answers") or {"name": acct["name"] or "", "currency": "INR"})
    if profile:                                       # saved answers count as already answered
        answers["_src"] = {k: "saved" for k in ("name", "age", "ctc", "take_home", "goal_type", "target_amount", "target_date",
                                                "expenses", "loans", "investments", "emergency", "term_cover", "health_cover", "risk")}
        answers["_loans_answered"] = answers["_inv_answered"] = True
    boot = intake_chat.payload(answers, acct["email"], [], {
        "returning": bool(profile), "first_name": (answers.get("name") or acct["name"] or "").split(" ")[0],
        "reports": [{"id": r["session_id"], "when": r["created_at"].strftime("%d %b %Y"), "verdict": r["verdict"]} for r in reports[:5]],
        "goals": GOALS, "loanTypes": LOAN_TYPES})
    return page(request, "intake_chat.html", acct=acct, boot=boot)


@app.get("/intake", response_class=HTMLResponse)
async def intake(request: Request, fresh: int = 0):
    acct = await signed_in(request)
    if not acct:
        return RedirectResponse("/login", 303)
    profile = None if fresh else await db.load_profile(acct["email"])
    answers = (profile or {}).get("answers") or {"name": acct["name"] or "", "currency": "INR"}
    answers["_returning"] = bool(profile)
    boot = {"answers": answers, "intro": intro_bubble(answers.get("name"), bool(profile)),
            "goals": GOALS, "currencies": CURRENCIES, "loanTypes": LOAN_TYPES, "risk": RISK_OPTIONS,
            "priorities": PRIORITIES, "maxExtraGoals": MAX_EXTRA_GOALS}
    return page(request, "intake.html", acct=acct, boot=boot)


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def report_page(request: Request, report_id: str, fragment: int = 0):
    acct = await signed_in(request)
    if not acct:
        return RedirectResponse("/login", 303)
    r = await db.load_report(report_id[:64], acct["email"])
    if not r:
        return page(request, "message.html", acct=acct, title="Report not found",
                    text="This report doesn't exist or belongs to another account.")
    v = view(r)
    if fragment:
        return templates.TemplateResponse(request, "_report_main.html", {**v, "report_id": report_id})
    return page(request, "report.html", acct=acct, report_id=report_id, **v)


# ------------------------------------------------------------------ APIs
async def _api_account(request: Request):
    auth.require_csrf(request)
    acct = await signed_in(request)
    if not acct:
        return None, JSONResponse({"error": "Please sign in again."}, 401)
    return acct, None


@app.post("/api/intake/step")
async def intake_step(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    step, answers = int(body.get("step") or 0), body.get("answers") or {}
    errors = check_step(step, answers)
    return {"errors": errors, "bubble": None if errors else reaction(step, answers)}


@app.post("/api/intake/chat")
async def intake_chat_message(request: Request):
    """Free text from the intake chat -> one AI read (max 3 per intake) -> merged answers + what's still missing."""
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    message, answers = str(body.get("message") or "")[:3000], body.get("answers") or {}
    refusal = intake_chat.blocked(message)
    if refusal:                                       # ID numbers or prompt injection: answered locally, ₹0
        return intake_chat.payload(answers, acct["email"], [], {"reply": {"title": refusal, "lines": []}, "usage": None})
    if intake_chat.reads_used(acct["email"]) >= intake_chat.MAX_READS or not settings.ai_enabled:
        return intake_chat.payload(answers, acct["email"], [], {"usage": None, "reply": {"title":
            "Let's finish with the boxes below - they're quicker for short answers." if settings.ai_enabled else
            "The AI assistant is off, so please use the boxes below (or the form).", "lines": []}})
    try:
        extracted, use = await intake_chat.extract(acct["email"], message)
    except Exception as e:
        log.warning("intake extract failed: %s", e)
        return intake_chat.payload(answers, acct["email"], [], {"usage": None, "reply": {"title":
            "Sorry - I couldn't read that just now. Please use the boxes below, or try again.", "lines": []}})
    updated = intake_chat.merge(answers, extracted)
    intake_chat.fill_defaults(answers)
    reply = intake_chat.reply_after_read(answers, updated, intake_chat.asks(answers))
    return intake_chat.payload(answers, acct["email"], updated, {"reply": reply, "usage": {
        "cost_inr": use["cost_inr"], "cost_usd": use["cost_usd"], "ms": use["elapsed_ms"],
        "tokens": use["input_tokens"] + use["output_tokens"]}})


@app.post("/api/intake/fill")
async def intake_fill(request: Request):
    """Short answers and edits from the intake chat: read by code, no AI (unless a free-text savings answer needs one read)."""
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    answers = body.get("answers") or {}
    updated, errors, text = intake_chat.fill(answers, body.get("values") or {})
    use = None
    if text and intake_chat.reads_used(acct["email"]) < intake_chat.MAX_READS and settings.ai_enabled and not intake_chat.blocked(text):
        try:
            extracted, u = await intake_chat.extract(acct["email"], "About my savings and investments: " + text)
            updated += intake_chat.merge(answers, {"has_investments": extracted.get("has_investments"),
                                                   "investments": extracted.get("investments"), "heard": extracted.get("heard")})
            use = {"cost_inr": u["cost_inr"], "cost_usd": u["cost_usd"], "ms": u["elapsed_ms"], "tokens": u["input_tokens"] + u["output_tokens"]}
        except Exception as e:
            log.warning("intake extract (investments) failed: %s", e)
    if text and not answers.get("_inv_answered"):
        errors["investments_text"] = "I couldn't read that - try e.g. 'MF 4.5L, PPF 2L' or 'none'."
    return intake_chat.payload(answers, acct["email"], list(dict.fromkeys(updated)), {"errors": errors, "usage": use})


@app.post("/api/plan")
async def make_plan(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    answers = intake_chat.clean_for_plan((await request.json()).get("answers") or {})
    for step in range(1, 6):
        errors = check_step(step, answers)
        if errors:
            return JSONResponse({"errors": errors, "step": step}, 400)
    previous = await db.load_profile(acct["email"])
    profile = build_profile(answers, acct["email"], previous)
    notes, fields = sanity_fixes(profile)
    if fields:
        return JSONResponse({"fix": {"notes": notes, "fields": fields}}, 422)
    report_id = await pipeline.create_plan(profile, "intake")
    intake_chat.reset_reads(acct["email"])
    return {"report_url": f"/report/{report_id}"}


# ------------------------------------------------------------------ v1.7: several goals
async def _goal_request(request: Request):
    acct, err = await _api_account(request)
    if err:
        return None, None, None, err
    body = await request.json()
    profile = await db.load_profile(acct["email"])
    if not profile:
        return None, None, None, JSONResponse({"error": "Build your plan first."}, 400)
    return acct, body, profile, None


@app.post("/api/goals/impact")
async def goal_impact(request: Request):
    """What a new goal costs, three ways - pure code, no AI call, no cost."""
    acct, body, profile, err = await _goal_request(request)
    if err:
        return err
    if len(profile.get("goals_extra") or []) >= MAX_EXTRA_GOALS:
        return JSONResponse({"error": f"Your plan already has {MAX_EXTRA_GOALS + 1} goals - remove one first."}, 400)
    goal, problem = new_goal_from(body)
    if problem:
        return JSONResponse({"error": problem}, 400)
    with tracing.span("Goal impact", "CHAIN") as s:
        tracing.user(s, acct["email"])
        imp = engine_goal_impact(profile, goal)
        tracing.io(s, input=goal, output={"recommended": imp["recommended"], "monthly_cost": imp["option_a"]["monthly_cost"],
                                          "wait_months": imp["option_c"]["delay_months"]})
    cur = profile["profile"].get("currency") or "INR"
    # The impact always uses the latest saved plan (that's what "Add" changes); say so on an older report.
    shown = await db.load_report(str(body.get("report_id") or "")[:64], acct["email"]) if body.get("report_id") else None
    def goals_of(p):
        return [(p.get("goal") or {}).get("target_amount"), (p.get("goal") or {}).get("target_date")] + \
               [(g.get("name"), g.get("target_amount"), g.get("target_date")) for g in p.get("goals_extra") or []]
    older = bool(shown) and goals_of(shown.get("profile") or {}) != goals_of(profile)
    html = templates.get_template("_goal_impact.html").render(
        imp=imp, mo=lambda n: money(n, cur), sh=lambda n: fmt_short(n, cur), month_text=month_text,
        older=older, saved_goals=1 + len(profile.get("goals_extra") or []))
    return {"html": html, "recommended": imp["recommended"]}


@app.post("/api/goals/add")
async def goal_add(request: Request):
    """Add the goal to the saved answers and rebuild the plan (a new report, linked to the previous one)."""
    acct, body, profile, err = await _goal_request(request)
    if err:
        return err
    goal, problem = new_goal_from(body)
    if problem:
        return JSONResponse({"error": problem}, 400)
    answers, log_lines, ignored = apply_changes(profile, {"add_goal": goal})
    if not answers:
        return JSONResponse({"error": "; ".join(ignored) or "Nothing to change."}, 400)
    new_profile = build_profile(answers, acct["email"], previous=profile)
    report_id = await pipeline.create_plan(new_profile, "goal added", change_log=log_lines,
                                           parent=str(body.get("report_id") or "")[:64] or None)
    return {"report_url": f"/report/{report_id}#goals"}


@app.post("/api/goals/remove")
async def goal_remove(request: Request):
    acct, body, profile, err = await _goal_request(request)
    if err:
        return err
    answers, log_lines, ignored = apply_changes(profile, {"remove_goal": str(body.get("name") or "")[:80]})
    if not answers:
        return JSONResponse({"error": "; ".join(ignored) or "Nothing to change."}, 400)
    new_profile = build_profile(answers, acct["email"], previous=profile)
    report_id = await pipeline.create_plan(new_profile, "goal removed", change_log=log_lines,
                                           parent=str(body.get("report_id") or "")[:64] or None)
    return {"report_url": f"/report/{report_id}#goals"}


@app.get("/api/reports/{report_id}/status")
async def report_status(request: Request, report_id: str):
    acct = await signed_in(request)
    if not acct:
        return JSONResponse({"error": "signed out"}, 401)
    r = await db.load_report(report_id[:64], acct["email"])
    if not r:
        return JSONResponse({"error": "not found"}, 404)
    return {"writing": view(r)["writing"]}


@app.post("/api/chat")
async def chat_message(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    return await chat.answer(acct["email"], str(body.get("message") or "")[:2000], (body.get("report_id") or None))


@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    """Same as /api/chat, streamed as server-sent events: progress stages first, then the result."""
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    q: asyncio.Queue = asyncio.Queue()

    async def progress(text: str) -> None:
        await q.put({"stage": text})

    async def run():
        try:
            res = await chat.answer(acct["email"], str(body.get("message") or "")[:2000], body.get("report_id") or None,
                                    progress=progress)
            await q.put({"result": res})
        except Exception:
            logging.getLogger("pfa.chat").exception("chat failed")
            await q.put({"result": {"reply": "Sorry - something went wrong on my side. Please try again."}})

    task = asyncio.create_task(run())

    async def events():
        while True:
            item = await q.get()
            yield f"data: {_json.dumps(item, ensure_ascii=False, default=str)}\n\n"
            if "result" in item:
                break
        await task
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/chat/confirm")
async def chat_confirm(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    body = await request.json()
    return await chat.confirm(acct["email"], str(body.get("id") or "")[:32], bool(body.get("accept")))


@app.get("/api/voice/config")
async def voice_config():
    return {"engine": "openai" if voice.enabled() else "browser"}


@app.post("/api/voice/transcribe")
async def voice_transcribe(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    audio = await request.body()
    try:
        seconds = float(request.headers.get("x-audio-seconds") or 10)
        text = await voice.transcribe(acct["email"], audio, request.headers.get("content-type") or "audio/webm", seconds)
    except (PermissionError, ValueError) as e:
        return JSONResponse({"error": str(e)}, 400)
    except Exception:
        logging.getLogger("pfa.voice").exception("transcribe failed")
        return JSONResponse({"error": "I couldn't hear that clearly - please try again or type your question."}, 502)
    return {"text": text}


@app.post("/api/voice/speak")
async def voice_speak(request: Request):
    acct, err = await _api_account(request)
    if err:
        return err
    text = str((await request.json()).get("text") or "")
    if not text.strip():
        return JSONResponse({"error": "Nothing to read."}, 400)
    try:
        audio = await voice.speak(acct["email"], text)
    except PermissionError as e:
        return JSONResponse({"error": str(e)}, 400)
    except Exception:
        logging.getLogger("pfa.voice").exception("speak failed")
        return JSONResponse({"error": "The natural voice isn't available right now."}, 502)
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/chat/history")
async def chat_history(request: Request):
    acct = await signed_in(request)
    if not acct:
        return JSONResponse({"error": "signed out"}, 401)
    rows = await chat.history(acct["email"], 20)
    return {"messages": [{"role": m["role"], "content": m["content"]} for m in rows]}


@app.get("/usage", response_class=HTMLResponse)
async def usage_page(request: Request):
    acct = await signed_in(request)
    if not acct:
        return RedirectResponse("/login", 303)
    u = await db.usage_for(acct["email"])
    plans = [p for p in u["plans"] if p["usd"] is not None]
    chats = u["chats"]

    def avg(rows, k):
        vals = [r[k] for r in rows if r[k] is not None]
        return sum(vals) / len(vals) if vals else 0
    ai_chats = [c for c in chats if c["kind"] not in ("guardrail", "ai_off")]
    summary = {
        "plans": len(plans), "plan_inr": sum(p["inr"] for p in plans), "plan_avg_inr": avg(plans, "inr"),
        "plan_avg_tokens": avg(plans, "tokens"), "plan_avg_ms": avg(plans, "ms"),
        "chats": len(chats), "chat_inr": sum(c["inr"] or 0 for c in chats), "chat_avg_inr": avg(ai_chats, "inr"),
        "chat_avg_tokens": avg(ai_chats, "tokens"), "chat_avg_ms": avg(chats, "ms"),
        "blocked": sum(1 for c in chats if c["kind"] == "guardrail"),
    }
    from .usage import USD_TO_INR as _R
    summary["voice"] = {"stt": u["voice"]["stt"], "tts": u["voice"]["tts"], "inr": u["voice"]["usd"] * _R}
    summary["intake"] = {"reads": u["intake"]["reads"], "inr": u["intake"]["usd"] * _R}
    summary["total_inr"] = summary["plan_inr"] + summary["chat_inr"] + summary["voice"]["inr"] + summary["intake"]["inr"]
    from .usage import PRICES, USD_TO_INR
    return page(request, "usage.html", acct=acct, s=summary, plans=u["plans"], chats=chats,
                prices=PRICES, usd_to_inr=USD_TO_INR, model=settings.chat_model)


@app.get("/api/kb/status")
async def kb_status():
    """Public, no personal data: drives the "Updating the knowledge base" banner and start.sh progress."""
    return {k: kb_refresh.STATUS.get(k) for k in ("state", "step", "total", "message", "last_refresh")}


@app.get("/healthz")
async def healthz():
    out = {"ok": True, "ai": settings.ai_enabled, "google": settings.google_enabled, "tracing": tracing.enabled(),
           "live_data": settings.live_enabled, "kb_refresh": kb_refresh.STATUS.get("state")}
    try:
        row = await db.fetchone("SELECT to_regclass(%s) IS NOT NULL AS t", settings.kb_table)
        out["kb_chunks"] = (await db.fetchone(f"SELECT count(*) AS n FROM {settings.kb_table}"))["n"] if row["t"] else 0
    except Exception as e:
        out.update(ok=False, db_error=str(e)[:200])
    return JSONResponse(out, 200 if out["ok"] else 503)
