// Report page: swaps in the AI explanation when it is ready, and runs the chat with Arth
// (streamed progress, confirm-before-change, suggestion chips, optional voice in and out).
(() => {
  const { el } = pfa;
  const main = document.getElementById('report-main');
  const reportId = main.dataset.report;
  const note = document.getElementById('writing-note');
  const store = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };

  // ---------- AI text: poll until written, then re-render the report body once ----------
  async function waitForAi() {
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, i < 10 ? 1200 : 2500));
      const res = await fetch(`/api/reports/${reportId}/status`, { credentials: 'same-origin' });
      if (!res.ok) return;
      if (!(await res.json()).writing) {
        const frag = await fetch(`/report/${reportId}?fragment=1`, { credentials: 'same-origin' });
        if (frag.ok) { main.innerHTML = await frag.text(); main.classList.add('fresh'); }
        note.hidden = true;
        return;
      }
    }
    note.hidden = true;
  }
  if (main.querySelector('[data-writing="true"]')) waitForAi();

  // ---------- rendering: short paragraphs, "- " bullets, **bold**; text is escaped first ----------
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  function renderText(text) {
    const box = el('div', { class: 'msg-body' });
    let list = null;
    for (const raw of String(text).split('\n')) {
      const line = raw.trim();
      if (!line) { list = null; continue; }
      if (/^[-•]\s+/.test(line)) {
        if (!list) { list = el('ul'); box.append(list); }
        list.append(el('li', { html: inline(line.replace(/^[-•]\s+/, '')) }));
      } else {
        list = null;
        box.append(el('p', { class: line.startsWith('Live data:') ? 'live-src' : null, html: inline(line) }));
      }
    }
    return box;
  }

  // ---------- chat ----------
  const log = document.getElementById('chat-log');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const send = document.getElementById('chat-send');
  const chips = document.getElementById('suggestions');
  const readAloud = document.getElementById('read-aloud');
  const naturalBox = document.getElementById('natural-voice');

  function costLine(use, link) {
    if (!use) return null;
    const t = use.kind === 'guardrail' ? 'answered locally · ₹0'
      : `₹${use.cost_inr >= 0.1 ? use.cost_inr.toFixed(2) : (use.cost_inr || 0).toFixed(3)} · ${((use.input_tokens || 0) + (use.output_tokens || 0)).toLocaleString('en-IN')} tokens · ${((use.elapsed_ms || 0) / 1000).toFixed(1)} s`
        + (use.serp_searches ? ` · ${use.serp_searches} live search` : '') + (link ? ' (+ the updated report)' : '');
    const b = el('button', { type: 'button', class: 'info-btn', title: t, 'aria-label': `Cost: ${t}`, text: 'ⓘ' });
    b.addEventListener('click', () => { b.textContent = b.textContent === 'ⓘ' ? t : 'ⓘ'; });
    return b;
  }

  function bubble(role, text, extra = {}) {
    const b = el('div', { class: `msg ${role}` });
    b.append(role === 'assistant' ? renderText(text) : el('p', { text }));
    if (extra.link) b.append(el('a', { class: 'btn primary small', href: extra.link, text: 'Open the updated report →' }));
    if (extra.confirm) b.append(confirmBox(extra.confirm));
    const tools = el('div', { class: 'msg-tools' });
    if (role === 'assistant' && !extra.thinking) {
      const spk = el('button', { type: 'button', class: 'info-btn', title: 'Read this aloud', 'aria-label': 'Read this aloud', text: '🔊' });
      spk.addEventListener('click', () => speak(text));
      tools.append(spk);
    }
    const c = costLine(extra.usage, extra.link);
    if (c) tools.append(c);
    if (tools.childNodes.length) b.append(tools);
    log.append(b);
    b.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    return b;
  }

  function confirmBox(c) {
    const box = el('div', { class: 'confirm' },
      el('div', { class: 'confirm-title', text: 'I’ll change:' }),
      el('ul', {}, c.changes.map(x => el('li', { text: x }))),
      c.not_applied && c.not_applied.length ? el('div', { class: 'muted small', text: 'Not changed: ' + c.not_applied.join('; ') }) : null);
    const yes = el('button', { type: 'button', class: 'btn primary small', text: 'Yes, update my plan' });
    const no = el('button', { type: 'button', class: 'btn ghost small', text: 'No, keep it' });
    const act = async accept => {
      yes.disabled = no.disabled = true;
      const thinking = bubble('assistant thinking', accept ? 'Updating your plan…' : '…', { thinking: true });
      const r = await pfa.post('/api/chat/confirm', { id: c.id, accept });
      thinking.remove();
      box.replaceChildren(el('div', { class: 'muted small', text: accept ? '✓ Confirmed' : 'Kept as it is' }));
      reply(r.data || {});
    };
    yes.addEventListener('click', () => act(true));
    no.addEventListener('click', () => act(false));
    box.append(el('div', { class: 'confirm-actions' }, yes, no));
    return box;
  }

  function setChips(list) {
    if (!list || !list.length) return;
    chips.replaceChildren(...list.map(t => el('button', { type: 'button', class: 'chip-btn', text: t })));
  }

  function reply(d) {
    bubble('assistant', d.reply || d.error || 'Sorry, something went wrong.', { link: d.report_url, usage: d.usage, confirm: d.confirm });
    setChips(d.suggestions);
    if (readAloud.checked && d.reply) speak(d.reply);
  }

  fetch('/api/chat/history', { credentials: 'same-origin' }).then(r => r.ok ? r.json() : { messages: [] }).then(j => {
    const msgs = j.messages.slice(-6);
    if (!msgs.length) bubble('assistant', "Hi! I'm Arth. I've read your plan - ask me anything, or tell me what you'd like to change.");
    msgs.forEach(m => bubble(m.role, m.content));
  });

  async function ask(text) {
    if (!text.trim()) return;
    stopSpeaking();
    bubble('user', text);
    input.value = ''; send.disabled = true; input.disabled = true;
    const thinking = bubble('assistant thinking', 'Reading your plan…', { thinking: true });
    const setStage = s => { thinking.querySelector('.msg-body').replaceChildren(el('p', { text: s })); };
    try {
      const res = await fetch('/api/chat/stream', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-PFA': '1' }, body: JSON.stringify({ message: text, report_id: reportId }) });
      if (res.status === 401) { location.href = '/login'; return; }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '', result = null;
      while (!result) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf('\n\n')) >= 0) {
          const line = buf.slice(0, i).replace(/^data: /, ''); buf = buf.slice(i + 2);
          try { const ev = JSON.parse(line); if (ev.stage) setStage(ev.stage); if (ev.result) result = ev.result; } catch (e) { /* partial */ }
        }
      }
      thinking.remove();
      reply(result || { reply: 'Sorry, something went wrong.' });
    } catch (e) {
      thinking.remove();
      bubble('assistant', 'I could not reach the server. Please try again.');
    } finally { send.disabled = false; input.disabled = false; input.focus(); }
  }
  form.addEventListener('submit', e => { e.preventDefault(); ask(input.value); });
  chips.addEventListener('click', e => { const b = e.target.closest('.chip-btn'); if (b) ask(b.textContent); });

  // ---------- voice (shared module static/voice.js): only when the user presses a button ----------
  const V = window.pfaVoice;
  const mic = document.getElementById('mic');
  const vnote = document.getElementById('voice-note');
  const speak = text => V.speak(text);
  const stopSpeaking = () => V.stopSpeaking();
  document.addEventListener('pfa-voice-note', e => { vnote.textContent = e.detail; });
  readAloud.checked = store.get('pfa-read-aloud') === '1';
  readAloud.addEventListener('change', () => { store.set('pfa-read-aloud', readAloud.checked ? '1' : '0'); if (!readAloud.checked) stopSpeaking(); });
  V.ready.then(() => {
    if (V.engine === 'openai') {
      document.getElementById('natural-wrap').hidden = false;
      naturalBox.checked = V.natural.get();
      naturalBox.addEventListener('change', () => V.natural.set(naturalBox.checked));
    }
    if (V.canListen()) mic.hidden = false;
  });
  mic.addEventListener('click', async () => {
    if (V.isListening()) { V.stopListening(); return; }
    mic.classList.add('on'); vnote.textContent = 'Listening… tap 🎙 again to stop';
    const text = await V.listen({ onInterim: t => { input.value = t; }, maxMs: 60000 });
    mic.classList.remove('on'); vnote.textContent = '';
    if (text) ask(text);
  });
})();
