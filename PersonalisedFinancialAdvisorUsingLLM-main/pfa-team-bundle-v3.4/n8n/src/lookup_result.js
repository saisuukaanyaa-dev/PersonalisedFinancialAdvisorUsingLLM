
// POST /webhook/pfa/lookup -> who is this? Pre-filled answers and their plan history for the start page.
const email = String($('Lookup API').first().json.body?.email || '').trim().toLowerCase();
const row = $json || {};
let saved = row.profile_json || null;
if (typeof saved === 'string') { try { saved = JSON.parse(saved); } catch (e) { saved = null; } }
const known = Boolean(row.user_id && saved && saved.profile);
const history = (row.history || []).map(h => ({
  id: h.session_id, created_at: h.created_at, verdict: h.verdict || null,
  verdict_label: VERDICT_LABEL[h.verdict] || '', change_log: h.change_log || [],
}));
return [{ json: {
  ok: true, email, known,
  name: known ? (saved.profile.user_name || '') : '',
  saved_on: row.updated_at || null,
  user_id: row.user_id || null,
  answers: known ? answersFromProfile(saved) : null,
  history,
}}];
