
// Preview only - nothing is saved to the profile until the user presses Yes.
const ctx = $('Chat Result').first().json;
const row = $json || {};
let saved = row.profile_json;
if (typeof saved === 'string') { try { saved = JSON.parse(saved); } catch (e) { saved = null; } }
let reply = ctx.reply, confirm = null, pending = null;
if (!saved || !saved.profile) {
  reply += '\n\nI could not find a saved plan for that email, so there is nothing to change yet.';
} else {
  const res = applyPlanChanges(answersFromProfile(saved), ctx.changes);
  if (res.answers) {
    const id = newReportId().slice(0, 16);
    const reportId = ctx.report_id || row.latest_report || null;
    confirm = { id, changes: res.log, not_applied: res.ignored, report_id: reportId };
    pending = { id, user_key: ctx.change_email, report_id: reportId, changes: ctx.changes, preview: res.log, message: String(ctx.chatInput || '').slice(0, 300) };
  } else {
    reply += res.ignored.length ? `\n\nI couldn't turn that into a plan change: ${res.ignored.join('; ')}.` : "\n\nThat's already how your plan is set up.";
  }
}
return [{ json: { ...ctx, reply, confirm,
  pending_b64: Buffer.from(JSON.stringify(pending || {}), 'utf8').toString('base64') } }];
