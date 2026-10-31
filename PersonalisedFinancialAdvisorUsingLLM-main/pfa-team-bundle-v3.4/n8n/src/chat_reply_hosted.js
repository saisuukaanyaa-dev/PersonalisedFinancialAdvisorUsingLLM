
// Hosted chat page: it shows only text, so a proposed change is confirmed on the report page.
const j = $json;
let output = j.reply ?? j.output ?? '';
if (j.confirm && j.confirm.report_id) {
  let base = 'http://localhost:5678/';
  try { base = $env.WEBHOOK_URL || $env.N8N_WEBHOOK_URL || base; } catch (e) { /* env access blocked: keep the default */ }
  output += `\n\nTo apply it, open your plan and press Yes: ${base.replace(/\/$/, '')}/webhook/pfa/report?id=${j.confirm.report_id}&pending=${j.confirm.id}`;
}
return [{ json: { output } }];
