(() => {
  let mode = 'login';
  const form = document.getElementById('auth-form');
  const err = document.getElementById('auth-error');
  const submit = document.getElementById('auth-submit');
  const setMode = m => {
    mode = m;
    document.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.mode === m)));
    document.querySelectorAll('.signup-only').forEach(n => { n.hidden = m !== 'signup'; });
    document.getElementById('password').autocomplete = m === 'signup' ? 'new-password' : 'current-password';
    submit.textContent = m === 'signup' ? 'Create account' : 'Sign in';
    err.hidden = true;
  };
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  form.addEventListener('submit', async e => {
    e.preventDefault();
    err.hidden = true; submit.disabled = true;
    const body = { email: form.email.value, password: form.password.value, name: form.name.value };
    const r = await pfa.post(mode === 'signup' ? '/auth/signup' : '/auth/login', body);
    submit.disabled = false;
    if (r.ok) { location.href = r.data.next || '/start'; return; }
    err.textContent = r.data.error || 'Something went wrong. Please try again.'; err.hidden = false;
  });
})();
