// Chat-first intake (v1.6). One AI read for the user's own words; short answers, edits and the review are code only.
(() => {
  const boot = JSON.parse(document.getElementById('boot').textContent);
  const $ = (id) => document.getElementById(id);
  const { el, post } = window.pfa;
  let S = boot;                                   // latest payload: answers, asks, summary, progress, reads_used
  let spent = 0, busy = false;

  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function add(cls, html, who) {
    const d = el('div', { class: cls === 'note' ? 'inote' : `imsg ${cls}`, html: (who ? `<div class="who">${who}</div>` : '') + html });
    $('log').append(d); $('log').scrollTop = 1e6; return d;
  }
  const arth = (html) => add('arth', html, 'Arth');
  const lines = (r) => (r.lines || []).map((l) => `<p>${l}</p>`).join('');   // reaction lines come pre-escaped from the server
  function meter() { $('meter').textContent = `AI reads ${S.reads_used} of ${S.reads_max} · ₹${spent.toFixed(2)}`; }

  // ---------------------------------------------------------------- profile panel
  function renderProfile(flash = []) {
    let html = '', group = '';
    for (const r of S.summary) {
      if (r.group !== group) { group = r.group; html += `<div class="iprof-group">${esc(group)}</div>`; }
      const mark = r.src === 'ai' ? ' ✦' : r.src === 'code' ? ' ✓' : r.src === 'estimated' ? ' ≈' : r.src === 'saved' ? ' · saved' : '';
      html += `<div class="iprof-row${flash.includes(r.key) ? ' flash' : ''}"><span class="k">${esc(r.label)}</span>
        <span class="v${r.value ? '' : ' empty'}">${r.value ? esc(r.value) : 'not yet'}<small>${mark}</small></span>
        ${r.heard ? `<span class="q">“${esc(r.heard)}”</span>` : ''}</div>`;
    }
    $('profile').innerHTML = html;
    $('progress-text').textContent = `${S.progress.have} of ${S.progress.total} answers`;
    $('progress-bar').style.width = `${(S.progress.have / S.progress.total) * 100}%`;
    if (flash.length) setTimeout(() => document.querySelectorAll('.iprof-row.flash').forEach((r) => r.classList.remove('flash')), 1800);
    meter();
  }
  if (boot.reports && boot.reports.length) {
    $('reports').innerHTML = '<div class="iprof-group">Your plans</div>' + boot.reports.map((r) =>
      `<a class="iprof-report" href="/report/${encodeURIComponent(r.id)}">${esc(r.when)} <span class="tag ${esc(r.verdict)}">${esc(
        { on_track: 'On track', small_gap: 'Slightly behind', large_gap: 'Significant gap' }[r.verdict] || '')}</span></a>`).join('');
  }

  // ---------------------------------------------------------------- grouped questions (code only)
  function askCard(asks, errors = {}) {
    const box = el('div', { class: 'iask' });
    const values = {};
    for (const a of asks) {
      const row = el('div', { class: 'iask-row' });
      row.append(el('div', { class: 'iask-label', html: `${esc(a.label)}${a.hint ? `<small>${esc(a.hint)}</small>` : ''}` }));
      if (a.kind === 'risk' || a.kind === 'goal' || a.kind === 'loans') {
        const opts = a.kind === 'risk' ? a.options : a.kind === 'goal' ? a.options.map((g) => [g, g]) : [...a.options.map((t) => [t, t]), ['__none', 'None - debt-free']];
        const wrap = el('div', { class: 'ichips' });
        const picked = new Set();
        for (const [val, text] of opts) {
          const b = el('button', { type: 'button', class: 'ichip', text });
          b.addEventListener('click', () => {
            if (a.kind === 'loans') {
              if (val === '__none') { picked.clear(); wrap.querySelectorAll('.ichip').forEach((x) => x.classList.remove('on')); picked.add('__none'); b.classList.add('on'); }
              else { picked.delete('__none'); wrap.querySelector('.ichip:last-child').classList.remove('on'); b.classList.toggle('on'); b.classList.contains('on') ? picked.add(val) : picked.delete(val); }
              values[a.key] = [...picked].filter((x) => x !== '__none'); values[a.key]._set = picked.size > 0;
            } else {
              wrap.querySelectorAll('.ichip').forEach((x) => x.classList.remove('on')); b.classList.add('on'); values[a.key] = val;
            }
            check();
          });
          wrap.append(b);
        }
        row.append(wrap);
      } else {
        const inp = el('input', { 'data-k': a.key, type: a.kind === 'number' ? 'number' : 'text', inputmode: a.kind === 'amount' ? 'decimal' : undefined,
          placeholder: a.hint && a.hint.startsWith('e.g.') ? a.hint.slice(5) : '' });
        inp.addEventListener('input', () => { values[a.key] = inp.value; check(); });
        row.append(inp);
      }
      if (errors[a.key]) row.append(el('div', { class: 'iask-err', text: errors[a.key] }));
      box.append(row);
    }
    const done = el('button', { type: 'button', class: 'btn primary', text: 'Done', disabled: true });
    const check = () => {
      done.disabled = !asks.every((a) => a.kind === 'loans' ? values[a.key] && values[a.key]._set : String(values[a.key] ?? '').trim() !== '');
    };
    done.addEventListener('click', async () => {
      done.disabled = true; box.querySelectorAll('input, button').forEach((x) => { x.disabled = true; });
      const shown = asks.map((a) => {
        const v = values[a.key];
        if (a.kind === 'loans') return v.length ? v.join(', ') : 'no loans';
        if (a.kind === 'risk') return `${v} risk`;   // e.g. "Medium risk"
        return v;
      }).join(' · ');
      add('user', esc(shown), 'You');
      await send('/api/intake/fill', { answers: S.answers, values });
    });
    box.append(done);
    return box;
  }

  // ---------------------------------------------------------------- review: Build my plan / Edit my plan
  function review(title) {
    const d = arth(`${esc(title)}<div class="iask isum">${S.summary.filter((r) => r.value).map((r) =>
      `<div class="isum-row"><span>${esc(r.label)}</span><b>${esc(r.value)}</b></div>`).join('')}</div>`);
    const btns = el('div', { class: 'ibtns' });
    const build = el('button', { type: 'button', class: 'btn primary', text: 'Build my plan' });
    const edit = el('button', { type: 'button', class: 'btn ghost', text: 'Edit my plan' });
    build.addEventListener('click', () => buildPlan(btns));
    edit.addEventListener('click', () => { btns.remove(); editCard(d); });
    btns.append(build, edit); d.querySelector('.iask').append(btns);
  }

  function editCard(d) {                            // every answer becomes an input in place - code only, ₹0
    const a = S.answers, inv = a.inv || {}, loans = a.loans || {};
    const f = [['name', 'Name', a.name], ['age', 'Age', a.age], ['ctc', 'CTC (yearly)', a.ctc], ['take_home', 'In-hand (monthly)', a.take_home],
      ['target_amount', 'Target', a.target_amount], ['target_date', 'By (YYYY-MM-DD)', a.target_date], ['expenses', 'Essentials (monthly)', a.expenses],
      ['emergency', 'Emergency fund', a.emergency], ['term_cover', 'Term life cover', a.term_cover], ['health_cover', 'Health cover', a.health_cover]];
    for (const t of (a.loan_types || []).filter((x) => boot.loanTypes.includes(x))) {
      f.push([`loans.${t}.outstanding`, `${t}: amount left`, (loans[t] || {}).outstanding], [`loans.${t}.rate`, `${t}: rate %`, (loans[t] || {}).rate],
        [`loans.${t}.emi`, `${t}: EMI`, (loans[t] || {}).emi]);
    }
    for (const [k, label] of [['mf', 'Mutual funds'], ['stocks', 'Stocks'], ['gold', 'Gold'], ['fd', 'FD / RD'], ['pf', 'PPF / EPF'], ['cash', 'Savings / cash']]) {
      f.push([`inv.${k}_value`, `${label}: value`, inv[`${k}_value`]], [`inv.${k}_monthly`, `${label}: monthly`, inv[`${k}_monthly`]]);
    }
    const box = d.querySelector('.iask');
    box.innerHTML = '';
    const goal = el('select', { 'data-k': 'goal_type' }, ...boot.goals.map((g) => el('option', { value: g, text: g, selected: g === a.goal_type })));
    const risk = el('select', { 'data-k': 'risk' }, ...[['Low', 'Low · keep it safe'], ['Medium', 'Medium · some ups and downs'], ['High', 'High · big swings for growth']]
      .map(([r, t]) => el('option', { value: r, text: t, selected: r === a.risk })));
    box.append(el('label', { class: 'iedit' }, el('span', { text: 'Goal' }), goal));
    for (const [k, label, v] of f) box.append(el('label', { class: 'iedit' }, el('span', { text: label }), el('input', { 'data-k': k, value: v ?? '' })));
    box.append(el('label', { class: 'iedit' }, el('span', { text: 'Risk-taking capacity' }), risk));
    const save = el('button', { type: 'button', class: 'btn primary', text: 'Save and build my plan' });
    save.addEventListener('click', async () => {
      const values = {};
      box.querySelectorAll('[data-k]').forEach((x) => { values[x.dataset.k] = x.value.trim(); });
      save.disabled = true;
      const res = await send('/api/intake/fill', { answers: S.answers, values }, { quiet: true });
      if (res && res.complete && !Object.keys(res.errors || {}).length) buildPlan(null);
      else save.disabled = false;
    });
    box.append(el('div', { class: 'ibtns' }, save));
  }

  async function buildPlan(btns) {
    if (btns) btns.querySelectorAll('button').forEach((b) => { b.disabled = true; });
    const wait = arth('<span class="typing"><i></i><i></i><i></i></span> Building your plan…');
    const r = await post('/api/plan', { answers: S.answers });
    wait.remove();
    if (r.ok && r.data.report_url) { add('note', 'Opening your report…'); location.href = r.data.report_url; return; }
    if (r.status === 422 && r.data.fix) {                       // numbers that can't all be true: ask again, code only
      arth(`${r.data.fix.notes.map((n) => `<p>${n}</p>`).join('')}`).append(askCard(r.data.fix.fields.map((x) => ({ key: x.key, label: x.label, kind: 'amount' }))));
      return;
    }
    const errs = (r.data && r.data.errors) || {};
    arth(`Something still needs a look: ${esc(Object.values(errs).join(' ') || (r.data && r.data.error) || 'please try again.')}`);
    if (btns) btns.querySelectorAll('button').forEach((b) => { b.disabled = false; });
  }

  // ---------------------------------------------------------------- talk to the server
  async function send(url, body, opt = {}) {
    if (busy) return null;
    busy = true;
    $('send').disabled = true;
    const wait = url.endsWith('/chat') ? arth('<span class="typing"><i></i><i></i><i></i></span> Reading your message…') : null;
    const r = await post(url, body);
    if (wait) wait.remove();
    busy = false;
    if (!r.ok) { arth(esc((r.data && r.data.error) || 'Something went wrong - please try again.')); return null; }
    S = { ...S, ...r.data };
    if (r.data.usage) { spent += r.data.usage.cost_inr || 0; add('note', `1 AI read · ₹${(r.data.usage.cost_inr || 0).toFixed(2)} · ${((r.data.usage.ms || 0) / 1000).toFixed(1)} s`); }
    else if (url.endsWith('/fill') && !opt.quiet) add('note', 'Read by code, no AI · ₹0');
    renderProfile(r.data.updated || []);
    const errs = r.data.errors || {};
    if (Object.keys(errs).length) {
      const asks = S.asks.filter((a) => errs[a.key]);
      arth('A couple of those I couldn\'t read:').append(asks.length ? askCard(asks, errs) : el('span', { text: Object.values(errs).join(' ') }));
      return S;
    }
    if (opt.quiet) return S;
    const head = r.data.reply ? `${esc(r.data.reply.title)}${lines(r.data.reply)}` : '';
    if (S.asks.length) {
      arth(head || `Thanks! ${S.asks.length} quick thing${S.asks.length > 1 ? 's' : ''} left:`).append(askCard(S.asks));
    } else {
      if (head) arth(head);
      const fn = String(S.answers.name || boot.first_name || '').trim().split(' ')[0];
      review(`Here's what I understood${fn ? `, ${fn}` : ''}. Build your plan, or edit anything first.`);
    }
    return S;
  }

  // ---------------------------------------------------------------- input bar: grows with the text, send only when there is text
  const HINT = 'Enter to send · Shift + Enter for a new line';
  const hint = (text, warn) => { $('hint').textContent = text || HINT; $('hint').classList.toggle('warn', !!warn); };
  const grow = () => {
    const t = $('msg');
    t.style.height = 'auto';
    t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
    $('send').disabled = !t.value.trim() || busy;
  };
  $('msg').addEventListener('input', grow);
  $('composer').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = $('msg').value.trim();
    if (!text || busy) return;
    if (window.pfaVoice && window.pfaVoice.isListening()) window.pfaVoice.stopListening();
    add('user', esc(text), 'You');
    $('msg').value = ''; grow();
    await send('/api/intake/chat', { message: text, answers: S.answers });
    grow();
  });
  $('msg').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('composer').requestSubmit(); } });
  window.pfaIntakeFill = (text) => { $('msg').value = text; grow(); $('msg').focus(); };

  // ---------------------------------------------------------------- voice (browser speech by default, free). The mic is always
  // shown; if this browser can't listen, tapping it says so instead of the button silently missing.
  const V = window.pfaVoice;
  let voiceNote = '';
  document.addEventListener('pfa-voice-note', (e) => {          // the exact reason voice stopped, with what to do about it
    voiceNote = e.detail || '';
    const err = V && V.lastError;
    const fix = err === 'not-allowed' || err === 'audio-capture'
      ? ' Allow the microphone for this site (icon in the address bar) and for your browser (Mac: System Settings → Privacy & Security → Microphone), or type instead.'
      : err === 'network' || err === 'service-not-allowed' ? ' Try Chrome or Edge, or type instead.' : ' Or type instead.';
    hint(voiceNote + fix, true);
  });
  $('mic').addEventListener('click', async () => {
    if (!V) { hint('Voice input isn\'t available here - please type instead.', true); return; }
    await V.ready;
    if (!V.canListen()) { hint('Voice input needs Chrome, Edge or Safari (or the natural voice setting). You can type instead.', true); return; }
    if (V.isListening()) { V.stopListening(); return; }
    const before = $('msg').value.trim();
    voiceNote = '';
    $('mic').classList.add('on'); $('mic').setAttribute('aria-pressed', 'true');
    hint('Listening… speak naturally (pauses are fine), then tap the mic again to stop');
    const said = await V.listen({ onInterim: (t) => { $('msg').value = [before, t].filter(Boolean).join(' '); grow(); }, maxMs: 90000, continuous: true });
    $('mic').classList.remove('on'); $('mic').setAttribute('aria-pressed', 'false');
    if (said) { $('msg').value = [before, said].filter(Boolean).join(' '); grow(); hint('Check the text, then press Enter to send'); }
    else if (!voiceNote) hint(before ? '' : 'I didn\'t catch that - try again, or type instead.', !before);
    $('msg').focus();
  });

  // ---------------------------------------------------------------- opening message
  renderProfile();
  const examples = [
    "I'm Priya, 32, CTC 18 lakh, take-home about 1.2L. I want to buy a 2BHK around 80 lakh by 2034. Expenses roughly 45K a month. Car loan 3.2L left at 9.2%, EMI 11K. 4.5L in mutual funds with a 15K SIP and 2L in FDs.",
    "Meera here, 28. I earn 12L a year and want a car worth 8 lakh in about 3.5 years. Essentials are 40K a month, no loans. 1L in mutual funds plus 5K SIP, 50K in an FD and 2L in PPF.",
  ];
  if (boot.returning) {
    arth(`Welcome back, ${esc(boot.first_name || 'there')}! 👋 Here's your saved profile. Has anything changed? Tell me in your own words (e.g. "my salary is now 20L"), or:`);
    review('Your saved answers:');
  } else {
    const d = arth(`Hi${boot.first_name ? ` ${esc(boot.first_name)}` : ''}! I'm Arth. Tell me about yourself, your goal and your money in your own words - a few sentences is plenty. You can also tap 🎙 and just talk.
      <div class="ichips">${['Example: buying a home', 'Example: saving for a car'].map((t, i) => `<button type="button" class="ichip" data-ex="${i}">${t}</button>`).join('')}</div>`);
    d.querySelectorAll('[data-ex]').forEach((b) => b.addEventListener('click', () => window.pfaIntakeFill(examples[+b.dataset.ex])));
  }
})();
