// node tools/test/test_optimiser.js  - checks the optimiser against the generated rate table (made-up inputs)
const fs = require('fs'), path = require('path'), assert = require('assert');
const { planDeposits, rdMaturity } = require('../deposit_optimiser.js');
const csv = fs.readFileSync(path.join(__dirname, '../../deposits/deposit_schemes.csv'), 'utf8').trim().split('\n');
const head = csv.shift().split(',');
const rows = csv.map(line => { const cells = line.match(/("([^"]|"")*"|[^,]*)(,|$)/g).map(c => c.replace(/,$/, '').replace(/^"|"$/g, '').replace(/""/g, '"'));
  const o = {}; head.forEach((h, i) => o[h] = cells[i] === '' ? null : cells[i]); return o; });
let n = 0; const ok = (name, f) => { f(); n++; console.log('ok -', name); };

ok('RD maturity matches bank calculators (5000/month, 7%, 12 months ~ 62,000)', () => {
  const m = rdMaturity(5000, 7, 12); assert(m > 61500 && m < 62600, m);
});
ok('FD alone reaches a modest goal', () => {
  const r = planDeposits(rows, { initial_amount: 500000, goal_amount: 520000, goal_date: '2029-10-01', start_date: '2026-10-01', inflation_pct: 4 });
  assert(r.ok && r.fixed_deposit_plan.reached, JSON.stringify(r).slice(0, 400));
  assert.equal(r.shortfall_todays_money, 0);
  console.log('   ', r.fixed_deposit_plan.steps.map(s => `${s.bank} ${s.tenor} x${s.times} @${s.rate_pct}%`).join(' -> '), r.fixed_deposit_plan.search);
});
ok('FD + RD: FD short, RD covers the rest', () => {
  const r = planDeposits(rows, { initial_amount: 300000, monthly_installment: 15000, goal_amount: 900000, goal_date: '2030-10-01', start_date: '2026-10-01', inflation_pct: 5 });
  assert(r.ok); assert(!r.fixed_deposit_plan.reached); assert(r.recurring_deposit_plan.reached, JSON.stringify(r.recurring_deposit_plan.best));
  assert.equal(r.recurring_deposit_plan.best.total_paid, 15000 * r.recurring_deposit_plan.best.months);
  console.log('    FD', r.fixed_deposit_plan.final_value_in_todays_money, 'remaining', r.remaining_goal_after_fd_todays_money, 'RD best', r.recurring_deposit_plan.best.steps.map(s => `${s.bank} ${s.term_months}m x${s.times} @${s.rate_pct}%`).join(' -> '), r.recurring_deposit_plan.best.value_in_todays_money, r.verdict);
});
ok('Impossible goal gives shortfall + installment needed, no crash', () => {
  const r = planDeposits(rows, { initial_amount: 100000, monthly_installment: 2000, goal_amount: 5000000, goal_date: '2028-10-01', start_date: '2026-10-01', inflation_pct: 5 });
  assert(r.ok && r.shortfall_todays_money > 0 && r.recurring_deposit_plan.best.installment_needed_for_goal > 2000);
  assert(r.recurring_deposit_plan.best.value_in_todays_money >= r.recurring_deposit_plan.alternatives[0].value_in_todays_money);
  console.log('   ', r.verdict, '| shortfall', r.shortfall_todays_money, '| installment needed', r.recurring_deposit_plan.best.installment_needed_for_goal);
});
ok('Horizon shorter than any RD -> teammate message', () => {
  const r = planDeposits(rows, { monthly_installment: 5000, goal_amount: 100000, goal_date: '2026-12-01', start_date: '2026-10-01', inflation_pct: 5 });
  assert.equal(r.verdict, 'Not possible with current fixed/recurring deposits interest rates.');
});
ok('Senior rates and bank filter', () => {
  const g = planDeposits(rows, { initial_amount: 500000, goal_amount: 2000000, goal_date: '2036-10-01', start_date: '2026-10-01', inflation_pct: 4, banks: 'sbi' });
  const s = planDeposits(rows, { initial_amount: 500000, goal_amount: 2000000, goal_date: '2036-10-01', start_date: '2026-10-01', inflation_pct: 4, banks: 'sbi', senior: 'yes' });
  assert(g.fixed_deposit_plan.steps.every(x => x.bank === 'State Bank of India'));
  assert(s.fixed_deposit_plan.final_value > g.fixed_deposit_plan.final_value);
});
ok('Bad input returns errors', () => {
  const r = planDeposits(rows, { goal_amount: 'abc', goal_date: '2020-01-01', inflation_pct: 5 });
  assert(!r.ok && r.errors.length >= 2);
});
ok('Long horizon stays fast (search budget)', () => {
  const t = Date.now();
  const r = planDeposits(rows, { initial_amount: 100000, goal_amount: 100000000, goal_date: '2046-10-01', start_date: '2026-10-01', inflation_pct: 3 });
  assert(Date.now() - t < 3000, Date.now() - t); assert(r.ok);
  console.log('   ', Date.now() - t, 'ms', r.fixed_deposit_plan.search);
});
console.log(`${n} passed`);
