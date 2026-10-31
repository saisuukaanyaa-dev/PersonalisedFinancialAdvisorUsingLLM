
// v3.4: the whole step form (or a confirmed chat change) -> the canonical profile every downstream node reads.
// Input: a plan request { email, journey, user_id, is_returning, answers, change_log, parent, pending_id }.
const req = $json;
const a = req.answers || {};
const email = String(req.email || '').trim().toLowerCase();
if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error('A valid email address is required.');
const cur = a.currency || 'INR';

// ---- about you and your goal
const ctc = parseAmount(a.annual_ctc);
const target = parseAmount(a.target_amount);
const estimate = estimateInHand(ctc, cur);
const goalType = GOALS.includes(a.goal_type) ? a.goal_type : 'Other';
const details = String(a.goal_details || '').trim().slice(0, 200);
const description = goalType === 'Other' ? (details || 'Other') : (details ? `${goalType} - ${details}` : goalType);

// ---- money in, money out
const takeHome = parseAmount(a.take_home);
const expenses = parseAmount(a.expenses);

// ---- safety net
const s = {};
for (const k of ['emergency', 'term_cover', 'term_premium', 'health_cover', 'health_premium']) {
  s[k] = parseOptional(a[k]); s[`${k}_raw`] = a[k];
}

// ---- loans (only the ticked types)
let picked = Array.isArray(a.loan_types) ? a.loan_types : (a.loan_types ? [a.loan_types] : []);
picked = picked.filter(t => LOAN_TYPES.includes(t));
const loanAnswers = a.loans || {};
const liabilities = picked.map(t => {
  const l = loanAnswers[t] || {};
  const raw = [l.outstanding, l.rate, l.emi];
  const card = t === 'Credit card dues';
  const emiBlank = l.emi === null || l.emi === undefined || String(l.emi).trim() === '';
  return {
    type: t,
    outstanding_amount: parseAmount(l.outstanding),
    interest_rate: parseRate(l.rate),
    // Card dues with no fixed payment: assume the usual 5% minimum due so the EMI load is not understated.
    emi: card && emiBlank ? Math.round((parseAmount(l.outstanding) || 0) * 0.05) : parseAmount(l.emi),
    _raw: raw.filter(x => x !== null && x !== undefined && x !== '').join(' | '),
  };
});

// ---- what you already own
const INV = [['mf', 'Equity Mutual Funds'], ['stocks', 'Direct Stocks'], ['gold', 'Gold (SGB / coins / gold funds)'],
             ['fd', 'FD / RD'], ['pf', 'PPF / EPF / VPF'], ['cash', 'Savings account / cash'], ['other', null]];
const invA = a.investments || {};
const savings_investments = [];
const investments = {};
for (const [k, label] of INV) {
  const vRaw = invA[`${k}_value`], mRaw = k === 'cash' ? '' : invA[`${k}_monthly`];
  const value = parseOptional(vRaw), monthly = parseOptional(mRaw);
  investments[`${k}_value`] = value; investments[`${k}_monthly`] = monthly;
  if (value === 0 && monthly === 0) continue;
  const type = label || String(invA.other_label || '').trim().slice(0, 60) || 'Other investment';
  savings_investments.push({ type, _key: k, current_value: value, monthly_contribution: monthly,
    _raw: [type, vRaw, mRaw].filter(x => x !== null && x !== undefined && x !== '').join(' | ') });
}
investments.other_label = String(invA.other_label || '').trim().slice(0, 60);

const insurance = [];
if (s.term_cover || s.term_premium) insurance.push({ type: 'Term Life', sum_assured: s.term_cover, premium_annual: s.term_premium });
if (s.health_cover || s.health_premium) insurance.push({ type: 'Health', sum_assured: s.health_cover, premium_annual: s.health_premium });
const loansForPrefill = {};
liabilities.forEach(l => { loansForPrefill[l.type] = { outstanding: l.outstanding_amount, rate: l.interest_rate, emi: l.emi }; });
const risk = ['Low', 'Medium', 'High'].includes(a.risk) ? a.risk : (riskFromAnswer(a.risk) || 'Medium');

const d = {
  session_id: newReportId(),
  user_key: email,
  user_id: req.user_id || null,
  is_returning_user: Boolean(req.is_returning),
  profile_source: req.change_log && req.change_log.length ? 'chat_change' : (req.journey === 'update' ? 'updated' : 'new'),
  submitted_at: new Date().toISOString(),
  change_log: req.change_log || [],
  parent_report: req.parent || null,
  pending_id: req.pending_id || null,
  profile: {
    user_name: String(a.user_name || '').trim().slice(0, 80),
    email,
    age: parseAmount(a.age),
    currency: cur,
    annual_ctc: ctc,
    estimated_monthly_in_hand: estimate,
    current_monthly_salary: takeHome,
    in_hand_source: estimate && takeHome === estimate ? 'estimated_from_ctc' : 'user_confirmed',
    risk_appetite: risk,
  },
  goal: { goal_type: goalType, details, description, target_amount: target, target_date: a.target_date || null },
  liabilities,
  savings_investments,
  insurance,
  emergency_fund: { current_amount: s.emergency, monthly_essential_expenses: expenses },
  form_answers: {
    term_cover: s.term_cover, term_premium: s.term_premium, health_cover: s.health_cover, health_premium: s.health_premium,
    loans: loansForPrefill, investments,
    raw: { ...a, risk },          // the step form's answers as typed: pre-fills the next visit, and chat changes edit these
  },
};

// Anything typed that we could not read; the page shows it on the right step.
const unreadable = [];
const bad = (label, raw, path, kind) => unreadable.push({ label, raw: raw ?? '', path, kind });
if (ctc === null) bad('Current CTC (annual)', a.annual_ctc, ['profile', 'annual_ctc'], 'amount');
if (target === null) bad('Target amount', a.target_amount, ['goal', 'target_amount'], 'amount');
if (takeHome === null) bad('Monthly in-hand salary', a.take_home, ['profile', 'current_monthly_salary'], 'amount');
if (expenses === null) bad('Monthly essential expenses', a.expenses, ['emergency_fund', 'monthly_essential_expenses'], 'amount');
for (const [k, label] of [['emergency', 'Emergency fund'], ['term_cover', 'Term life cover'], ['term_premium', 'Term premium per year'],
                          ['health_cover', 'Health cover'], ['health_premium', 'Health premium per year']]) {
  if (s[k] === null) bad(label, s[`${k}_raw`], k === 'emergency' ? ['emergency_fund', 'current_amount'] : ['form_answers', k], 'amount');
}
liabilities.forEach((l, i) => {
  if (l.outstanding_amount === null) bad(`${l.type} · amount outstanding`, l._raw, ['liabilities', i, 'outstanding_amount'], 'amount');
  if (l.interest_rate === null) bad(`${l.type} · interest rate (% per year)`, l._raw, ['liabilities', i, 'interest_rate'], 'rate');
  if (l.emi === null) bad(`${l.type} · monthly EMI`, l._raw, ['liabilities', i, 'emi'], 'amount');
});
savings_investments.forEach((v, i) => {
  if (v.current_value === null) bad(`${v.type} · current value`, v._raw, ['savings_investments', i, 'current_value'], 'amount');
  if (v.monthly_contribution === null) bad(`${v.type} · monthly amount`, v._raw, ['savings_investments', i, 'monthly_contribution'], 'amount');
});
d.unreadable = unreadable;

return [{ json: computeDerived(d) }];
