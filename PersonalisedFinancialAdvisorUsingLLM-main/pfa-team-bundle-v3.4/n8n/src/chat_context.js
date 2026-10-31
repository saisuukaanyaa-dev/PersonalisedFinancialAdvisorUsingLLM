
// One chat, two doors: the chat panel on the report page (POST /webhook/pfa/chat) and n8n's hosted chat page.
// Everything after this node reads $('Chat Context').
let page = false;
try { page = $('Chat API').isExecuted; } catch (e) { page = false; }
if (page) {
  const b = $('Chat API').first().json.body || {};
  const owner = String($json.user_key || '').toLowerCase();
  const msg = String(b.message || '').slice(0, 2000);
  const reportId = String(b.report_id || '');
  return [{ json: {
    channel: 'page', chatInput: msg, sessionId: `page-${String(b.session || reportId).slice(0, 64)}`,
    user_key: owner, report_id: reportId,
    agentInput: owner
      ? `[Context from the app: the signed-in user's email is ${owner} and they are looking at report ${reportId}. ` +
        `Use the profile and report tools with this email - never ask for it.]\n\n${msg}`
      : msg,
  }}];
}
const j = $json;
return [{ json: { channel: 'hosted', chatInput: j.chatInput, sessionId: j.sessionId, user_key: '', report_id: '', agentInput: j.chatInput } }];
