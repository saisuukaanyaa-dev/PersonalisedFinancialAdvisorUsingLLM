// Conversational intake: five short steps, a review, then the plan. The server checks each step and
// writes the "reaction" shown at the top of the next one, so the logic lives in one place (Python).
(() => {
  const boot = JSON.parse(document.getElementById('boot').textContent);
  const { el } = pfa;
  const A = boot.answers || {};
  A.inv = A.inv || {}; A.loans = A.loans || {}; A.loan_types = A.loan_types || [];
  A.extra_goals = Array.isArray(A.extra_goals) ? A.extra_goals : [];
  const MAX_EXTRA = boot.maxExtraGoals || 3;
  const NONE = "None - I'm debt-free";
  const INV = [['mf', 'Mutual funds'], ['stocks', 'Direct stocks'], ['gold', 'Gold (SGB, coins, gold funds)'],
               ['fd', 'FD / RD'], ['pf', 'PPF / EPF / VPF'], ['cash', 'Savings account / cash'], ['other', 'Anything else']];
  const STEPS = ['About you & your goal', 'Cash flow', 'Safety net', 'Loans', 'Investments & risk', 'Review'];
  let step = 1;
  const bubbles = { 1: boot.intro };

  const get = path => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), A);
  const set = (path, v) => {
    const keys = path.split('.'); let o = A;
    keys.slice(0, -1).forEach(k => { if (typeof o[k] !== 'object' || o[k] === null) o[k] = {}; o = o[k]; });
    o[keys[keys.length - 1]] = v;
  };

  // ---------- field builders ----------
  const input = (path, label, opts = {}) => el('label', { class: 'field' + (opts.half ? ' half' : '') },
    el('span', { text: label }), opts.hint ? el('small', { class: 'hint', text: opts.hint }) : null,
    el('input', { name: path, id: 'f-' + path.replace(/\W/g, '_'), type: opts.type || 'text', value: get(path) ?? '',
                  placeholder: opts.placeholder || '', inputmode: opts.inputmode, min: opts.min, autocomplete: 'off' }),
    el('em', { class: 'err', 'data-err': path }));
  const amount = (path, label, placeholder, opts = {}) => input(path, label, { placeholder, inputmode: 'text', ...opts });
  const select = (path, label, options) => el('label', { class: 'field' }, el('span', { text: label }),
    el('select', { name: path, id: 'f-' + path }, el('option', { value: '', text: 'Choose…' }),
      options.map(o => el('option', { value: o, text: o, selected: get(path) === o }))),
    el('em', { class: 'err', 'data-err': path }));

  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  const BUILD = {
    1: () => [
      input('name', 'Your name', { placeholder: 'e.g. Priya Sharma' }),
      el('div', { class: 'row' }, input('age', 'Age', { type: 'number', inputmode: 'numeric', half: true }),
        el('div', { class: 'half' }, select('currency', 'Currency', boot.currencies))),
      amount('ctc', 'Current CTC (annual, before tax)', 'e.g. 18L'),
      select('goal_type', 'What are you saving for?', boot.goals),
      input('goal_details', 'Tell me a little more (optional)', { placeholder: 'e.g. 2BHK in Pune' }),
      el('div', { class: 'row' }, amount('target_amount', 'Roughly how much will you need?', 'e.g. 80L', { half: true }),
        input('target_date', 'By when?', { type: 'date', min: tomorrow, half: true })),
      extraGoals(),
    ],
    2: () => [
      amount('take_home', 'Monthly in-hand salary', 'What reaches your bank account, e.g. 1.2L'),
      amount('expenses', 'Monthly essential expenses', 'Rent, food, bills, school fees - not EMIs', { hint: 'Leave out EMIs and investments - I ask about those next.' }),
    ],
    3: () => [
      el('div', { class: 'row' }, amount('emergency', 'Emergency fund set aside', 'e.g. 1.5L (blank if none)', { half: true }),
        amount('emergency_monthly', 'Adding to it every month (optional)', 'e.g. 5K', { half: true })),
      el('div', { class: 'row' }, amount('term_cover', 'Term life cover', 'e.g. 1Cr', { half: true }),
        amount('term_premium', 'Premium per year (optional)', 'e.g. 12K', { half: true })),
      el('div', { class: 'row' }, amount('health_cover', 'Health insurance cover', 'e.g. 10L', { half: true }),
        amount('health_premium', 'Premium per year (optional)', 'e.g. 18K', { half: true })),
    ],
    4: () => {
      const box = el('div', { class: 'loan-details', id: 'loan-details' });
      const types = [...boot.loanTypes, NONE];
      const chips = el('fieldset', { class: 'chips' }, el('legend', { text: 'Which of these do you have right now?' }),
        types.map(t => el('label', { class: 'chip' }, el('input', { type: 'checkbox', name: 'loan_type', value: t,
          checked: t === NONE ? (A.loan_types.length === 0 && A._loans_answered) : A.loan_types.includes(t) }), el('span', { text: t }))),
        el('em', { class: 'err', 'data-err': 'loan_types' }));
      const render = () => {
        box.replaceChildren(...A.loan_types.map(t => el('div', { class: 'loan' }, el('h3', { text: t }),
          el('div', { class: 'row three' },
            amount(`loans.${t}.outstanding`, 'Amount outstanding', 'e.g. 3.2L'),
            input(`loans.${t}.rate`, 'Interest % a year', { placeholder: 'e.g. 9.2', inputmode: 'decimal' }),
            amount(`loans.${t}.emi`, 'Monthly EMI', 'e.g. 11K')))));
      };
      chips.addEventListener('change', e => {
        const cb = e.target; if (cb.name !== 'loan_type') return;
        collect();
        if (cb.value === NONE && cb.checked) chips.querySelectorAll('input').forEach(i => { if (i.value !== NONE) i.checked = false; });
        if (cb.value !== NONE && cb.checked) chips.querySelector(`input[value="${NONE}"]`).checked = false;
        A.loan_types = [...chips.querySelectorAll('input:checked')].map(i => i.value).filter(v => v !== NONE);
        render();
      });
      render();
      return [chips, box];
    },
    5: () => [
      el('div', { class: 'inv-table' },
        el('div', { class: 'inv-head' }, el('span', { text: 'What you hold' }), el('span', { text: 'Already invested (value today)' }),
          el('span', { text: 'SIP / added every month' })),
        INV.map(([k, label]) => el('div', { class: 'inv-row' },
          k === 'other' ? input('inv.other_label', label, { placeholder: 'e.g. NPS, bonds' }) : el('span', { class: 'inv-label', text: label }),
          amount(`inv.${k}_value`, `${label}: invested so far`, 'e.g. 4.5L'), amount(`inv.${k}_monthly`, `${label}: every month`, 'e.g. 15K')))),
      el('label', { class: 'field' }, el('span', { text: 'What kind of mutual funds are they mostly?' }),
        el('small', { class: 'hint', text: 'Equity funds invest in shares; debt funds in bonds; hybrid funds in both. This makes your allocation pie correct.' }),
        el('select', { name: 'inv.mf_type', id: 'f-inv_mf_type' },
          ['Equity', 'Debt', 'Hybrid', 'Not sure'].map(o => el('option', { value: o, text: o === 'Not sure' ? 'Not sure (count as equity)' : o + ' funds',
            selected: (A.inv.mf_type || 'Equity') === o })))),
      el('fieldset', { class: 'risk' }, el('legend', { text: 'If your investments fell 20% in a month, what would you do?' }),
        Object.entries(boot.risk).map(([k, text]) => el('label', { class: 'radio' },
          el('input', { type: 'radio', name: 'risk', value: k, checked: A.risk === k }),
          el('span', {}, el('b', { text: k }), ' ', text.replace(/^\w+ - /, '')))),
        el('em', { class: 'err', 'data-err': 'risk' })),
    ],
    6: () => review(),
  };

  // v1.7: up to 3 more goals (a car before the home, a child's education after it…). Each gets its own risk level.
  function extraGoals() {
    const box = el('div', { class: 'extra-goals' });
    const draw = () => {
      const rows = A.extra_goals.map((g, i) => el('div', { class: 'extra-goal' },
        el('div', { class: 'extra-goal-head' }, el('h3', { text: `Goal ${i + 2}` }),
          el('button', { type: 'button', class: 'linkish', text: 'Remove', 'data-xg-remove': i })),
        el('div', { class: 'row' }, el('div', { class: 'half' }, select(`extra_goals.${i}.goal_type`, 'What is it for?', boot.goals)),
          el('div', { class: 'half' }, input(`extra_goals.${i}.details`, 'Name (optional)', { placeholder: 'e.g. Family car' }))),
        el('div', { class: 'row three' },
          amount(`extra_goals.${i}.target_amount`, 'How much?', 'e.g. 6L'),
          input(`extra_goals.${i}.target_date`, 'By when?', { type: 'date', min: tomorrow }),
          el('label', { class: 'field' }, el('span', { text: 'Priority' }),
            el('select', { name: `extra_goals.${i}.priority` }, (boot.priorities || ['Must-have', 'Nice-to-have'])
              .map(p => el('option', { value: p, text: p, selected: (g.priority || 'Must-have') === p })))))));
      const add = A.extra_goals.length < MAX_EXTRA
        ? el('button', { type: 'button', class: 'btn ghost small', 'data-xg-add': '1',
                         text: A.extra_goals.length ? '+ Add another goal' : '+ Saving for something else too? Add a goal' })
        : el('p', { class: 'hint', text: `That's the maximum of ${MAX_EXTRA + 1} goals.` });
      box.replaceChildren(...rows, add,
        A.extra_goals.length ? el('p', { class: 'hint', text: 'Must-have goals are secured first, nearest date first. Each goal gets its own risk level for its own date.' }) : '');
    };
    box.addEventListener('click', e => {
      const add = e.target.closest('[data-xg-add]'), rm = e.target.closest('[data-xg-remove]');
      if (!add && !rm) return;
      collect();
      if (add) A.extra_goals.push({ priority: 'Must-have' });
      if (rm) A.extra_goals.splice(Number(rm.dataset.xgRemove), 1);
      draw();
    });
    draw();
    return box;
  }

  function review() {
    const rows = (pairs) => el('dl', {}, pairs.filter(p => p[1] !== undefined && p[1] !== '' && p[1] !== null)
      .map(([k, v]) => [el('dt', { text: k }), el('dd', { text: String(v) })]).flat());
    const card = (n, title, pairs) => el('section', { class: 'review-card' },
      el('div', { class: 'review-head' }, el('h3', { text: title }),
        el('button', { type: 'button', class: 'linkish', text: 'Edit', 'data-goto': n })), rows(pairs));
    const invPairs = INV.filter(([k]) => A.inv[`${k}_value`] || A.inv[`${k}_monthly`])
      .map(([k, l]) => [k === 'other' ? (A.inv.other_label || l) : l,
        `${A.inv[`${k}_value`] || '0'} invested so far · ${A.inv[`${k}_monthly`] || '0'} every month`]);
    return [
      card(1, 'About you & your goal', [['Name', A.name], ['Age', A.age], ['CTC', A.ctc], ['Goal', A.goal_type + (A.goal_details ? ' - ' + A.goal_details : '')],
        ['Target', A.target_amount], ['By', A.target_date],
        ...A.extra_goals.filter(g => g.goal_type && g.target_amount).map((g, i) => [`Goal ${i + 2}`,
          `${g.details || g.goal_type} · ${g.target_amount} by ${g.target_date} · ${g.priority || 'Must-have'}`])]),
      card(2, 'Cash flow', [['In-hand pay', A.take_home], ['Essentials', A.expenses]]),
      card(3, 'Safety net', [['Emergency fund', A.emergency || '0'], ['Term cover', A.term_cover || 'None'], ['Health cover', A.health_cover || 'None']]),
      card(4, 'Loans', A.loan_types.length ? A.loan_types.map(t => [t, `${get(`loans.${t}.outstanding`)} at ${get(`loans.${t}.rate`)}% · EMI ${get(`loans.${t}.emi`)}`]) : [['Loans', 'None - debt-free']]),
      card(5, 'Investments & risk', [...(invPairs.length ? invPairs : [['Investments', 'None yet']]),
        ...((A.inv.mf_value || A.inv.mf_monthly) ? [['Mutual fund type', A.inv.mf_type || 'Equity']] : []), ['Risk', A.risk]]),
    ];
  }

  // ---------- render ----------
  const fields = document.getElementById('fields');
  const bubbleEl = document.getElementById('bubble');
  const nextBtn = document.getElementById('next');
  const backBtn = document.getElementById('back');
  const formErr = document.getElementById('form-error');

  function showBubble(b) {
    if (!b) { bubbleEl.hidden = true; return; }
    bubbleEl.hidden = false;
    bubbleEl.replaceChildren(el('h1', { text: b.title }), ...(b.lines || []).map(l => el('p', { html: l })));
  }

  function render() {
    document.getElementById('progress-bar').style.width = `${(step - 1) / 5 * 100}%`;
    document.getElementById('step-label').textContent = step <= 5 ? `Step ${step} of 5 · ${STEPS[step - 1]}` : 'Review';
    showBubble(bubbles[step]);
    fields.replaceChildren(...BUILD[step]());
    backBtn.hidden = step === 1;
    nextBtn.textContent = step === 6 ? 'Build my plan ✨' : 'Next';
    formErr.hidden = true;
    const first = fields.querySelector('input:not([type=checkbox]):not([type=radio]), select');
    if (first && step !== 6) first.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }

  function collect() {
    fields.querySelectorAll('input[name], select[name]').forEach(i => {
      if (i.name === 'loan_type') return;
      if (i.type === 'radio') { if (i.checked) set(i.name, i.value); return; }
      set(i.name, i.value.trim());
    });
    if (step === 4) {
      A.loan_types = [...fields.querySelectorAll('input[name=loan_type]:checked')].map(i => i.value).filter(v => v !== NONE);
      A._loans_answered = fields.querySelectorAll('input[name=loan_type]:checked').length > 0;
    }
  }

  function showErrors(errors) {
    fields.querySelectorAll('[data-err]').forEach(n => { n.textContent = ''; });
    fields.querySelectorAll('.invalid').forEach(n => n.classList.remove('invalid'));
    let first = null;
    Object.entries(errors).forEach(([k, msg]) => {
      const slot = fields.querySelector(`[data-err="${CSS.escape(k)}"]`);
      if (slot) { slot.textContent = msg; slot.parentElement.classList.add('invalid'); first = first || slot.parentElement; }
    });
    if (first) { first.scrollIntoView({ block: 'center' }); const i = first.querySelector('input, select'); if (i) i.focus(); }
  }

  fields.addEventListener('click', e => {
    const g = e.target.closest('[data-goto]');
    if (g) { step = Number(g.dataset.goto); render(); }
  });
  backBtn.addEventListener('click', () => { collect(); step = Math.max(1, step - 1); render(); });

  document.getElementById('step-form').addEventListener('submit', async e => {
    e.preventDefault();
    collect();
    if (step === 1) {          // drop extra-goal rows left completely blank
      A.extra_goals = A.extra_goals.filter(g => g && ['goal_type', 'details', 'target_amount', 'target_date'].some(k => String(g[k] || '').trim()));
    }
    if (step === 4 && !A._loans_answered) { showErrors({ loan_types: `Tick your loans, or "${NONE}".` }); return; }
    nextBtn.disabled = true;
    try {
      if (step <= 5) {
        const r = await pfa.post('/api/intake/step', { step, answers: A });
        if (!r.ok) throw new Error(r.data.error || 'Please try again.');
        if (Object.keys(r.data.errors).length) { showErrors(r.data.errors); return; }
        const b = r.data.bubble;
        if (b && b.prefill) Object.entries(b.prefill).forEach(([k, v]) => { if (v && !get(k)) set(k, String(v)); });
        bubbles[step + 1] = b;
        step += 1; render();
      } else {
        await buildPlan();
      }
    } catch (err) {
      formErr.textContent = err.message || 'Something went wrong. Please try again.'; formErr.hidden = false;
    } finally { nextBtn.disabled = false; }
  });

  async function buildPlan() {
    const building = document.getElementById('building');
    const form = document.getElementById('step-form');
    form.hidden = true; building.hidden = false; bubbleEl.hidden = true;
    const r = await pfa.post('/api/plan', { answers: A });
    if (r.ok && r.data.report_url) { location.href = r.data.report_url; return; }
    form.hidden = false; building.hidden = true;
    if (r.status === 422 && r.data.fix) return showFix(r.data.fix);
    if (r.status === 400 && r.data.step) { step = r.data.step; render(); showErrors(r.data.errors); return; }
    throw new Error(r.data.error || 'Could not build the plan. Please try again.');
  }

  // "Nearly there": numbers that can't all be true, pre-filled with what the user typed.
  function showFix(fix) {
    step = 6;
    showBubble({ title: 'Nearly there! 🙂', lines: fix.notes.map(n => n.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]))) });
    fields.replaceChildren(...fix.fields.map(f => amount(f.key, f.label, '')));
    nextBtn.textContent = 'Update and build my plan';
  }

  // ================================================================ voice (v1.4)
  // Nothing listens or speaks unless the user turns it on. Browser voice is free; the natural voice is optional.
  const V = window.pfaVoice;
  const bar = document.getElementById('voice-bar');
  const stepBtn = document.getElementById('voice-step');
  const readBox = document.getElementById('voice-read');
  const vnote = document.getElementById('voice-note');
  const say = t => { vnote.textContent = t; };
  let guided = false;
  try { readBox.checked = localStorage.getItem('pfa-read-aloud') === '1'; } catch (e) { /* private mode */ }
  readBox.addEventListener('change', () => { try { localStorage.setItem('pfa-read-aloud', readBox.checked ? '1' : '0'); } catch (e) {} if (!readBox.checked) V.stopSpeaking(); });
  document.addEventListener('pfa-voice-note', e => say(e.detail));
  V.ready.then(() => {
    if (!V.canListen() && !V.canSpeak()) return;
    bar.hidden = false;
    stepBtn.hidden = !V.canListen();
    if (V.engine === 'openai') {
      const w = document.getElementById('v-natural-wrap'), nb = document.getElementById('v-natural');
      w.hidden = false; nb.checked = V.natural.get(); nb.addEventListener('change', () => V.natural.set(nb.checked));
    }
    addMics();
  });

  const WORDS = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11,
    twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20,
    thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
  function smallNumber(t) {                              // "thirty two" -> 32, "32" -> 32
    const d = t.match(/\d+/); if (d) return Number(d[0]);
    let n = null; for (const w of t.toLowerCase().split(/[\s-]+/)) if (w in WORDS) n = (n || 0) + WORDS[w];
    return n;
  }
  const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  function spokenDate(t) {                               // "June 2034", "30 June 2034", "in 8 years", "2034"
    const low = t.toLowerCase();
    const inYears = low.match(/in\s+(\w+(?:[\s-]\w+)?)\s+years?/);
    const now = new Date();
    if (inYears) { const n = smallNumber(inYears[1]); if (n) { const d = new Date(now.getFullYear() + n, now.getMonth(), 1); return d.toISOString().slice(0, 10); } }
    const y = low.match(/\b(20\d\d)\b/); if (!y) return null;
    const mi = MONTHS.findIndex(m => low.includes(m));
    const day = (low.match(/\b([0-2]?\d|3[01])(st|nd|rd|th)?\b(?!\d)/) || [])[1];
    const mm = mi >= 0 ? mi + 1 : 12, dd = day && Number(day) <= 31 && mi >= 0 ? Number(day) : (mi >= 0 ? 1 : 31);
    return `${y[1]}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
  }
  function matchOption(select, t) {
    const low = t.toLowerCase();
    const alias = { rupee: 'INR', rupees: 'INR', dollar: 'USD', dollars: 'USD', euro: 'EUR', pound: 'GBP', dirham: 'AED',
                    house: 'Buy a home', home: 'Buy a home', flat: 'Buy a home', retire: 'Retirement', education: "Child's education",
                    wedding: "Child's wedding", marriage: "Child's wedding", car: 'Buy a car', business: 'Start a business',
                    travel: 'Travel or sabbatical', wealth: 'Build long-term wealth', debt: 'Debt', hybrid: 'Hybrid', equity: 'Equity', sure: 'Not sure' };
    const opts = [...select.options].filter(o => o.value);
    for (const [k, v] of Object.entries(alias)) if (low.includes(k)) { const o = opts.find(o => o.value === v); if (o) return o.value; }
    const o = opts.find(o => low.includes(o.value.toLowerCase()) || o.textContent.toLowerCase().split(' ').some(w => w.length > 3 && low.includes(w)));
    return o ? o.value : null;
  }

  // Put a spoken answer into one control. Returns what to confirm aloud, or null if it wasn't understood.
  function apply(ctrl, text) {
    const t = text.trim(); const low = t.toLowerCase();
    if (/^(keep|keep it|yes|correct|that'?s right|same|fine|ok(ay)?)\b/.test(low) && ctrl.value) return 'kept';
    if (/^(skip|none|no|nothing|zero|nil|not applicable)\b/.test(low) && ctrl.type !== 'date') {
      if (ctrl.tagName === 'SELECT') return null;
      ctrl.value = ctrl.type === 'number' ? '' : ''; return 'skipped';
    }
    if (ctrl.tagName === 'SELECT') { const v = matchOption(ctrl, t); if (!v) return null; ctrl.value = v; return ctrl.selectedOptions[0].textContent; }
    if (ctrl.type === 'date') { const d = spokenDate(t); if (!d) return null; ctrl.value = d; return new Date(d).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }); }
    if (ctrl.type === 'number') { const n = smallNumber(t); if (n == null) return null; ctrl.value = n; return String(n); }
    if (ctrl.name === 'name') { ctrl.value = t.replace(/^(my name is|i am|i'm|this is)\s+/i, '').replace(/\b\w/g, c => c.toUpperCase()); return ctrl.value; }
    ctrl.value = t.replace(/\.$/, ''); return ctrl.value;
  }

  function prompts() {                                    // the step's questions, in order
    const out = [];
    fields.querySelectorAll('.field, fieldset').forEach(node => {
      if (node.closest('.inv-row') && node.matches('.field') === false) return;
      if (node.tagName === 'FIELDSET') {
        const legend = node.querySelector('legend').textContent;
        const opts = [...node.querySelectorAll('input')].map(i => i.value);
        out.push({ node, kind: node.classList.contains('risk') ? 'risk' : 'multi', q: legend + (node.classList.contains('risk') ? ' Say low, medium or high.' : ' Name them, or say none.'), opts });
        return;
      }
      const ctrl = node.querySelector('input:not([type=checkbox]):not([type=radio]), select');
      if (!ctrl || node.closest('fieldset')) return;
      const span = node.querySelector('span').cloneNode(true);
      span.querySelectorAll('.mic-mini').forEach(b => b.remove());
      const label = span.textContent.replace(/\(optional\)/i, '').trim();
      const have = ctrl.tagName === 'SELECT' ? (ctrl.value ? ctrl.selectedOptions[0].textContent : '') : ctrl.value;
      const hint = have ? ` I have ${have}. Say keep, or tell me the new answer.`
        : (/optional|premium|every month|invested so far|anything else|tell me/i.test(node.textContent) ? ' Say skip if none.' : '');
      out.push({ node, kind: 'one', ctrl, q: label + '.' + hint });
    });
    return out;
  }

  function applyGroup(p, text) {
    const low = text.toLowerCase();
    const inputs = [...p.node.querySelectorAll('input')];
    if (p.kind === 'risk') {
      const lvl = ['low', 'medium', 'high'].find(l => low.includes(l)); if (!lvl) return null;
      const r = inputs.find(i => i.value.toLowerCase() === lvl); r.checked = true; return lvl;
    }
    const keys = { home: 'Home loan', house: 'Home loan', car: 'Car loan', vehicle: 'Car loan', personal: 'Personal loan', education: 'Education loan',
                   student: 'Education loan', credit: 'Credit card dues', card: 'Credit card dues', gold: 'Gold loan', other: 'Other loan' };
    if (/\b(none|no loans?|nothing|debt.?free|zero)\b/.test(low)) {
      inputs.forEach(i => { i.checked = i.value.startsWith('None'); }); inputs.find(i => i.value.startsWith('None')).dispatchEvent(new Event('change', { bubbles: true }));
      return 'no loans';
    }
    const picked = [...new Set(Object.entries(keys).filter(([k]) => low.includes(k)).map(([, v]) => v))];
    if (!picked.length) return null;
    inputs.forEach(i => { i.checked = picked.includes(i.value); });
    inputs.find(i => picked.includes(i.value)).dispatchEvent(new Event('change', { bubbles: true }));
    return picked.join(' and ');
  }

  async function ask(p) {                                 // speak the question, listen, apply; up to 2 tries
    for (let attempt = 0; attempt < 2 && guided; attempt++) {
      p.node.classList.add('asking'); p.node.scrollIntoView({ block: 'center', behavior: 'smooth' });
      await V.speak(attempt ? 'Sorry, I didn\u2019t catch that. ' + p.q : p.q);
      if (!guided) break;
      say('Listening…');
      const heard = await V.listen({ onInterim: t => say('Heard: ' + t) });
      p.node.classList.remove('asking');
      if (!heard) continue;
      const got = p.kind === 'one' ? apply(p.ctrl, heard) : applyGroup(p, heard);
      if (got) { say(''); if (got !== 'skipped' && got !== 'kept') await V.speak('Got it: ' + got); return true; }
    }
    p.node.classList.remove('asking');
    return false;
  }

  async function guide() {                                // walk the current step by voice
    guided = true; stepBtn.textContent = '⏹ Stop voice'; readBox.checked = true;
    if (bubbles[step]) await V.speak([bubbles[step].title, ...(bubbles[step].lines || [])].join(' '));
    if (step === 6) {
      await V.speak('Here is your summary. Say build my plan when you are ready, or tap Edit to change anything.');
    } else {
      let list = prompts();
      for (let i = 0; i < list.length && guided; i++) {
        await ask(list[i]);
        if (step === 4 && list[i].kind === 'multi') list = list.concat(prompts().slice(list.length));   // loan details appear after ticking
      }
      if (!guided) return;
      await V.speak('That\u2019s this step. Say next to continue, or tap any field to change it.');
    }
    say('Listening…');
    const cmd = (await V.listen({ onInterim: t => say('Heard: ' + t) })).toLowerCase();
    say('');
    if (guided && /\b(next|continue|yes|go|build|done|okay|ok)\b/.test(cmd)) document.getElementById('step-form').requestSubmit();
    else stopGuide();
  }
  function stopGuide() { guided = false; stepBtn.textContent = '🎙 Answer this step by voice'; V.stopListening(); V.stopSpeaking(); say(''); }
  stepBtn.addEventListener('click', () => (guided ? stopGuide() : guide()));

  function addMics() {                                    // a small 🎙 on every field, for dictating just that one
    if (!V.canListen()) return;
    fields.querySelectorAll('.field').forEach(node => {
      const ctrl = node.querySelector('input:not([type=checkbox]):not([type=radio]), select');
      if (!ctrl || node.querySelector('.mic-mini')) return;
      const b = el('button', { type: 'button', class: 'mic-mini', title: 'Say it instead', 'aria-label': 'Speak this answer', text: '🎙' });
      b.addEventListener('click', async ev => {
        ev.preventDefault();
        b.classList.add('on'); say('Listening…');
        const heard = await V.listen({ onInterim: t => say('Heard: ' + t) });
        b.classList.remove('on');
        const got = heard ? apply(ctrl, heard) : null;
        say(got ? '' : (heard ? `Couldn\u2019t use "${heard}" here - please type it.` : ''));
      });
      node.querySelector('span').append(b);
    });
  }

  // re-render hooks: mics on new fields; read the bubble aloud; continue a guided session on the next step
  const baseRender = render;
  render = function () {
    baseRender();
    V.ready.then(addMics);
    if (guided) setTimeout(guide, 300);
    else if (readBox.checked && bubbles[step]) V.speak([bubbles[step].title, ...(bubbles[step].lines || [])].join(' '));
  };
  const baseErrors = showErrors;
  showErrors = function (errors) {
    baseErrors(errors);
    if (guided || readBox.checked) V.speak('Please check: ' + Object.values(errors).join('. '));
    if (guided) stopGuide();
  };
  fields.addEventListener('change', () => V.ready.then(addMics));

  render();
})();
