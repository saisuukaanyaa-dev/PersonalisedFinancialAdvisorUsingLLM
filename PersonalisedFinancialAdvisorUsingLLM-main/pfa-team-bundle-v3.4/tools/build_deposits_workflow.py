"""Builds the two n8n workflows of the bank-deposits bundle (the v3.2 bundle is only read):

  n8n/pfa_bank_deposits.json          "PFA · Bank deposit planner" - the teammate's LangGraph agent + MCP server,
                                      rebuilt as n8n nodes (gpt-5-mini, rates from Postgres, optimiser in a Code node)
  n8n/pfa_advisor_v3.2-deposits.json  the v3.2 advisor with an MCP Client tool pointing at the planner's MCP server

Run:  python3 tools/build_deposits_workflow.py      (after tools/build_deposit_db.py)
"""
import copy, json, os, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(os.path.dirname(ROOT), 'pfa-team-bundle-v3.2', 'n8n', 'pfa_advisor_v3.2.json')
NS = uuid.UUID('6c1f7f0e-2a57-4b8e-9d0c-5e3b1a9d4f21')
sid = lambda s: str(uuid.uuid5(NS, s))
DEP_ID = 'pfaBankDepositsV1'
MCP_PATH = 'bank-deposits'
MODEL = 'gpt-5-mini'
PG = {'postgres': {'id': 'DLigOZtLp73yVBeP', 'name': 'Postgres account'}}
OPENAI = {'openAiApi': {'id': 'X8YO6z75FjdGlh8o', 'name': 'OpenAI account'}}
BEARER = {'httpBearerAuth': {'id': 'pfaMcpBearer0001', 'name': 'PFA MCP bearer token'}}
WB_URL = 'https://api.worldbank.org/v2/country/IND/indicator/FP.CPI.TOTL.ZG?format=json&per_page=6'

nodes, C, by = [], {}, {}
def add(n):
    n.setdefault('id', sid(n['name'])); nodes.append(n); by[n['name']] = n; return n
def link(a, b, out=0, kind='main'):
    outs = C.setdefault(a, {}).setdefault(kind, [])
    while len(outs) <= out: outs.append([])
    outs[out].append({'node': b, 'type': kind, 'index': 0})
def code(name, pos, js, **kw):
    return add({'parameters': {'jsCode': js.strip() + '\n'}, 'name': name, 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': pos, **kw})
def llm(name, pos):
    return add({'parameters': {'model': {'__rl': True, 'mode': 'list', 'value': MODEL}, 'options': {}}, 'name': name,
                'type': '@n8n/n8n-nodes-langchain.lmChatOpenAi', 'typeVersion': 1.3, 'position': pos, 'credentials': OPENAI})
def ifnode(name, pos, expr):
    return add({'parameters': {'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
        'conditions': [{'id': sid('c:' + name), 'leftValue': expr, 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True}}],
        'combinator': 'and'}, 'options': {}}, 'name': name, 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': pos})
def note(name, pos, text, w=460, h=300, color=7):
    return add({'parameters': {'content': text, 'height': h, 'width': w, 'color': color}, 'name': name,
                'type': 'n8n-nodes-base.stickyNote', 'typeVersion': 1, 'position': pos})

INPUTS = [('action', 'string'), ('request', 'string'), ('initial_amount', 'any'), ('monthly_installment', 'any'), ('goal_amount', 'any'),
          ('goal_date', 'string'), ('inflation_pct', 'any'), ('senior', 'any'), ('banks', 'string'), ('start_date', 'string')]
def tool_workflow(name, pos, description, values):
    return add({'parameters': {'description': description, 'source': 'database', 'workflowId': {'__rl': True, 'mode': 'id', 'value': DEP_ID},
        'workflowInputs': {'mappingMode': 'defineBelow', 'value': values, 'matchingColumns': [],
            'schema': [{'id': k, 'displayName': k, 'required': False, 'defaultMatch': False, 'display': True, 'canBeUsedToMatch': True,
                        'type': t, 'removed': k not in values} for k, t in INPUTS],
            'attemptToConvertTypes': False, 'convertFieldsToString': False}},
        'name': name, 'type': '@n8n/n8n-nodes-langchain.toolWorkflow', 'typeVersion': 2.2, 'position': pos})

# ====================================================================== notes
note('About this workflow', [-420, -420], (
    "## PFA · Bank deposit planner\n"
    "The teammate's **OptimalBankDepositFinderAgent** (LangGraph + FastMCP + SQLite) rebuilt as n8n nodes.\n\n"
    "- **MCP server** `/mcp/bank-deposits` (bearer = MCP_BEARER_TOKEN) - the advisor v3.2 calls it\n"
    "- **Plan branch** (no AI): read rates from Postgres → optimiser Code node (port of GoalSearch.py)\n"
    "- **Ask branch**: guardrail → gpt-5-mini agent (same steps as the teammate's prompt) → sanitizer\n"
    "- **Chat** (hosted) for trying it by hand\n\n"
    "Rates: table `deposit_schemes`, built from the team's bank documents by `tools/build_deposit_db.py`."), w=560, h=300, color=4)

# ====================================================================== MCP server (replaces FastMCP "DocumentMCP")
add({'parameters': {'authentication': 'bearerAuth', 'path': MCP_PATH}, 'name': 'Bank Deposits MCP Server',
     'type': '@n8n/n8n-nodes-langchain.mcpTrigger', 'typeVersion': 2, 'position': [1180, 520], 'webhookId': sid('mcp-webhook'), 'credentials': BEARER})

# ====================================================================== entry points
add({'parameters': {'inputSource': 'workflowInputs', 'workflowInputs': {'values': [{'name': k, 'type': t} for k, t in INPUTS]}},
     'name': 'Planner Request', 'type': 'n8n-nodes-base.executeWorkflowTrigger', 'typeVersion': 1.1, 'position': [-400, 0]})
ifnode('Ask or Plan?', [-180, 0], "={{ String($json.action || '').toLowerCase() === 'ask' }}")
link('Planner Request', 'Ask or Plan?')

# ---------------------------------------------------------------------- plan branch (deterministic)
ifnode('Inflation Given?', [60, 120], "={{ $('Planner Request').first().json.inflation_pct !== null && $('Planner Request').first().json.inflation_pct !== undefined && String($('Planner Request').first().json.inflation_pct).trim() !== '' }}")
add({'parameters': {'url': WB_URL, 'options': {'timeout': 8000, 'response': {'response': {'responseFormat': 'text', 'outputPropertyName': 'data'}}}},
     'name': 'Get India Inflation (World Bank)', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [300, 220],
     'onError': 'continueRegularOutput'})
add({'parameters': {'operation': 'executeQuery', 'query':
        "SELECT bank_name, scheme_type, scheme_name, tenor_label, duration_months, interest_rate_general, interest_rate_senior,\n"
        "       compounding_months, installment_months, rate_source, as_of\nFROM deposit_schemes ORDER BY scheme_type, bank_name, duration_months;",
        'options': {}},
     'name': 'Read Deposit Rates', 'type': 'n8n-nodes-base.postgres', 'typeVersion': 2.5, 'position': [540, 120],
     'executeOnce': True, 'alwaysOutputData': True, 'credentials': PG})
optimiser = open(os.path.join(HERE, 'deposit_optimiser.js')).read()
optimiser = optimiser[:optimiser.index('// ---- end deposit optimiser ----') + len('// ---- end deposit optimiser ----')]
code('Optimise FD & RD Plan', [780, 120], optimiser + r'''

// Inputs from the caller; inflation from the caller, else the World Bank (latest year with data), else a stated fallback.
const p = { ...$('Planner Request').first().json };
let inflation = p.inflation_pct, source = 'given by the user';
if (inflation === null || inflation === undefined || String(inflation).trim() === '') {
  try {
    const raw = $('Get India Inflation (World Bank)').first().json.data;
    const data = (typeof raw === 'string' ? JSON.parse(raw) : raw)[1] || [];
    const pt = data.find(x => x.value !== null && x.value !== undefined);
    inflation = Math.round(pt.value * 100) / 100;
    source = `World Bank, India consumer price inflation ${pt.date}`;
  } catch (e) {
    inflation = 4; source = 'fallback 4% (RBI inflation target) - World Bank data unavailable';
  }
}
const rows = $input.all().map(i => i.json).filter(r => r && r.scheme_type);
if (!rows.length) return [{ json: { ok: false, errors: ['No deposit rates in the database - run ./start.sh to load postgres/deposits.sql'] } }];
return [{ json: planDeposits(rows, { ...p, inflation_pct: inflation, inflation_source: source }) }];
''')
link('Ask or Plan?', 'Inflation Given?', out=1)
link('Inflation Given?', 'Read Deposit Rates', out=0)
link('Inflation Given?', 'Get India Inflation (World Bank)', out=1)
link('Get India Inflation (World Bank)', 'Read Deposit Rates')
link('Read Deposit Rates', 'Optimise FD & RD Plan')
note('Plan Notes', [40, -240], (
    "### Plan branch - no AI, costs nothing\n"
    "Same maths as the teammate's `OptimalActionFixedDepositTool` / `OptimalActionRecurringDepositTool`: "
    "FD for the lump sum (rate-sorted goal search), then RD for what is left. "
    "\n\n**Two maths bugs fixed** (checked by `deposits/teammate-fixes/check_fixes.py`):\n"
    "1. **RD maturity** - standard bank formula. Rs 5,000/month, 7%, 1 year: original Rs 11,03,576, fixed Rs 62,311.\n"
    "2. **Inflation** over the whole time elapsed, not one term. 2-year FD renewed 5x at 5% inflation: original Rs 1,81,963, fixed Rs 1,22,881.\n"
    "Also: no crash when nothing fits. A fixed copy of the teammate's Python is in `deposits/teammate-fixes/`. See docs/BANK_DEPOSITS.md."),
    w=900, h=230, color=5)

# ---------------------------------------------------------------------- ask branch (agent) + chat
add({'parameters': {'public': True, 'mode': 'hostedChat', 'authentication': 'none',
                    'initialMessages': "Hi! Tell me your savings goal and I'll find the best bank FD / RD sequence.\n"
                                       "Example: I have 3 lakh now and can save 10,000 a month. I need 8 lakh by March 2030.",
                    'options': {'title': 'Bank deposit planner', 'subtitle': 'Fixed & recurring deposits - educational information, not licensed advice'}},
     'name': 'Chat Trigger', 'type': '@n8n/n8n-nodes-langchain.chatTrigger', 'typeVersion': 1.3, 'position': [-400, 420], 'webhookId': sid('chat-webhook')})
code('Question', [60, 420], r'''
// One shape for both entry points: the hosted chat and the MCP / sub-workflow "ask" call.
const j = $json;
const question = String(j.chatInput || j.request || '').slice(0, 2000);
return [{ json: { question, sessionId: j.sessionId || ('mcp-' + $execution.id) } }];
''')
link('Chat Trigger', 'Question')
link('Ask or Plan?', 'Question', out=0)

add({'parameters': {'operation': 'classify', 'text': '={{ $json.question }}', 'guardrails': {
        'jailbreak': {'value': {'threshold': 0.7}},
        'topicalAlignment': {'value': {'threshold': 0.7, 'prompt':
            "You are a content analysis system that determines if text stays on topic.\n\nBUSINESS SCOPE: Saving towards a money goal with bank "
            "fixed deposits (FD) and recurring deposits (RD) in India: amounts, goal dates, monthly savings, interest rates, banks, tenures, "
            "inflation, senior citizen rates, and general personal finance questions about deposits. Greetings and thanks are in scope.\n\n"
            "Determine if the text stays within the defined business scope. Flag any content that strays from the allowed topics."}},
        'secretKeys': {'value': {'permissiveness': 'balanced'}},
        'pii': {'value': {'type': 'selected', 'entities': ['CREDIT_CARD', 'IBAN_CODE', 'US_BANK_NUMBER', 'IN_PAN', 'IN_AADHAAR', 'IN_PASSPORT', 'IN_VOTER']}}}},
     'name': 'Deposit Question Guardrail', 'type': '@n8n/n8n-nodes-langchain.guardrails', 'typeVersion': 2, 'position': [280, 420]})
llm('Guardrail LLM', [280, 640])
link('Guardrail LLM', 'Deposit Question Guardrail', kind='ai_languageModel')
link('Question', 'Deposit Question Guardrail')

code('Polite Refusal', [560, 600], r'''
// Replaces the teammate's "I dont know the answer." for off-topic questions, and blocks PII / secrets.
const checks = JSON.stringify($json.checks || []).toLowerCase();
let output;
if (/pii|credit_card|pan|aadhaar|passport|iban|bank_number/.test(checks)) {
  output = "For your safety, please don't share card numbers, PAN, Aadhaar, passport or account numbers - I never need them.";
} else if (/secret/.test(checks)) {
  output = 'That looks like a password or secret key - please never paste those into a chat.';
} else {
  output = "I don't know the answer - I can only help with saving for a goal using bank fixed and recurring deposits.";
}
return [{ json: { output, guardrail: 'refused' } }];
''')
link('Deposit Question Guardrail', 'Polite Refusal', out=1)

SYSTEM = (
    "=You are a bank-deposit planner for India. Today is {{ $now.toFormat('yyyy-LL-dd') }}.\n\n"
    "Follow these steps (the same flow as the team's LangGraph agent):\n"
    "1. From the question, get: the lump sum they have now (initial_amount), the monthly amount they can save (monthly_installment), "
    "the goal amount and the goal date. Amounts in rupees as plain numbers (3 lakh = 300000, 1.2 crore = 12000000). "
    "A goal year alone means 1 April of that year. If the goal amount or date is missing, ask for it - never guess.\n"
    "2. Inflation: use the rate the user gives; otherwise leave inflation_pct empty and the planner fetches India's latest rate "
    "(Get_India_Inflation is for when the user asks about inflation itself).\n"
    "3. Call Plan_Bank_Deposits once with those values (senior = yes if they say they are 60+, banks = only if they name banks). "
    "It runs the fixed-deposit search for the lump sum first, then the recurring-deposit plan for whatever is left.\n"
    "4. Reply with both parts: the FD sequence (bank, tenure, rate, how many times, dates, value) and the best RD "
    "(bank, tenure, rate, monthly amount, value), then the verdict. If there is a shortfall, give the monthly installment_needed_for_goal.\n"
    "5. If the planner finds nothing, say exactly: \"Not possible with current fixed/recurring deposits interest rates.\"\n"
    "6. For questions about a bank's rates, use Get_Deposit_Rates. Never quote a rate from memory.\n\n"
    "RULES: amounts in Indian format (₹3,00,000). Say that values 'in today's money' are after inflation. Rates are card rates "
    "as of the date the tools give - tell the user to confirm with the bank, and that interest is taxable. Keep it short. "
    "If the question is not about deposits or saving for a goal, answer: \"I dont know the answer.\" "
    "End with: Educational information, not licensed financial advice.")
add({'parameters': {'promptType': 'define', 'text': "={{ $('Question').first().json.question }}", 'hasOutputParser': False,
                    'options': {'systemMessage': SYSTEM, 'maxIterations': 6}},
     'name': 'Deposit Planner Agent', 'type': '@n8n/n8n-nodes-langchain.agent', 'typeVersion': 1.7, 'position': [560, 360]})
link('Deposit Question Guardrail', 'Deposit Planner Agent', out=0)
llm('Planner LLM', [420, 700])
link('Planner LLM', 'Deposit Planner Agent', kind='ai_languageModel')
add({'parameters': {'sessionIdType': 'customKey', 'sessionKey': "={{ $('Question').first().json.sessionId }}", 'contextWindowLength': 10},
     'name': 'Chat Memory', 'type': '@n8n/n8n-nodes-langchain.memoryBufferWindow', 'typeVersion': 1.3, 'position': [560, 760]})
link('Chat Memory', 'Deposit Planner Agent', kind='ai_memory')

# tools (shared by the agent and the MCP server)
num_arg = lambda k, d: "={{ $fromAI('%s', '%s', 'number') }}" % (k, d)
str_arg = lambda k, d: "={{ $fromAI('%s', '%s', 'string') }}" % (k, d)
tool_workflow('Plan_Bank_Deposits', [700, 760],
    "Best sequence of Indian bank fixed deposits (for a lump sum) and recurring deposits (for a monthly saving) to reach a money goal "
    "by a date, after inflation. Uses the rate table from the team's bank documents. Returns the FD steps, the best RD, the verdict, "
    "any shortfall and the monthly installment needed. Pass 0 for an amount the user does not have.",
    {'action': 'plan',
     'initial_amount': num_arg('initial_amount', 'Lump sum available now, rupees. 0 if none'),
     'monthly_installment': num_arg('monthly_installment', 'Amount the user can save every month, rupees. 0 if none'),
     'goal_amount': num_arg('goal_amount', 'Goal amount in rupees, in today money'),
     'goal_date': str_arg('goal_date', 'Goal date, YYYY-MM-DD'),
     'inflation_pct': str_arg('inflation_pct', 'Yearly inflation in percent if the user gave one, else empty'),
     'senior': str_arg('senior', 'yes if the depositor is 60 or older, else no'),
     'banks': str_arg('banks', 'Comma-separated bank names to limit to (e.g. SBI, HDFC), or empty for all banks')})
link('Plan_Bank_Deposits', 'Deposit Planner Agent', kind='ai_tool')
link('Plan_Bank_Deposits', 'Bank Deposits MCP Server', kind='ai_tool')

add({'parameters': {'descriptionType': 'manual', 'toolDescription':
        "Current FD and RD card rates by bank from the team's bank documents: tenor, general and senior-citizen rate, as-of date. "
        "Input: one bank name (e.g. SBI, HDFC, Axis) or 'all' for the highest rates across banks.",
        'operation': 'executeQuery', 'query':
        "SELECT bank_name, scheme_type, tenor_label, duration_months, interest_rate_general, interest_rate_senior, rate_source, as_of\n"
        "FROM deposit_schemes\n"
        "WHERE lower($1) IN ('', 'all', 'any')\n"
        "   OR bank_name ILIKE '%' || $1 || '%'\n"
        "   OR (lower($1) = 'sbi' AND bank_name = 'State Bank of India') OR (lower($1) = 'pnb' AND bank_name = 'Punjab National Bank')\n"
        "   OR (lower($1) = 'bob' AND bank_name = 'Bank of Baroda')\n"
        "ORDER BY interest_rate_general DESC, duration_months LIMIT 30;",
        'options': {'queryReplacement': "={{ String($fromAI('bank', 'One bank name, or all', 'string') || 'all').replace(/,/g, ' ').replace(/\\bbank\\b/ig, '').trim() }}"}},
     'name': 'Get_Deposit_Rates', 'type': 'n8n-nodes-base.postgresTool', 'typeVersion': 2.5, 'position': [840, 760], 'credentials': PG})
link('Get_Deposit_Rates', 'Deposit Planner Agent', kind='ai_tool')
link('Get_Deposit_Rates', 'Bank Deposits MCP Server', kind='ai_tool')

add({'parameters': {'url': WB_URL, 'options': {},
                    'toolDescription': "India's yearly consumer price inflation (%) from the World Bank. The first entry with a value is the latest year."},
     'name': 'Get_India_Inflation', 'type': 'n8n-nodes-base.httpRequestTool', 'typeVersion': 4.5, 'position': [980, 760]})
link('Get_India_Inflation', 'Deposit Planner Agent', kind='ai_tool')

tool_workflow('GetBestBankDepositSchemeSequence', [1320, 760],
    "Ask the bank-deposit planner a question in plain English, e.g. 'I have 3 lakh and can save 10,000 a month; I need 8 lakh by March 2030'. "
    "Returns a written answer with the best FD and RD sequence. (Same tool name as the team's FastMCP server.)",
    {'action': 'ask', 'request': str_arg('request', 'The user question, with amounts, goal and goal date')})
link('GetBestBankDepositSchemeSequence', 'Bank Deposits MCP Server', kind='ai_tool')

add({'parameters': {'operation': 'sanitize', 'text': '={{ $json.output }}', 'guardrails': {
        'pii': {'value': {'type': 'selected', 'entities': ['CREDIT_CARD', 'IBAN_CODE', 'US_BANK_NUMBER', 'IN_PAN', 'IN_AADHAAR', 'IN_PASSPORT', 'IN_VOTER', 'PHONE_NUMBER']}},
        'secretKeys': {'value': {'permissiveness': 'balanced'}}}},
     'name': 'Deposit Output Sanitizer', 'type': '@n8n/n8n-nodes-langchain.guardrails', 'typeVersion': 2, 'position': [900, 360]})
code('Planner Reply', [1120, 360], r'''
// The sanitizer returns the redacted text as guardrailsInput; the chat widget and the MCP caller read `output`.
return [{ json: { output: $json.guardrailsInput } }];
''')
link('Deposit Planner Agent', 'Deposit Output Sanitizer')
link('Deposit Output Sanitizer', 'Planner Reply')
note('MCP Notes', [1120, 900], (
    "### MCP server - tools plug in from below\n"
    "An MCP Server Trigger has **no output arrow**: it is not a step in a flow. Callers (the advisor's *Bank_Deposits_MCP* node, "
    "or any MCP client) call the tools attached to its bottom. **Plan_Bank_Deposits** and **Get_Deposit_Rates** are shared with "
    "the Deposit Planner Agent, so they have two lines. **GetBestBankDepositSchemeSequence** runs this workflow's Ask branch."),
    w=520, h=190, color=3)
note('Ask Notes', [-420, 300], (
    "### Ask branch & chat (gpt-5-mini)\n"
    "Replaces LangGraph Studio and the gpt-4o agent. The input guardrail replaces llm_guard + the extra gpt-4.1 call; "
    "no tool can run free-form SQL (the original let the model write any SQL)."), w=400, h=110, color=6)

dep = {'name': 'PFA · Bank deposit planner', 'nodes': nodes, 'pinData': {}, 'connections': C, 'active': False,
       'settings': {'executionOrder': 'v1', 'callerPolicy': 'workflowsFromSameOwner'},
       'versionId': sid('dep-version-1'), 'meta': {'templateCredsSetupCompleted': True}, 'tags': [], 'id': DEP_ID}
with open(os.path.join(ROOT, 'n8n', 'pfa_bank_deposits.json'), 'w') as f:
    json.dump(dep, f, indent=2, ensure_ascii=False)

# ====================================================================== advisor v3.2 + MCP client
wf = json.load(open(SRC))
aby = {n['name']: n for n in wf['nodes']}
AC = wf['connections']
def alink(a, b, kind):
    AC.setdefault(a, {}).setdefault(kind, [[]])[0].append({'node': b, 'type': kind, 'index': 0})
kb = aby['Knowledge_Base_Search']['position']
wf['nodes'].append({'parameters': {'endpointUrl': 'http://localhost:5678/mcp/' + MCP_PATH, 'serverTransport': 'httpStreamable',
                                   'authentication': 'bearerAuth', 'include': 'selected',
                                   'includeTools': ['Plan_Bank_Deposits', 'Get_Deposit_Rates'], 'options': {'timeout': 30000}},
                    'name': 'Bank_Deposits_MCP', 'type': '@n8n/n8n-nodes-langchain.mcpClientTool', 'typeVersion': 1.4,
                    'position': [kb[0] - 220, kb[1] + 220], 'id': sid('advisor-mcp-client'), 'credentials': BEARER})
alink('Bank_Deposits_MCP', 'Investment Recommender Agent', 'ai_tool')
alink('Bank_Deposits_MCP', 'Financial Q&A Agent', 'ai_tool')
RULE = ("\n\nBANK DEPOSITS (team deposit planner over MCP): Plan_Bank_Deposits finds the best Indian bank FD/RD sequence for a goal "
        "(lump sum, monthly saving, goal amount, goal date); Get_Deposit_Rates lists card rates by bank. Use them for the fixed-income / "
        "low-risk part of the plan, for goals under 3 years, or when the user asks about FDs or RDs. Bank names, tenures and rates from "
        "these tools may be named (this is the one exception to the no-brands rule), with the as-of date the tool gives. "
        "The deposit tools do not need the user's email - for general FD/RD or rate questions, call them straight away. "
        "Never invent a rate; if the tools fail, say so and stay at category level.")
for agent in ('Investment Recommender Agent', 'Financial Q&A Agent'):
    aby[agent]['parameters']['options']['systemMessage'] += RULE
# ====================================================================== Low risk -> bank deposit planner (always, not left to the LLM)
# Compute Future Projection -> [Low risk -> bank deposits?] -yes-> Plan Bank Deposits -> Attach Deposit Plan -> Investment Recommender
#                                                           -no--------------------------------------------> Investment Recommender
cfp = aby['Compute Future Projection']
cx, cy = cfp['position']
AC['Compute Future Projection']['main'] = [[{'node': 'Low risk → bank deposits?', 'type': 'main', 'index': 0}]]
def anode(n):
    n.setdefault('id', sid('advisor:' + n['name'])); wf['nodes'].append(n); aby[n['name']] = n; return n
def amain(a, b, out=0):
    outs = AC.setdefault(a, {}).setdefault('main', [])
    while len(outs) <= out: outs.append([])
    outs[out].append({'node': b, 'type': 'main', 'index': 0})
FI = "(($json.monthly_plan && $json.monthly_plan.rows) || []).find(r => r.bucket === 'Fixed income')"
anode({'parameters': {'conditions': {'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'loose', 'version': 2},
    'conditions': [{'id': sid('c:lowrisk'), 'rightValue': True, 'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True},
        'leftValue': "={{ ($json.risk_plan.effective_risk === 'Low' || $json.risk_plan.stated_risk === 'Low' || Number($json.future_projection.years_remaining) < 3)"
                     " && Number((" + FI + " || {}).amount || 0) > 0 }}"}],
    'combinator': 'and'}, 'options': {}},
    'name': 'Low risk → bank deposits?', 'type': 'n8n-nodes-base.if', 'typeVersion': 2.2, 'position': [cx + 110, cy - 200]})
VALUES = {
    'action': 'plan',
    'initial_amount': '0',
    'monthly_installment': "={{ (" + FI + " || {}).amount || 0 }}",
    # the fixed-income share of what the monthly saving must fund: target minus what today's investments grow to
    'goal_amount': "={{ Math.round(Math.max(0, Number($json.future_projection.target_amount || 0) - Number($json.future_projection.current_corpus || 0)"
                   " * Math.pow(1 + Number($json.future_projection.assumptions.expected_annual_return_pct || 0) / 1200, Number($json.future_projection.months_remaining || 0)))"
                   " * Number($json.risk_plan.target_allocation.debt || 0) / 100) }}",
    'goal_date': "={{ String($json.future_projection.target_date || '').slice(0, 10) }}",
    'inflation_pct': '0',        # the advisor's target is a nominal amount, so compare nominal values
    'senior': "={{ Number($('Restore User State').first().json.profile?.age) >= 60 ? 'yes' : 'no' }}",
    'banks': '', 'request': '', 'start_date': '',
}
anode({'parameters': {'source': 'database', 'workflowId': {'__rl': True, 'mode': 'id', 'value': DEP_ID},
    'workflowInputs': {'mappingMode': 'defineBelow', 'value': VALUES, 'matchingColumns': [],
        'schema': [{'id': k, 'displayName': k, 'required': False, 'defaultMatch': False, 'display': True, 'canBeUsedToMatch': True,
                    'type': t, 'removed': False} for k, t in INPUTS],
        'attemptToConvertTypes': False, 'convertFieldsToString': True},
    'options': {'waitForSubWorkflow': True}},
    'name': 'Plan Bank Deposits', 'type': 'n8n-nodes-base.executeWorkflow', 'typeVersion': 1.2,
    'position': [cx + 330, cy - 200], 'onError': 'continueRegularOutput'})
anode({'parameters': {'jsCode': r'''
// The deposit planner's answer for the fixed-income part of a Low-risk (or short-horizon) plan.
// A failure never blocks the report - the plan simply goes on without the deposit section.
const proj = $('Compute Future Projection').first().json;
const p = $json || {};
const fi = (proj.monthly_plan.rows || []).find(r => r.bucket === 'Fixed income') || {};
let deposit_plan;
if (!p.ok) {
  deposit_plan = { ok: false, reason: (p.errors || [p.error && (p.error.message || p.error)] || []).filter(Boolean).join('; ') || 'deposit planner unavailable' };
} else {
  const rd = p.recurring_deposit_plan || {};
  const best = rd.best;
  deposit_plan = {
    ok: true,
    monthly_amount: fi.amount || 0,
    goal_share: p.inputs.goal_amount_todays_money,
    goal_date: p.inputs.goal_date,
    rate_type: p.inputs.rate_type,
    reached: !!rd.reached,
    verdict: best ? (rd.reached ? 'covers the fixed-income share of your goal' : 'falls short of the fixed-income share') : p.verdict,
    steps: best ? best.steps.map(s => ({ bank: s.bank, tenor: s.tenor, term_months: s.term_months, times: s.times, rate_pct: s.rate_pct,
                                         start: s.start, end: s.end, value_at_end: s.value_at_end,
                                         rate_note: /RD rate list/.test(s.rate_source || '') ? 'RD rate' : 'FD card rate for this tenor' })) : [],
    cash_months: best ? best.cash_months : 0,
    cash_value: best ? Math.round((fi.amount || 0) * best.cash_months) : 0,
    total_paid: best ? best.total_paid : 0,
    value_on_goal_date: best ? best.value_on_goal_date : 0,
    installment_needed: best ? best.installment_needed_for_goal : null,
    alternatives: (rd.alternatives || []).map(a => ({ bank: a.bank, tenor: a.tenor, rate_pct: a.rate_pct, value: a.value_in_todays_money })),
    as_of: (p.notes || []).join(' ').match(/as of ([^)]+)\)/)?.[1] || '',
  };
}
// the monthly-plan row now says where the fixed-income money goes
const rows = (proj.monthly_plan.rows || []).map(r => r.bucket === 'Fixed income' && deposit_plan.ok && deposit_plan.steps.length
  ? { ...r, instrument: 'Bank RD: ' + deposit_plan.steps.map(s => `${s.bank} ${s.term_months}m @ ${s.rate_pct}%`).join(', then ') } : r);
return [{ json: { ...proj, monthly_plan: { ...proj.monthly_plan, rows }, deposit_plan } }];
'''.strip() + '\n'}, 'name': 'Attach Deposit Plan', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [cx + 550, cy - 200]})
amain('Low risk → bank deposits?', 'Plan Bank Deposits', 0)
amain('Low risk → bank deposits?', 'Investment Recommender Agent', 1)
amain('Plan Bank Deposits', 'Attach Deposit Plan')
amain('Attach Deposit Plan', 'Investment Recommender Agent')
wf['nodes'].append({'parameters': {'content': "### Low risk → bank deposits\nLow risk (chosen or applied) or a goal under 3 years: the **fixed-income** "
    "part of the monthly plan always goes through the team's deposit planner (workflow *PFA · Bank deposit planner*). "
    "The result feeds the Recommender and the report's **Bank deposits** section. No AI, no cost.", 'height': 160, 'width': 640, 'color': 4},
    'name': 'Deposit Planner Notes', 'type': 'n8n-nodes-base.stickyNote', 'typeVersion': 1, 'position': [cx + 60, cy - 400], 'id': sid('advisor:depnote')})

rec = aby['Investment Recommender Agent']['parameters']
rec['text'] += ("{{ $json.deposit_plan ? '\\n\\nBank deposit plan for the fixed-income part (computed by the team deposit planner - present it: "
                "name these banks, tenures and rates exactly, say the rates are card rates as of ' + $json.deposit_plan.as_of + "
                "' to confirm with the bank; do not invent other rates): ' + JSON.stringify($json.deposit_plan) : '' }}")

ari = aby['Assemble Report Inputs']['parameters']
old = "const proj = $('Compute Future Projection').first().json;"
assert ari['jsCode'].count(old) == 1
ari['jsCode'] = ari['jsCode'].replace(old, "// Low-risk runs carry the deposit plan (and the updated fixed-income row) from Attach Deposit Plan.\n"
    "const proj = $('Attach Deposit Plan').isExecuted ? $('Attach Deposit Plan').first().json : $('Compute Future Projection').first().json;")

rrc = aby['Render Report Card']['parameters']
anchor = "  <h2>What you own vs what you owe</h2>"
assert rrc['jsCode'].count(anchor) == 1
DEP_SECTION = r'''  ${(() => {
    const dp = src.deposit_plan;
    if (!dp) return '';
    if (!dp.ok || !dp.steps || !dp.steps.length) return `
  <h2>Bank deposits for your fixed-income part</h2>
  <div class="card"><p class="muted">The bank deposit planner could not build a plan (${esc(dp.reason || dp.verdict || 'no deposit fits before your goal date')}).
    Use the fixed-income instruments above.</p></div>`;
    const stepRows = dp.steps.map(s => `<tr><td>${esc(s.bank)}</td><td>${esc(s.tenor)}${s.times > 1 ? ` <span class="sub">× ${s.times} back to back</span>` : ''}</td>
      <td class="num">${Number(s.rate_pct).toFixed(2)}%<br><span class="sub">${esc(s.rate_note)}</span></td>
      <td>${esc(new Date(s.start).toDateString().slice(4))} → ${esc(new Date(s.end).toDateString().slice(4))}</td>
      <td class="num">${esc(money(s.value_at_end))}</td></tr>`).join('')
      + (dp.cash_months ? `<tr><td>Savings account</td><td>Last ${dp.cash_months} month${dp.cash_months > 1 ? 's' : ''} <span class="sub">too short for an RD</span></td>
      <td class="num">-</td><td>until ${esc(new Date(dp.goal_date).toDateString().slice(4))}</td><td class="num">${esc(money(dp.cash_value))}</td></tr>` : '');
    return `
  <h2>Bank deposits for your fixed-income part · ${esc(money(dp.monthly_amount))}/month</h2>
  <div class="card">
    <p>Your ${esc(plan.effective_risk)}-risk plan puts <strong>${esc(money(dp.monthly_amount))} a month</strong> into fixed income.
      The team's deposit planner picked this recurring-deposit sequence (${esc(dp.rate_type)} rates):</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Bank</th><th>Tenure</th><th class="num">Rate</th><th>When</th><th class="num">Matures at</th></tr></thead>
      <tbody>${stepRows}</tbody></table></div>
    <div class="grid" style="margin-top:14px">
      ${tile('You pay in', money(dp.total_paid), 'monthly instalments', 'var(--muted)')}
      ${tile('Value by goal date', money(dp.value_on_goal_date), 'before tax', 'var(--c-debt)')}
      ${tile('Fixed-income share to fund', money(dp.goal_share), plan.target_allocation.debt + '% of what your monthly saving must build', 'var(--s1)')}
    </div>
    <p>${dp.reached ? `This <strong>covers</strong> the fixed-income share of your goal (your current investments cover the rest of the target as they grow).`
      : `This <strong>falls short</strong> of the fixed-income share. About <strong>${esc(money(dp.installment_needed))} a month</strong> in these deposits would cover it.`}</p>
    ${dp.alternatives && dp.alternatives.length ? `<p class="ab-legend">Single-bank alternatives: ${dp.alternatives.map(a => `${esc(a.bank)} ${esc(a.tenor)} @ ${Number(a.rate_pct).toFixed(2)}% → ${esc(money(a.value))}`).join(' · ')}.</p>` : ''}
    <p class="ab-legend">Card rates from the team's bank documents${dp.as_of ? ` (as of ${esc(dp.as_of)})` : ''} - confirm with the bank before opening.
      Interest is taxable; values are before tax. Matured deposits are kept, not reinvested.</p>
  </div>`;
  })()}

'''
rrc['jsCode'] = rrc['jsCode'].replace(anchor, DEP_SECTION + anchor)

wf['name'] = 'Personal Finance Advisor v3.2 + bank deposits'
with open(os.path.join(ROOT, 'n8n', 'pfa_advisor_v3.2-deposits.json'), 'w') as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)
print('wrote n8n/pfa_bank_deposits.json (%d nodes) and n8n/pfa_advisor_v3.2-deposits.json (%d nodes)' % (len(nodes), len(wf['nodes'])))
