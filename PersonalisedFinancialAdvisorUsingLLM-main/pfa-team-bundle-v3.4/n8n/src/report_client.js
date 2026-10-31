// Report page chat (v3.4): one chat for the plan, bank deposits and the teammate's scheme / fund knowledge.
// Plan changes come back as a Yes / No card; Yes builds a new version of the plan and opens it.
(function () {
  'use strict';
  const B = window.BOOT || {};
  const base = location.pathname.replace(/\/report\/?$/, '');
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Light markdown: **bold**, "- " bullets, paragraphs, links.
  function md(t) {
    const lines = esc(t).split(/\n/); let out = '', list = false;
    for (const l of lines) {
      const li = l.match(/^\s*[-•*]\s+(.*)/);
      if (li) { if (!list) { out += '<ul>'; list = true; } out += `<li>${inline(li[1])}</li>`; continue; }
      if (list) { out += '</ul>'; list = false; }
      if (l.trim()) out += `<p>${inline(l)}</p>`;
    }
    return out + (list ? '</ul>' : '');
  }
  const inline = s => s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1">$1</a>');
  const session = 'r' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  function add(cls, html) { const d = document.createElement('div'); d.className = 'm ' + cls; d.innerHTML = html; $('log').appendChild(d); $('log').scrollTop = 1e9; return d; }
  async function post(path, data) {
    const r = await fetch(base + '/' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const t = await r.text(); try { return JSON.parse(t); } catch (e) { throw new Error('The server returned an error (' + r.status + ').'); }
  }
  function chips(list) { $('chips').innerHTML = (list || []).map(s => `<button type="button">${esc(s)}</button>`).join('');
    $('chips').querySelectorAll('button').forEach(b => b.onclick = () => send(b.textContent)); }
  function confirmCard(c) {
    const d = add('bot confirm', `<b>Change your plan?</b><ul>${(c.changes || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>
      ${c.not_applied && c.not_applied.length ? `<p class="small">Not changed: ${esc(c.not_applied.join('; '))}</p>` : ''}
      <div class="row"><button class="yes">Yes, update my plan</button><button class="no">No, keep it</button></div>`);
    const [yes, no] = d.querySelectorAll('button');
    const answer = async accept => {
      yes.disabled = no.disabled = true;
      const w = add('bot wait', accept ? 'Building your updated plan… (1-3 minutes)' : '…');
      try {
        const r = await post('confirm', { id: c.id, accept });
        w.remove(); add('bot', md(r.reply || (accept ? 'Done.' : 'OK.')));
        if (r.report_id) waitFor(r.report_id);
      } catch (e) { w.remove(); add('bot', esc(e.message)); yes.disabled = no.disabled = false; }
    };
    yes.onclick = () => answer(true); no.onclick = () => answer(false);
  }
  function waitFor(id) {
    const w = add('bot wait', 'Updating your plan… this page will open the new version when it is ready.');
    const t0 = Date.now();
    const poll = async () => {
      try { const r = await (await fetch(base + '/status?id=' + encodeURIComponent(id))).json();
        if (r.ready) { location.href = base + '/report?id=' + encodeURIComponent(id); return; } } catch (e) { /* retry */ }
      w.textContent = `Updating your plan… ${Math.round((Date.now() - t0) / 1000)} s`;
      if (Date.now() - t0 < 15 * 60 * 1000) setTimeout(poll, 5000);
    };
    setTimeout(poll, 40000);
  }
  async function send(text) {
    text = String(text || '').trim(); if (!text) return;
    $('msg').value = ''; chips([]); add('user', esc(text));
    const btn = document.querySelector('.send'); btn.disabled = true;
    const w = add('bot wait', 'Thinking…');
    try {
      const r = await post('chat', { report_id: B.report_id, session, message: text });
      w.remove(); add('bot', md(r.reply || 'Sorry, I have no answer for that.'));
      if (r.confirm && r.confirm.id) confirmCard(r.confirm);
      chips(r.suggestions);
    } catch (e) { w.remove(); add('bot', 'Sorry - I could not reach the advisor just now. Please try again.'); }
    btn.disabled = false; $('msg').focus();
  }
  $('box').addEventListener('submit', e => { e.preventDefault(); send($('msg').value); });
  add('bot', md(`Hi ${B.first_name || 'there'}! Ask me anything about this plan, try a what-if like **"What if I invest 40K a month?"**, ` +
    `or ask about bank deposits and the mutual funds in our documents. I'll show any change before it's made.`));
  chips(['Why is term cover my first action?', 'Which bank FD pays most for 3 years?', 'What if I invest 40K a month?']);
  if (B.pending) confirmCard({ id: B.pending.id, changes: B.pending.changes });
})();
