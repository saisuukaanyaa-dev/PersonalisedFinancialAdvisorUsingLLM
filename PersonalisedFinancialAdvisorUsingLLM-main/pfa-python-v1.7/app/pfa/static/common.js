// Shared helpers: JSON calls with the anti-CSRF header, sign-out.
window.pfa = {
  async post(url, body) {
    const res = await fetch(url, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-PFA': '1' }, body: JSON.stringify(body || {}) });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (res.status === 401) { location.href = '/login'; }
    return { ok: res.ok, status: res.status, data };
  },
  el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v; else n.setAttribute(k, v === true ? '' : v);
    }
    kids.flat().forEach(k => k && n.append(k));
    return n;
  },
};
document.querySelectorAll('[data-logout]').forEach(b => b.addEventListener('click', async () => {
  const r = await pfa.post('/auth/logout');
  location.href = (r.data && r.data.next) || '/login';
}));

// "Updating the knowledge base…" banner while the startup refresh runs (live data via SerpAPI).
(async function kbBanner() {
  const box = document.getElementById('kb-banner');
  if (!box) return;
  const text = document.getElementById('kb-text');
  for (let i = 0; i < 120; i++) {
    let s;
    try { s = await (await fetch('/api/kb/status')).json(); } catch (e) { return; }
    if (s.state === 'updating') {
      box.hidden = false; box.className = 'kb-banner';
      text.textContent = `${s.message} (${s.step}/${s.total})`;
    } else if (!box.hidden && (s.state === 'done' || s.state === 'partial')) {
      box.className = 'kb-banner done'; text.textContent = s.message;
      setTimeout(() => { box.hidden = true; }, 6000);
      return;
    } else if (s.state === 'error') {
      if (!box.hidden) { box.className = 'kb-banner warn'; text.textContent = s.message; }
      return;
    } else if (s.state !== 'idle') {
      return;                                   // fresh / off / skipped: nothing to show
    }
    await new Promise(r => setTimeout(r, 1500));
  }
})();
