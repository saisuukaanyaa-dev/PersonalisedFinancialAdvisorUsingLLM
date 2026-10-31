
// GET /webhook/pfa - the advisor app: start page, step form with Back / Edit, building view.
// APP_CSS and APP_JS are inlined by tools/build_v34.py from src/app.css and src/app_client.js.
const q = $json.query || {};
const boot = {
  email: String(q.email || '').trim().toLowerCase().slice(0, 120),
  building: String(q.building || '').replace(/[^a-z0-9]/gi, '').slice(0, 40),
};
const helpers = [parseAmount, parseOptional, parseRate, estimateInHand, fmtShort, shorthand].map(f => f.toString()).join('\n')
  + `\nconst trim2 = ${trim2.toString()};\nconst LOAN_TYPES = ${JSON.stringify(LOAN_TYPES)};\nconst NO_LOANS = ${JSON.stringify(NO_LOANS)};`
  + `\nconst GOALS = ${JSON.stringify(GOALS)};\nconst CURRENCIES = ${JSON.stringify(CURRENCIES)};`;
const safe = s => s.replace(/<\/script/gi, '<\\/script');
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Personal Finance Advisor</title><style>${APP_CSS}</style></head><body>
<header class="top"><div class="logo">₹</div><div><b>Personal Finance Advisor</b><span>Educational information, not licensed financial advice</span></div></header>
<main id="app"><div class="card"><p class="muted">Loading…</p></div></main>
<p class="foot">Group 2 capstone · made-up data only, please · nothing here is licensed financial advice</p>
<script>window.BOOT=${JSON.stringify(boot).replace(/</g, '\\u003c')};
${safe(helpers)}
${safe(APP_JS)}</script></body></html>`;
return [{ json: { html } }];
