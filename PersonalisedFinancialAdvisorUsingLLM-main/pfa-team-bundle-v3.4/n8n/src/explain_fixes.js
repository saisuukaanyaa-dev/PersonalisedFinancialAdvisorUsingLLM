
// The completeness check found gaps -> tell the step form which fields to fix (instead of n8n's "Nearly there" page).
const d = $json;
const fields = d.clarification_form_fields || [];
const notes = [];
const fixes = [];
const html = (fields.find(f => f.fieldType === 'html') || {}).html || '';
html.replace(/<p>([\s\S]*?)<\/p>/g, (m, p) => { notes.push(p); return m; });
const fieldOf = (path) => {
  const [a, b, c] = path;
  if (a === 'profile') return { annual_ctc: 'annual_ctc', current_monthly_salary: 'take_home', user_name: 'user_name', age: 'age' }[b];
  if (a === 'goal') return { target_amount: 'target_amount', description: 'goal_type', target_date: 'target_date' }[b];
  if (a === 'emergency_fund') return { monthly_essential_expenses: 'expenses', current_amount: 'emergency' }[b];
  if (a === 'form_answers') return b;
  if (a === 'liabilities') { const t = d.liabilities?.[b]?.type; return t ? `loans.${t}.${{ outstanding_amount: 'outstanding', interest_rate: 'rate', emi: 'emi' }[c]}` : null; }
  if (a === 'savings_investments') { const k = d.savings_investments?.[b]?._key; return k ? `investments.${k}_${c === 'current_value' ? 'value' : 'monthly'}` : null; }
  return null;
};
(d.clarification_map || []).forEach(m => {
  const f = fields.find(x => x.fieldName === m.fieldName) || {};
  fixes.push({ field: fieldOf(m.path), label: f.fieldLabel || m.path.join('.'), message: f.placeholder || '', value: f.defaultValue ?? null });
});
const plain = notes.map(x => x.replace(/<[^>]+>/g, '')).join(' ');
const reply = `I couldn't apply that yet: ${plain || fixes.map(f => f.label).join(', ')} Open "Update my answers" on the start page to fix it.`;
return [{ json: { ok: false, notes, fixes, reply } }];
