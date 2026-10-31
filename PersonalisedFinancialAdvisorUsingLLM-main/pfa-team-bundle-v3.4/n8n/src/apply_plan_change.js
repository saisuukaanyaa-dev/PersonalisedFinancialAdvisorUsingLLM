
// POST /webhook/pfa/confirm -> the user pressed Yes or No on a change the chat proposed.
const body = $('Confirm API').first().json.body || {};
const row = $json || {};
const accept = body.accept === true || body.accept === 'true';
if (!row.id) return [{ json: { action: 'gone', reply: 'That change has already been handled.' } }];
if (!accept) return [{ json: { action: 'decline', id: row.id, status: 'declined',
  reply: "No problem - I've left your plan exactly as it is. What would you like to look at instead?" } }];
let saved = row.profile_json;
if (typeof saved === 'string') { try { saved = JSON.parse(saved); } catch (e) { saved = {}; } }
let changes = row.changes;
if (typeof changes === 'string') { try { changes = JSON.parse(changes); } catch (e) { changes = {}; } }
const res = applyPlanChanges(answersFromProfile(saved), changes);
if (!res.answers) return [{ json: { action: 'stale', id: row.id, status: 'stale',
  reply: 'Your plan already has those numbers, so there was nothing to change.' } }];
return [{ json: {
  action: 'apply',
  email: row.user_key, journey: 'update', is_returning: true, user_id: row.user_id || null,
  answers: res.answers, change_log: res.log, parent: row.report_id || null, pending_id: row.id,
}}];
