
// POST /webhook/pfa/submit from the step form -> a plan request for "Build Financial Profile".
const b = $json.body || {};
const answers = (b.answers && typeof b.answers === 'object') ? b.answers : {};
return [{ json: {
  email: String(b.email || '').trim().toLowerCase(),
  journey: b.journey === 'update' ? 'update' : 'new',
  is_returning: b.journey === 'update',
  user_id: null,
  answers,
  change_log: [],
  parent: null,
  pending_id: null,
}}];
