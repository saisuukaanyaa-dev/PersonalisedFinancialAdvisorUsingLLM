// v1.7 · several goals on the report page: "What if a new goal comes up?" (instant, computed on the server - no AI),
// add the goal to the plan, or remove an extra goal. Handlers are delegated because the report body is re-rendered
// when the AI explanation arrives.
(() => {
  const main = document.getElementById('report-main');
  if (!main) return;
  const reportId = main.dataset.report;
  let last = null;                              // the goal behind the impact shown, for "Add it to my plan"

  const iso = d => d.toISOString().slice(0, 10);
  function prepDate(input) {
    if (!input || input.dataset.ready) return;
    const t = new Date(); t.setDate(t.getDate() + 31); input.min = iso(t);
    if (!input.value) { const d = new Date(); d.setFullYear(d.getFullYear() + 2); input.value = iso(d); }
    input.dataset.ready = '1';
  }
  prepDate(document.querySelector('#whatif-form [name=target_date]'));
  document.addEventListener('focusin', e => { if (e.target.matches('#whatif-form [name=target_date]')) prepDate(e.target); });

  function showError(text) {
    const box = document.getElementById('whatif-err');
    if (!box) return;
    box.textContent = text || ''; box.hidden = !text;
  }

  document.addEventListener('submit', async e => {
    if (e.target.id !== 'whatif-form') return;
    e.preventDefault();
    const form = e.target, btn = form.querySelector('button[type=submit]');
    const body = Object.fromEntries(new FormData(form).entries());
    showError(''); btn.disabled = true; btn.textContent = 'Working it out…';
    try {
      const r = await pfa.post('/api/goals/impact', { ...body, report_id: reportId });
      if (!r.ok) { showError(r.data.error || 'Something went wrong - please try again.'); return; }
      last = body;
      const out = document.getElementById('whatif-result');
      out.innerHTML = r.data.html;
      out.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } finally { btn.disabled = false; btn.textContent = 'See the impact'; }
  });

  document.addEventListener('click', async e => {
    const add = e.target.closest('[data-add-goal]');
    const rm = e.target.closest('[data-remove-goal]');
    if (add && last) {
      document.querySelectorAll('[data-add-goal]').forEach(b => { b.disabled = true; });
      add.textContent = 'Rebuilding your plan…';
      const r = await pfa.post('/api/goals/add', { ...last, target_date: add.dataset.addGoal, report_id: reportId });
      if (r.ok) { location.href = r.data.report_url; return; }
      showError(r.data.error || 'Could not add the goal.');
      document.querySelectorAll('[data-add-goal]').forEach(b => { b.disabled = false; });
      add.textContent = 'Add it to my plan';
    } else if (rm) {
      if (!confirm(`Remove "${rm.dataset.removeGoal}" and rebuild your plan?`)) return;
      rm.disabled = true; rm.textContent = 'Rebuilding…';
      const r = await pfa.post('/api/goals/remove', { name: rm.dataset.removeGoal, report_id: reportId });
      if (r.ok) { location.href = r.data.report_url; return; }
      alert(r.data.error || 'Could not remove the goal.');
      rm.disabled = false; rm.textContent = 'Remove';
    }
  });
})();
