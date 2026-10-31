// Personal Finance Advisor v3.4 - the step form (Back / Continue / review with Edit), the start page with
// plan history, and the "building your plan" view. Served by n8n (GET /webhook/pfa); talks to the
// /webhook/pfa/* endpoints of the same workflow. parseAmount, estimateInHand etc. are the same helpers
// the workflow's Code nodes use, so the page and the server read "1.35Cr" the same way.
(function () {
  'use strict';
  const BASE = location.pathname.replace(/\/+$/, '');
  const api = p => BASE + '/' + p;
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const S = { email: '', known: false, name: '', userId: null, history: [], answers: blank(), journey: 'new', step: 1, editing: false, fixes: {} };
  const STEPS = 5;
  const RISK = [
    ['Low', 'Keep my money safe', 'Steady growth: FDs, PPF, an index fund. A fall would worry me.'],
    ['Medium', 'Some ups and downs are fine', 'Mostly mutual funds; I can wait out a bad year.'],
    ['High', 'I can take big swings', 'Funds plus direct stocks; I would invest more after a fall.'],
  ];
  const INV = [['mf', 'Mutual funds', 'SIP'], ['stocks', 'Stocks (direct equity)', 'monthly'], ['gold', 'Gold (coins, SGB, ETF)', 'monthly'],
               ['fd', 'FD / RD', 'monthly deposit'], ['pf', 'PPF / EPF / VPF', 'your monthly contribution'], ['cash', 'Savings / cash beyond the emergency fund', null]];
  const TYPICAL = { 'Home loan': '8.5', 'Car loan': '9.5', 'Personal loan': '13', 'Education loan': '10', 'Credit card dues': '36', 'Gold loan': '10', 'Other loan': '12' };

  function blank() {
    const inv = { other_label: '' };
    ['mf', 'stocks', 'gold', 'fd', 'pf', 'cash', 'other'].forEach(k => { inv[k + '_value'] = ''; inv[k + '_monthly'] = ''; });
    return { user_name: '', age: '', currency: 'INR', annual_ctc: '', goal_type: '', goal_details: '', target_amount: '', target_date: '',
             take_home: '', expenses: '', emergency: '', term_cover: '', term_premium: '', health_cover: '', health_premium: '',
             loan_types: [], loans: {}, investments: inv, risk: '' };
  }
  const cur = () => S.answers.currency || 'INR';
  const money = v => { const n = parseAmount(v); return n === null ? String(v || '') : fmtShort(n, cur()); };
  const get = path => path.split('.').reduce((o, k) => (o == null ? undefined : o[k]), S.answers);
  function set(path, v) {
    const ks = path.split('.'); let o = S.answers;
    ks.slice(0, -1).forEach(k => { if (typeof o[k] !== 'object' || o[k] === null) o[k] = {}; o = o[k]; });
    o[ks[ks.length - 1]] = v;
  }
  async function call(path, data, method) {
    const opt = method === 'GET' ? { method: 'GET' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data || {}) };
    const r = await fetch(api(path) + (method === 'GET' && data ? '?' + new URLSearchParams(data) : ''), opt);
    const text = await r.text();
    let j; try { j = JSON.parse(text); } catch (e) { throw new Error(r.ok ? 'Unexpected reply from the server.' : 'The server returned an error (' + r.status + ').'); }
    if (!r.ok && !j) throw new Error('Server error ' + r.status);
    return j;
  }
  const view = html => { $('app').innerHTML = html; window.scrollTo(0, 0); };

  // ------------------------------------------------------------------ start: email, then welcome back
  function showEmail(msg) {
    view(`<div class="card"><h1>Your money, made simple</h1>
      <p class="sub">A friendly 3-minute walk-through of your money, then a personal plan with charts. Rough numbers are fine.</p>
      ${msg ? `<div class="notice bad">${esc(msg)}</div>` : ''}
      <div class="field"><label class="f" for="email">Your email</label>
      <input type="email" id="email" autocomplete="email" placeholder="you@example.com" value="${esc(S.email)}"></div>
      <p class="hint">Your email finds your saved answers and plans. (Pilot: there is no password yet.)</p>
      <div class="actions"><span></span><button class="btn primary" id="go">Continue</button></div></div>`);
    $('email').focus();
    $('email').addEventListener('keydown', e => { if (e.key === 'Enter') $('go').click(); });
    $('go').onclick = async () => {
      const email = $('email').value.trim().toLowerCase();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return showEmail('Please enter a valid email address.');
      $('go').disabled = true; $('go').textContent = 'Checking…';
      try { await lookup(email); } catch (e) { showEmail(e.message); }
    };
  }
  async function lookup(email) {
    const r = await call('lookup', { email });
    Object.assign(S, { email, known: !!r.known, name: r.name || '', userId: r.user_id || null, history: r.history || [] });
    if (r.known) { S.saved = r.answers || blank(); showWelcome(); }
    else { S.answers = blank(); S.journey = 'new'; S.step = 1; showStep(); }
  }
  function showWelcome() {
    const first = (S.name || 'there').split(' ')[0];
    const latest = S.history[0];
    const goal = S.saved && S.saved.goal_type ? `${S.saved.goal_type}${S.saved.goal_details ? ' - ' + S.saved.goal_details : ''}` : 'your goal';
    view(`<div class="card"><div class="bubble"><h3>Welcome back, ${esc(first)}! 👋</h3><p>Your goal: <strong>${esc(goal)}</strong>. What would you like to do?</p></div>
      <div class="opts">
        ${latest ? `<a class="opt" href="${api('report')}?id=${encodeURIComponent(latest.id)}"><b>See my latest plan</b><span>Open your most recent report and chat about it.</span></a>` : ''}
        <button class="opt" id="upd"><b>Update my answers</b><span>Your saved answers are filled in - change only what's different.</span></button>
        <button class="opt" id="fresh"><b>Start fresh</b><span>Plan for a new goal from a blank form.</span></button>
      </div>
      ${S.history.length ? `<h2>Your plans</h2><ul class="history">${S.history.map(h => `<li><a href="${api('report')}?id=${encodeURIComponent(h.id)}">${esc(fmtDate(h.created_at))}</a>
        ${h.verdict ? `<span class="tag ${esc(h.verdict)}">${esc(h.verdict_label)}</span>` : ''}
        ${h.change_log && h.change_log.length ? `<span class="muted small"> · updated in chat: ${esc(h.change_log.join(', '))}</span>` : ''}</li>`).join('')}</ul>` : ''}
      <div class="actions"><button class="btn ghost" id="other">Use a different email</button><span></span></div></div>`);
    $('upd').onclick = () => { S.answers = Object.assign(blank(), JSON.parse(JSON.stringify(S.saved))); S.journey = 'update'; S.step = 1; showStep(); };
    $('fresh').onclick = () => { const b = blank(); b.user_name = S.saved.user_name || ''; b.age = S.saved.age || ''; b.currency = S.saved.currency || 'INR';
      S.answers = b; S.journey = 'update'; S.step = 1; showStep(); };
    $('other').onclick = () => { S.email = ''; showEmail(); };
  }
  const fmtDate = d => { const t = new Date(d); return isNaN(t) ? String(d || '') : t.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }); };

  // ------------------------------------------------------------------ field builders
  function field(path, label, opts) {
    opts = opts || {};
    const v = get(path) ?? '';
    const fix = S.fixes[path];
    const type = opts.type || 'text';
    const input = type === 'select'
      ? `<select data-path="${path}" id="f_${path}">${opts.blankOpt ? '<option value="">Choose…</option>' : ''}${opts.options.map(o => `<option${o === v ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select>`
      : `<input type="${type}" data-path="${path}" id="f_${path}" value="${esc(v)}" placeholder="${esc(opts.ph || '')}"${opts.inputmode ? ` inputmode="${opts.inputmode}"` : ''}${opts.min ? ` min="${opts.min}"` : ''}>`;
    return `<div class="field${opts.full ? ' full' : ''}${fix ? ' bad' : ''}" data-for="${path}"><label class="f" for="f_${path}">${esc(label)}${opts.req ? ' <em>*</em>' : ''}</label>
      ${input}<div class="err" data-err="${path}">${fix ? esc(fix) : ''}</div>${opts.hint ? `<div class="hint">${opts.hint}</div>` : ''}</div>`;
  }
  const amount = (path, label, req, ph, extra) => field(path, label, Object.assign({ req, ph: ph || 'e.g. 85K, 12L or 1.5Cr', inputmode: 'decimal', kind: 'amount' }, extra || {}));
  function bindInputs() {
    document.querySelectorAll('[data-path]').forEach(el => el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', () => {
      set(el.dataset.path, el.value);
      const box = el.closest('.field'); if (box) { box.classList.remove('bad'); const e = box.querySelector('.err'); if (e) e.textContent = ''; }
      delete S.fixes[el.dataset.path];
      if (el.dataset.path === 'annual_ctc' || el.dataset.path === 'currency') updateCtcHint();
    }));
  }
  function updateCtcHint() {
    const h = $('ctc_hint'); if (!h) return;
    const ctc = parseAmount(S.answers.annual_ctc), est = estimateInHand(ctc, cur());
    h.innerHTML = est ? `That's usually about <strong>${esc(fmtShort(est, cur()))} a month</strong> in hand (we'll check on the next step).` : '';
  }

  // ------------------------------------------------------------------ the five steps + review
  function stepHtml(n) {
    const a = S.answers, c = cur(), first = (a.user_name || '').split(' ')[0];
    if (n === 1) return `<div class="bubble"><h3>${S.journey === 'update' ? `Welcome back${first ? ', ' + esc(first) : ''}! 👋` : "Hi, I'm your finance buddy 👋"}</h3>
        <p>${S.journey === 'update' ? 'Your saved answers are filled in. Change what has moved - a raise, a new goal, a loan paid off.' : "Let's start with you and what you're saving for. Amounts accept shorthand like <strong>85K</strong>, <strong>12L</strong> or <strong>1.5Cr</strong>."}</p></div>
      <div class="grid">${field('user_name', 'Your full name', { req: true, ph: 'e.g. Priya Sharma' })}${field('age', 'Your age', { req: true, type: 'number', ph: 'e.g. 32', inputmode: 'numeric' })}
      ${field('currency', 'Currency', { type: 'select', options: CURRENCIES })}${amount('annual_ctc', 'Current CTC (annual, before tax)', true, 'e.g. 18L or 1.35Cr', { hint: '<span id="ctc_hint"></span>' })}
      ${field('goal_type', 'What are you saving for?', { req: true, type: 'select', options: GOALS, blankOpt: true })}${field('goal_details', 'Tell me a little more (optional)', { ph: 'e.g. 2BHK in Pune, or retire at 50' })}
      ${amount('target_amount', 'Roughly how much will you need?', true, 'e.g. 80L or 1.5Cr')}${field('target_date', 'Target date', { req: true, type: 'date' })}</div>`;
    if (n === 2) {
      const ctc = parseAmount(a.annual_ctc), est = estimateInHand(ctc, c);
      if (!a.take_home && est) a.take_home = shorthand(est, c);
      return `<div class="bubble"><h3>Money in, money out</h3>
        <p>${est ? `💼 A CTC of <strong>${esc(fmtShort(ctc, c))}</strong> usually lands around <strong>${esc(fmtShort(est, c))} a month</strong> after PF and tax (new regime). I've filled that in - correct it if your real take-home is different.` : '💼 Tell me what actually reaches your bank account each month.'}</p></div>
      <div class="grid">${amount('take_home', 'Monthly in-hand salary', true, 'e.g. 1.2L')}${amount('expenses', 'Monthly essential expenses', true, 'Rent, groceries, bills, school fees - not EMIs')}</div>`;
    }
    if (n === 3) {
      const exp = parseAmount(a.expenses), th = parseAmount(a.take_home);
      const left = th && exp !== null ? th - exp : null;
      return `<div class="bubble"><h3>Your safety net</h3>
        ${left !== null ? `<p>${left >= 0 ? `✅ After essentials you have about <strong>${esc(fmtShort(left, c))} a month</strong> before any EMIs.` : `⚠️ Essentials are more than your take-home - we'll focus on breathing room first.`}</p>` : ''}
        <p>🛟 A 6-month emergency fund for you would be about <strong>${esc(fmtShort((exp || 0) * 6, c))}</strong>. Enter <strong>0</strong> for anything you don't have yet - that's very common.</p></div>
      <div class="grid">${amount('emergency', 'Emergency fund set aside', true, 'Money you can reach in a day or two, e.g. 2L')}<div></div>
      ${amount('term_cover', 'Term life insurance cover', false, 'Sum assured, e.g. 1Cr (blank if none)')}${amount('term_premium', 'Term premium per year (optional)', false, 'e.g. 18K')}
      ${amount('health_cover', 'Health insurance cover', false, 'Include employer cover, e.g. 5L')}${amount('health_premium', 'Health premium per year (optional)', false, 'e.g. 24K')}</div>`;
    }
    if (n === 4) {
      const picked = a.loan_types || [];
      return `<div class="bubble"><h3>Loans and card dues</h3><p>💳 Tick everything you have right now - I'll only ask about those. Rough numbers from your latest statement are fine.</p></div>
      <div class="field${S.fixes.loan_types ? ' bad' : ''}" data-for="loan_types"><label class="f">Which of these do you have? <em>*</em></label>
      <div class="choices">${[...LOAN_TYPES, NO_LOANS].map(t => `<label class="chip${picked.includes(t) ? ' on' : ''}"><input type="checkbox" data-loan="${esc(t)}"${picked.includes(t) ? ' checked' : ''}>${esc(t)}</label>`).join('')}</div>
      <div class="err" data-err="loan_types">${esc(S.fixes.loan_types || '')}</div></div>
      ${picked.filter(t => t !== NO_LOANS).map(t => { const card = t === 'Credit card dues'; return `<div class="loan"><h4>${esc(t)}</h4><div class="grid">
        ${amount(`loans.${t}.outstanding`, 'Amount outstanding', true, card ? 'Total unpaid balance, e.g. 90K' : 'e.g. 25L')}
        ${field(`loans.${t}.rate`, 'Interest rate (% per year)', { req: true, ph: `Typical is around ${TYPICAL[t]}%`, inputmode: 'decimal' })}
        ${amount(`loans.${t}.emi`, card ? 'What you pay each month (optional)' : 'Monthly EMI', !card, card ? 'Leave blank if it varies' : 'e.g. 22K')}</div></div>`; }).join('')}`;
    }
    if (n === 5) {
      const th = parseAmount(a.take_home) || 0, exp = parseAmount(a.expenses) || 0;
      const emi = (a.loan_types || []).filter(t => t !== NO_LOANS).reduce((s, t) => s + (parseAmount(get(`loans.${t}.emi`)) || 0), 0);
      const sur = th - exp - emi;
      return `<div class="bubble"><h3>What you already own</h3><p>${th ? (sur >= 0 ? `That leaves roughly <strong>${esc(fmtShort(sur, c))} a month</strong> after essentials and EMIs. ` : `Essentials and EMIs are about <strong>${esc(fmtShort(-sur, c))}</strong> more than your pay - we'll tackle that first. `) : ''}📈 Current value and what you add each month - leave blank anything you don't have.</p></div>
      <div class="inv"><div class="h lbl"></div><div class="h">Current value</div><div class="h">Each month</div>
      ${INV.map(([k, label, m]) => `<div class="lbl">${esc(label)}</div>${invInput(`investments.${k}_value`, 'e.g. 2L')}${m ? invInput(`investments.${k}_monthly`, 'e.g. 5K') : '<div></div>'}`).join('')}
      <div class="lbl">${invInput('investments.other_label', 'Anything else? e.g. NPS', true)}</div>${invInput('investments.other_value', 'e.g. 1L')}${invInput('investments.other_monthly', 'e.g. 2K')}</div>
      <div class="field${S.fixes.risk ? ' bad' : ''}" data-for="risk" style="margin-top:20px"><label class="f">What's your risk-taking capacity? <em>*</em></label>
      <div class="risk">${RISK.map(([v, t, d]) => `<label class="${a.risk === v ? 'on' : ''}"><input type="radio" name="risk" value="${v}"${a.risk === v ? ' checked' : ''}><div><b>${v} - ${esc(t)}</b><span>${esc(d)}</span></div></label>`).join('')}</div>
      <div class="err" data-err="risk">${esc(S.fixes.risk || '')}</div><div class="hint">Goals under 3 years away are always planned at Low risk, whatever you choose.</div></div>`;
    }
    return '';
  }
  function invInput(path, ph, text) {
    const fix = S.fixes[path];
    return `<div class="field${fix ? ' bad' : ''}" data-for="${path}"><input type="text" data-path="${path}" value="${esc(get(path) ?? '')}" placeholder="${esc(ph)}"${text ? '' : ' inputmode="decimal"'} aria-label="${esc(path)}"><div class="err" data-err="${path}">${fix ? esc(fix) : ''}</div></div>`;
  }
  const TITLES = ['About you and your goal', 'Money in, money out', 'Your safety net', 'Loans and dues', 'What you already own'];

  function showStep(notice) {
    if (S.step > STEPS) return showReview(notice);
    const n = S.step;
    view(`<div class="card"><p class="step-label">Step ${n} of ${STEPS} · ${TITLES[n - 1]}</p>
      <div class="progress">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= n ? 'on' : ''}"></i>`).join('')}</div>
      ${notice ? `<div class="notice bad">${notice}</div>` : ''}
      ${stepHtml(n)}
      <div class="actions"><button class="btn ghost" id="back">${S.editing ? 'Cancel' : 'Back'}</button>
      <button class="btn primary" id="next">${S.editing ? 'Save and return to review' : n === STEPS ? 'Review my answers' : 'Continue'}</button></div></div>`);
    bindInputs(); updateCtcHint();
    document.querySelectorAll('[data-loan]').forEach(cb => cb.addEventListener('change', () => {
      let picked = (S.answers.loan_types || []).slice(); const t = cb.dataset.loan;
      if (cb.checked) { picked = t === NO_LOANS ? [NO_LOANS] : picked.filter(x => x !== NO_LOANS).concat(t); }
      else picked = picked.filter(x => x !== t);
      S.answers.loan_types = picked; delete S.fixes.loan_types; showStep();
    }));
    document.querySelectorAll('input[name=risk]').forEach(r => r.addEventListener('change', () => { S.answers.risk = r.value; delete S.fixes.risk; showStep(); }));
    $('back').onclick = () => {
      if (S.editing) { S.editing = false; S.step = STEPS + 1; return showReview(); }
      if (n === 1) return S.known ? showWelcome() : showEmail();
      S.step = n - 1; showStep();
    };
    $('next').onclick = () => {
      const errs = validate(n);
      if (Object.keys(errs).length) {
        Object.assign(S.fixes, errs); showStep('Please check the highlighted fields.');
        const firstBad = document.querySelector('.field.bad input, .field.bad select'); if (firstBad) firstBad.focus();
        return;
      }
      if (S.editing) { S.editing = false; S.step = STEPS + 1; return showReview(); }
      S.step = n + 1; showStep();
    };
  }

  function validate(n) {
    const a = S.answers, e = {};
    const needAmount = (p, label) => { const v = get(p); if (v === '' || v == null) e[p] = `${label} is needed.`; else if (parseAmount(v) === null || parseAmount(v) < 0) e[p] = `I couldn't read "${String(v).slice(0, 30)}" - try e.g. 85K, 12L or 1.5Cr.`; };
    const optAmount = p => { const v = get(p); if (v !== '' && v != null && (parseAmount(v) === null || parseAmount(v) < 0)) e[p] = `I couldn't read "${String(v).slice(0, 30)}" - try e.g. 85K, 12L or 1.5Cr, or leave it blank.`; };
    if (n === 1) {
      if (!String(a.user_name || '').trim()) e.user_name = 'Please tell me your name.';
      const age = Number(a.age); if (!(age >= 16 && age <= 100)) e.age = 'Please enter your age in years (16-100).';
      needAmount('annual_ctc', 'Your CTC');
      if (!a.goal_type) e.goal_type = 'Please choose a goal.';
      needAmount('target_amount', 'The target amount');
      if (!e.target_amount && parseAmount(a.target_amount) < 10000) e.target_amount = 'That looks too small for a goal - e.g. 8L or 1.5Cr.';
      const d = new Date(a.target_date); if (!a.target_date || isNaN(d) || d <= new Date()) e.target_date = 'Please pick a date in the future.';
    } else if (n === 2) { needAmount('take_home', 'Your in-hand salary'); needAmount('expenses', 'Your essential expenses');
      if (!e.take_home && !(parseAmount(a.take_home) > 0)) e.take_home = 'In-hand salary should be more than 0.';
    } else if (n === 3) { needAmount('emergency', 'Your emergency fund (0 is fine)'); ['term_cover', 'term_premium', 'health_cover', 'health_premium'].forEach(optAmount);
    } else if (n === 4) {
      const picked = a.loan_types || [];
      if (!picked.length) e.loan_types = 'Tick your loans, or "None - I\'m debt-free".';
      picked.filter(t => t !== NO_LOANS).forEach(t => {
        needAmount(`loans.${t}.outstanding`, 'The amount outstanding');
        const r = get(`loans.${t}.rate`), rn = parseRate(r);
        if (r === '' || r == null) e[`loans.${t}.rate`] = 'The interest rate is needed.'; else if (rn === null || rn < 0 || rn > 60) e[`loans.${t}.rate`] = 'Enter the yearly rate as a number, e.g. 9.5.';
        if (t === 'Credit card dues') optAmount(`loans.${t}.emi`); else needAmount(`loans.${t}.emi`, 'The monthly EMI');
      });
    } else if (n === 5) {
      ['mf', 'stocks', 'gold', 'fd', 'pf', 'cash', 'other'].forEach(k => { optAmount(`investments.${k}_value`); if (k !== 'cash') optAmount(`investments.${k}_monthly`); });
      if (!a.risk) e.risk = 'Please choose one.';
    }
    return e;
  }

  // ------------------------------------------------------------------ review with Edit, then build
  function showReview(notice) {
    const a = S.answers, c = cur();
    const dl = rows => `<dl>${rows.filter(r => r[1] !== '' && r[1] != null).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
    const loans = (a.loan_types || []).filter(t => t !== NO_LOANS);
    const inv = INV.concat([['other', a.investments.other_label || 'Other', 'monthly']]).map(([k, label]) => {
      const v = a.investments[k + '_value'], m = a.investments[k + '_monthly'];
      const hv = (parseAmount(v) || 0) > 0, hm = (parseAmount(m) || 0) > 0;
      return (hv || hm) ? [label, [hv ? money(v) : '', hm ? money(m) + ' a month' : ''].filter(Boolean).join(' + ')] : null;
    }).filter(Boolean);
    const sec = (n, title, body) => `<section><div class="rh"><h3>${esc(title)}</h3><button class="linkish" data-edit="${n}">Edit</button></div>${body}</section>`;
    view(`<div class="card review"><p class="step-label">Review</p><div class="progress">${[1, 2, 3, 4, 5].map(() => '<i class="on"></i>').join('')}</div>
      <div class="bubble"><h3>Here's what you told me</h3><p>Check it over, fix anything with <strong>Edit</strong>, then build your plan.</p></div>
      ${notice ? `<div class="notice bad">${notice}</div>` : ''}
      ${sec(1, 'About you and your goal', dl([['Name', a.user_name], ['Age', a.age], ['Currency', c], ['CTC', money(a.annual_ctc) + ' a year'],
        ['Goal', a.goal_type + (a.goal_details ? ' - ' + a.goal_details : '')], ['Target', money(a.target_amount) + ' by ' + a.target_date]]))}
      ${sec(2, 'Money in, money out', dl([['In-hand pay', money(a.take_home) + ' a month'], ['Essentials', money(a.expenses) + ' a month']]))}
      ${sec(3, 'Safety net', dl([['Emergency fund', money(a.emergency)], ['Term cover', a.term_cover ? money(a.term_cover) : 'none'], ['Health cover', a.health_cover ? money(a.health_cover) : 'none']]))}
      ${sec(4, 'Loans', loans.length ? dl(loans.map(t => [t, `${money(get(`loans.${t}.outstanding`))} at ${get(`loans.${t}.rate`)}%${get(`loans.${t}.emi`) ? ', EMI ' + money(get(`loans.${t}.emi`)) : ''}`])) : '<p class="muted">None - debt-free 🙌</p>')}
      ${sec(5, 'What you own and your risk', dl(inv.concat([['Risk', a.risk]])))}
      <div class="actions"><button class="btn ghost" id="back">Back</button><button class="btn primary" id="build">Build my plan</button></div></div>`);
    document.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => { S.editing = true; S.step = Number(b.dataset.edit); showStep(); });
    $('back').onclick = () => { S.step = STEPS; showStep(); };
    $('build').onclick = submit;
  }

  async function submit() {
    const b = $('build'); b.disabled = true; b.textContent = 'Checking your answers…';
    let r;
    try { r = await call('submit', { email: S.email, journey: S.journey, answers: S.answers }); }
    catch (e) { b.disabled = false; b.textContent = 'Build my plan'; return showReview(esc(e.message) + ' Please try again.'); }
    if (r && r.ok && r.report_id) return showBuilding(r.report_id);
    // The server found something to fix: show it on the right step.
    S.fixes = {}; let firstStep = STEPS + 1;
    (r && r.fixes || []).forEach(f => {
      if (!f.field) return;
      S.fixes[f.field] = f.message || f.label;
      if (f.value !== null && f.value !== undefined && f.value !== '') set(f.field, f.value);
      firstStep = Math.min(firstStep, stepOf(f.field));
    });
    const notes = (r && r.notes || []).join(' ');
    S.step = firstStep; S.editing = false;
    if (firstStep > STEPS) return showReview(notes || 'Something needs checking - please review your answers.');
    showStep(notes || 'Nearly there - please fix the highlighted field.');
  }
  function stepOf(f) {
    if (['user_name', 'age', 'currency', 'annual_ctc', 'goal_type', 'goal_details', 'target_amount', 'target_date'].includes(f)) return 1;
    if (['take_home', 'expenses'].includes(f)) return 2;
    if (['emergency', 'term_cover', 'term_premium', 'health_cover', 'health_premium'].includes(f)) return 3;
    if (f.startsWith('loans.') || f === 'loan_types') return 4;
    return 5;
  }

  // ------------------------------------------------------------------ building: progress, then the report
  function showBuilding(id) {
    const steps = ['Checking your answers', 'Saving your profile', 'Analysing your debts and investments (2 AI agents)', 'Projecting your goal and planning bank deposits',
                   'Choosing investments (knowledge base + market data)', 'Writing your report'];
    const at = [0, 4, 8, 40, 55, 95];
    view(`<div class="card"><h1>Building your plan…</h1><p class="sub">This takes 1-3 minutes while four AI agents work through your numbers. Keep this page open.</p>
      <ul class="steps" id="steps">${steps.map(s => `<li>${esc(s)}</li>`).join('')}</ul><p class="muted small" id="elapsed"></p></div>`);
    const t0 = Date.now();
    const tick = setInterval(() => {
      const s = (Date.now() - t0) / 1000;
      document.querySelectorAll('#steps li').forEach((li, i) => { li.className = s >= (at[i + 1] ?? 1e9) ? 'done' : s >= at[i] ? 'doing' : ''; });
      $('elapsed').textContent = `${Math.round(s)} s` + (s > 300 ? ' - taking longer than usual. Keep the page open; if it doesn\'t finish, open your plans from the start page later.' : '');
    }, 1000);
    const poll = async () => {
      try {
        const r = await call('status', { id }, 'GET');
        if (r && r.ready) { clearInterval(tick); location.href = api('report') + '?id=' + encodeURIComponent(id); return; }
      } catch (e) { /* keep polling */ }
      if (Date.now() - t0 < 15 * 60 * 1000) setTimeout(poll, 5000);
    };
    setTimeout(poll, 40000);                     // a plan never takes less than ~40 s; then check every 5 s
  }

  // ------------------------------------------------------------------ boot
  const boot = window.BOOT || {};
  if (boot.building) showBuilding(boot.building);
  else if (boot.email) { S.email = boot.email; lookup(boot.email).catch(e => showEmail(e.message)); }
  else showEmail();
})();
