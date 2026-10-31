// ---- deposit optimiser (embedded verbatim in the n8n Code node "Optimise FD & RD Plan") ----
// JavaScript port of the teammate's GoalSearch.py + StateActionState.py (PersonalisedFinancialAdvisorUsingLLM).
// Kept from the original: the state/action model, the rate-sorted depth-first goal search (BruteForce),
// the FD transition (quarterly compounding, the same deposit repeated `count` times) and the FD sort key.
// Fixed (see docs/BANK_DEPOSITS.md):
//   1. RD maturity uses the standard Indian bank formula (each monthly installment compounds quarterly to maturity);
//      the original gave Rs 11,03,576 for Rs 5,000/month at 7% for 1 year - the bank figure is about Rs 62,000.
//   2. Inflation compounds over the whole time elapsed. The original divided by (1 + term x inflation) once per step,
//      so a 2-year FD renewed 5 times was deflated for 2 years, not 10 (Rs 1,81,963 instead of Rs 1,22,881).
//   3. No crash when nothing fits (the original zip(*[]) / unset aM errors) - returns a clear verdict instead.
//   4. When the goal is out of reach, returns the best sequence found rather than a single step.
//   5. A search budget and memo, so a large rate table can't hang the workflow.
const GOAL_REACHED = 1, GOAL_NOT_REACHABLE = 2, GOAL_NOT_YET_REACHED = 3;
const DAY = 86400000;

function toDate(s) { const d = new Date(String(s).slice(0, 10) + 'T00:00:00Z'); return isNaN(d) ? null : d; }
function iso(d) { return new Date(d).toISOString().slice(0, 10); }
function num(v) { if (v === null || v === undefined || v === '') return null; const n = Number(String(v).replace(/[,₹\s]/g, '')); return isFinite(n) ? n : null; }
function r0(x) { return Math.round(x); }

function rateOf(row, senior) {
  const g = Number(row.interest_rate_general), s = row.interest_rate_senior == null ? null : Number(row.interest_rate_senior);
  return senior && s ? s : g;
}

// ---------- FD: the teammate's transition and sort key, with inflation compounding over elapsed time
function planFD({ amount, start, goalDate, goal, inflation, deposits, budget = 60000 }) {
  const sg = { balance: goal, time: goalDate.getTime() };
  const infl = t => Math.pow(1 + inflation / 100, (t - start.getTime()) / (365 * DAY));
  const real = s => s.balance / infl(s.time);
  const totalDays = (sg.time - start.getTime()) / DAY;
  const sortBase = d => Math.pow(1 + d.rate * d.comp / 100, (d.years / d.comp) * Math.floor(totalDays / (365 * d.years)));
  const A = deposits.slice().sort((a, b) => sortBase(b) - sortBase(a));

  const T = (s, d) => {
    let count = Math.floor(((sg.time - s.time) / DAY) / (365 * d.years));
    if (count === 0) count = 1;
    return [{ balance: s.balance * Math.pow(1 + d.rate * d.comp / 100, (d.years / d.comp) * count),
              time: s.time + Math.round(d.years * count * 365) * DAY }, count];
  };
  const isGR = s => s.time <= sg.time ? (real(s) >= sg.balance ? GOAL_REACHED : GOAL_NOT_YET_REACHED) : GOAL_NOT_REACHABLE;

  let expanded = 0, truncated = false;
  const failed = new Map();                       // time -> highest balance already shown not to reach the goal
  let best = { value: -1, path: [] };
  const stack = [];
  function bruteForce(s) {
    const r = isGR(s);
    if (r !== GOAL_NOT_YET_REACHED) return r;
    if (stack.length && real(s) > best.value) best = { value: real(s), path: stack.slice() };
    if ((failed.get(s.time) ?? -1) >= s.balance) return GOAL_NOT_REACHABLE;
    for (const d of A) {
      if (++expanded > budget) { truncated = true; return GOAL_NOT_REACHABLE; }
      const [sn, count] = T(s, d);
      stack.push({ d, count, s: sn });
      if (bruteForce(sn) === GOAL_REACHED) return GOAL_REACHED;
      stack.pop();
    }
    failed.set(s.time, Math.max(failed.get(s.time) ?? -1, s.balance));
    return GOAL_NOT_REACHABLE;
  }
  const s0 = { balance: amount, time: start.getTime() };
  const reached = bruteForce(s0) === GOAL_REACHED;
  const path = reached ? stack.slice() : best.path;
  let t = start.getTime();
  const steps = path.map(({ d, count, s }) => {
    const step = { bank: d.bank, scheme: d.scheme, tenor: d.tenor, term_months: d.months, times: count,
                   rate_pct: d.rate, rate_source: d.rate_source, start: iso(t), end: iso(s.time),
                   value_at_end: r0(s.balance), value_at_end_in_todays_money: r0(real(s)) };
    t = s.time;
    return step;
  });
  const last = path.length ? path[path.length - 1].s : s0;
  return { reached, steps, final_value: r0(last.balance), final_value_in_todays_money: r0(real(last)),
           final_date: iso(last.time), search: { expanded, truncated } };
}

// ---------- RD: standard maturity (each monthly installment compounds quarterly until maturity)
function rdMaturity(P, ratePct, months) {
  const i = ratePct / 400;
  let m = 0;
  for (let k = 1; k <= months; k++) m += P * Math.pow(1 + i, (months - k + 1) / 3);
  return m;
}

function planRD({ installment, start, goalDate, goal, inflation, deposits }) {
  // Fill every month up to the goal date with back-to-back RDs, choosing the mix with the highest maturity
  // (dynamic programme over months; everything scales with the installment, so it is solved for Rs 1 a month).
  // Months no RD fits are saved as cash. Matured RDs are kept, not reinvested (conservative).
  const monthsLeft = Math.floor((goalDate - start) / DAY / 30.4375);
  const cands = [];
  for (const d of deposits) {
    const n = Math.round(d.months);
    if (n >= 1 && n <= monthsLeft) cands.push({ d, n, v: rdMaturity(1, d.rate, n) });
  }
  if (!cands.length) return { reached: false, best: null, alternatives: [] };
  const best = new Array(monthsLeft + 1).fill(0), choice = new Array(monthsLeft + 1).fill(null);
  for (let m = 1; m <= monthsLeft; m++) {
    best[m] = best[m - 1] + 1; choice[m] = null;              // this month as cash
    for (const c of cands) if (c.n <= m && best[m - c.n] + c.v > best[m] + 1e-12) { best[m] = best[m - c.n] + c.v; choice[m] = c; }
  }
  const segs = [];
  for (let m = monthsLeft; m > 0;) {
    const c = choice[m];
    if (!c) { m--; continue; }
    const last = segs[segs.length - 1];
    if (last && last.c === c) last.times++; else segs.push({ c, times: 1 });
    m -= c.n;
  }
  segs.reverse();
  const deflate = Math.pow(1 + inflation / 100, monthsLeft / 12);
  let t = start.getTime();
  const steps = segs.map(({ c, times }) => {
    const end = t + Math.round(c.n * times * 30.4375) * DAY;
    const step = { bank: c.d.bank, scheme: c.d.scheme, tenor: c.d.tenor, term_months: c.n, times, rate_pct: c.d.rate,
                   rate_source: c.d.rate_source, start: iso(t), end: iso(end), value_at_end: r0(installment * c.v * times) };
    t = end;
    return step;
  });
  const cashMonths = monthsLeft - segs.reduce((x, s) => x + s.c.n * s.times, 0);
  const plan = { steps, months: monthsLeft, cash_months: cashMonths, total_paid: r0(installment * monthsLeft),
                 value_on_goal_date: r0(installment * best[monthsLeft]),
                 value_in_todays_money: r0(installment * best[monthsLeft] / deflate),
                 installment_needed_for_goal: goal > 0 ? r0(goal * deflate / best[monthsLeft]) : 0 };
  // single-scheme alternatives (the same RD renewed back to back), for comparison
  const alternatives = cands.map(c => {
    const times = Math.floor(monthsLeft / c.n), v = c.v * times + (monthsLeft - c.n * times);
    return { bank: c.d.bank, tenor: c.d.tenor, term_months: c.n, times, rate_pct: c.d.rate, value_in_todays_money: r0(installment * v / deflate) };
  }).sort((x, y) => y.value_in_todays_money - x.value_in_todays_money).slice(0, 3);
  return { reached: installment > 0 && plan.value_in_todays_money >= goal, best: plan, alternatives };
}

// ---------- the whole plan: FD for the lump sum first, then RD for whatever is left (the teammate's agent steps 1-5)
function planDeposits(rows, p) {
  const start = toDate(p.start_date) || toDate(new Date().toISOString());
  const goalDate = toDate(p.goal_date);
  const goal = num(p.goal_amount), amount = num(p.initial_amount) || 0, installment = num(p.monthly_installment) || 0;
  const inflation = num(p.inflation_pct);
  const senior = p.senior === true || /^(true|yes|y|1|senior)$/i.test(String(p.senior || ''));
  const errors = [];
  if (!goalDate) errors.push('goal_date is required (YYYY-MM-DD)');
  else if (goalDate <= start) errors.push('goal_date must be in the future');
  if (!(goal > 0)) errors.push('goal_amount must be a positive rupee amount');
  if (!(amount > 0) && !(installment > 0)) errors.push('give initial_amount (lump sum) and/or monthly_installment');
  if (inflation === null || inflation < 0 || inflation > 30) errors.push('inflation_pct missing or out of range');
  if (errors.length) return { ok: false, errors };

  const ALIAS = { sbi: 'state bank of india', pnb: 'punjab national', bob: 'bank of baroda', baroda: 'bank of baroda',
                  idfc: 'idfc first', kotak: 'kotak mahindra', indusind: 'indusind', canara: 'canara' };
  // compare names without the word "bank": 'State Bank of India' -> 'state of india', 'HDFC Bank' -> 'hdfc'
  const norm = x => String(x).toLowerCase().replace(/\bbank\b/g, ' ').replace(/\s+/g, ' ').trim();
  const bankFilter = String(p.banks || '').split(/[,;]|\band\b/i).map(norm)
    .filter(b => b && !/^(any|all)$/.test(b)).map(b => norm(ALIAS[b] || b));
  const pick = type => rows
    .filter(r => r.scheme_type === type && Number(r.duration_months) > 0)
    .filter(r => !bankFilter.length || bankFilter.some(b => norm(r.bank_name).includes(b)))
    .map(r => ({ bank: r.bank_name, scheme: r.scheme_name, tenor: r.tenor_label, months: Number(r.duration_months),
                 years: Number(r.duration_months) / 12, comp: (Number(r.compounding_months) || 3) / 12,
                 rate: rateOf(r, senior), rate_source: r.rate_source }))
    .filter(d => d.rate > 0);

  const fd = amount > 0 ? planFD({ amount, start, goalDate, goal, inflation, deposits: pick('Fixed Deposit') }) : null;
  const remaining = Math.max(0, goal - (fd ? fd.final_value_in_todays_money : 0));
  const rd = remaining > 0 ? planRD({ installment, start, goalDate, goal: remaining, inflation, deposits: pick('Recurring Deposit') }) : null;

  const covered = (fd && fd.reached) || remaining === 0 || (rd && rd.reached);
  const verdict = covered ? 'Goal reachable with bank deposits'
    : (!fd || !fd.steps.length) && (!rd || !rd.best) ? 'Not possible with current fixed/recurring deposits interest rates.'
    : 'Goal not reachable with the amounts given - see the shortfall and the installment needed';
  const rdValue = rd && rd.best && installment > 0 ? rd.best.value_in_todays_money : 0;
  return {
    ok: true, verdict,
    inputs: { initial_amount: amount, monthly_installment: installment, goal_amount_todays_money: goal,
              goal_amount_on_goal_date: r0(goal * Math.pow(1 + inflation / 100, (goalDate - start) / DAY / 365)),
              start_date: iso(start), goal_date: iso(goalDate), inflation_pct: inflation, inflation_source: p.inflation_source || 'given',
              rate_type: senior ? 'senior citizen' : 'general', banks: bankFilter.length ? bankFilter : 'all' },
    fixed_deposit_plan: fd,
    remaining_goal_after_fd_todays_money: r0(remaining),
    recurring_deposit_plan: rd,
    shortfall_todays_money: covered ? 0 : r0(Math.max(0, remaining - rdValue)),
    notes: ['Amounts "in today\'s money" are deflated by the inflation rate; the goal is compared in today\'s money.',
            'Rates are card rates from the team\'s bank documents (as of ' + (rows[0] && rows[0].as_of || 'n/a') + '); confirm with the bank before investing.',
            'Interest is shown before tax (TDS applies above the yearly threshold). Educational information, not licensed advice.'],
  };
}
// ---- end deposit optimiser ----

if (typeof module !== 'undefined') module.exports = { planDeposits, rdMaturity };
