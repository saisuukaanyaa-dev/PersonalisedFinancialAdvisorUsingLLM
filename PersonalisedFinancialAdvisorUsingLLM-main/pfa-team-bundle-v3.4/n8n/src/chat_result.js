
// The agent's answer (already sanitised) + any plan change it proposed via Propose_Plan_Change.
const ctx = $('Chat Context').first().json;
const agent = $('Financial Q&A Agent').first().json;
const reply = $json.guardrailsInput ?? agent.output ?? '';
const steps = agent.intermediateSteps || [];
const prop = [...steps].reverse().find(s => s && s.action && s.action.tool === 'Propose_Plan_Change');
let changes = null, email = ctx.user_key;
if (prop) {
  let ti = prop.action.toolInput;
  if (typeof ti === 'string') { try { ti = JSON.parse(ti); } catch (e) { ti = {}; } }
  if (ti && ti.input && typeof ti.input === 'object') ti = ti.input;
  email = String(ctx.user_key || ti.email || '').trim().toLowerCase();
  changes = Object.fromEntries(Object.entries(ti || {}).filter(([k, v]) => k !== 'email' && v !== null && v !== undefined && v !== ''));
  if (!Object.keys(changes).length) changes = null;
}
return [{ json: { ...ctx, reply, changes, change_email: email, has_change: Boolean(changes && email) ? 'yes' : 'no' } }];
