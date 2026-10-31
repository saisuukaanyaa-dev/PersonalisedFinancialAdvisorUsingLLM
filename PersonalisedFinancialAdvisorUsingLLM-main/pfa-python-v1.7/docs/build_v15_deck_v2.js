// Deck v2 for the mentor and the team: Personal Finance Advisor, Python v1.5 - models and concepts.
// Plain titles, real screenshots from the sample run, varied layouts, conversational speaker notes.
// Build: NODE_PATH=<node_modules with pptxgenjs> node build_v15_deck_v2.js <out.pptx> <shots dir> [apply_theme.js]
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2] || "PFA_v1.5_Models_and_Concepts_v2.pptx";
const SHOTS = process.argv[3] || ".";
const APPLY = process.argv[4];
const THEME = {
  name: "PFA Lavender", headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: "1C1A22", lt1: "FFFFFF", dk2: "5B1A96", lt2: "F7F3FA", accent1: "8E2DE2", accent2: "D9376E", accent3: "E8871E",
            accent4: "6E59A5", accent5: "2E7D4F", accent6: "6F6A78", hlink: "8E2DE2", folHlink: "6E59A5" },
};
const img = (f) => "image/png;base64," + fs.readFileSync(path.join(SHOTS, f)).toString("base64");

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";                      // 10 x 5.625 in
  pres.title = "Personal Finance Advisor - Python v1.5 - models and concepts";
  pres.author = "Group 2";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  pres.defineSlideMaster({
    title: "Content", background: { color: C.background2 }, margin: [0.5, 0.5, 0.5, 0.5],
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.75, fontSize: 24, bold: true, color: C.text1,
        valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: "Personal Finance Advisor · Python v1.5", options: { x: 0.5, y: 5.3, w: 5, h: 0.2, fontSize: 8, color: C.accent6 } } },
    ],
    slideNumber: { x: 9.0, y: 5.3, w: 0.5, h: 0.2, fontSize: 8, color: C.accent6, align: "right" },
  });
  pres.defineSlideMaster({ title: "Cover", background: { color: C.text2 } });

  const T = (s, text, o) => s.addText(text, { color: C.text1, isTextBox: true, margin: 0, valign: "top", fontSize: 12, ...o });
  const bullets = (items, o = {}) => items.map((t, i) => ({ text: t, options: { bullet: o.bullet === false ? false : { indent: 12 }, breakLine: i < items.length - 1, ...o.run } }));
  let section = "";
  const slide = (title, notes) => {
    const s = pres.addSlide({ masterName: "Content", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    s.addNotes(notes);
    return s;
  };
  const panel = (s, x, y, w, h, fill = C.background1, name) =>
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: "E2D9EA", width: 0.75 }, objectName: name });
  const shot = (s, file, x, y, w, ratio, name) => {          // screenshot with a thin frame and a soft shadow
    const h = w / ratio;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.background1 }, line: { color: "D8CFE3", width: 0.75 },
      shadow: { type: "outer", color: "3A2A55", opacity: 0.18, blur: 10, offset: 3, angle: 90 } });
    s.addImage({ data: img(file), x, y, w, h, objectName: name });
    return h;
  };
  const caption = (s, text, x, y, w) => T(s, text, { x, y, w, h: 0.25, fontSize: 9, italic: true, color: C.accent6 });
  const line = (s, x1, y1, x2, y2, arrow = true) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2),
    w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001, flipV: y2 < y1,
    line: { color: C.accent6, width: 1, endArrowType: arrow ? "triangle" : undefined } });
  const hbars = (s, { x, y, w, h, items, max, fmt, labW = 1.6 }) => {
    const rowH = h / items.length, barW = w - labW - 0.7;
    items.forEach(([label, v, col], i) => {
      const yy = y + i * rowH, bh = Math.min(0.3, rowH * 0.62);
      T(s, label, { x, y: yy, w: labW - 0.12, h: bh, fontSize: 10, valign: "middle", align: "right" });
      const bw = Math.max(0.03, barW * v / max);
      s.addShape(pres.shapes.RECTANGLE, { x: x + labW, y: yy, w: bw, h: bh, fill: { color: col }, line: { color: col } });
      T(s, fmt(v), { x: x + labW + bw + 0.06, y: yy, w: 0.7, h: bh, fontSize: 10, bold: true, valign: "middle" });
    });
  };
  const table = (s, rows, o) => s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: {
      bold: i === 0 || (o.boldFirstCol && j === 0), fontSize: o.fontSize || 10.5, color: i === 0 ? C.background1 : C.text1,
      fill: { color: i === 0 ? C.text2 : C.background1 }, valign: "middle" } }))),
    { x: o.x, y: o.y, w: o.w, colW: o.colW, rowH: o.rowH || 0.36, border: { type: "solid", pt: 0.5, color: "E2D9EA" }, margin: [0.04, 0.08, 0.04, 0.08] });

  // ================================================================ 1. Cover
  section = "Overview";
  pres.addSection({ title: section });
  {
    const s = pres.addSlide({ masterName: "Cover", sectionTitle: section });
    T(s, "Group 2 · Capstone review", { x: 0.6, y: 0.6, w: 4.4, h: 0.3, fontSize: 12, color: C.background2 });
    T(s, "Personal Finance\nAdvisor", { x: 0.6, y: 1.05, w: 4.6, h: 1.2, fontSize: 32, bold: true, color: C.background1 });
    T(s, "How the Python version works: the models we use and the ideas behind them", { x: 0.6, y: 2.45, w: 4.3, h: 0.9, fontSize: 15, color: C.background2 });
    T(s, "Version 1.5 · October 2026", { x: 0.6, y: 4.75, w: 4.4, h: 0.3, fontSize: 11, color: C.background2 });
    s.addImage({ data: img("c_hero.png"), x: 5.45, y: 0.55, w: 4.0, h: 4.0 / (1150 / 1165), objectName: "report screenshot" });
    s.addNotes(`Hi everyone. Today we're walking you through the Python version of our finance advisor, version 1.5.

We'll keep it to three things: which AI models we use, the ideas we had to get right to make them reliable, and the finance logic that sits underneath. The screenshot on the right is a real report from our test run yesterday, for a made-up person called Meera who wants to buy a car.

We'll show you real output throughout, not mock-ups.`);
  }

  // ================================================================ 2. What the user gets
  {
    const s = slide("What the user sees", `Here's the experience from the user's side.

They sign in, then answer five short steps: who they are and their goal, income and expenses, their safety net, loans, and what they already own. The last question is about risk: if a hundred thousand rupees dropped to eighty thousand in a bad year, what would you do?

As soon as they submit, the report on the left appears, numbers and charts included. That takes about two hundredths of a second. The written explanation fills in roughly fourteen seconds later, while they're already reading.

At the bottom of the report there's a chat. We call the assistant Arth, from the Sanskrit word artha, wealth. It answers questions about the plan and can change the plan if the user confirms.`);
    shot(s, "c_hero.png", 0.5, 1.2, 3.85, 1150 / 1165, "report top");
    const steps = [["1", "Five short questions", "goal, income, safety net, loans, what you own, then one question about risk. Voice works too."],
      ["2", "Numbers in 0.02 seconds", "projection, risk plan, monthly plan in rupees, safety-net check, stocks or deposits"],
      ["3", "Explanation in about 14 seconds", "written by gpt-5-mini from those numbers, swapped in while you read"],
      ["4", "Questions to Arth", "rates, what-ifs, plan changes after you say yes"]];
    steps.forEach(([n, h, d], i) => {
      const y = 1.3 + i * 0.95;
      T(s, n, { x: 4.8, y, w: 0.4, h: 0.4, fontSize: 22, bold: true, color: C.accent1 });
      T(s, h, { x: 5.3, y: y + 0.02, w: 4.2, h: 0.3, fontSize: 13, bold: true });
      T(s, d, { x: 5.3, y: y + 0.33, w: 4.2, h: 0.5, fontSize: 10.5, color: C.accent6 });
    });
  }

  // ================================================================ 3. The rule
  {
    const s = slide("Our one rule: the model never produces a number", `If you remember one thing from today, make it this.

Every figure in a report, every rupee and every percentage, is computed by ordinary Python code that we unit-test. The language model only ever sees those numbers as finished facts. Its job is to explain them in plain English, to hold the conversation, and to turn what the user says into structured data, like "change my SIP to forty thousand".

Why so strict? Because models are good at language and unreliable at arithmetic. A finance tool that's wrong by a few thousand rupees is worse than no tool. So the prompt tells the model that every number it mentions must come from the facts, and where the model proposes something, like a list of stocks, the code checks it again.`);
    panel(s, 0.5, 1.25, 4.35, 3.75, C.background1, "code column");
    T(s, "Python computes", { x: 0.75, y: 1.42, w: 3.9, h: 0.35, fontSize: 15, bold: true, color: C.accent5 });
    T(s, bullets(["take-home pay from CTC, using the 2026-27 tax slabs", "debt totals and the order to pay loans off", "the risk plan and the target mix",
      "the goal projection and the monthly amount needed", "the monthly plan, rupee by rupee", "which NIFTY 50 stocks pass the risk rules", "the bank FD / RD plan"]),
      { x: 0.75, y: 1.9, w: 3.9, h: 2.95, fontSize: 11.5, paraSpaceAfter: 5 });
    panel(s, 5.15, 1.25, 4.35, 3.75, C.background1, "model column");
    T(s, "gpt-5-mini writes", { x: 5.4, y: 1.42, w: 3.9, h: 0.35, fontSize: 15, bold: true, color: C.accent1 });
    T(s, bullets(["the headline and summary of the report", "the reasons behind each priority action", "Arth's chat answers",
      "plan changes, as structured data for the code to apply", "deposit requests (amounts and a date) for the planner"]),
      { x: 5.4, y: 1.9, w: 3.9, h: 2.1, fontSize: 11.5, paraSpaceAfter: 5 });
    T(s, "From the prompt: \"Every number you mention must appear in the FACTS. Never recalculate, round differently or invent figures.\"",
      { x: 5.4, y: 4.05, w: 3.9, h: 0.8, fontSize: 10, italic: true, color: C.text2 });
  }

  // ================================================================ 4. Architecture
  {
    const s = slide("How the pieces fit together", `This is the whole system on one slide.

The app is a single FastAPI application written in Python. Inside it, the engine folder holds all the finance maths, the ai folder holds everything that talks to a model, and the report folder turns the results into a web page with charts drawn as SVG on the server.

Around it are four services. Postgres stores accounts, profiles, reports and chat history, and with the pgvector extension it also stores our knowledge base for search. A small market service serves five years of NIFTY 50 history. OpenAI provides the models. And two outside sources give us live data: SerpAPI for today's prices and news, and the World Bank for India's inflation rate.

Everything runs in Docker with one start script, and nothing listens beyond localhost.`);
    panel(s, 0.5, 1.3, 3.6, 3.6, C.background1, "app");
    T(s, "FastAPI app", { x: 0.7, y: 1.42, w: 3.2, h: 0.3, fontSize: 14, bold: true });
    [["engine/", "all the finance maths"], ["ai/", "chat, report text, search, guardrails, voice"], ["report/", "web page + SVG charts"],
      ["live/", "SerpAPI refresh, cost tracking"], ["tracing", "every step sent to Phoenix"]].forEach(([h, d], i) => {
      const y = 1.88 + i * 0.58;
      T(s, h, { x: 0.7, y, w: 1.05, h: 0.45, fontSize: 11, bold: true, fontFace: "Courier New", color: C.text2, valign: "middle" });
      T(s, d, { x: 1.75, y, w: 2.25, h: 0.45, fontSize: 10.5, valign: "middle" });
    });
    const svc = [["Postgres + pgvector", "accounts, profiles, reports, chat, 1,632 knowledge chunks"], ["Market service", "NIFTY 50 history to 26 Aug 2026"],
      ["OpenAI", "gpt-5-mini, embeddings, voice"], ["SerpAPI + World Bank", "today's prices and news; India inflation"], ["Phoenix", "traces, tokens and cost per step"]];
    svc.forEach(([h, d], i) => {
      const y = 1.3 + i * 0.73;
      panel(s, 5.0, y, 4.5, 0.6, C.background1, `service ${i + 1}`);
      T(s, h, { x: 5.15, y: y + 0.06, w: 4.2, h: 0.25, fontSize: 11.5, bold: true });
      T(s, d, { x: 5.15, y: y + 0.32, w: 4.2, h: 0.24, fontSize: 9.5, color: C.accent6 });
      line(s, 4.12, y + 0.3, 4.98, y + 0.3);
    });
  }

  // ================================================================ 5. Models
  section = "Models and AI ideas";
  pres.addSection({ title: section });
  {
    const s = slide("The models we use, and what each one costs", `Five models, but really one does most of the work.

gpt-5-mini writes the report and answers the chat. We run it with reasoning effort set to low, which keeps answers quick. Its pricing is what drives our costs: about forty-five paise per plan and eleven paise per chat question.

The embedding model turns our 830 knowledge documents, and every question, into vectors so we can search by meaning. Embedding the whole knowledge base once cost us about thirty-five paise.

Voice is optional. By default we use the browser's own speech recognition and voice, which is free. If someone wants a more natural voice, the two OpenAI voice models take over, and we cap how much each user can use per day.

One more thing worth mentioning: we also built a fake OpenAI server for testing, so most of our test runs cost nothing.`);
    table(s, [["Model", "What we use it for", "Price"],
      ["gpt-5-mini", "report text, Arth's answers, turning requests into structured data", "$0.25 / 1M tokens in, $2.00 out"],
      ["text-embedding-3-small", "searching our 830 knowledge documents by meaning", "$0.02 / 1M tokens"],
      ["gpt-4o-mini-transcribe", "speech to text, only if the browser can't do it", "$0.003 per minute"],
      ["gpt-4o-mini-tts (voice \"sage\")", "the optional natural read-aloud voice", "about $0.015 per minute"],
      ["Browser speech (Web Speech API)", "default voice in and out", "free"]],
      { x: 0.5, y: 1.25, w: 9, colW: [2.6, 4.2, 2.2], rowH: 0.42, boldFirstCol: true });
    const stats = [["₹0.45", "per plan"], ["₹0.11", "per chat question"], ["₹0", "for a blocked question"]];
    stats.forEach(([n, l], i) => {
      T(s, n, { x: 0.5 + i * 2.6, y: 4.2, w: 1.2, h: 0.55, fontSize: 24, bold: true, color: C.accent1, valign: "middle" });
      T(s, l, { x: 1.7 + i * 2.6, y: 4.2, w: 1.35, h: 0.55, fontSize: 11, color: C.accent6, valign: "middle" });
    });
  }

  // ================================================================ 6. Two stages
  {
    const s = slide("A plan is built in two stages, so nobody waits for the AI", `Our first version, in n8n, took one to three minutes to show anything, because four AI agents ran one after another. This was the mentor's first piece of feedback, so we changed the order.

Stage one is pure computation: debt, risk plan, projection, monthly plan and, for low-risk plans, the deposit plan. That's done in about twenty milliseconds and the page opens straight away.

Stage two runs in the background. One search pulls relevant passages from the knowledge base, then two model calls run at the same time: one writes the story, one writes the details. You can see on the chart that each call takes twelve or thirteen seconds, but because they overlap, the text is ready in about fourteen.`);
    T(s, "Stage 1 · computed", { x: 0.5, y: 1.25, w: 4, h: 0.3, fontSize: 13, bold: true, color: C.accent5 });
    T(s, "debt, risk plan, projection, monthly plan, deposit plan, stock screen. The page opens with everything except the written text.",
      { x: 0.5, y: 1.58, w: 3.9, h: 0.9, fontSize: 11 });
    T(s, "Stage 2 · written in the background", { x: 0.5, y: 2.75, w: 4, h: 0.3, fontSize: 13, bold: true, color: C.accent1 });
    T(s, "one knowledge search, then two gpt-5-mini calls at the same time. The text replaces the computed placeholder when it's ready.",
      { x: 0.5, y: 3.08, w: 3.9, h: 0.9, fontSize: 11 });
    caption(s, "n8n v3.2 for comparison: 4 agents in a row, 1-3 minutes before anything showed.", 0.5, 4.3, 4.2);
    panel(s, 4.8, 1.25, 4.7, 3.7, C.background1, "timing");
    T(s, "One measured plan, in seconds", { x: 5.0, y: 1.38, w: 4.3, h: 0.3, fontSize: 11.5, bold: true });
    hbars(s, { x: 5.0, y: 1.85, w: 4.35, h: 2.9, max: 14, fmt: (v) => (v < 1 ? v.toFixed(2) : v.toFixed(1)) + " s", items: [
      ["numbers + charts", 0.02, C.accent5], ["knowledge search", 0.5, C.accent4], ["story call", 12.3, C.accent1],
      ["details call", 13.1, C.accent1], ["text ready", 13.7, C.accent2]] });
  }

  // ================================================================ 7. Structured outputs
  {
    const s = slide("Structured outputs: the model fills in a form, not free text", `A big part of making the model dependable is never asking it for free text where the code needs to act.

OpenAI's structured outputs let us give the model a strict JSON schema, and the answer is guaranteed to match it. This is the actual shape of a chat reply. In one call the model tells us whether the question is on topic, writes the reply, suggests follow-ups, and fills in any plan change or deposit request.

The code then acts on those fields. For example, if plan_changes says the monthly SIP should be forty thousand, the code applies that, re-runs the plan and shows the user a preview first. The model never edits the plan directly.`);
    panel(s, 0.5, 1.25, 4.9, 2.95, C.background1, "json sample");
    caption(s, "The shape of a real chat reply, trimmed. The full schema has a few more fields.", 0.5, 4.32, 4.9);
    T(s, `{
  "on_topic": true,
  "reply": "Sure, here's what changes…",
  "suggestions": ["What changed in my plan?"],
  "plan_changes": {"monthly_sip_total": 40000},
  "needs_live_data": false,
  "deposit_request": {
    "wanted": false, … }
}`, { x: 0.7, y: 1.45, w: 4.6, h: 2.6, fontFace: "Courier New", fontSize: 11, color: C.text2 });
    T(s, "Why it matters", { x: 5.75, y: 1.3, w: 3.7, h: 0.3, fontSize: 14, bold: true });
    T(s, bullets(["One call returns everything, so one chat question costs about 11 paise", "Code reads plan_changes and applies them, after the user says yes",
      "If the schema can't be met, the call fails loudly instead of guessing", "The same idea writes the report: a schema for headline, summary, actions, reasons"]),
      { x: 5.75, y: 1.75, w: 3.75, h: 3.1, fontSize: 11.5, paraSpaceAfter: 7 });
  }

  // ================================================================ 8. RAG
  {
    const s = slide("RAG: answers come from documents we chose", `RAG stands for retrieval-augmented generation. In plain terms: before the model answers, we look up the most relevant passages from our own documents and hand them over.

We wrote and collected 830 short documents: how each investment works, tax rules, how to read risk measures, the NIFTY 50 methodology. They're split into 1,632 chunks, and each chunk is turned into a list of 1,536 numbers by the embedding model. Those vectors live in Postgres.

When a question comes in, it's turned into a vector too, and Postgres finds the closest chunks. The model gets them numbered and cites them, so a reader can see where a statement came from.

One deliberate decision: we don't use RAG for exact figures. A stock's five-year growth comes straight from the market service, because searching text for a number is asking for trouble.`);
    const steps = ["830 documents", "1,632 chunks", "vectors in Postgres", "closest passages", "answer with [1] [2]"];
    steps.forEach((t, i) => {
      const x = 0.5 + i * 1.84;
      panel(s, x, 1.35, 1.6, 0.75, C.background1, `rag step ${i + 1}`);
      T(s, t, { x: x + 0.08, y: 1.35, w: 1.44, h: 0.75, fontSize: 11.5, bold: true, align: "center", valign: "middle" });
      if (i < 4) line(s, x + 1.62, 1.72, x + 1.82, 1.72);
    });
    T(s, "Good for", { x: 0.5, y: 2.5, w: 4.2, h: 0.3, fontSize: 13, bold: true, color: C.accent5 });
    T(s, bullets(["explaining a concept, like an ELSS lock-in or a liquid fund", "tax rules and how the plan follows them", "how to read a drawdown or a CAGR"]),
      { x: 0.5, y: 2.85, w: 4.2, h: 1.6, fontSize: 11.5, paraSpaceAfter: 5 });
    T(s, "Not used for", { x: 5.3, y: 2.5, w: 4.2, h: 0.3, fontSize: 13, bold: true, color: C.accent2 });
    T(s, bullets(["a stock's five-year growth, swing or worst fall (market service)", "bank deposit rates (the rate table)", "anything about the user (their saved profile)"]),
      { x: 5.3, y: 2.85, w: 4.2, h: 1.6, fontSize: 11.5, paraSpaceAfter: 5 });
  }

  // ================================================================ 9. Guardrails
  {
    const s = slide("Most safety checks don't need a model at all", `In the n8n version, every chat message went through a separate guardrail model on the way in and again on the way out. That cost time and money on every message.

In Python we do most of it with plain rules. Phrases like "ignore your previous instructions" are caught by pattern matching. Indian ID numbers, like PAN, Aadhaar and passport numbers, are recognised by their format, and card numbers are double-checked with the Luhn checksum so a random long number isn't flagged. That takes about a millisecond and costs nothing.

Whether a question is on topic is decided by the chat model itself, inside the same call that answers it, so that's free too. And before anything is shown, stored or traced, ID numbers are masked.

The quote at the bottom is exactly what a user sees if they paste their PAN.`);
    table(s, [["Check", "How", "Cost"],
      ["Prompt injection", "pattern rules: \"ignore previous instructions\", \"system prompt\", \"developer mode\"…", "₹0, ~1 ms"],
      ["ID numbers", "PAN, Aadhaar, phone, passport, IFSC formats; cards confirmed with the Luhn checksum", "₹0, ~1 ms"],
      ["Off-topic", "an on_topic flag in the chat's own answer", "no extra call"],
      ["Output", "ID numbers masked before showing, saving or tracing", "₹0"]],
      { x: 0.5, y: 1.25, w: 9, colW: [1.8, 5.6, 1.6], rowH: 0.44, boldFirstCol: true });
    panel(s, 0.5, 3.7, 9, 1.2, "F1E9F8", "refusal quote");
    T(s, "What the user sees", { x: 0.7, y: 3.82, w: 3, h: 0.25, fontSize: 10, bold: true, color: C.text2 });
    T(s, "\"For your safety, please don't share card numbers, PAN, Aadhaar, passport or bank account details here - I never need them.\"",
      { x: 0.7, y: 4.12, w: 8.6, h: 0.65, fontSize: 13, italic: true });
  }

  // ================================================================ 10. Arth
  {
    const s = slide("Arth, the chat, answering real questions", `These are two real answers from our test run on the first of October, with the actual gpt-5-mini model, lightly trimmed for space.

In the first one, the question is about SBI's FD rates. That question used to go to a paid web search. Now our router sees it's about bank deposits and answers from the team's rate table, which is free and gives the date of the rates.

The second one is the more interesting case. The user gives a lump sum, a monthly amount and a goal. The model doesn't do the maths. It fills in a deposit request, our planner computes the FD and RD sequence, and a second, short call explains the result.

The router has five routes in total: local knowledge, live web data, the stock watchlist, bank deposits, and "let the model decide" when the rules can't tell. And any plan change is shown as a preview and only applied when the user says yes.`);
    const bubble = (who, text, x, y, w, h, user) => {
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: user ? C.text2 : C.background1 },
        line: { color: user ? C.text2 : "D8CFE3", width: 0.75 } });
      T(s, who, { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.2, fontSize: 8.5, bold: true, color: user ? "E9DDF6" : C.accent1 });
      T(s, text, { x: x + 0.15, y: y + 0.3, w: w - 0.3, h: h - 0.38, fontSize: 10, color: user ? C.background1 : C.text1 });
    };
    bubble("User", "What are the best FD rates at SBI?", 2.3, 1.2, 3.0, 0.62, true);
    bubble("Arth", "You asked for SBI FD rates. Here they are (card rates as of 2026-09): 7-45 days: 3.05% general, 3.55% senior · 46-179 days: 4.90% / 5.40% · 180-210 days: 5.65% / 6.15% …",
      0.5, 1.95, 4.8, 1.0, false);
    bubble("User", "I have 3L now and can put 10k a month in RD. I need 8L by 2030.", 1.6, 3.1, 3.7, 0.62, true);
    bubble("Arth", "Got it. With ₹3,00,000 now and ₹10,000 a month, here's what the deposit planner found (as of 2026-09): Axis Bank FD, 30 months at 7.1% → ₹3,57,711, then Kotak 1-2 years at 7.1% → ₹3,83,793 …",
      0.5, 3.85, 4.8, 1.1, false);
    T(s, "How Arth decides where to look", { x: 5.75, y: 1.2, w: 3.75, h: 0.3, fontSize: 13, bold: true });
    [["local", "concepts and your own plan"], ["live", "today's prices, NIFTY, repo rate, news"], ["picks", "stock watchlist with today's prices"],
      ["deposits", "FD and RD rates and plans (new)"], ["model decides", "when the rules can't tell"]].forEach(([r, d], i) => {
      const y = 1.62 + i * 0.5;
      T(s, r, { x: 5.75, y, w: 1.25, h: 0.36, fontSize: 10.5, bold: true, fontFace: "Courier New", color: i === 3 ? C.accent2 : C.text2, valign: "middle" });
      T(s, d, { x: 7.0, y, w: 2.5, h: 0.36, fontSize: 10.5, valign: "middle" });
    });
    T(s, "Plan changes are previewed (\"I'll change: SIP ₹25K → ₹40K\") and only applied after the user says yes.",
      { x: 5.75, y: 4.25, w: 3.75, h: 0.7, fontSize: 10.5, italic: true, color: C.accent6 });
    caption(s, "Real replies from the test run on 1 Oct 2026, trimmed.", 0.5, 5.02, 4.8);
  }

  // ================================================================ 11. Risk plan
  section = "Finance logic";
  pres.addSection({ title: section });
  {
    const s = slide("Risk: what you choose vs what your goal can carry", `Now the finance side, starting with risk, because almost everything else depends on it.

The user picks Low, Medium or High. Each level maps to a target mix of equity, fixed income, gold and cash. The expected return for the projection comes from blending long-run returns for each class: eleven percent for equity, seven for fixed income, eight for gold and four for cash.

Two rules can override the user's choice. First, time: money needed within three years shouldn't be in shares at all, so the plan drops to Low. Between three and five years, Medium is the most we allow. Second, direct stocks need a safety net first: a goal at least five years away, three months of emergency fund, health insurance, and no loan above twelve percent.

When we lower someone's risk, the report says why in plain words.`);
    table(s, [["", "Low", "Medium", "High"],
      ["Equity / fixed income / gold / cash", "15 / 70 / 10 / 5", "50 / 35 / 10 / 5", "70 / 20 / 7 / 3"],
      ["Direct stocks, share of goal money", "none", "up to 10%", "up to 25%"],
      ["Expected return used in the projection", "7.55%", "8.95%", "9.78%"]],
      { x: 0.5, y: 1.25, w: 9, colW: [3.3, 1.9, 1.9, 1.9], rowH: 0.42, boldFirstCol: true });
    T(s, "The goal date caps the risk", { x: 0.5, y: 3.15, w: 4.2, h: 0.3, fontSize: 13, bold: true });
    T(s, "Under 3 years: Low, with no shares at all. 3 to 5 years: Medium at most. The report explains any change in one sentence.",
      { x: 0.5, y: 3.5, w: 4.2, h: 1.2, fontSize: 11.5 });
    T(s, "Stocks need a safety net first", { x: 5.3, y: 3.15, w: 4.2, h: 0.3, fontSize: 13, bold: true });
    T(s, "Goal 5+ years away, 3+ months of emergency fund, health cover, no loan above 12%. Otherwise the report lists exactly what to fix.",
      { x: 5.3, y: 3.5, w: 4.2, h: 1.2, fontSize: 11.5 });
  }

  // ================================================================ 12. Projection + monthly plan
  {
    const s = slide("From the projection to rupees per instrument", `The projection is the standard future-value formula. Today's savings grow at the monthly rate, and each month's contribution grows from the month it goes in. Turn the same formula around and you get the monthly amount needed to hit the target.

The verdict is simple: on track if the projection reaches the target, a small gap if it's within fifteen percent, otherwise a large gap.

Then the monthly plan, which is what people actually act on. The emergency fund is topped up first, aiming for six months of expenses within about a year, but never more than forty percent of the spare money. The rest is split by the target mix and rounded to the nearest hundred rupees. In Meera's case, on the right, five thousand of her seventy-two hundred goes to fixed income, and the planner has already turned that into a specific bank RD.

Take-home pay, by the way, is estimated from the CTC using this year's new tax regime, including the rebate that makes income up to twelve lakh tax-free.`);
    panel(s, 0.5, 1.25, 4.3, 1.75, C.background1, "formula");
    T(s, `FV = savings × (1+r)^n
     + monthly × ((1+r)^n − 1) / r

r = expected return ÷ 12, n = months`, { x: 0.7, y: 1.4, w: 4.0, h: 1.5, fontFace: "Courier New", fontSize: 12, color: C.text2 });
    T(s, bullets(["On track, small gap (within 15%) or large gap", "Emergency fund first: 6 months in about a year, at most 40% of spare cash",
      "Take-home from CTC: 2026-27 slabs, ₹12L rebate, 4% cess"]), { x: 0.5, y: 3.2, w: 4.3, h: 1.7, fontSize: 11, paraSpaceAfter: 6 });
    shot(s, "c_monthly.png", 5.15, 1.3, 4.35, 1150 / 330, "monthly plan");
    caption(s, "Meera's monthly plan, from the sample report. Fixed income already names the bank.", 5.15, 2.65, 4.35);
    T(s, "Meera: CTC ₹12L, car goal ₹8L in 3.5 years, Low risk.\nProjected ₹8,67,429 against ₹8,00,000, so she's on track.",
      { x: 5.15, y: 3.2, w: 4.35, h: 0.8, fontSize: 11 });
  }

  // ================================================================ 13. Stocks
  {
    const s = slide("Stocks only appear when the plan can take the risk", `Direct stocks are where a careless finance tool can do real damage, so this part is fully rule-based.

From five years of NIFTY 50 history we use three measures: CAGR, the steady yearly growth; volatility, how much the price usually swings in a year; and maximum drawdown, the worst fall from a peak.

A stock passes if its worst fall and its swing are within the plan's limits and it grew at least half as much as it swings. Then we rank by growth per unit of swing and allow at most two per sector.

A real example from testing: Hindalco was removed because its worst fall was almost fifty percent, past the thirty-five percent limit. Bajaj Finance went because eight percent growth wasn't enough for twenty-eight percent swings.

Meera is on a Low-risk plan, so she doesn't get stocks. She gets a watchlist under the same rules, for when she's ready.`);
    shot(s, "c_watch.png", 0.5, 1.25, 3.9, 1150 / 950, "watchlist");
    T(s, "The rules", { x: 4.85, y: 1.25, w: 4.6, h: 0.3, fontSize: 13, bold: true });
    T(s, bullets(["Worst fall within the limit: 35%, or 45% for High risk with 10+ years", "Yearly swing within 30% (Medium) or 38% (High)",
      "Growth at least half the swing", "Best growth per unit of swing first, max 2 per sector, up to 5 names"]),
      { x: 4.85, y: 1.62, w: 4.65, h: 1.75, fontSize: 11, paraSpaceAfter: 5 });
    panel(s, 4.85, 3.5, 4.65, 1.05, "F1E9F8", "removed examples");
    T(s, "Removed during testing", { x: 5.05, y: 3.6, w: 4.3, h: 0.25, fontSize: 10.5, bold: true, color: C.text2 });
    T(s, [{ text: "HINDALCO: ", options: { bold: true } }, { text: "worst fall ▼49.9%, past the 35% limit", options: { breakLine: true } },
      { text: "BAJFINANCE: ", options: { bold: true } }, { text: "8.2% growth for 28.3% swings" }], { x: 5.05, y: 3.92, w: 4.3, h: 0.9, fontSize: 11 });
  }

  // ================================================================ 14. Deposits
  {
    const s = slide("New in v1.5: the team's bank deposit planner", `This is the newest piece, and it came from a teammate's project, a LangGraph agent that plans fixed and recurring deposits.

We kept the core idea. For a lump sum, it searches through sequences of fixed deposits, each renewed as many times as fits before the goal date. For a monthly amount, it finds the best mix of recurring deposits month by month. The rates come from 211 entries across ten banks, read from the team's bank documents.

While porting it we found two maths bugs. The recurring deposit formula overstated returns by about eighteen times: five thousand a month for a year came out as eleven lakh instead of about sixty-two thousand. And inflation was only applied for one deposit term instead of the whole period. Both are fixed, and we checked the old and new code side by side.

In the app, any Low-risk plan now gets this section automatically, as you can see in Meera's report.`);
    shot(s, "c_deposits.png", 0.5, 1.25, 4.6, 1150 / 670, "deposit section");
    caption(s, "Meera's report: ₹5,000 a month into an HDFC 3-year RD, last 5 months kept as cash.", 0.5, 4.0, 4.6);
    T(s, "How it works", { x: 5.5, y: 1.25, w: 4, h: 0.3, fontSize: 13, bold: true });
    T(s, bullets(["211 rates from 10 banks, read from the team's documents", "Lump sum: search through FD sequences up to the goal date",
      "Monthly: best mix of back-to-back RDs, month by month", "Inflation from the World Bank (2.4% for 2025) when not given"]),
      { x: 5.5, y: 1.6, w: 4.0, h: 1.75, fontSize: 11, paraSpaceAfter: 5 });
    panel(s, 5.5, 3.45, 4.0, 1.05, "FFF4E8", "bugs fixed");
    T(s, "Two bugs we fixed in the original", { x: 5.7, y: 3.55, w: 3.7, h: 0.25, fontSize: 10.5, bold: true, color: C.accent3 });
    T(s, [{ text: "RD maturity, ₹5,000/month, 1 year: ", options: {} }, { text: "₹11,03,576 → ₹62,311", options: { bold: true, breakLine: true } },
      { text: "2-year FD × 5, at 5% inflation: ", options: {} }, { text: "₹1,81,963 → ₹1,22,881", options: { bold: true } }],
      { x: 5.7, y: 3.85, w: 3.7, h: 0.6, fontSize: 10.5 });
  }

  // ================================================================ 15. Tracing and cost
  section = "Quality";
  pres.addSection({ title: section });
  {
    const s = slide("We can see every step, and what it cost", `When something goes wrong in an AI app, the first question is always "which step?". So the app traces itself.

Every plan and every chat question becomes a trace in Phoenix, using the OpenTelemetry standard. On the left is the shape of one plan: the computation, the deposit planner, the stock screen, and then the background writing with its search and two model calls. For each model call we can see the prompt, the answer, the tokens and the cost.

Privacy was part of the design: users show up as a hashed ID, ID numbers are masked, and we can switch off recording the content entirely.

On the right are the costs we measured. A thousand typical users a month would come to roughly two thousand one hundred rupees.`);
    panel(s, 0.5, 1.25, 4.4, 3.7, C.background1, "trace");
    T(s, "One plan in Phoenix", { x: 0.7, y: 1.37, w: 4, h: 0.28, fontSize: 11.5, bold: true });
    T(s, `Build plan
├ Compute numbers
├ Bank deposit planner
├ Screen NIFTY 50
└ Write explanation
  ├ Knowledge-base search
  │ └ embeddings
  ├ report_story   (gpt-5-mini)
  └ report_details (gpt-5-mini)`, { x: 0.7, y: 1.75, w: 4.1, h: 2.45, fontFace: "Courier New", fontSize: 11, color: C.text2 });
    T(s, "Each step: timing · model calls: prompt, answer, tokens, cost", { x: 0.7, y: 4.3, w: 4.0, h: 0.5, fontSize: 9.5, color: C.accent6 });
    panel(s, 5.15, 1.25, 4.35, 3.7, C.background1, "costs");
    T(s, "Measured AI cost per action", { x: 5.35, y: 1.37, w: 4, h: 0.28, fontSize: 11.5, bold: true });
    hbars(s, { x: 5.35, y: 1.85, w: 4.0, h: 2.0, max: 0.56, labW: 1.45, fmt: (v) => "₹" + v.toFixed(2), items: [
      ["one plan", 0.45, C.accent1], ["chat question", 0.11, C.accent4], ["what-if", 0.56, C.accent2], ["blocked question", 0, C.accent6]] });
    T(s, "1,000 typical users a month ≈ ₹2,100 ($24)", { x: 5.35, y: 4.15, w: 4.0, h: 0.5, fontSize: 11.5, bold: true, color: C.text2 });
  }

  // ================================================================ 16. Testing
  {
    const s = slide("How we tested it: 30 sample plans, all checks passed", `We didn't want to rely on clicking through the app, so we automated the testing.

There are fifty-one unit tests for the finance maths, parsing, guardrails and the deposit planner. There's a parity test that runs the Python planner and the JavaScript version from n8n on the same inputs and insists on identical results. That test is how we found the rounding bug we'll mention in a moment.

The most useful one is the sample run. We wrote ten made-up people, from a twenty-five-year-old saving for travel to a sixty-one-year-old retiree, and ran each of them at Low, Medium and High risk. That's thirty real plans through the real pipeline, each checked against the rules and printed to PDF. All thirty passed, and the whole run cost about fifteen rupees.

The chart shows the risk rules doing their job. Two of the people who chose High were planned at Low, because their goals were less than three years away.`);
    [["51", "unit tests"], ["1", "parity test, Python vs n8n"], ["30", "sample plans, all passed"], ["₹14.57", "for the whole sample run"]].forEach(([n, l], i) => {
      const y = 1.3 + i * 0.9;
      T(s, n, { x: 0.5, y, w: 1.45, h: 0.6, fontSize: 26, bold: true, color: C.accent1, valign: "middle" });
      T(s, l, { x: 2.0, y, w: 2.3, h: 0.6, fontSize: 11.5, valign: "middle" });
    });
    panel(s, 4.6, 1.25, 4.9, 3.7, C.background1, "sample run");
    T(s, "Risk chosen vs risk planned (10 people each)", { x: 4.8, y: 1.37, w: 4.5, h: 0.28, fontSize: 11.5, bold: true });
    const base = 4.15, plotH = 2.2, colW = 1.5, bw = 0.7, cats = ["Chose Low", "Chose Medium", "Chose High"];
    const series = [["Planned Low", C.accent5, [10, 2, 2]], ["Planned Medium", C.accent1, [0, 8, 1]], ["Planned High", C.accent2, [0, 0, 7]]];
    s.addShape(pres.shapes.LINE, { x: 4.85, y: base, w: 4.5, h: 0, line: { color: "D8CFE3", width: 1 } });
    cats.forEach((c, i) => {
      const cx = 4.85 + i * colW + (colW - bw) / 2;
      let acc = 0;
      series.forEach(([, col, vals]) => {
        const v = vals[i]; if (!v) return;
        const bh = plotH * v / 10; acc += bh;
        s.addShape(pres.shapes.RECTANGLE, { x: cx, y: base - acc, w: bw, h: bh, fill: { color: col }, line: { color: C.background1, width: 0.75 } });
        T(s, String(v), { x: cx, y: base - acc, w: bw, h: bh, fontSize: 10, bold: true, color: C.background1, align: "center", valign: "middle" });
      });
      T(s, c, { x: 4.85 + i * colW, y: base + 0.06, w: colW, h: 0.25, fontSize: 9.5, align: "center" });
    });
    series.forEach(([n, col], j) => {
      const lx = 4.85 + j * 1.5;
      s.addShape(pres.shapes.RECTANGLE, { x: lx, y: 4.62, w: 0.13, h: 0.13, fill: { color: col }, line: { color: col } });
      T(s, n, { x: lx + 0.2, y: 4.57, w: 1.25, h: 0.22, fontSize: 9, valign: "middle" });
    });
  }

  // ================================================================ 17. What went wrong
  {
    const s = slide("Things that went wrong, and what we learned", `We want to be honest about the problems, because each one taught us something.

The RD formula you've already heard about. The lesson is to test money calculations against a number you already know, like a bank's own calculator.

The rounding one was subtle. Python rounds 730.5 down to 730, because it rounds halves to the nearest even number, while JavaScript rounds it up to 731. One day's difference made the two planners pick different deposits. We'd never have caught it without comparing the two.

Searching for "State Bank of India" found nothing, while "SBI" worked. Real users type full names, so test with them.

Early on, Low-risk plans didn't actually use the deposit planner, because we'd left it to the model to decide when to call it. Important steps should be in code, not left to the model's choice.

And one of our shared zip files included an API key, which then had to be revoked. Shared bundles never include the secrets file now.`);
    const L = [["The RD formula overstated returns 18×", "Test money maths against a number you already know."],
      ["Python and JavaScript rounded 730.5 differently", "Run two versions against each other; it's the only way we caught it."],
      ["\"State Bank of India\" found no rates, \"SBI\" did", "Test with the words real users type."],
      ["Low-risk plans skipped the deposit planner", "Don't leave important steps to the model's choice."],
      ["An API key leaked in a shared zip", "Secrets stay in .env, and .env never leaves the machine."]];
    L.forEach(([what, lesson], i) => {
      const y = 1.25 + i * 0.75;
      T(s, what, { x: 0.5, y, w: 4.5, h: 0.6, fontSize: 12.5, bold: true, valign: "middle" });
      T(s, lesson, { x: 5.2, y, w: 4.3, h: 0.6, fontSize: 12, color: C.text2, valign: "middle" });
      if (i < L.length - 1) s.addShape(pres.shapes.LINE, { x: 0.5, y: y + 0.68, w: 9, h: 0, line: { color: "E2D9EA", width: 0.75 } });
    });
  }

  // ================================================================ 18. Next
  {
    const s = pres.addSlide({ masterName: "Cover", sectionTitle: section });
    T(s, "What we'd do next", { x: 0.6, y: 0.6, w: 8.8, h: 0.6, fontSize: 28, bold: true, color: C.background1 });
    T(s, bullets(["Refresh bank rates weekly instead of reading them from documents", "Add a senior citizen with a shortfall to the sample run, so senior rates get tested",
      "Stop field names like \"term_cover\" leaking into the report text", "Add email verification before anyone outside the team uses it"]),
      { x: 0.6, y: 1.45, w: 8.6, h: 2.2, fontSize: 15, color: C.background2, paraSpaceAfter: 10 });
    T(s, "Thank you. Questions?", { x: 0.6, y: 4.0, w: 8.8, h: 0.6, fontSize: 24, bold: true, color: C.background1 });
    T(s, "Group 2 · Personal Finance Advisor, Python v1.5 · educational information, not licensed financial advice", { x: 0.6, y: 4.9, w: 8.8, h: 0.3, fontSize: 9.5, color: C.background2 });
    s.addNotes(`To wrap up, four things we'd like to do next.

Bank rates should be refreshed weekly rather than read from documents. The sample run needs a senior citizen who is short of their goal, so the senior deposit rates actually get exercised. We noticed in the sample reports that the model sometimes writes internal field names like "term_cover" into the text, which we want to stop. And before anyone outside the team uses it, sign-up needs email verification.

That's everything from us. Thank you, and we're happy to take questions.`);
  }

  await pres.writeFile({ fileName: OUT });
  if (APPLY) await require(APPLY).applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
