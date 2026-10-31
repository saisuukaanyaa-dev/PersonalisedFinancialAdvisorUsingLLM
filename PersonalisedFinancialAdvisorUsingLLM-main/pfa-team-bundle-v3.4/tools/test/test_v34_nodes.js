// Offline checks for the v3.4 Code nodes (no n8n, no AI): syntax of every Code node, then the main ones run with
// made-up data in a tiny n8n-like harness.   node tools/test/test_v34_nodes.js
const fs = require('fs'); const path = require('path'); const vm = require('vm');
const wf = JSON.parse(fs.readFileSync(path.join(__dirname, '../../n8n/pfa_advisor_v3.4.json'), 'utf8'));
const nodes = Object.fromEntries(wf.nodes.map(n => [n.name, n]));
let ok = true; const check = (label, cond, extra) => { ok = ok && !!cond; console.log((cond ? 'PASS ' : 'FAIL ') + label + (cond || !extra ? '' : '  ' + extra)); };
// 1. every Code node parses
for (const n of wf.nodes.filter(n => n.type === 'n8n-nodes-base.code')) {
  try { new Function('$json', '$', '$execution', '$env', 'Buffer', n.parameters.jsCode); } catch (e) { check(`syntax: ${n.name}`, false, e.message); continue; }
}
check('all Code nodes parse', ok);
// 2. run a node: $json = input, $('Name').first().json from a map
function run(name, input, refs = {}) {
  const fn = new Function('$json', '$', '$execution', '$env', 'Buffer', nodes[name].parameters.jsCode);
  const $ = n => ({ first: () => ({ json: refs[n] }), get isExecuted() { return n in refs; } });
  return fn(input, $, { id: '99' }, {}, Buffer)[0].json;
}
const answers = { user_name: 'Anil Sample', age: '34', currency: 'INR', annual_ctc: '1.35Cr', goal_type: 'Buy a home', goal_details: '3BHK',
  target_amount: '3Cr', target_date: '2033-06-30', take_home: '6.5L', expenses: '2L', emergency: '12L', term_cover: '5Cr', term_premium: '45K',
  health_cover: '25L', health_premium: '40K', loan_types: ['Car loan'], loans: { 'Car loan': { outstanding: '3L', rate: '9.2', emi: '11K' } },
  investments: { mf_value: '40L', mf_monthly: '1.5L', fd_value: '20L', pf_value: '30L', pf_monthly: '25K', other_label: '' }, risk: 'Low' };
const req = run('Plan Request (form)', { body: { email: 'Anil.Test@Example.test', journey: 'new', answers } });
check('plan request lower-cases the email', req.email === 'anil.test@example.test');
const d = run('Build Financial Profile', req);
check('profile: CTC 1.35Cr read', d.profile.annual_ctc === 13500000, d.profile.annual_ctc);
check('profile: in-hand, risk, goal', d.profile.current_monthly_salary === 650000 && d.profile.risk_appetite === 'Low' && d.goal.description === 'Buy a home - 3BHK');
check('profile: loan + investments', d.liabilities.length === 1 && d.liabilities[0].emi === 11000 && d.savings_investments.length === 3);
check('profile: nothing unreadable', d.unreadable.length === 0, JSON.stringify(d.unreadable));
check('profile: unguessable report id', /^[a-z0-9]{32}$/.test(d.session_id), d.session_id);
check('profile: raw answers kept', d.form_answers.raw.annual_ctc === '1.35Cr');
const bad = run('Build Financial Profile', { ...req, answers: { ...answers, annual_ctc: '1Cr 35L' } });
check('"1Cr 35L" is flagged, not guessed', bad.profile.annual_ctc === null && bad.unreadable[0].path.join('.') === 'profile.annual_ctc');
// 3. the completeness check output -> fixes for the page
const cpcOut = { ...bad, clarification_form_fields: [{ fieldType: 'html', html: '<h3>Nearly there</h3><p>There\'s one thing I couldn\'t quite read.</p>' },
  { fieldLabel: 'Current CTC (annual)', fieldName: 'fix_0', placeholder: 'I couldn\'t read "1Cr 35L"' }], clarification_map: [{ fieldName: 'fix_0', path: ['profile', 'annual_ctc'], kind: 'amount' }] };
const fx = run('Explain Fixes', cpcOut);
check('fixes point at the CTC field', fx.ok === false && fx.fixes[0].field === 'annual_ctc' && fx.notes.length === 1);
// 4. lookup -> answers back from a saved v3.4 profile, and from an older profile
const lk = run('Lookup Result', { user_id: 7, updated_at: '2026-10-05', profile_json: d, history: [{ session_id: 'abc', created_at: '2026-10-05', verdict: 'on_track', change_log: [] }] },
  { 'Lookup API': { body: { email: 'anil.test@example.test' } } });
check('lookup: known user, raw answers, history', lk.known && lk.answers.annual_ctc === '1.35Cr' && lk.history[0].verdict_label === 'On track');
const old = { profile: { user_name: 'Old User', currency: 'INR', annual_ctc: 1800000, current_monthly_salary: 122000, risk_appetite: 'Medium' },
  goal: { description: 'Buy a home', target_amount: 8000000, target_date: '2031-12-31' }, liabilities: [{ type: 'Car loan', outstanding_amount: 320000, interest_rate: 9.2, emi: 11000 }],
  savings_investments: [{ type: 'Equity Mutual Funds', current_value: 450000, monthly_contribution: 15000 }], emergency_fund: { current_amount: 150000, monthly_essential_expenses: 45000 }, insurance: [] };
const lk2 = run('Lookup Result', { user_id: 8, profile_json: old, history: [] }, { 'Lookup API': { body: { email: 'old@example.test' } } });
check('lookup: older profile mapped to answers', lk2.answers.annual_ctc === '18L' && lk2.answers.loans['Car loan'].outstanding === '3.2L' && lk2.answers.goal_type === 'Buy a home');
// 5. chat: proposed change -> preview -> confirm applies it
const ctx = { channel: 'page', chatInput: 'what if I invest 2L a month?', user_key: 'anil.test@example.test', report_id: 'abc', sessionId: 'page-x' };
const agent = { output: 'Sure!', intermediateSteps: [{ action: { tool: 'Propose_Plan_Change', toolInput: { email: 'anil.test@example.test', monthly_sip_total: 200000, target_date: null } } }] };
const cr = run('Chat Result', { guardrailsInput: 'Sure! Confirm below.' }, { 'Chat Context': ctx, 'Financial Q&A Agent': agent });
check('chat: change found', cr.has_change === 'yes' && cr.changes.monthly_sip_total === 200000 && !('target_date' in cr.changes));
const pv = run('Preview Plan Change', { profile_json: d, latest_report: 'abc' }, { 'Chat Result': cr });
check('chat: preview lists the change', pv.confirm && /Monthly investing ₹1.75L → ₹2L/.test(pv.confirm.changes[0]), JSON.stringify(pv.confirm));
const pend = JSON.parse(Buffer.from(pv.pending_b64, 'base64').toString());
const ap = run('Apply Plan Change', { id: pend.id, user_key: pend.user_key, report_id: 'abc', changes: pend.changes, profile_json: d, user_id: 7 },
  { 'Confirm API': { body: { id: pend.id, accept: true } } });
check('confirm: answers changed, change log, parent', ap.action === 'apply' && ap.answers.investments.mf_monthly === '1.75L' && ap.parent === 'abc' && ap.change_log.length === 1, JSON.stringify(ap.answers.investments));
const d2 = run('Build Financial Profile', ap);
check('confirm: new profile invests 2L a month', d2.derived.monthlyContrib === 200000 && d2.change_log.length === 1 && d2.profile_source === 'chat_change', d2.derived.monthlyContrib);
const no = run('Apply Plan Change', { id: pend.id, user_key: 'x', profile_json: d }, { 'Confirm API': { body: { id: pend.id, accept: false } } });
check('confirm: No keeps the plan', no.action === 'decline');
const rm = run('Apply Plan Change', { id: 'p2', user_key: 'anil.test@example.test', report_id: 'abc', changes: { remove_loan: 'car loan' }, profile_json: d }, { 'Confirm API': { body: { id: 'p2', accept: true } } });
check('confirm: remove loan -> debt-free', rm.answers.loan_types[0] === "None - I'm debt-free" && run('Build Financial Profile', rm).liabilities.length === 0);
// 6. the pages render and their scripts parse
const app = run('Render App Page', { query: { email: 'anil.test@example.test' } });
const scripts = [...app.html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
try { new vm.Script(scripts[0]); check('app page: script parses', true); } catch (e) { check('app page: script parses', false, e.message); }
check('app page: boot email set', /"email":"anil.test@example.test"/.test(app.html));
const rp = run('Render Report Page', { session_id: 'abc', user_key: 'anil.test@example.test', created_at: '2026-10-05', report_json: { html: '<div>REPORT</div>', user_name: 'Anil', change_log: ['Monthly investing ₹1.75L → ₹2L'], parent: 'old1' },
  pending: { id: 'p1', status: 'pending', preview: ['x → y'] } }, { 'Report API': { query: { id: 'abc', pending: 'p1' } } });
const rs = [...rp.html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
try { new vm.Script(rs[0]); check('report page: script parses', true); } catch (e) { check('report page: script parses', false, e.message); }
check('report page: banner, report, pending card', /Updated plan/.test(rp.html) && /REPORT/.test(rp.html) && /"pending":\{"id":"p1"/.test(rp.html));
check('report page: 404 for unknown id', run('Render Report Page', {}, { 'Report API': { query: {} } }).status === 404);
// 7. run the page script in a fake browser far enough to render the email step
console.log(ok ? '\nALL PASSED' : '\nSOME CHECKS FAILED'); process.exit(ok ? 0 : 1);
