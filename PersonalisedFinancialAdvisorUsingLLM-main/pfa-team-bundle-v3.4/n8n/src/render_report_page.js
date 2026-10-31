
// GET /webhook/pfa/report?id=…[&pending=…] - the saved report with the chat beside it.
// REPORT_CSS and REPORT_JS are inlined by tools/build_v34.py.
const row = $json || {};
const q = $('Report API').first().json.query || {};
let rep = row.report_json;
if (typeof rep === 'string') { try { rep = JSON.parse(rep); } catch (e) { rep = null; } }
const safe = s => String(s).replace(/<\/script/gi, '<\\/script');
if (!row.session_id || !rep) {
  return [{ json: { status: 404, html: `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Plan not found</title><style>${REPORT_CSS}</style>
<main class="wrap"><div class="card"><h1>That plan could not be found</h1><p>The link may be incomplete. <a href="../pfa">Go to the start page</a>.</p></div></main>` } }];
}
let pending = row.pending || null;
if (typeof pending === 'string') { try { pending = JSON.parse(pending); } catch (e) { pending = null; } }
const changes = rep.change_log || [];
const first = String(rep.user_name || '').split(' ')[0] || 'there';
const boot = {
  report_id: row.session_id, email: row.user_key, first_name: first,
  pending: pending && pending.status === 'pending' && pending.id === String(q.pending || '') ? { id: pending.id, changes: pending.preview || [] } : null,
};
const banner = changes.length ? `<div class="updated"><strong>Updated plan</strong> - changes you asked for in the chat:<ul>${changes.map(c => `<li>${esc(c)}</li>`).join('')}</ul>
  ${rep.parent ? `<a href="report?id=${encodeURIComponent(rep.parent)}">See the previous version</a>` : ''}</div>` : '';
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Your plan · Personal Finance Advisor</title><style>${REPORT_CSS}</style></head><body>
<header class="bar"><div class="logo">₹</div><div><b>Personal Finance Advisor</b><span>Plan for ${esc(rep.user_name || row.user_key)} · ${esc(new Date(row.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }))}</span></div>
<a class="plans" href="../pfa?email=${encodeURIComponent(row.user_key)}">Your plans</a></header>
<div class="layout"><div class="report-col">${banner}${rep.html || ''}</div>
<aside class="chat" id="chat"><div class="chat-head"><b>Ask about your plan</b><span>Questions, what-ifs, bank deposits, mutual funds. Changes are shown first and only made when you press Yes.</span></div>
<div class="chat-log" id="log"></div><div class="chips" id="chips"></div>
<form class="chat-box" id="box"><input id="msg" autocomplete="off" placeholder="e.g. What if I invest 40K a month?" maxlength="1500"><button class="send" type="submit">Send</button></form></aside></div>
<script>window.BOOT=${JSON.stringify(boot).replace(/</g, '\\u003c')};
${safe(REPORT_JS)}</script></body></html>`;
return [{ json: { status: 200, html } }];
