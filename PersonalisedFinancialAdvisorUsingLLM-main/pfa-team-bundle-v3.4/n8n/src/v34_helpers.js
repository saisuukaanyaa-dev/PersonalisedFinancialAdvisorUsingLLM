
// ---- v3.4 helpers (appended to the shared helpers by tools/build_v34.py) ----

const GOALS = ['Buy a home', 'Retirement', "Child's education", "Child's wedding", 'Buy a car',
               'Start a business', 'Travel or sabbatical', 'Build long-term wealth', 'Other'];
const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SGD'];
const INVESTMENT_KEYS = ['mf', 'stocks', 'gold', 'fd', 'pf', 'cash', 'other'];
const VERDICT_LABEL = { on_track: 'On track', small_gap: 'Slightly behind', large_gap: 'Significant gap' };

// A report id nobody can guess (it is the only key to a report page).
function newReportId() {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID().replace(/-/g, '');
  let s = '';
  while (s.length < 32) s += Math.random().toString(16).slice(2);
  return s.slice(0, 32);
}

// The step form's answers (strings as typed) for a saved profile. v3.4 profiles keep the raw answers;
// older ones (v2 / v3 forms) are mapped back the same way the old "Evaluate Journey" node did.
function answersFromProfile(saved) {
  if (typeof saved === 'string') { try { saved = JSON.parse(saved); } catch (e) { saved = {}; } }
  saved = saved || {};
  if (saved.form_answers && saved.form_answers.raw) return JSON.parse(JSON.stringify(saved.form_answers.raw));
  const fa = saved.form_answers || {};
  const cur = saved.profile?.currency || 'INR';
  const pick = (...vals) => vals.find(v => v !== undefined && v !== null && v !== '') ?? '';
  const loanBucket = t => {
    t = String(t || '').toLowerCase();
    if (/home|house|housing|mortgage/.test(t)) return 'Home loan';
    if (/car|vehicle|auto|bike/.test(t)) return 'Car loan';
    if (/educat|student/.test(t)) return 'Education loan';
    if (/credit|card/.test(t)) return 'Credit card dues';
    if (/gold/.test(t)) return 'Gold loan';
    if (/personal/.test(t)) return 'Personal loan';
    return 'Other loan';
  };
  const invBucket = t => {
    t = String(t || '').toLowerCase();
    if (/mutual|\bmf\b|sip|elss|index|etf|fund/.test(t) && !/gold/.test(t)) return 'mf';
    if (/gold|sgb|silver/.test(t)) return 'gold';
    if (/stock|share|equity|demat/.test(t)) return 'stocks';
    if (/\bfd\b|\brd\b|fixed|recurring|deposit|bond/.test(t)) return 'fd';
    if (/ppf|epf|vpf|provident/.test(t)) return 'pf';
    if (/saving|cash|bank|liquid/.test(t)) return 'cash';
    return 'other';
  };
  let loans = fa.loans;
  if (!loans) {
    loans = {};
    (saved.liabilities || []).forEach(l => {
      const b = loanBucket(l.type);
      const o = loans[b] || { outstanding: 0, rate: 0, emi: 0, _w: 0 };
      const amt = Number(l.outstanding_amount) || 0;
      o.outstanding += amt; o.emi += Number(l.emi) || 0; o._w += amt * (Number(l.interest_rate) || 0);
      o.rate = o.outstanding > 0 ? Number((o._w / o.outstanding).toFixed(2)) : Number(l.interest_rate) || 0;
      loans[b] = o;
    });
  }
  let inv = fa.investments;
  if (!inv) {
    inv = {};
    (saved.savings_investments || []).forEach(s => {
      const b = invBucket(s.type);
      inv[b + '_value'] = (Number(inv[b + '_value']) || 0) + (Number(s.current_value) || 0);
      inv[b + '_monthly'] = (Number(inv[b + '_monthly']) || 0) + (Number(s.monthly_contribution) || 0);
      if (b === 'other' && !inv.other_label) inv.other_label = s.type;
    });
  }
  const insOf = re => (saved.insurance || []).filter(i => re.test(String(i.type || '').toLowerCase()));
  const sum = (arr, k) => arr.reduce((s, x) => s + (Number(x[k]) || 0), 0);
  const termIns = insOf(/term|life/), healthIns = insOf(/health|medic|mediclaim/);
  const desc = String(saved.goal?.description || '').toLowerCase();
  const goalType = saved.goal?.goal_type || (!desc ? '' : /house|home|flat|property/.test(desc) ? 'Buy a home'
    : /retire/.test(desc) ? 'Retirement' : /educat|college|school/.test(desc) ? "Child's education"
    : /wedding|marriage/.test(desc) ? "Child's wedding" : /car|vehicle/.test(desc) ? 'Buy a car'
    : /business|startup/.test(desc) ? 'Start a business' : /travel|sabbatical|trip/.test(desc) ? 'Travel or sabbatical'
    : /wealth|corpus|invest/.test(desc) ? 'Build long-term wealth' : 'Other');
  const sh = v => shorthand(v, cur);
  const loanAnswers = {};
  for (const [t, l] of Object.entries(loans)) loanAnswers[t] = { outstanding: sh(l.outstanding), rate: l.rate ? String(l.rate) : '', emi: sh(l.emi) };
  const invAnswers = { other_label: inv.other_label || '' };
  for (const k of INVESTMENT_KEYS) { invAnswers[`${k}_value`] = sh(inv[`${k}_value`]); invAnswers[`${k}_monthly`] = sh(inv[`${k}_monthly`]); }
  return {
    user_name: pick(saved.profile?.user_name), age: pick(saved.profile?.age), currency: cur,
    annual_ctc: sh(saved.profile?.annual_ctc), goal_type: goalType,
    goal_details: pick(saved.goal?.details, goalType === 'Other' ? saved.goal?.description : ''),
    target_amount: sh(saved.goal?.target_amount), target_date: pick(saved.goal?.target_date),
    take_home: sh(saved.profile?.current_monthly_salary), expenses: sh(saved.emergency_fund?.monthly_essential_expenses),
    emergency: sh(saved.emergency_fund?.current_amount),
    term_cover: sh(pick(fa.term_cover, termIns.length ? sum(termIns, 'sum_assured') : '')),
    term_premium: sh(pick(fa.term_premium, termIns.length ? sum(termIns, 'premium_annual') : '')),
    health_cover: sh(pick(fa.health_cover, healthIns.length ? sum(healthIns, 'sum_assured') : '')),
    health_premium: sh(pick(fa.health_premium, healthIns.length ? sum(healthIns, 'premium_annual') : '')),
    loan_types: saved.profile ? (Object.keys(loans).length ? Object.keys(loans) : [NO_LOANS]) : [],
    loans: loanAnswers, investments: invAnswers,
    risk: saved.profile?.risk_appetite || '',
  };
}

// A plan change asked for in the chat, applied to the step-form answers (port of the Python app's
// apply_changes). Returns { answers, log, ignored }; answers is null when nothing would change.
function applyPlanChanges(answers, changes) {
  const a = JSON.parse(JSON.stringify(answers || {}));
  const cur = a.currency || 'INR';
  const log = [], ignored = [];
  const amt = (label, v) => { const n = parseAmount(v); if (n === null || n < 0) { ignored.push(`${label} (could not read "${v}")`); return null; } return n; };
  const setAmount = (field, label, v, current) => {
    const n = amt(label, v); if (n === null) return;
    if (current !== null && current !== undefined && Math.abs(Number(current) - n) < 0.5) { ignored.push(`${label} is already ${fmtShort(n, cur)}`); return; }
    log.push(`${label} ${fmtShort(current || 0, cur)} → ${fmtShort(n, cur)}`);
    a[field] = shorthand(n, cur);
  };
  a.investments = a.investments || {};
  for (const [k, v] of Object.entries(changes || {})) {
    if (v === null || v === undefined || v === '') continue;
    if (k === 'monthly_sip_total') {
      const n = amt('monthly investing', v); if (n === null) continue;
      const inv = a.investments;
      const before = INVESTMENT_KEYS.reduce((s, key) => s + (parseOptional(inv[`${key}_monthly`]) || 0), 0);
      if (Math.abs(before - n) < 0.5) { ignored.push(`Monthly investing is already ${fmtShort(n, cur)}`); continue; }
      if (n > before) inv.mf_monthly = shorthand((parseOptional(inv.mf_monthly) || 0) + (n - before), cur);   // the extra goes to mutual funds
      else {
        const f = before ? n / before : 0;                                                                   // scale every SIP down
        for (const key of INVESTMENT_KEYS) { const m = parseOptional(inv[`${key}_monthly`]) || 0; if (m) inv[`${key}_monthly`] = shorthand(Math.round(m * f), cur); }
      }
      log.push(`Monthly investing ${fmtShort(before, cur)} → ${fmtShort(n, cur)}`);
    } else if (k === 'target_amount') {
      const n = amt('target', v); if (n !== null && n >= 10000) setAmount('target_amount', 'Target', n, parseAmount(a.target_amount));
    } else if (k === 'target_date') {
      const s = String(v).slice(0, 10), t = new Date(s);
      if (isNaN(t.getTime()) || t <= new Date()) ignored.push('target date (must be in the future)');
      else if (s === a.target_date) ignored.push(`Target date is already ${s}`);
      else { log.push(`Target date ${a.target_date || '-'} → ${s}`); a.target_date = s; }
    } else if (k === 'risk_appetite') {
      const m = String(v).match(/low|medium|high/i);
      const r = m ? m[0][0].toUpperCase() + m[0].slice(1).toLowerCase() : '';
      if (!['Low', 'Medium', 'High'].includes(r)) ignored.push('risk (Low, Medium or High)');
      else if (r === a.risk) ignored.push(`Risk is already ${r}`);
      else { log.push(`Risk ${a.risk || 'Medium'} → ${r}`); a.risk = r; }
    } else if (k === 'take_home') setAmount('take_home', 'In-hand pay', v, parseAmount(a.take_home));
    else if (k === 'annual_ctc') setAmount('annual_ctc', 'CTC', v, parseAmount(a.annual_ctc));
    else if (k === 'expenses') setAmount('expenses', 'Essentials', v, parseAmount(a.expenses));
    else if (k === 'emergency_fund') setAmount('emergency', 'Emergency fund', v, parseOptional(a.emergency));
    else if (k === 'emergency_lumpsum') {
      const n = amt('emergency deposit', v);
      if (n) { const before = parseOptional(a.emergency) || 0; log.push(`Emergency fund ${fmtShort(before, cur)} → ${fmtShort(before + n, cur)}`); a.emergency = shorthand(before + n, cur); }
    } else if (k === 'term_cover' || k === 'health_cover') setAmount(k, k === 'term_cover' ? 'Term cover' : 'Health cover', v, parseOptional(a[k]));
    else if (k === 'remove_loan') {
      const t = (a.loan_types || []).find(x => x.toLowerCase() === String(v).toLowerCase().trim());
      if (!t) ignored.push(`remove loan (no "${v}" on file)`);
      else {
        a.loan_types = a.loan_types.filter(x => x !== t);
        if (!a.loan_types.length) a.loan_types = [NO_LOANS];
        if (a.loans) delete a.loans[t];
        log.push(`Removed ${t}`);
      }
    } else ignored.push(k);
  }
  return { answers: log.length ? a : null, log, ignored };
}
