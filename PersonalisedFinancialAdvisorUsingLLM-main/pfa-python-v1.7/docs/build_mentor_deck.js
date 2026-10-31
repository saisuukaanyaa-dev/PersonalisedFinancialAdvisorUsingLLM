// Mentor deck for the PFA Python edition v1.1 - palette taken from the reference page:
// lavender ground, deep purple panels, bright violet highlight letters, black pill buttons,
// grey word-cloud text, orange -> pink -> purple gradient artwork.
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fa = require("react-icons/fa");

const C = {
  bg: "F8F3FA", purple: "6B0FA8", violet: "9B19F5", ink: "111111", body: "3A3440", muted: "7A7383",
  grey: "A8A2AE", white: "FFFFFF", lav: "EFE4F6", orange: "F7931E", pink: "E8307A", plum: "7B4FBF", line: "D9CCE3",
};
const FONT = "Arial";

async function icon(Comp, color, px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: px }));
  const buf = await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function infinity(w = 1200, h = 620) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 600 310">
    <defs>
      <linearGradient id="g" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0" stop-color="#F7B733"/><stop offset="0.25" stop-color="#F4652C"/>
        <stop offset="0.55" stop-color="#E8307A"/><stop offset="0.8" stop-color="#B43FB0"/><stop offset="1" stop-color="#6A5ACD"/>
      </linearGradient>
      <filter id="s" x="-20%" y="-20%" width="140%" height="160%"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#6B0FA8" flood-opacity="0.18"/></filter>
    </defs>
    <path filter="url(#s)" d="M300 155 C 250 80, 200 55, 150 55 C 85 55, 45 100, 45 155 C 45 210, 85 255, 150 255 C 200 255, 250 230, 300 155 C 350 80, 400 55, 450 55 C 515 55, 555 100, 555 155 C 555 210, 515 255, 450 255 C 400 255, 350 230, 300 155 Z"
      fill="none" stroke="url(#g)" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

// ---------- helpers ----------
const T = (slide, text, o) => slide.addText(text, { fontFace: FONT, color: C.body, isTextBox: true, margin: 0, valign: "top", ...o });

// Title with violet highlight letters, like "Age of Intelligence": parts = [["Why it is ",0],["F",1],["aster",0]]
function title(slide, parts, o = {}) {
  T(slide, parts.map(([t, hi]) => ({ text: t, options: { color: hi ? C.violet : C.ink, bold: true } })),
    { x: 0.5, y: 0.32, w: 9, h: 0.7, fontSize: 30, valign: "middle", ...o });
}
const eyebrow = (slide, text, o = {}) => T(slide, text.toUpperCase(), { x: 0.5, y: 0.14, w: 9, h: 0.25, fontSize: 9.5, bold: true, color: C.purple, charSpacing: 2, ...o });

function pill(slide, text, x, y, w, o = {}) {
  slide.addShape("roundRect", { x, y, w, h: 0.34, rectRadius: 0.17, fill: { color: o.fill || C.ink }, line: { color: o.line || o.fill || C.ink, width: 1 } });
  T(slide, text, { x, y, w, h: 0.34, fontSize: o.size || 11, bold: true, color: o.color || C.white, align: "center", valign: "middle" });
}
function card(slide, x, y, w, h, fill = C.white) {
  slide.addShape("roundRect", { x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: fill === C.white ? C.line : fill, width: 0.75 },
    shadow: fill === C.white ? { type: "outer", color: "6B0FA8", opacity: 0.10, blur: 8, offset: 2, angle: 90 } : undefined });
}
function iconDot(slide, data, x, y, d = 0.5, fill = C.purple) {
  slide.addShape("ellipse", { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
  slide.addImage({ data, x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
}
const arrow = (slide, x1, y1, x2, y2, color = C.grey) =>
  slide.addShape("line", { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipV: y2 < y1, line: { color, width: 1.5, endArrowType: "triangle" } });
const footer = (slide, n) => T(slide, `Personal Finance Advisor · Python edition v1.1   ${n}`, { x: 5.5, y: 5.3, w: 4.0, h: 0.2, fontSize: 8, color: C.grey, align: "right" });

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";   // 10 x 5.625 in
  pres.title = "Personal Finance Advisor - Python edition v1.1";
  pres.author = "Group 2";

  const I = {};
  const white = [["bolt", fa.FaBolt], ["feather", fa.FaFeatherAlt], ["chart", fa.FaChartLine], ["google", fa.FaGoogle], ["chat", fa.FaComments],
    ["rupee", fa.FaRupeeSign], ["eye", fa.FaEye], ["db", fa.FaDatabase], ["robot", fa.FaRobot], ["shield", fa.FaShieldAlt], ["lock", fa.FaLock],
    ["user", fa.FaUserSecret], ["server", fa.FaServer], ["globe", fa.FaGlobe], ["cogs", fa.FaCogs], ["search", fa.FaSearch], ["check", fa.FaCheckCircle],
    ["key", fa.FaKey], ["mask", fa.FaMask], ["list", fa.FaListOl], ["flask", fa.FaFlask], ["play", fa.FaPlay], ["file", fa.FaFileAlt], ["layer", fa.FaLayerGroup]];
  for (const [k, comp] of white) I[k] = await icon(comp, C.white);
  const INF = await infinity();

  // ================================================================ 1. Title
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    T(s, "GROUP 2 CAPSTONE  ·  MENTOR REVIEW", { x: 0.5, y: 0.45, w: 5, h: 0.25, fontSize: 10, bold: true, color: C.purple, charSpacing: 2 });
    T(s, [{ text: "Personal ", options: { color: C.ink } }, { text: "F", options: { color: C.violet } }, { text: "inance", options: { color: C.ink } }],
      { x: 0.5, y: 0.8, w: 5, h: 0.6, fontSize: 36, bold: true });
    T(s, [{ text: "A", options: { color: C.violet } }, { text: "dvisor ", options: { color: C.ink } }, { text: "in ", options: { color: C.ink } },
          { text: "P", options: { color: C.violet } }, { text: "ython", options: { color: C.ink } }],
      { x: 0.5, y: 1.38, w: 5, h: 0.6, fontSize: 36, bold: true });
    T(s, "From the n8n v3.2 workflow to a fast, modular web app - with sign-in, chat, cost tracking and observability.",
      { x: 0.5, y: 2.1, w: 4.6, h: 0.6, fontSize: 13, color: C.body });
    s.addImage({ data: INF, x: 0.55, y: 2.85, w: 4.4, h: 2.27 });

    // purple "offer" card
    s.addShape("roundRect", { x: 5.45, y: 0.72, w: 3.0, h: 4.1, rectRadius: 0.14, fill: { color: C.purple }, line: { color: C.purple } });
    s.addShape("roundRect", { x: 5.95, y: 0.56, w: 2.0, h: 0.32, rectRadius: 0.16, fill: { color: C.white }, line: { color: C.white } });
    T(s, "Version 1.1", { x: 5.95, y: 0.56, w: 2.0, h: 0.32, fontSize: 11, bold: true, color: C.ink, align: "center", valign: "middle" });
    T(s, "What changed", { x: 5.7, y: 1.05, w: 2.5, h: 0.35, fontSize: 16, bold: true, color: C.white });
    const stats = [["0.02 s", "numbers & charts on screen"], ["₹0.45", "AI cost per plan"], ["₹0.11", "AI cost per chat question"], ["25 + 31", "unit tests + end-to-end checks"]];
    stats.forEach(([n, l], i) => {
      const y = 1.55 + i * 0.78;
      T(s, n, { x: 5.7, y, w: 2.5, h: 0.4, fontSize: 22, bold: true, color: C.white });
      T(s, l, { x: 5.7, y: y + 0.38, w: 2.5, h: 0.25, fontSize: 10, color: "E6D5F5" });
    });
    // word cloud (grey), like the reference page
    const words = [["FastAPI", 20, 8.65, 0.7], ["Python", 13, 9.0, 1.2], ["pgvector", 14, 8.62, 1.55], ["OpenAI", 19, 8.7, 1.95],
      ["RAG", 13, 9.35, 2.45], ["Phoenix", 18, 8.62, 2.8], ["Docker", 12, 8.95, 3.25], ["OAuth", 14, 8.65, 3.6], ["Postgres", 13, 8.8, 4.0], ["OTel", 17, 9.1, 4.35]];
    words.forEach(([w, sz, x, y]) => T(s, w, { x: x - 0.12, y, w: 1.3, h: 0.4, fontSize: sz, color: C.grey, bold: sz > 16 }));
    s.addNotes(`Opening (30 seconds).
Good morning. Last time we presented the n8n v3.2 advisor and you gave us three pieces of feedback: it was slow, the pages were HTML-heavy, and the goal projection should be the first thing people see.
This is our answer: the same advisor, rebuilt as a small modular Python app. The finance logic is identical - we ported it line for line - but the numbers and charts now appear in about two hundredths of a second, and the AI explanation fills in while the user is already reading.
On the right you can see the headline numbers we will prove in this deck: 0.02 seconds to first view, about 45 paise of AI cost per plan, 11 paise per chat question, and 25 unit tests plus a 31-step end-to-end check.
We also added sign-in, the chat at the end of the report, cost tracking and observability - the last one converted from a teammate's n8n work.`);
  }

  // ================================================================ 2. Feedback -> response
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Mentor feedback");
    title(s, [["What you ", 0], ["a", 1], ["sked, what we ", 0], ["d", 1], ["id", 0]]);
    const items = [
      [I.bolt, "“n8n takes too long to respond”", "Numbers and charts in 0.02 s. The AI text is written in the background by 2 parallel calls instead of 4 agents in a row."],
      [I.feather, "“The application is HTML heavy”", "Server-rendered 26 KB report (was 34-44 KB). CSS and JS are cached files; charts are small inline SVGs."],
      [I.chart, "“Show Goal projection at the top”", "The report now opens with the verdict, progress ring, target vs projected and the projection chart."],
    ];
    items.forEach(([ic, q, a], i) => {
      const x = 0.5 + i * 3.05;
      card(s, x, 1.3, 2.85, 2.55);
      iconDot(s, ic, x + 0.25, 1.52, 0.55);
      T(s, q, { x: x + 0.25, y: 2.2, w: 2.4, h: 0.6, fontSize: 13, bold: true, italic: true, color: C.purple });
      T(s, a, { x: x + 0.25, y: 2.85, w: 2.4, h: 1.2, fontSize: 11.5, color: C.body });
    });
    T(s, "Also added", { x: 0.5, y: 4.2, w: 1.2, h: 0.34, fontSize: 11, bold: true, color: C.muted, valign: "middle" });
    ["Google + email sign-in", "Chat at the end", "Cost per plan & question", "Phoenix observability"].forEach((t, i) =>
      pill(s, t, 1.6 + i * 2.0, 4.2, 1.85, { size: 10 }));
    footer(s, 2);
    s.addNotes(`This slide maps each piece of feedback to what we changed.
One - speed. The slowness in n8n came from AI work done one step after another: four agents in a row, tool round trips for the stock screen, and guardrail model calls on the way in and out. Now every number is computed in code first and shown immediately; the explanation is written by just two AI calls that run at the same time.
Two - HTML weight. Each n8n report carried all its CSS inline and every intake page was a full n8n form round trip. Now the report is a 26 KB server-rendered page; styles and scripts are separate cached files.
Three - the goal projection is now the very first section of the report.
Along the way we added the items at the bottom: sign-in, the chat at the end of the report which can change the plan, cost tracking per plan and per question, and observability with Phoenix.`);
  }

  // ================================================================ 3. Architecture
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Architecture");
    title(s, [["Three containers, ", 0], ["o", 1], ["ne app", 0]]);
    // browser
    card(s, 0.5, 2.25, 1.35, 1.1);
    iconDot(s, I.globe, 0.93, 2.38, 0.48, C.ink);
    T(s, "Browser", { x: 0.5, y: 2.92, w: 1.35, h: 0.3, fontSize: 11, bold: true, color: C.ink, align: "center" });
    arrow(s, 1.87, 2.8, 2.25, 2.8, C.purple);
    // app panel
    s.addShape("roundRect", { x: 2.3, y: 1.2, w: 4.25, h: 3.75, rectRadius: 0.14, fill: { color: C.purple }, line: { color: C.purple } });
    T(s, "App container · FastAPI (Python 3.12)", { x: 2.5, y: 1.32, w: 3.9, h: 0.3, fontSize: 12, bold: true, color: C.white });
    const mods = [["Web & sign-in", "main.py · auth.py"], ["Intake & profile", "profile.py · money.py"], ["Finance engine", "debt · allocation · projection"],
      ["Plan pipeline", "pipeline.py"], ["AI layer", "llm · rag · narrative · chat · guard"], ["Report & charts", "report.py · charts.py"],
      ["Cost meter", "usage.py"], ["Tracing", "tracing.py → Phoenix"]];
    mods.forEach(([h, sub], i) => {
      const x = 2.5 + (i % 2) * 1.98, y = 1.75 + Math.floor(i / 2) * 0.78;
      s.addShape("roundRect", { x, y, w: 1.85, h: 0.66, rectRadius: 0.08, fill: { color: C.white }, line: { color: C.white } });
      T(s, h, { x: x + 0.1, y: y + 0.07, w: 1.7, h: 0.26, fontSize: 10.5, bold: true, color: C.ink });
      T(s, sub, { x: x + 0.1, y: y + 0.34, w: 1.7, h: 0.26, fontSize: 8.5, color: C.muted });
    });
    // services
    const svc = [[I.db, "Postgres + pgvector", "accounts · plans · chat · knowledge base"],
      [I.chart, "market-analyzer", "NIFTY 50 history (cached)"], [I.robot, "OpenAI", "gpt-5-mini · text-embedding-3-small"],
      [I.eye, "Arize Phoenix", "traces dashboard :6006"], [I.google, "Google sign-in", "optional OAuth"]];
    svc.forEach(([ic, h, sub], i) => {
      const y = 1.2 + i * 0.76;
      card(s, 7.0, y, 2.5, 0.64);
      iconDot(s, ic, 7.1, y + 0.1, 0.44, i < 2 ? C.purple : i === 3 ? C.violet : C.ink);
      T(s, h, { x: 7.62, y: y + 0.08, w: 1.85, h: 0.25, fontSize: 10.5, bold: true, color: C.ink });
      T(s, sub, { x: 7.62, y: y + 0.33, w: 1.85, h: 0.25, fontSize: 8, color: C.muted });
      arrow(s, 6.57, y + 0.32, 6.98, y + 0.32, C.purple);
    });
    footer(s, 3);
    s.addNotes(`Three containers on one Docker network, started by a single ./start.sh.
In the middle is the app: a FastAPI service that does everything the n8n canvas did - it serves the pages, checks the intake, computes the numbers, calls the AI, renders the report and runs the chat. Each white box is a module with one job; we will map them to the old n8n nodes on slide 5.
On the right: Postgres with pgvector holds accounts, profiles, reports, chat history and the 1,632 knowledge-base chunks - the same table format as v3.2. The market-analyzer is the same NIFTY 50 history API, called once and cached. OpenAI is used for the text and embeddings. Phoenix receives traces for observability, and Google sign-in is optional.
The key design rule, carried over from v3.2: numbers come from code, words come from AI. That rule is also what makes it fast.`);
  }

  // ================================================================ 4. How a plan is built
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Request flow");
    title(s, [["How a ", 0], ["p", 1], ["lan is built", 0]]);
    const steps = [["1", "Intake", "5 short steps, each checked by the server with a friendly reaction", "few ms per step"],
      ["2", "Compute", "Debt, risk plan, projection and monthly plan - all in code", "0.1 ms"],
      ["3", "Screen stocks", "Risk rules applied to all NIFTY 50 names in one cached call", "~10 ms"],
      ["4", "Report opens", "Numbers and charts on screen, saved to Postgres", "0.02 s"],
      ["5", "AI explanation", "1 knowledge-base search + 2 AI calls in parallel, swapped in live", "11-19 s"]];
    steps.forEach(([n, h, d, t], i) => {
      const x = 0.5 + i * 1.84;
      s.addShape("ellipse", { x: x + 0.55, y: 1.3, w: 0.6, h: 0.6, fill: { color: i === 3 ? C.violet : C.purple }, line: { color: C.white, width: 2 } });
      T(s, n, { x: x + 0.55, y: 1.3, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.white, align: "center", valign: "middle" });
      if (i < 4) arrow(s, x + 1.2, 1.6, x + 2.35, 1.6, C.grey);
      T(s, h, { x, y: 2.05, w: 1.7, h: 0.3, fontSize: 13, bold: true, color: C.ink, align: "center" });
      T(s, d, { x: x + 0.05, y: 2.4, w: 1.6, h: 1.0, fontSize: 10.5, color: C.body, align: "center" });
      pill(s, t, x + 0.2, 3.45, 1.3, { fill: i === 4 ? C.plum : C.ink, size: 10.5 });
    });
    card(s, 0.5, 4.1, 9.0, 0.85, C.lav);
    T(s, [{ text: "The numbers never wait for AI.  ", options: { bold: true, color: C.purple } },
          { text: "If OpenAI is slow or down, the report still opens complete, with explanation text written from the numbers.", options: { color: C.body } }],
      { x: 0.75, y: 4.1, w: 8.5, h: 0.85, fontSize: 13, valign: "middle" });
    footer(s, 4);
    s.addNotes(`Walk through the five steps.
Step one, the intake: five short steps in one page. After each step the server checks the answers - for example it can read 85K or 1.5 crore - and writes a friendly reaction, like estimating in-hand pay from the CTC.
Steps two and three are pure code: the debt metrics, the risk plan, the projection and the monthly plan take about a tenth of a millisecond; the stock screen applies the risk rules to all NIFTY 50 names from one cached call.
Step four: the report is saved and opens - about 20 milliseconds after pressing Build my plan.
Step five runs in the background: one embeddings request for the knowledge-base search, then two AI calls at the same time - one for the headline, summary and actions, one for the debt, allocation and stock notes. When they finish, the page swaps the text in.
The important property is in the box: the user never waits for AI to see their numbers, and an AI outage never breaks a report.`);
  }

  // ================================================================ 5. Module map
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "From nodes to modules");
    title(s, [["Every n8n node has a ", 0], ["P", 1], ["ython home", 0]]);
    const hdr = (t) => ({ text: t, options: { bold: true, color: C.white, fill: { color: C.purple }, fontSize: 10.5 } });
    const rows = [
      ["Intake Form, Chat 1-5, Read … nodes", "profile.py · intake.js", "Per-step checks and reactions, one page"],
      ["Compute Debt / Allocation / Projection", "engine/*.py", "Same formulas, unit-tested"],
      ["Debt, Portfolio, Recommender, Report agents", "ai/narrative.py", "2 parallel calls + fallback text"],
      ["Screen NIFTY50 + Historical data tools", "engine/stocks.py", "Rules in code, one cached call"],
      ["Knowledge_Base_Search (PGVector)", "ai/rag.py", "Same table; queries batched"],
      ["Guardrails + Output Sanitizer", "ai/guard.py", "Local rules; no extra AI calls"],
      ["Render Report Card (786 lines of JS)", "report.py · charts.py", "Server-side SVG, Goal projection first"],
      ["Q&A Agent, Chat Memory, Update_My_Plan", "ai/chat.py", "One call: on-topic + reply + changes"],
      ["Team telemetry API + Phoenix", "tracing.py", "App traces itself (v1.1)"],
    ].map(r => r.map((t, j) => ({ text: t, options: { color: j === 1 ? C.purple : C.body, bold: j === 1, fontSize: 10 } })));
    s.addTable([[hdr("n8n v3.2 node(s)"), hdr("Python module"), hdr("What changed")], ...rows], {
      x: 0.5, y: 1.2, w: 9.0, colW: [3.6, 2.1, 3.3], fontFace: FONT, border: { type: "solid", pt: 0.5, color: C.line },
      fill: { color: C.white }, rowH: 0.36, valign: "middle", margin: [0.03, 0.08, 0.03, 0.08],
    });
    footer(s, 5);
    s.addNotes(`For the mentor who knows the n8n version: every node has a direct home in the Python code, so nothing was lost - only reorganised.
The intake chat pages and their Read nodes became profile.py plus a small JavaScript file for the page.
The three Compute Code nodes became the engine package, with the same formulas and thresholds, now covered by unit tests.
The four agents became one module that makes two parallel calls, with deterministic fallback text.
The stock tools became a code filter, the vector search is the same table, the guardrails are local rules, and the 786-line report renderer became server-side templates and SVG charts.
The chat agent and the re-plan tool from 3.2.3 became one chat module, and the team's telemetry service became tracing.py.
About 4,000 lines in total, each module with one clear job.`);
  }

  // ================================================================ 6. Report layout
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "The report");
    title(s, [["G", 1], ["oal projection comes ", 0], ["f", 1], ["irst", 0]]);
    // mock page
    card(s, 0.5, 1.2, 3.6, 3.95);
    s.addShape("roundRect", { x: 0.7, y: 1.38, w: 3.2, h: 1.35, rectRadius: 0.1, fill: { color: C.purple }, line: { color: C.purple } });
    T(s, "On track", { x: 0.85, y: 1.48, w: 1.2, h: 0.22, fontSize: 9, bold: true, color: "E6D5F5" });
    T(s, "Goal projection", { x: 0.85, y: 1.7, w: 2.2, h: 0.3, fontSize: 13, bold: true, color: C.white });
    T(s, "Target ₹80L · Projected ₹82.15L", { x: 0.85, y: 2.0, w: 2.3, h: 0.25, fontSize: 9, color: C.white });
    s.addShape("ellipse", { x: 3.15, y: 1.6, w: 0.62, h: 0.62, fill: { color: C.purple }, line: { color: C.white, width: 3 } });
    T(s, "100%", { x: 3.15, y: 1.6, w: 0.62, h: 0.62, fontSize: 9, bold: true, color: C.white, align: "center", valign: "middle" });
    s.addChart(pres.charts.LINE, [{ name: "Today", labels: ["Now", "2", "4", "6", "8"], values: [13, 26, 42, 61, 82] }, { name: "Needed", labels: ["Now", "2", "4", "6", "8"], values: [13, 25, 40, 58, 80] }],
      { x: 0.85, y: 2.22, w: 2.9, h: 0.5, chartColors: ["FFFFFF", C.orange], lineSize: 2, showLegend: false, catAxisHidden: true, valAxisHidden: true,
        valGridLine: { style: "none" }, catGridLine: { style: "none" }, lineDataSymbol: "none", plotArea: { fill: { color: C.purple } } });
    const secs = ["Where you stand today", "Where your pay goes", "Your risk profile", "Monthly plan by instrument", "Do these first", "Allocation · safety net · loans", "Chat: questions & what-ifs"];
    secs.forEach((t, i) => {
      const y = 2.85 + i * 0.315;
      s.addShape("roundRect", { x: 0.7, y, w: 3.2, h: 0.25, rectRadius: 0.05, fill: { color: i === 6 ? C.lav : "F3EEF6" }, line: { color: "F3EEF6" } });
      T(s, t, { x: 0.8, y, w: 3.0, h: 0.25, fontSize: 9, color: i === 6 ? C.purple : C.muted, bold: i === 6, valign: "middle" });
    });
    // explanation
    const pts = [["Opens with the answer", "Verdict, progress ring, target vs projected, needed per month and the projection chart - the first screen."],
      ["Then the detail", "Same sections as v3.2, in the same order: snapshot, pay split, risk, monthly plan, actions, allocation, safety net, loans, stocks."],
      ["Ends with the chat", "Ask a question or a what-if; a change creates an updated report with an “Updated plan” banner."],
      ["Cost and timing shown", "Footer: “AI cost of this plan ₹0.37 · 2 AI calls + 1 search” and build time."]];
    pts.forEach(([h, d], i) => {
      const y = 1.25 + i * 0.97;
      iconDot(s, [I.chart, I.list, I.chat, I.rupee][i], 4.5, y, 0.46);
      T(s, h, { x: 5.1, y: y - 0.02, w: 4.4, h: 0.3, fontSize: 13.5, bold: true, color: C.ink });
      T(s, d, { x: 5.1, y: y + 0.29, w: 4.4, h: 0.6, fontSize: 11, color: C.body });
    });
    footer(s, 6);
    s.addNotes(`This answers the third piece of feedback.
On the left is the shape of the report. The first screen is now the goal projection: the verdict pill, the progress ring, target versus projected, the monthly amount needed, and the chart comparing today's pace with the pace needed.
Everything else follows in the same order as v3.2 - where you stand, where your pay goes, the risk profile, where to put your money each month, the priority actions, allocation, the safety net, loans and the stock shortlist.
The report ends with the chat, so the natural next step after reading is to ask a question or try a what-if. A change produces a new report with an Updated plan banner and a link back to the previous one.
The footer shows what this plan cost in AI and how fast it was built, which leads into the next two slides.`);
  }

  // ================================================================ 7. Speed
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Measured with the real OpenAI API");
    title(s, [["Why it is ", 0], ["f", 1], ["aster", 0]]);
    const big = [["1-3 min", "v3.2: until anything appeared", C.grey], ["0.02 s", "now: numbers and charts on screen", C.purple], ["11-19 s", "now: AI text, while the user reads", C.violet]];
    big.forEach(([n, l, col], i) => {
      const x = 0.5 + i * 3.05;
      card(s, x, 1.2, 2.85, 1.35);
      T(s, n, { x: x + 0.2, y: 1.3, w: 2.5, h: 0.7, fontSize: 36, bold: true, color: col });
      T(s, l, { x: x + 0.2, y: 2.0, w: 2.5, h: 0.4, fontSize: 11, color: C.body });
    });
    const why = [["Numbers never wait for AI", "the report opens as soon as the maths is done"], ["2 AI calls in parallel", "instead of 4 agents one after another"],
      ["Stocks and guardrails in code", "no tool loops, no guardrail model calls"], ["1 batched search request", "all knowledge-base queries embedded at once"],
      ["reasoning_effort = low", "quick answers; medium is a setting away"], ["Chat answer in 4.5-6.5 s", "one call returns reply + plan changes"]];
    why.forEach(([h, d], i) => {
      const x = 0.5 + (i % 2) * 4.55, y = 2.85 + Math.floor(i / 2) * 0.72;
      iconDot(s, I.check, x, y + 0.03, 0.36, C.purple);
      T(s, h, { x: x + 0.5, y, w: 3.9, h: 0.28, fontSize: 12.5, bold: true, color: C.ink });
      T(s, d, { x: x + 0.5, y: y + 0.28, w: 3.9, h: 0.28, fontSize: 10.5, color: C.muted });
    });
    footer(s, 7);
    s.addNotes(`These are measured numbers, from runs with the real OpenAI API on 28 September.
In v3.2 nothing appeared until every agent had finished - one to three minutes. Now the numbers and charts are on screen in about 0.02 seconds. The AI explanation takes 11 to 19 seconds depending on OpenAI, but the user is already reading while it is written.
Where the speed comes from, bottom half: the numbers do not wait for AI; two AI calls run in parallel instead of four agents in sequence; the stock screen and the guardrails are code, so there are no tool loops or extra guardrail model calls; all knowledge-base queries go in one embeddings request; and the model runs with low reasoning effort, which is a single setting if we want more thorough text.
A chat answer takes 4.5 to 6.5 seconds, including a what-if that re-runs the whole plan.`);
  }

  // ================================================================ 8. Cost
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Cost per plan and per question · gpt-5-mini · $1 = ₹88");
    title(s, [["What one plan ", 0], ["c", 1], ["osts", 0]]);
    const st = [["₹0.45", "per plan (avg)", "~7,000 tokens"], ["₹0.11", "per chat question", "~2,900 tokens"], ["₹0", "blocked locally", "guardrail, no AI call"]];
    st.forEach(([n, l, sub], i) => {
      const y = 1.2 + i * 1.05;
      s.addShape("roundRect", { x: 0.5, y, w: 2.9, h: 0.9, rectRadius: 0.12, fill: { color: i === 0 ? C.purple : C.white }, line: { color: i === 0 ? C.purple : C.line } });
      T(s, n, { x: 0.7, y: y + 0.1, w: 1.3, h: 0.7, fontSize: 28, bold: true, color: i === 0 ? C.white : C.purple, valign: "middle" });
      T(s, l, { x: 1.95, y: y + 0.17, w: 1.4, h: 0.3, fontSize: 11, bold: true, color: i === 0 ? C.white : C.ink });
      T(s, sub, { x: 1.95, y: y + 0.47, w: 1.4, h: 0.28, fontSize: 9.5, color: i === 0 ? "E6D5F5" : C.muted });
    });
    s.addChart(pres.charts.BAR, [{ name: "Cost (₹)", labels: ["report_details", "report_story", "chat_reply", "embeddings"], values: [0.271, 0.252, 0.107, 0.0001] }], {
      x: 3.65, y: 1.15, w: 3.3, h: 2.45, barDir: "bar", chartColors: [C.purple], showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
      dataLabelFontSize: 9, dataLabelColor: C.ink, showTitle: true, title: "Cost per AI call (₹)", titleFontSize: 11, titleColor: C.ink, titleFontFace: FONT,
      catAxisLabelColor: C.body, catAxisLabelFontSize: 9, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
      catAxisLabelFontFace: FONT,
    });
    T(s, "Output tokens (incl. reasoning) are ~80% of the cost. Prompt caching cut one plan to ₹0.37.", { x: 3.7, y: 3.65, w: 3.2, h: 0.5, fontSize: 10, color: C.muted, italic: true });
    const sc = [["Light user", "1 plan + 3 questions", "₹0.8"], ["Typical user", "1 plan + 5 questions + 2 what-ifs", "₹2.1"], ["Heavy user", "3 plans + 20 questions + 5 what-ifs", "₹6.3"], ["1,000 typical users", "per month", "₹2,100"]];
    card(s, 7.15, 1.2, 2.35, 3.0);
    T(s, "Per user", { x: 7.3, y: 1.3, w: 2.1, h: 0.3, fontSize: 12, bold: true, color: C.ink });
    sc.forEach(([h, d, v], i) => {
      const y = 1.68 + i * 0.62;
      T(s, h, { x: 7.3, y, w: 1.4, h: 0.25, fontSize: 10.5, bold: true, color: C.ink });
      T(s, v, { x: 8.55, y, w: 0.8, h: 0.25, fontSize: 12, bold: true, color: C.purple, align: "right" });
      T(s, d, { x: 7.3, y: y + 0.25, w: 2.05, h: 0.3, fontSize: 8.5, color: C.muted });
    });
    card(s, 0.5, 4.4, 9.0, 0.62, C.lav);
    T(s, [{ text: "Where to see it:  ", options: { bold: true, color: C.purple } },
          { text: "each report's footer · under each chat answer · the Usage page · ./scripts/usage-report.sh for every user", options: { color: C.body } }],
      { x: 0.75, y: 4.4, w: 8.6, h: 0.62, fontSize: 12, valign: "middle" });
    footer(s, 8);
    s.addNotes(`You asked us to calculate the cost per user, per plan and per chat query. Every OpenAI response includes a usage block; the app records it against the plan or question that caused it and prices it at OpenAI's published rates - gpt-5-mini is 25 cents per million input tokens and 2 dollars per million output tokens.
Measured: a plan costs between 37 and 52 paise, about 45 on average, for roughly 7,000 tokens. A chat question costs about 11 paise. A message blocked by the guardrails costs nothing because it never reaches the AI.
The chart shows the split: the two report calls are about 25 to 27 paise each; the embeddings are negligible. About 80 percent of the cost is output tokens, so shorter answers or a smaller model like gpt-5-nano are the levers. Prompt caching already brought one plan down to 37 paise.
Per user: a typical user - one plan, five questions and two what-ifs - costs about two rupees. A thousand such users a month is about 2,100 rupees, roughly 24 dollars.
Users see their own costs on the report, under each chat answer and on the Usage page; the team report script lists every user.`);
  }

  // ================================================================ 9. Chat
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Chat at the end of the report");
    title(s, [["Ask, or ", 0], ["c", 1], ["hange the plan", 0]]);
    // conversation
    card(s, 0.5, 1.2, 4.3, 3.8);
    s.addShape("roundRect", { x: 1.55, y: 1.45, w: 3.05, h: 0.62, rectRadius: 0.14, fill: { color: C.purple }, line: { color: C.purple } });
    T(s, "What if I invest 40K a month with medium risk?", { x: 1.7, y: 1.45, w: 2.8, h: 0.62, fontSize: 11, color: C.white, valign: "middle" });
    s.addShape("roundRect", { x: 0.7, y: 2.25, w: 3.4, h: 1.75, rectRadius: 0.14, fill: { color: "F3EEF6" }, line: { color: C.line } });
    T(s, [{ text: "Updated plan: ", options: { bold: true, color: C.ink } },
          { text: "Monthly investing ₹18K → ₹40K, Risk High → Medium. You're now on track - projected ₹82.15L against ₹80L.", options: { color: C.body } }],
      { x: 0.85, y: 2.35, w: 3.1, h: 0.95, fontSize: 11 });
    pill(s, "Open the updated report →", 0.85, 3.35, 2.4, { fill: C.purple, size: 10 });
    T(s, "₹0.111 · 2,916 tokens · 6.5 s", { x: 0.85, y: 3.75, w: 3.0, h: 0.2, fontSize: 8.5, color: C.muted });
    T(s, "The PAN in “My PAN is …” is refused locally - ₹0, never stored.", { x: 0.7, y: 4.2, w: 3.9, h: 0.6, fontSize: 10, italic: true, color: C.muted });
    // how
    const steps = [[I.shield, "Local guardrail", "ID numbers and prompt injection refused before any AI call"],
      [I.search, "Knowledge-base search", "the question is matched to the 830 curated documents"],
      [I.robot, "One AI call, three answers", "on-topic? · the reply · any plan changes (11 fields)"],
      [I.cogs, "Re-run the plan", "same rules and charts; new report with an Updated plan banner"]];
    steps.forEach(([ic, h, d], i) => {
      const y = 1.25 + i * 0.93;
      iconDot(s, ic, 5.15, y, 0.5, i === 2 ? C.violet : C.purple);
      if (i < 3) s.addShape("line", { x: 5.4, y: y + 0.52, w: 0.001, h: 0.4, line: { color: C.line, width: 1.5 } });
      T(s, h, { x: 5.85, y: y - 0.01, w: 3.6, h: 0.3, fontSize: 13, bold: true, color: C.ink });
      T(s, d, { x: 5.85, y: y + 0.29, w: 3.6, h: 0.5, fontSize: 10.5, color: C.body });
    });
    footer(s, 9);
    s.addNotes(`The chat sits at the end of the report. The user is signed in, so it already knows their profile and latest plan - no need to type an email.
Left: a real exchange. The user asks "What if I invest 40K a month with medium risk?" The reply lists exactly what changed, the new verdict - now on track, 82 lakh against 80 - and a button to the updated report. That question cost 11 paise and took 6.5 seconds, including re-running the whole plan.
Right: how it works. First a local guardrail: ID numbers like a PAN or Aadhaar, and prompt-injection attempts, are refused before any AI call, so they cost nothing and are never stored. Then a knowledge-base search. Then one AI call that returns three things at once: whether the question is on topic, the reply, and any plan changes. If there are changes, the same pipeline re-runs, so an updated plan is exactly as trustworthy as the first one.`);
  }

  // ================================================================ 10. Sign-in & safety
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Accounts and privacy");
    title(s, [["S", 1], ["ign-in and ", 0], ["s", 1], ["afety", 0]]);
    const g = [[I.google, "Google or email", "Google OAuth when configured; email + password (scrypt) always works."],
      [I.lock, "Login throttling", "8 failed attempts lock that email for 15 minutes; success never counts."],
      [I.key, "Signed sessions", "HTTP-only cookie with only the account id; anti-CSRF header on every write."],
      [I.user, "Private reports", "Only the owner can open a report or its status; others get “not found”."],
      [I.mask, "ID numbers masked", "PAN, Aadhaar, cards, phone refused in chat and masked in AI output."],
      [I.shield, "Strict page policy", "Scripts only from the app itself; no framing; no external CDNs."]];
    g.forEach(([ic, h, d], i) => {
      const x = 0.5 + (i % 3) * 3.05, y = 1.25 + Math.floor(i / 3) * 1.85;
      card(s, x, y, 2.85, 1.65);
      iconDot(s, ic, x + 0.22, y + 0.22, 0.5, i % 2 ? C.ink : C.purple);
      T(s, h, { x: x + 0.22, y: y + 0.82, w: 2.45, h: 0.3, fontSize: 13, bold: true, color: C.ink });
      T(s, d, { x: x + 0.22, y: y + 1.12, w: 2.45, h: 0.5, fontSize: 10, color: C.body });
    });
    footer(s, 10);
    s.addNotes(`Sign-in was a new requirement from the team, so we kept it simple but correct.
Google sign-in works as soon as a Google client ID is added; email and password always works, with passwords hashed using scrypt. Repeated failed logins are throttled.
Sessions are signed HTTP-only cookies, and every write request needs a special header that other websites cannot send, which blocks cross-site request forgery.
Reports are private: another account asking for your report gets "not found".
ID numbers are refused in the chat and masked in anything the AI writes, and the pages only run scripts from the app itself.
One honest limitation: email sign-up does not verify the address. That is fine for local testing; for a public version we would use Google only or add email verification. If a Google user signs in with an email that already has a password account, the Google owner takes over and the old password stops working.`);
  }

  // ================================================================ 11. Observability
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "New in v1.1 · from a teammate's n8n work");
    title(s, [["O", 1], ["bservability with ", 0], ["P", 1], ["hoenix", 0]]);
    card(s, 0.5, 1.2, 4.4, 3.85);
    T(s, "One plan = one trace", { x: 0.7, y: 1.32, w: 4.0, h: 0.3, fontSize: 12.5, bold: true, color: C.ink });
    const tree = [[0, "Build plan", "CHAIN", C.purple], [1, "Compute numbers", "CHAIN", C.purple], [1, "Screen NIFTY 50", "TOOL", C.ink],
      [1, "Write explanation", "CHAIN", C.purple], [2, "Knowledge-base search", "RETRIEVER", C.plum], [3, "embeddings", "EMBEDDING", C.plum],
      [2, "report_story", "LLM", C.violet], [2, "report_details", "LLM", C.violet]];
    tree.forEach(([lvl, name, kind, col], i) => {
      const y = 1.75 + i * 0.4, x = 0.75 + lvl * 0.35;
      s.addShape("roundRect", { x, y, w: 3.9 - lvl * 0.35, h: 0.34, rectRadius: 0.06, fill: { color: "F3EEF6" }, line: { color: C.line } });
      T(s, name, { x: x + 0.1, y, w: 2.1, h: 0.34, fontSize: 10, bold: lvl < 2, color: C.ink, valign: "middle" });
      pill(s, kind, x + 3.9 - lvl * 0.35 - 1.0, y, 1.0, { fill: col, size: 7.5 });
    });
    const pts = [["Every step timed", "see the two AI calls run side by side"], ["Tokens and cost per call", "prompt, completion, cached, reasoning, pfa.cost_usd"],
      ["Prompts, answers, passages", "switch off with PFA_TRACE_CONTENT=false"], ["A user's journey", "Sessions: all plans and chats of user-<hash>"],
      ["Safe by design", "no emails, IDs masked; Phoenix down → app just as fast"]];
    pts.forEach(([h, d], i) => {
      const y = 1.25 + i * 0.77;
      iconDot(s, [I.bolt, I.rupee, I.file, I.user, I.shield][i], 5.2, y, 0.44);
      T(s, h, { x: 5.8, y: y - 0.02, w: 3.7, h: 0.28, fontSize: 12.5, bold: true, color: C.ink });
      T(s, d, { x: 5.8, y: y + 0.26, w: 3.7, h: 0.4, fontSize: 10, color: C.body });
    });
    footer(s, 11);
    s.addNotes(`Observability is new in version 1.1, and it came from a teammate's work on the n8n bundle. They added Arize Phoenix and a small telemetry API that turns workflow events into OpenTelemetry traces. In n8n the workflow did not yet call it; in Python the app traces itself, so the extra service was not needed.
On the left is one plan as Phoenix shows it: a trace with a span for each step, labelled with standard kinds - chain, tool, retriever, embedding, LLM. The chat has the same, plus a guardrail span.
On the right, what we get: the timing of every step - you can literally see the two AI calls overlapping; tokens and cost on every AI call; the prompts, answers and retrieved passages, which can be switched off; and a session per user, so we can follow one person's journey.
It is safe by design: users appear as a hash, never their email; ID numbers are masked before export; and when Phoenix is stopped the app is just as fast - we tested that.`);
  }

  // ================================================================ 12. Testing
  {
    const s = pres.addSlide(); s.background = { color: C.bg };
    eyebrow(s, "Evidence");
    title(s, [["H", 1], ["ow we ", 0], ["t", 1], ["ested it", 0]]);
    const nums = [["25", "unit tests", "parsing, tax, risk plan, projection, stocks, chat changes, guardrails, passwords, cost maths, tracing"],
      ["31", "end-to-end checks", "sign-up to chat on an isolated stack: order of sections, privacy between accounts, refusals"],
      ["28", "spans in Phoenix", "one plan + three chat messages, correct links, tokens and costs, PAN never exported"],
      ["1,632", "knowledge chunks", "loaded in 21 s with the real API; second run resumes and skips all"]];
    nums.forEach(([n, l, d], i) => {
      const x = 0.5 + (i % 2) * 4.55, y = 1.2 + Math.floor(i / 2) * 1.5;
      card(s, x, y, 4.35, 1.3);
      T(s, n, { x: x + 0.25, y: y + 0.18, w: 1.5, h: 0.6, fontSize: 32, bold: true, color: C.purple });
      T(s, l, { x: x + 1.75, y: y + 0.22, w: 2.45, h: 0.3, fontSize: 13, bold: true, color: C.ink });
      T(s, d, { x: x + 1.75, y: y + 0.52, w: 2.45, h: 0.7, fontSize: 9.5, color: C.body });
    });
    T(s, "Still to do", { x: 0.5, y: 4.3, w: 1.3, h: 0.34, fontSize: 11, bold: true, color: C.muted, valign: "middle" });
    ["Real Google sign-in (client ID)", "Phone-layout pass", "Email verification (public use)"].forEach((t, i) =>
      pill(s, t, 1.75 + i * 2.6, 4.3, 2.45, { fill: C.white, color: C.ink, line: C.ink, size: 10 }));
    footer(s, 12);
    s.addNotes(`How we know it works.
25 unit tests cover the deterministic parts - including the exact v3.2 example: an 18 lakh CTC gives 1.22 lakh in hand - plus the risk plan, projection consistency, the stock rules, chat changes, guardrails, passwords, the cost maths and the tracing attributes.
A 31-step end-to-end check runs the real journey on an isolated Docker stack with a stand-in for OpenAI: sign-up, the five intake steps, the "nearly there" step for impossible numbers, the report order with the goal projection first, the AI text being swapped in, a chat what-if, refusals, and privacy between two accounts.
Phoenix received 28 correctly linked spans for one plan and three chat messages, and the PAN we typed never reached it.
And with the real OpenAI API we loaded the knowledge base and measured the timings and costs shown earlier.
Still to do: a real Google sign-in needs the team's Google client ID, a phone-layout pass, and email verification before any public use.`);
  }

  // ================================================================ 13. Close (dark purple)
  {
    const s = pres.addSlide(); s.background = { color: C.purple };
    T(s, "DEMO AND NEXT STEPS", { x: 0.5, y: 0.45, w: 5, h: 0.25, fontSize: 10, bold: true, color: "E6D5F5", charSpacing: 2 });
    T(s, [{ text: "Let's see it ", options: { color: C.white } }, { text: "l", options: { color: C.orange } }, { text: "ive", options: { color: C.white } }],
      { x: 0.5, y: 0.8, w: 5, h: 0.7, fontSize: 36, bold: true });
    const demo = ["Sign in and build a plan (5 steps)", "Report opens with Goal projection first", "Ask: “What if I invest 40K a month?”", "Open the updated report", "Usage page: cost per plan and question", "Phoenix: the same plan as a trace"];
    demo.forEach((t, i) => {
      const y = 1.7 + i * 0.5;
      s.addShape("ellipse", { x: 0.5, y, w: 0.36, h: 0.36, fill: { color: C.white }, line: { color: C.white } });
      T(s, String(i + 1), { x: 0.5, y, w: 0.36, h: 0.36, fontSize: 11, bold: true, color: C.purple, align: "center", valign: "middle" });
      T(s, t, { x: 1.0, y, w: 4.2, h: 0.36, fontSize: 13, color: C.white, valign: "middle" });
    });
    s.addImage({ data: INF, x: 5.45, y: 0.65, w: 4.1, h: 2.12 });
    s.addShape("roundRect", { x: 5.6, y: 3.0, w: 3.9, h: 1.95, rectRadius: 0.14, fill: { color: C.white }, line: { color: C.white } });
    T(s, "What we'd like from you", { x: 5.8, y: 3.12, w: 3.5, h: 0.3, fontSize: 13, bold: true, color: C.ink });
    T(s, [{ text: "Is the Python edition the right direction for the final submission, alongside the n8n bundle?", options: { bullet: { indent: 12 }, breakLine: true } },
          { text: "Is ₹0.45 per plan acceptable, or should we try gpt-5-nano?", options: { bullet: { indent: 12 }, breakLine: true } },
          { text: "Anything else to show on the first screen?", options: { bullet: { indent: 12 } } }],
      { x: 5.8, y: 3.45, w: 3.55, h: 1.4, fontSize: 11, color: C.body, paraSpaceAfter: 4 });
    s.addNotes(`Close with the live demo - about four minutes - in this order.
One: sign in and build a plan through the five steps; point out the reactions, like the in-hand estimate from the CTC.
Two: the report opens instantly with the goal projection first; show the explanation text arriving a few seconds later.
Three: in the chat at the end, ask "What if I invest 40K a month with medium risk?"
Four: open the updated report and show the Updated plan banner.
Five: open the Usage page to show the cost of that plan and that question.
Six: open Phoenix at localhost:6006 and show the same plan as a trace, with the two AI calls running side by side.
Then the three questions on the right: is the Python edition the right direction for the final submission next to the n8n bundle; is about 45 paise per plan acceptable or should we try the cheaper gpt-5-nano model; and is there anything else the mentor wants on the first screen.
Backup if the demo fails: docs/ARCHITECTURE.html and docs/COST_AND_PERFORMANCE.md in the project folder.`);
  }

  await pres.writeFile({ fileName: "PFA_Python_v1.1_Mentor_Review.pptx" });
  console.log("written");
})();
