#!/usr/bin/env python3
"""Builds n8n/pfa_advisor_v3.4.json from the v3.3 workflows plus the sources in n8n/src/.

What changes from v3.3:
  1. The five n8n Form pages are replaced by the app page (GET /webhook/pfa): a step form with Back, Continue and a
     review page with Edit, a start page with plan history, and a "building your plan" view.
  2. Report page with the chat beside it (GET /webhook/pfa/report). Plan changes asked in the chat are previewed,
     confirmed with Yes / No (POST /webhook/pfa/confirm) and built as a new "Updated plan" version.
  3. The bank deposit planner (formerly the separate workflow pfaBankDepositsV1) now lives inside this workflow:
     the Low-risk report step, the chat tools and the /mcp/bank-deposits MCP server. One chat for everything.

Run:  python3 tools/build_v34.py      (inputs: n8n/v33_source/*.json, n8n/src/*; output: n8n/pfa_advisor_v3.4.json)
"""
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
N8N = ROOT / "n8n"
SRC = N8N / "src"
SELF_ID = "pfaAdvisorV32App"
PG = {"postgres": {"id": "DLigOZtLp73yVBeP", "name": "Postgres account"}}
END = "// ---- end shared helpers ----"

adv = json.loads((N8N / "v33_source" / "pfa_advisor_v3.3.json").read_text())
dep = json.loads((N8N / "v33_source" / "pfa_bank_deposits.json").read_text())
nodes = {n["name"]: n for n in adv["nodes"]}
conn = adv["connections"]

# ------------------------------------------------------------------ shared helpers
bfp = nodes["Build Financial Profile"]["parameters"]["jsCode"]
HELPERS = bfp[: bfp.index(END)] + (SRC / "v34_helpers.js").read_text() + "\n" + END + "\n"


def src(name, **inline):
    code = (SRC / name).read_text()
    pre = "".join(f"const {k} = {json.dumps(v)};\n" for k, v in inline.items())
    return HELPERS + pre + code


def uid(tag):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pfa-v3.4-{tag}"))


def add(node):
    assert node["name"] not in nodes, node["name"]
    adv["nodes"].append(node)
    nodes[node["name"]] = node
    return node


def code(name, js, pos):
    return add({"parameters": {"jsCode": js}, "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2,
                "position": pos, "id": uid(name)})


def webhook(name, method, path, pos):
    return add({"parameters": {"httpMethod": method, "path": path, "responseMode": "responseNode",
                               "options": {"allowedOrigins": "*"}},
                "name": name, "type": "n8n-nodes-base.webhook", "typeVersion": 2.1, "position": pos,
                "id": uid(name), "webhookId": uid(name + "-hook")})


def respond(name, body, pos, html=False, status=None):
    headers = [{"name": "Cache-Control", "value": "no-store"}]
    if html:
        headers.insert(0, {"name": "Content-Type", "value": "text/html; charset=utf-8"})
    opts = {"responseHeaders": {"entries": headers}}
    if status:
        opts["responseCode"] = status
    return add({"parameters": {"respondWith": "text" if html else "json", "responseBody": body, "options": opts},
                "name": name, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.5, "position": pos,
                "id": uid(name)})


def pg(name, query, params, pos, always=True):
    n = {"parameters": {"operation": "executeQuery", "query": query, "options": {"queryReplacement": params}},
         "name": name, "type": "n8n-nodes-base.postgres", "typeVersion": 2.5, "position": pos, "id": uid(name),
         "credentials": PG}
    if always:
        n["alwaysOutputData"] = True
    return add(n)


def iff(name, expr, pos):
    return add({"parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                                              "conditions": [{"id": uid(name + "-c"), "leftValue": expr, "rightValue": True,
                                                              "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                                              "combinator": "and"}, "options": {}},
                "name": name, "type": "n8n-nodes-base.if", "typeVersion": 2.2, "position": pos, "id": uid(name)})


def link(a, b, out=0, kind="main", idx=0):
    outs = conn.setdefault(a, {}).setdefault(kind, [])
    while len(outs) <= out:
        outs.append([])
    outs[out].append({"node": b, "type": kind, "index": idx})


def drop(name):
    adv["nodes"].remove(nodes.pop(name))
    conn.pop(name, None)
    for c in conn.values():
        for kind, outs in c.items():
            for o in outs:
                o[:] = [t for t in o if t["node"] != name]


SAFE_ID = "String({v} || '').replace(/[^a-z0-9]/gi, '').slice(0, 40)"

# ================================================================== 1. remove the n8n Form conversation
for n in ["Intake Form", "Lookup User Profile", "Evaluate Journey", "Chat 1 · About You & Goal", "Read Goal & Income",
          "Chat 2 · Cash Flow", "Read Cash Flow", "Chat 3 · Safety Net", "Read Safety Net", "Chat 4 · Loan Types",
          "Read Loan Types", "Any Loans?", "Chat 4b · Loan Details", "Read Loan Details", "Prepare Investments Chat",
          "Chat 5 · Investments", "Ask For Missing Details", "Apply Clarifications", "Show Report", "Bank_Deposits_MCP"]:
    drop(n)

# ================================================================== 2. the app page, lookup, status, report page
X0, Y0 = -560, 900
webhook("Advisor App", "GET", "pfa", [X0, Y0])
code("Render App Page", src("app_page.js", APP_CSS=(SRC / "app.css").read_text(), APP_JS=(SRC / "app_client.js").read_text()), [X0 + 240, Y0])
respond("Respond: App Page", "={{ $json.html }}", [X0 + 480, Y0], html=True)
link("Advisor App", "Render App Page"); link("Render App Page", "Respond: App Page")

webhook("Lookup API", "POST", "pfa/lookup", [X0, Y0 + 200])
pg("Lookup User",
   """SELECT u.user_id, u.updated_at, u.profile_json,
  COALESCE((SELECT json_agg(h ORDER BY h.created_at DESC) FROM (
     SELECT session_id, created_at, report_json->'computed'->'future_projection'->>'verdict' AS verdict,
            report_json->'change_log' AS change_log
     FROM advice_sessions WHERE user_key = q.k ORDER BY created_at DESC LIMIT 12) h), '[]'::json) AS history
FROM (SELECT $1::text AS k) q LEFT JOIN users u ON u.user_key = q.k;""",
   "={{ String($json.body?.email || '').trim().toLowerCase().replace(/,/g, '') }}", [X0 + 240, Y0 + 200])
code("Lookup Result", src("lookup_result.js"), [X0 + 480, Y0 + 200])
respond("Respond: Lookup", "={{ JSON.stringify($json) }}", [X0 + 720, Y0 + 200])
link("Lookup API", "Lookup User"); link("Lookup User", "Lookup Result"); link("Lookup Result", "Respond: Lookup")

webhook("Status API", "GET", "pfa/status", [X0, Y0 + 400])
pg("Report Status", "SELECT EXISTS(SELECT 1 FROM advice_sessions WHERE session_id = $1) AS ready;",
   "={{ " + SAFE_ID.format(v="$json.query?.id") + " }}", [X0 + 240, Y0 + 400])
respond("Respond: Status", "={{ JSON.stringify({ ready: $json.ready === true }) }}", [X0 + 480, Y0 + 400])
link("Status API", "Report Status"); link("Report Status", "Respond: Status")

webhook("Report API", "GET", "pfa/report", [X0, Y0 + 600])
pg("Load Report",
   """SELECT a.session_id, a.user_key, a.created_at, a.report_json,
  (SELECT row_to_json(p) FROM pfa_chat_pending p WHERE p.id = $2 AND p.user_key = a.user_key) AS pending
FROM advice_sessions a WHERE a.session_id = $1;""",
   "={{ " + SAFE_ID.format(v="$json.query?.id") + " }},{{ " + SAFE_ID.format(v="$json.query?.pending") + " || 'none' }}",
   [X0 + 240, Y0 + 600])
code("Render Report Page", src("render_report_page.js", REPORT_CSS=(SRC / "report.css").read_text(),
                               REPORT_JS=(SRC / "report_client.js").read_text()), [X0 + 480, Y0 + 600])
respond("Respond: Report Page", "={{ $json.html }}", [X0 + 720, Y0 + 600], html=True, status="={{ $json.status }}")
link("Report API", "Load Report"); link("Load Report", "Render Report Page"); link("Render Report Page", "Respond: Report Page")

# ================================================================== 3. plan requests: form submit and confirmed chat changes
bx, by = nodes["Build Financial Profile"]["position"]
webhook("Submit API", "POST", "pfa/submit", [bx - 480, by - 160])
code("Plan Request (form)", src("plan_request_form.js"), [bx - 240, by - 160])
link("Submit API", "Plan Request (form)"); link("Plan Request (form)", "Build Financial Profile")
nodes["Build Financial Profile"]["parameters"]["jsCode"] = src("build_profile.js")

webhook("Confirm API", "POST", "pfa/confirm", [bx - 960, by + 200])
pg("Load Pending Change",
   """SELECT p.id, p.user_key, p.report_id, p.changes, u.profile_json, u.user_id
FROM pfa_chat_pending p JOIN users u ON u.user_key = p.user_key
WHERE p.id = $1 AND p.status = 'pending';""",
   "={{ " + SAFE_ID.format(v="$json.body?.id") + " }}", [bx - 720, by + 200])
code("Apply Plan Change", src("apply_plan_change.js"), [bx - 480, by + 200])
iff("Confirmed?", "={{ $json.action === 'apply' }}", [bx - 240, by + 200])
pg("Close Pending Change", "UPDATE pfa_chat_pending SET status = $2 WHERE id = $1 RETURNING id;",
   "={{ " + SAFE_ID.format(v="$json.id") + " }},{{ $json.status || 'stale' }}", [bx, by + 360])
respond("Respond: Confirm", "={{ JSON.stringify({ ok: true, reply: $('Apply Plan Change').first().json.reply }) }}", [bx + 240, by + 360])
link("Confirm API", "Load Pending Change"); link("Load Pending Change", "Apply Plan Change"); link("Apply Plan Change", "Confirmed?")
link("Confirmed?", "Build Financial Profile", 0); link("Confirmed?", "Close Pending Change", 1); link("Close Pending Change", "Respond: Confirm")

# completeness: gaps go back to the page instead of an n8n form page
nm = conn["Needs More Info?"]["main"]
nm[0] = []; nm[1] = []
cx, cy = nodes["Needs More Info?"]["position"]
code("Explain Fixes", src("explain_fixes.js"), [cx + 240, cy - 140])
respond("Respond: Fix These", "={{ JSON.stringify($json) }}", [cx + 480, cy - 140])
respond("Respond: Building",
        "={{ JSON.stringify({ ok: true, report_id: $json.session_id, reply: ($json.change_log || []).length ? "
        "'Done! Building your updated plan:\\n' + $json.change_log.map(c => '- ' + c).join('\\n') : undefined }) }}",
        [cx + 240, cy + 120])
link("Needs More Info?", "Explain Fixes", 0); link("Explain Fixes", "Respond: Fix These")
link("Needs More Info?", "Respond: Building", 1); link("Respond: Building", "Prepare User Storage")

# save: keep the change log / parent version, and close the pending change that produced this plan
pah = nodes["Prepare Advice History"]["parameters"]["jsCode"]
pah = pah.replace("""    generated_at: new Date().toISOString(),
  },""", """    generated_at: new Date().toISOString(),
    user_name: d.profile?.user_name || '',
    change_log: d.change_log || [],
    parent: d.parent_report || null,
  },
  pending_id: d.pending_id || null,""")
assert "change_log: d.change_log" in pah
nodes["Prepare Advice History"]["parameters"]["jsCode"] = pah
nodes["Save Advice History"]["parameters"]["query"] = """WITH payload AS (
  SELECT convert_from(decode($1, 'base64'), 'UTF8')::jsonb AS d
), saved AS (
  INSERT INTO advice_sessions (session_id, user_id, user_key, question, report_json)
  SELECT p.d->>'session_id', u.user_id, p.d->>'user_key', p.d->>'question', p.d->'report'
  FROM payload p
  LEFT JOIN users u ON u.user_key = p.d->>'user_key'
  ON CONFLICT (session_id) DO UPDATE SET report_json = EXCLUDED.report_json
  RETURNING session_id
), applied AS (
  UPDATE pfa_chat_pending SET status = 'applied', new_report = (SELECT session_id FROM saved)
  WHERE id = (SELECT d->>'pending_id' FROM payload) AND status = 'pending'
  RETURNING id
)
SELECT session_id FROM saved;"""

# ================================================================== 4. one chat: report-page chat + hosted chat, plan changes
tx, ty = nodes["Chat Trigger"]["position"]
webhook("Chat API", "POST", "pfa/chat", [tx, ty + 220])
pg("Chat Report Owner", "SELECT (SELECT user_key FROM advice_sessions WHERE session_id = $1) AS user_key;",
   "={{ " + SAFE_ID.format(v="$json.body?.report_id") + " }}", [tx + 220, ty + 220])
code("Chat Context", src("chat_context.js"), [tx + 220, ty])
conn["Chat Trigger"]["main"] = [[]]
link("Chat Trigger", "Chat Context"); link("Chat API", "Chat Report Owner"); link("Chat Report Owner", "Chat Context")
gx, gy = nodes["Chat Input Guardrail"]["position"]
nodes["Chat Input Guardrail"]["position"] = [gx + 220, gy]
link("Chat Context", "Chat Input Guardrail")
nodes["Chat Trigger"]["parameters"]["initialMessages"] = ("Hi! I can answer questions about your saved plan, bank deposits and mutual funds.\n"
                                                          "Share the email you used in the advisor to get started - or chat right next to your plan on its report page.")

qa = nodes["Financial Q&A Agent"]
qa["parameters"]["text"] = "={{ $('Chat Context').first().json.agentInput }}"
qa["parameters"]["options"]["returnIntermediateSteps"] = True
qa["parameters"]["options"]["systemMessage"] += (
    "\n\nPLAN CHANGES (the app shows the user a Yes / No card - you never apply anything yourself)\n"
    "- When the user clearly asks to change a number in their plan (\"invest 40K a month\", \"my salary is now 1.6L\", "
    "\"move my goal to 2030\", \"I closed my car loan\", \"make it Low risk\"), call Propose_Plan_Change once with ONLY the fields "
    "they asked to change (plain rupee numbers: 40K -> 40000, 1.5L -> 150000; dates YYYY-MM-DD) and their email.\n"
    "- monthly_sip_total is the TOTAL they will invest every month, only when they change how much they invest. Money for the "
    "emergency fund is never monthly_sip_total: a one-time amount is emergency_lumpsum. Do not reduce their SIPs unless they say so.\n"
    "- A what-if question (\"what if I invested 40K?\") is a change request too: explain the likely effect briefly, then propose it.\n"
    "- If the request is ambiguous, ask one clarifying question instead of calling the tool.\n"
    "- After calling it, restate the change in one friendly sentence and say they can confirm with the Yes button below. "
    "Never say the plan has been updated.\n\n"
    "STYLE: never show internal field names (term_cover, recommended_term_cover, monthly_plan, effective_risk...) - say \"term cover\", "
    "\"recommended cover\". Write rupees the Indian way: ₹1.4 Cr, ₹24 L, ₹45,000 (not ₹14,000,000).")
nodes["Chat Memory"]["parameters"]["sessionKey"] = "={{ $('Chat Context').first().json.sessionId }}"

ax, ay = qa["position"]
add({"parameters": {"name": "Propose_Plan_Change",
                    "description": ("Propose a change to the user's saved plan. Nothing is changed until the user presses Yes in the app. "
                                    "Fill only the fields the user asked to change, plus their email."),
                    "language": "javaScript",
                    "jsCode": ("return JSON.stringify({ status: 'proposed', note: 'Nothing is changed yet. The app now shows the user a "
                               "Yes / No card listing these changes. Tell them in one sentence and ask them to confirm below.' });"),
                    "specifyInputSchema": True, "schemaType": "manual",
                    "inputSchema": json.dumps({
                        "type": "object", "required": ["email"],
                        "properties": {
                            "email": {"type": "string", "description": "The user's email (lowercase)"},
                            "monthly_sip_total": {"type": ["number", "null"], "description": "New TOTAL monthly investing in rupees"},
                            "target_amount": {"type": ["number", "null"]}, "target_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                            "risk_appetite": {"type": ["string", "null"], "enum": ["Low", "Medium", "High", None]},
                            "take_home": {"type": ["number", "null"], "description": "Monthly in-hand salary"},
                            "annual_ctc": {"type": ["number", "null"]}, "expenses": {"type": ["number", "null"], "description": "Monthly essentials"},
                            "emergency_fund": {"type": ["number", "null"], "description": "New emergency fund total"},
                            "emergency_lumpsum": {"type": ["number", "null"], "description": "One-time amount added to the emergency fund"},
                            "term_cover": {"type": ["number", "null"]}, "health_cover": {"type": ["number", "null"]},
                            "remove_loan": {"type": ["string", "null"], "description": "Loan type to remove, e.g. Car loan"}}}, indent=1)},
     "name": "Propose_Plan_Change", "type": "@n8n/n8n-nodes-langchain.toolCode", "typeVersion": 1.3,
     "position": [ax + 860, ay + 220], "id": uid("propose")})
link("Propose_Plan_Change", "Financial Q&A Agent", kind="ai_tool")

# after the agent: sanitise -> result -> (change? preview + save pending) -> reply to the right door
conn["Chat Output Sanitizer"]["main"] = [[]]
sx, sy = nodes["Chat Output Sanitizer"]["position"]
code("Chat Result", src("chat_result.js"), [sx + 220, sy])
iff("Plan Change?", "={{ $json.has_change === 'yes' }}", [sx + 440, sy])
pg("Load Profile For Change",
   """SELECT u.profile_json,
  (SELECT session_id FROM advice_sessions WHERE user_key = q.k ORDER BY created_at DESC LIMIT 1) AS latest_report
FROM (SELECT $1::text AS k) q LEFT JOIN users u ON u.user_key = q.k;""",
   "={{ String($json.change_email || '').replace(/,/g, '') }}", [sx + 660, sy - 160])
code("Preview Plan Change", src("preview_change.js"), [sx + 880, sy - 160])
pg("Save Pending Change",
   """WITH p AS (SELECT convert_from(decode($1, 'base64'), 'UTF8')::jsonb AS d)
INSERT INTO pfa_chat_pending (id, user_key, report_id, changes, preview, message)
SELECT d->>'id', d->>'user_key', d->>'report_id', d->'changes', d->'preview', d->>'message' FROM p WHERE d ? 'id'
RETURNING id;""", "={{ $json.pending_b64 }}", [sx + 1100, sy - 160])
code("Use Preview Reply", "\n// Back to the reply (the insert above returns only the id).\nreturn [{ json: $('Preview Plan Change').first().json }];\n",
     [sx + 1320, sy - 160])
iff("Reply To Page?", "={{ $('Chat Context').first().json.channel === 'page' }}", [sx + 1540, sy])
respond("Respond: Chat", "={{ JSON.stringify({ reply: $json.reply ?? $json.output ?? '', confirm: $json.confirm || null }) }}", [sx + 1760, sy - 100])
cr = nodes["Chat Reply"]
cr["parameters"]["jsCode"] = (SRC / "chat_reply_hosted.js").read_text()
cr["position"] = [sx + 1760, sy + 100]
link("Chat Output Sanitizer", "Chat Result"); link("Chat Result", "Plan Change?")
link("Plan Change?", "Load Profile For Change", 0); link("Plan Change?", "Reply To Page?", 1)
link("Load Profile For Change", "Preview Plan Change"); link("Preview Plan Change", "Save Pending Change")
link("Save Pending Change", "Use Preview Reply"); link("Use Preview Reply", "Reply To Page?")
link("Reply To Page?", "Respond: Chat", 0); link("Reply To Page?", "Chat Reply", 1)
conn["Polite Refusal"] = {"main": [[]]}
link("Polite Refusal", "Reply To Page?")

# ================================================================== 5. the deposit planner moves in (no separate workflow)
RENAME = {"Chat Memory": "Deposit Chat Memory", "Guardrail LLM": "Deposit Guardrail LLM", "Polite Refusal": "Deposit Polite Refusal",
          "About this workflow": "Deposit Planner Overview", "Chat Trigger": None}
max_y = max(n["position"][1] for n in adv["nodes"])
min_y = min(n["position"][1] for n in dep["nodes"])
min_x = min(n["position"][0] for n in dep["nodes"])
shift = (-560 - min_x, max_y + 700 - min_y)
for n in dep["nodes"]:
    if n["name"] in RENAME and RENAME[n["name"]] is None:
        continue
    n = json.loads(json.dumps(n))
    new = RENAME.get(n["name"], n["name"])
    p = json.dumps(n["parameters"])
    for old, nw in RENAME.items():
        if nw:
            p = p.replace(f"$('{old}')", f"$('{nw}')")
    p = p.replace('"pfaBankDepositsV1"', f'"{SELF_ID}"')
    n["parameters"] = json.loads(p)
    n["name"] = new
    n["id"] = uid("dep-" + new)
    n["position"] = [n["position"][0] + shift[0], n["position"][1] + shift[1]]
    if n["type"].endswith("mcpTrigger"):
        n["webhookId"] = uid("dep-mcp-hook")
    add(n)
for src_name, c in dep["connections"].items():
    if src_name == "Chat Trigger":
        continue
    a = RENAME.get(src_name, src_name)
    for kind, outs in c.items():
        for i, o in enumerate(outs):
            for t in o:
                link(a, RENAME.get(t["node"], t["node"]) or t["node"], i, kind, t.get("index", 0))
pbd = nodes["Plan Bank Deposits"]["parameters"]
pbd["workflowId"]["value"] = SELF_ID
pbd["workflowId"].pop("cachedResultName", None)
for tool in ["Plan_Bank_Deposits", "Get_Deposit_Rates"]:
    link(tool, "Financial Q&A Agent", kind="ai_tool"); link(tool, "Investment Recommender Agent", kind="ai_tool")
link("Get_India_Inflation", "Financial Q&A Agent", kind="ai_tool")

# ================================================================== 5b. teammate knowledge as HTTP tools (not MCP clients)
# n8n's MCP client connects when the agent starts, so a stopped teammate container made every chat fail.
# HTTP tools connect only when called, and a failure comes back to the agent as text.
for old in ["Teammate_Advisor_MCP", "Teammate_Deposit_Schemes"]:
    pos = nodes[old]["position"]
    drop(old)
TEAMMATE = "http://teammate-advisor:8090/ask/"
for i, (tool, desc) in enumerate([
        ("Ask_Bank_Deposit_Schemes", "The team's bank documents (teammate service): a named bank's deposit schemes - features, premature-withdrawal "
                                      "penalties, RD rules, senior-citizen benefits, loans or overdraft against FDs - for Axis, Bank of Baroda, Canara, "
                                      "HDFC, ICICI, IDFC FIRST, Kotak, PNB and SBI. Send one plain question."),
        ("Ask_Mutual_Funds", "The team's mutual-fund summaries (teammate service): facts about SBI Focused, Bank of India Flexi Cap, HDFC Flexi Cap, "
                             "ICICI Prudential Large Cap, JM Flexi Cap, Nippon India Large Cap, Nippon India Small Cap, Parag Parikh Flexi Cap, "
                             "Quant Flexi Cap - category, AMC, NAV, AUM, expense ratio, exit load, minimum investment. Send one plain question.")]):
    add({"parameters": {"toolDescription": desc, "method": "POST", "url": TEAMMATE + tool,
                        "authentication": "genericCredentialType", "genericAuthType": "httpBearerAuth",
                        "sendBody": True, "specifyBody": "json",
                        "jsonBody": "={{ JSON.stringify({ question: $fromAI('question', 'One plain-English question', 'string') }) }}",
                        "options": {"timeout": 120000}},
         "name": tool, "type": "n8n-nodes-base.httpRequestTool", "typeVersion": 4.5, "onError": "continueRegularOutput",
         "position": [620 + i * 220, 2460], "id": uid(tool),
         "credentials": {"httpBearerAuth": {"id": "pfaMcpBearer0001", "name": "PFA MCP bearer token"}}})
    link(tool, "Financial Q&A Agent", kind="ai_tool")
link("Ask_Bank_Deposit_Schemes", "Deposit Planner Agent", kind="ai_tool")
nodes["Teammate Notes"]["parameters"]["content"] = (
    "## 7. TEAMMATE SERVICE\n\n**Ask_Bank_Deposit_Schemes** and **Ask_Mutual_Funds** call the team's PersonalisedFinancialAdvisorUsingLLM "
    "project in its own container (`teammate-advisor`, Python + LangGraph): hybrid RAG (BM25 + Chroma + cross-encoder rerank) with "
    "their llm_guard checks.\n\nCalled as HTTP tools (`/ask/<tool>`, same bearer token) so the chat keeps working if that container "
    "is down. The same tools are also published over MCP at `:8090/mcp` for MCP clients. Traced in Phoenix (`pfa-teammate-advisor`).")

# ================================================================== 6. notes on the canvas
nodes["Stage 1 Notes"]["parameters"]["content"] = (
    "## 1-2. THE APP (v3.4)\n\n`GET /webhook/pfa` serves the advisor app: email -> **start page** (latest plan, update my answers, "
    "start fresh, plan history) -> **step form** with Back / Continue -> **review** with Edit -> Build my plan.\n\n"
    "`POST pfa/lookup` pre-fills returning users. `POST pfa/submit` -> Build Financial Profile -> guardrail -> completeness: gaps go "
    "back to the page (**Explain Fixes**), otherwise **Respond: Building** returns the report id and the pipeline carries on.\n"
    "The page polls `GET pfa/status` and opens `GET pfa/report` (report + chat).")
nodes["Stage 2 Notes"]["parameters"]["content"] = (
    "## 3. CHECKS BEFORE BUILDING\n\nAmounts are checked as you type on the page (same parseAmount as here). "
    "The Goal Text Guardrail and Check Profile Completeness still run on the server; anything they flag is sent back to the "
    "step it belongs to.")
nodes["Chat Notes"]["parameters"]["content"] = (
    "## 6. ONE CHAT (v3.4)\n\nTwo doors, one agent: the chat on the report page (`POST pfa/chat`) and n8n's hosted chat. "
    "**Chat Context** normalises both. Tools: profile, latest report, knowledge base, market data, bank deposits (planner, rates, "
    "inflation), the teammate's scheme / fund RAG, and **Propose_Plan_Change**.\n\nA proposed change is previewed and saved as "
    "pending; the page shows Yes / No. `POST pfa/confirm` applies it to the saved answers and re-runs the same pipeline -> a new "
    "**Updated plan** version.")
add({"parameters": {"width": 640, "height": 220, "color": 4, "content":
     "## 8. BANK DEPOSIT PLANNER (inside this workflow since v3.4)\n\nFormerly the separate workflow *PFA · Bank deposit planner*. "
     "`Planner Request` is called by **Plan Bank Deposits** (Low-risk report step) and by the chat tools **Plan_Bank_Deposits** / "
     "**GetBestBankDepositSchemeSequence** - all within this workflow. The MCP server `/mcp/bank-deposits` is here too."},
     "name": "Deposit Section Notes", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
     "position": [-560, shift[1] + min_y - 300], "id": uid("dep-notes")})

adv["name"] = "Personal Finance Advisor v3.4 (step form, one chat, deposits inside)"
out = N8N / "pfa_advisor_v3.4.json"
out.write_text(json.dumps(adv, indent=2, ensure_ascii=False))

# sanity: every connection points at a node that exists, and no expression names a node that is gone
names = set(nodes)
for a, c in conn.items():
    assert a in names, f"connection from missing node {a}"
    for kind, outs in c.items():
        for o in outs:
            for t in o:
                assert t["node"] in names, f"{a} -> missing {t['node']}"
missing = set()
PAGE_NODES = {"Render App Page", "Render Report Page"}      # their inlined browser code uses $('id') for document.getElementById
for n in adv["nodes"]:
    if n["name"] in PAGE_NODES:
        continue
    for ref in re.findall(r"\$\('([^']+)'\)", json.dumps(n["parameters"])):
        if ref not in names:
            missing.add((n["name"], ref))
assert not missing, f"expressions name missing nodes: {sorted(missing)}"
print(f"wrote {out.relative_to(ROOT)}: {len(adv['nodes'])} nodes")
