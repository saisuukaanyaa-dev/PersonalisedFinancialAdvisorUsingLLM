// Mentor + team deck: Personal Finance Advisor, Python edition v1.5 - the models we use and the concepts we cover.
// Same look as the earlier mentor deck (lavender ground, deep purple panels, violet highlight letters, black pills,
// orange -> pink -> purple gradient). Built as a structured deck: theme colours, layouts with placeholders, sections.
// Build:  NODE_PATH=<dir with pptxgenjs, sharp, react, react-dom, react-icons> node build_v15_deck.js <out.pptx> <apply_theme.js>
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const fa = require("react-icons/fa");

const OUT = process.argv[2] || "PFA_v1.5_Models_and_Concepts.pptx";
const APPLY = process.argv[3];
const THEME = {
  name: "PFA Lavender", headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: "111111", lt1: "FFFFFF", dk2: "6B0FA8", lt2: "F8F3FA", accent1: "9B19F5", accent2: "E8307A", accent3: "F7931E",
            accent4: "7B4FBF", accent5: "1F7A3F", accent6: "7A7383", hlink: "9B19F5", folHlink: "7B4FBF" },
};
const HEX = THEME.colors;

async function icon(Comp, hex = "FFFFFF", px = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + hex, size: px }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).resize(px, px).png().toBuffer()).toString("base64");
}
async function infinity() {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 600 310"><defs>
    <linearGradient id="g" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#F7B733"/><stop offset="0.25" stop-color="#F4652C"/>
    <stop offset="0.55" stop-color="#E8307A"/><stop offset="0.8" stop-color="#B43FB0"/><stop offset="1" stop-color="#6A5ACD"/></linearGradient></defs>
    <path d="M300 155 C 250 80, 200 55, 150 55 C 85 55, 45 100, 45 155 C 45 210, 85 255, 150 255 C 200 255, 250 230, 300 155 C 350 80, 400 55, 450 55 C 515 55, 555 100, 555 155 C 555 210, 515 255, 450 255 C 400 255, 350 230, 300 155 Z"
      fill="none" stroke="url(#g)" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";                        // 10 x 5.625 in
  pres.title = "Personal Finance Advisor - Python v1.5 - Models and Concepts";
  pres.author = "Group 2";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // ---------------------------------------------------------------- layouts
  const FOOT = { text: "Personal Finance Advisor · Python v1.5", options: { x: 0.5, y: 5.28, w: 6, h: 0.22, fontSize: 8, color: C.accent6 } };
  pres.defineSlideMaster({
    title: "PFA Content", background: { color: C.background2 }, margin: [0.5, 0.5, 0.5, 0.5],
    objects: [
      { placeholder: { options: { name: "eyebrow", type: "body", x: 0.5, y: 0.16, w: 9, h: 0.26, fontSize: 9.5, bold: true, color: C.text2, charSpacing: 2, margin: 0 }, text: "" } },
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.4, w: 9, h: 0.62, fontSize: 28, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: FOOT },
    ],
    slideNumber: { x: 9.0, y: 5.28, w: 0.5, h: 0.22, fontSize: 8, color: C.accent6, align: "right" },
  });
  pres.defineSlideMaster({
    title: "PFA Dark", background: { color: C.text2 },
    objects: [{ placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.2, fontSize: 36, bold: true, color: C.background1, valign: "middle", margin: 0 }, text: "" } }],
  });
  pres.defineSlideMaster({ title: "PFA Cover", background: { color: C.background2 } });

  // ---------------------------------------------------------------- helpers
  const T = (s, text, o) => s.addText(text, { color: C.text1, isTextBox: true, margin: 0, valign: "top", ...o });
  const hi = (parts) => parts.map(([t, h]) => ({ text: t, options: { color: h ? C.accent1 : C.text1 } }));   // violet highlight letters
  let section = "";
  const slide = (eyebrow, titleParts, notes) => {
    const s = pres.addSlide({ masterName: "PFA Content", sectionTitle: section });
    s.addText(eyebrow.toUpperCase(), { placeholder: "eyebrow" });
    s.addText(hi(titleParts), { placeholder: "title" });
    s.addNotes(notes);
    return s;
  };
  const shadow = () => ({ type: "outer", color: "6B0FA8", opacity: 0.12, blur: 8, offset: 2, angle: 90 });
  const card = (s, x, y, w, h, o = {}) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12,
    fill: { color: o.fill || C.background1, transparency: o.transparency || 0 }, line: { color: o.line || o.fill || "D9CCE3", width: 0.75 },
    shadow: o.flat ? undefined : shadow(), objectName: o.name });
  const pill = (s, text, x, y, w, o = {}) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: o.h || 0.32, rectRadius: (o.h || 0.32) / 2, fill: { color: o.fill || C.text1 }, line: { color: o.fill || C.text1 } });
    T(s, text, { x, y, w, h: o.h || 0.32, fontSize: o.size || 10, bold: true, color: o.color || C.background1, align: "center", valign: "middle" });
  };
  const dot = (s, img, x, y, d = 0.5, fill = C.text2) => {
    s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
    s.addImage({ data: img, x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
  };
  const arrow = (s, x1, y1, x2, y2) => s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001,
    h: Math.abs(y2 - y1) || 0.001, flipV: y2 < y1, line: { color: C.accent6, width: 1.25, endArrowType: "triangle" } });
  // Bar charts drawn with shapes, so they render the same in Keynote, PowerPoint and Google Slides
  // (Keynote does not import pptxgenjs chart objects - checked: 0 charts after import).
  const hbars = (s, { x, y, w, h, title, items, max, fmt }) => {
    T(s, title, { x, y, w, h: 0.3, fontSize: 11, bold: true });
    const top = y + 0.45, rowH = (h - 0.5) / items.length, labW = 1.55, barW = w - labW - 0.75;
    items.forEach(([label, v, col], i) => {
      const yy = top + i * rowH, bh = Math.min(0.32, rowH * 0.6);
      T(s, label, { x, y: yy, w: labW - 0.1, h: bh, fontSize: 9.5, valign: "middle", align: "right" });
      const bw = Math.max(0.03, barW * v / max);
      s.addShape(pres.shapes.RECTANGLE, { x: x + labW, y: yy, w: bw, h: bh, fill: { color: col || C.accent1 }, line: { color: col || C.accent1 } });
      T(s, fmt(v), { x: x + labW + bw + 0.06, y: yy, w: 0.75, h: bh, fontSize: 9.5, bold: true, valign: "middle" });
    });
  };
  const vbars = (s, { x, y, w, h, title, cats, series, max, fmt }) => {   // series: [[name, color, values[]]]; stacked
    T(s, title, { x, y, w, h: 0.3, fontSize: 11, bold: true });
    const base = y + h - 0.75, plotH = h - 1.35, colW = w / cats.length, bw = Math.min(0.85, colW * 0.5);
    s.addShape(pres.shapes.LINE, { x, y: base, w, h: 0, line: { color: "D9CCE3", width: 1 } });
    cats.forEach((c, i) => {
      const cx = x + i * colW + (colW - bw) / 2;
      let acc = 0;
      series.forEach(([name, col, vals]) => {
        const v = vals[i]; if (!v) return;
        const bh = plotH * v / max; acc += bh;
        s.addShape(pres.shapes.RECTANGLE, { x: cx, y: base - acc, w: bw, h: bh, fill: { color: col }, line: { color: C.background1, width: 0.75 } });
        T(s, fmt(v), { x: cx, y: base - acc, w: bw, h: Math.max(bh, 0.22), fontSize: 9.5, bold: true, color: series.length > 1 ? C.background1 : C.text1,
          align: "center", valign: series.length > 1 ? "middle" : "top", ...(series.length > 1 ? {} : { y: base - acc - 0.24, h: 0.22 }) });
      });
      T(s, c, { x: x + i * colW, y: base + 0.06, w: colW, h: 0.4, fontSize: 9, align: "center" });
    });
    if (series.length > 1) series.forEach(([name, col], j) => {
      const lx = x + j * (w / series.length);
      s.addShape(pres.shapes.RECTANGLE, { x: lx + 0.05, y: y + h - 0.22, w: 0.14, h: 0.14, fill: { color: col }, line: { color: col } });
      T(s, name, { x: lx + 0.24, y: y + h - 0.26, w: w / series.length - 0.3, h: 0.22, fontSize: 8.5, valign: "middle" });
    });
  };
  const mono = (s, text, x, y, w, h, size = 10) => {
    card(s, x, y, w, h, { fill: C.background1, flat: true });
    T(s, text, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: h - 0.2, fontFace: "Courier New", fontSize: size, color: C.text2 });
  };

  const I = {};
  for (const [k, comp] of Object.entries({ bolt: fa.FaBolt, robot: fa.FaRobot, chat: fa.FaComments, db: fa.FaDatabase, shield: fa.FaShieldAlt,
    route: fa.FaRoute, chart: fa.FaChartLine, rupee: fa.FaRupeeSign, bank: fa.FaUniversity, eye: fa.FaEye, flask: fa.FaFlask, mic: fa.FaMicrophone,
    search: fa.FaSearch, layer: fa.FaLayerGroup, check: fa.FaCheckCircle, code: fa.FaCode, user: fa.FaUserCircle, file: fa.FaFileAlt,
    bug: fa.FaBug, lock: fa.FaLock, cogs: fa.FaCogs, globe: fa.FaGlobe, balance: fa.FaBalanceScale, list: fa.FaListOl })) I[k] = await icon(comp);
  const INF = await infinity();

  // ================================================================ 1. Cover
  section = "Overview";
  pres.addSection({ title: section });
  {
    const s = pres.addSlide({ masterName: "PFA Cover", sectionTitle: section });
    T(s, "GROUP 2 CAPSTONE  ·  MENTOR AND TEAM REVIEW", { x: 0.5, y: 0.45, w: 5, h: 0.25, fontSize: 10, bold: true, color: C.text2, charSpacing: 2 });
    T(s, hi([["Personal ", 0], ["F", 1], ["inance ", 0], ["A", 1], ["dvisor", 0]]), { x: 0.5, y: 0.8, w: 4.85, h: 0.55, fontSize: 25, bold: true, fit: "none" });
    T(s, hi([["M", 1], ["odels and ", 0], ["C", 1], ["oncepts", 0]]), { x: 0.5, y: 1.35, w: 4.85, h: 0.6, fontSize: 30, bold: true });
    T(s, "Python edition v1.5: the AI models we use, the AI engineering concepts we applied, and the financial models behind every number.",
      { x: 0.5, y: 2.05, w: 4.6, h: 0.75, fontSize: 13, color: C.text1 });
    s.addImage({ data: INF, x: 0.55, y: 2.95, w: 4.2, h: 2.17 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.45, y: 0.72, w: 3.0, h: 4.1, rectRadius: 0.14, fill: { color: C.text2 }, line: { color: C.text2 } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 5.95, y: 0.56, w: 2.0, h: 0.32, rectRadius: 0.16, fill: { color: C.background1 }, line: { color: C.background1 } });
    T(s, "Version 1.5", { x: 5.95, y: 0.56, w: 2.0, h: 0.32, fontSize: 11, bold: true, align: "center", valign: "middle" });
    T(s, "In numbers", { x: 5.7, y: 1.05, w: 2.5, h: 0.35, fontSize: 16, bold: true, color: C.background1 });
    [["0.02 s", "numbers and charts on screen"], ["₹0.45", "AI cost per plan (gpt-5-mini)"], ["₹0.11", "AI cost per chat question"], ["30 / 30", "sample plans passed all checks"]]
      .forEach(([n, l], i) => {
        const y = 1.55 + i * 0.78;
        T(s, n, { x: 5.7, y, w: 2.5, h: 0.4, fontSize: 22, bold: true, color: C.background1 });
        T(s, l, { x: 5.7, y: y + 0.38, w: 2.5, h: 0.25, fontSize: 10, color: C.background2 });
      });
    [["gpt-5-mini", 18, 0.7], ["RAG", 13, 1.2], ["pgvector", 14, 1.55], ["MCP", 15, 1.95], ["FastAPI", 13, 2.4], ["Phoenix", 17, 2.75],
      ["FD / RD", 13, 3.2], ["SerpAPI", 12, 3.55], ["Voice", 15, 3.9], ["OTel", 16, 4.3]]
      .forEach(([w, sz, y]) => T(s, w, { x: 8.6, y, w: 1.3, h: 0.4, fontSize: sz, color: C.accent6, bold: sz > 15 }));
    s.addNotes(`Opening (30 seconds).
This deck is about Python edition v1.5 only: which AI models it uses, which AI engineering concepts we applied, and the financial models that produce every number in a report.
Headline figures on the right, all measured: numbers and charts appear in about two hundredths of a second, a plan costs about 45 paise of AI, a chat question about 11 paise, and our automated sample run of 30 plans passed every check.
The one idea to remember from today: numbers are computed in code; the language model explains them and talks to the user, but never invents a figure.`);
  }

  // ================================================================ 2. Agenda
  {
    const s = slide("Agenda", [["What we ", 0], ["c", 1], ["over today", 0]], `Agenda. Six parts. First what the product does and its one design rule. Then the AI models, then the AI engineering concepts: structured outputs, RAG, guardrails, the router and chat, observability and cost. Then the financial models: risk plan, projection, monthly plan, stock screen, and the new bank deposit planner. We finish with testing, what we learned, and next steps.`);
    const items = [[I.user, "The product", "Journey, design rule, architecture"], [I.robot, "AI models", "Text, embeddings, voice"],
      [I.layer, "AI concepts", "Structured outputs, RAG, guardrails, router, chat"], [I.rupee, "Financial models", "Risk plan, projection, monthly plan, stocks"],
      [I.bank, "Bank deposits", "New in v1.5: FD / RD planner"], [I.flask, "Quality", "Tests, sample run, lessons"]];
    items.forEach(([ic, h, d], i) => {
      const x = 0.5 + (i % 3) * 3.05, y = 1.35 + Math.floor(i / 3) * 1.85;
      card(s, x, y, 2.85, 1.6, { name: `agenda-${i + 1}` });
      dot(s, ic, x + 0.25, y + 0.25, 0.5, i === 4 ? C.accent2 : C.text2);
      T(s, `${i + 1}. ${h}`, { x: x + 0.25, y: y + 0.85, w: 2.4, h: 0.3, fontSize: 14, bold: true });
      T(s, d, { x: x + 0.25, y: y + 1.15, w: 2.4, h: 0.4, fontSize: 10.5, color: C.accent6 });
    });
  }

  // ================================================================ 3. Journey
  {
    const s = slide("The product", [["From five questions to a ", 0], ["p", 1], ["lan", 0]], `The user journey. Sign in with email and password or Google. A friendly five-step intake: about you and your goal, money in and out, safety net, loans, and what you already own, ending with a risk gut-check question. It can be answered by voice.
The report opens almost instantly because every number is computed in code. The written explanation arrives 11 to 19 seconds later from two parallel AI calls; the user is already reading.
Then Arth, the chat advisor, answers questions, quotes deposit rates, runs what-ifs and changes the plan only after the user confirms.`);
    const steps = [[I.lock, "Sign in", "email + password (scrypt) or Google"], [I.list, "5-step intake", "reactions to each answer; voice optional"],
      [I.bolt, "Report in 0.02 s", "all numbers and charts from code"], [I.file, "AI text in 11-19 s", "2 parallel calls, swapped in"], [I.chat, "Chat with Arth", "questions, what-ifs, deposits, voice"]];
    steps.forEach(([ic, h, d], i) => {
      const x = 0.5 + i * 1.86;
      card(s, x, 1.55, 1.66, 2.2, { name: `step-${i + 1}` });
      dot(s, ic, x + 0.58, 1.75, 0.5, i === 2 ? C.accent2 : C.text2);
      T(s, h, { x: x + 0.12, y: 2.4, w: 1.42, h: 0.5, fontSize: 12.5, bold: true, align: "center" });
      T(s, d, { x: x + 0.12, y: 2.9, w: 1.42, h: 0.75, fontSize: 9.5, color: C.accent6, align: "center" });
      if (i < 4) arrow(s, x + 1.67, 2.65, x + 1.85, 2.65);
    });
    T(s, "The report shows", { x: 0.5, y: 4.08, w: 1.6, h: 0.32, fontSize: 11, bold: true, color: C.accent6, valign: "middle" });
    ["Goal projection", "Risk profile", "Monthly plan in ₹", "Safety net", "Stocks or 'not yet'", "Bank deposits"].forEach((t, i) =>
      pill(s, t, 2.05 + i * 1.25, 4.08, 1.17, { size: 8.5, fill: i === 5 ? C.accent2 : C.text1 }));
  }

  // ================================================================ 4. Design rule
  {
    const s = slide("The one design rule", [["N", 1], ["umbers in code, ", 0], ["w", 1], ["ords from the model", 0]], `This is the rule behind every design decision. On the left, everything that is a number: tax, debt, the risk plan, the projection, the monthly plan, the stock screen and the deposit planner. All deterministic Python, unit-tested, and it runs in milliseconds.
On the right, what the language model does: explain those numbers in plain English, hold the conversation, and extract what the user wants into a strict schema, for example a plan change or a deposit request.
Between them is the contract: the prompt says every number must appear in the facts, and the code re-checks anything the model proposes.`);
    card(s, 0.5, 1.3, 4.3, 3.65, { name: "code-column" });
    dot(s, I.code, 0.75, 1.5, 0.5, C.accent5);
    T(s, "Code: deterministic, tested", { x: 1.4, y: 1.55, w: 3.3, h: 0.4, fontSize: 15, bold: true, valign: "middle" });
    T(s, ["In-hand pay from CTC (FY 2026-27 tax)", "Debt metrics and pay-off order", "Risk plan: mix, horizon cap, safety net", "Goal projection (future value)",
      "Monthly plan in ₹ per instrument", "NIFTY 50 stock screen", "Bank FD / RD planner"].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
      { x: 0.8, y: 2.15, w: 3.85, h: 2.6, fontSize: 12, paraSpaceAfter: 4 });
    card(s, 5.2, 1.3, 4.3, 3.65, { name: "model-column" });
    dot(s, I.robot, 5.45, 1.5, 0.5, C.accent1);
    T(s, "Model: explains and extracts", { x: 6.1, y: 1.55, w: 3.3, h: 0.4, fontSize: 15, bold: true, valign: "middle" });
    T(s, ["Writes the report story and details", "Answers chat questions as Arth", "Extracts plan changes into a schema", "Extracts deposit requests (amounts, date)",
      "Flags off-topic and live-data needs", "Cites knowledge passages as [n]"].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
      { x: 5.5, y: 2.15, w: 3.85, h: 2.2, fontSize: 12, paraSpaceAfter: 4 });
    pill(s, "\"Every number you mention must appear in the FACTS\"", 5.45, 4.45, 3.8, { size: 9, fill: C.accent1 });
  }

  // ================================================================ 5. Architecture
  {
    const s = slide("Architecture", [["One ", 0], ["a", 1], ["pp, four services", 0]], `Architecture. One FastAPI application with clear modules: auth and intake; the deterministic engine; the AI layer with narrative, chat, router, retrieval, guardrails and voice; report rendering with server-side SVG charts; live data; tracing; and evaluation.
It talks to four services: Postgres with pgvector for all data and the knowledge-base vectors; the market-analyzer for NIFTY 50 history; OpenAI; and SerpAPI plus the World Bank for live data. Traces go to Phoenix. Everything starts with one command, docker compose, bound to localhost.`);
    card(s, 0.5, 1.25, 4.2, 3.75, { name: "app-box" });
    T(s, "FastAPI app (pfa)", { x: 0.7, y: 1.35, w: 3.8, h: 0.35, fontSize: 14, bold: true });
    const mods = [["auth · profile", "sign-in, 5-step intake, checks", C.background2], ["engine/", "debt · risk plan · projection · stocks · deposits", "E7F6EC"],
      ["ai/", "narrative · chat · router · rag · guard · voice", "FFF1E6"], ["report + charts", "server-side SVG, Jinja templates", C.background2],
      ["tracing · usage · eval", "OpenInference spans, cost, samples", "EEF4FF"]];
    mods.forEach(([h, d, f], i) => {
      const y = 1.78 + i * 0.62;
      card(s, 0.7, y, 3.8, 0.54, { fill: f, flat: true });
      T(s, h, { x: 0.85, y: y + 0.06, w: 3.5, h: 0.22, fontSize: 10.5, bold: true });
      T(s, d, { x: 0.85, y: y + 0.28, w: 3.5, h: 0.22, fontSize: 9, color: C.accent6 });
    });
    const svc = [[I.db, "Postgres 16 + pgvector", "accounts · users · reports · chat · 1,632 KB chunks", C.text2], [I.chart, "market-analyzer", "NIFTY 50 history: CAGR, volatility, drawdown", C.text2],
      [I.robot, "OpenAI API", "gpt-5-mini · embeddings · voice models", C.accent3], [I.globe, "SerpAPI · World Bank", "live quotes and news · India CPI inflation", C.accent3],
      [I.eye, "Phoenix (OTLP)", "traces, tokens, cost, sessions", C.accent4]];
    svc.forEach(([ic, h, d, col], i) => {
      const y = 1.25 + i * 0.77;
      card(s, 5.3, y, 4.2, 0.65, { name: `svc-${i + 1}` });
      dot(s, ic, 5.42, y + 0.1, 0.45, col);
      T(s, h, { x: 6.0, y: y + 0.08, w: 3.4, h: 0.25, fontSize: 11.5, bold: true });
      T(s, d, { x: 6.0, y: y + 0.34, w: 3.4, h: 0.25, fontSize: 9, color: C.accent6 });
      arrow(s, 4.72, y + 0.33, 5.28, y + 0.33);
    });
  }

  // ================================================================ 6. Models
  section = "AI models and concepts";
  pres.addSection({ title: section });
  {
    const s = slide("The AI models", [["F", 1], ["ive models, each with ", 0], ["o", 1], ["ne job", 0]], `The models. gpt-5-mini does all the text: the report explanation and the chat. We run it with reasoning effort low for speed; its hidden reasoning tokens bill as output. Price: 25 cents per million input tokens, 2.5 cents cached, 2 dollars output.
text-embedding-3-small turns the 830 knowledge documents and every question into 1,536-number vectors for retrieval: 2 cents per million tokens, so the whole knowledge base costs about 35 paise to embed.
Voice is optional: the browser's own speech recognition and voice are free and the default; OpenAI transcription and text-to-speech give a natural voice, metered and capped per user per day.`);
    const rows = [
      [I.robot, "gpt-5-mini", "Report story + details, chat (Arth), plan-change and deposit extraction", "$0.25 in · $0.025 cached · $2.00 out per 1M", C.accent1],
      [I.search, "text-embedding-3-small", "RAG: 830 docs → 1,632 chunks → 1,536-dim vectors; every query", "$0.02 per 1M · whole KB ≈ ₹0.35", C.text2],
      [I.mic, "gpt-4o-mini-transcribe", "Speech to text (optional), prompted with SIP, PPF, lakh, crore", "$0.003 per minute", C.accent4],
      [I.chat, "gpt-4o-mini-tts · voice \"sage\"", "Natural read-aloud in warm Indian English (optional)", "≈ $0.015 per minute", C.accent4],
      [I.globe, "Browser Web Speech API", "Default voice in and out, on the user's device", "free", C.accent5],
    ];
    rows.forEach(([ic, m, use, price, col], i) => {
      const y = 1.25 + i * 0.77;
      card(s, 0.5, y, 9, 0.65, { name: `model-${i + 1}` });
      dot(s, ic, 0.65, y + 0.1, 0.45, col);
      T(s, m, { x: 1.25, y: y + 0.08, w: 2.6, h: 0.5, fontSize: 12, bold: true, valign: "middle" });
      T(s, use, { x: 3.85, y: y + 0.08, w: 3.4, h: 0.5, fontSize: 10, valign: "middle" });
      T(s, price, { x: 7.3, y: y + 0.08, w: 2.1, h: 0.5, fontSize: 9.5, color: C.text2, bold: true, valign: "middle", align: "right" });
    });
  }

  // ================================================================ 7. Plan pipeline + time chart
  {
    const s = slide("How a plan is built", [["N", 1], ["umbers first, ", 0], ["t", 1], ["ext in parallel", 0]], `How a plan is built. Step one computes everything in 10 to 20 milliseconds. Step two screens stocks from one cached market call. Step three saves the report and the page opens with computed fallback text. Step four, in the background: one batched embeddings search and two structured-output calls at the same time, report_story and report_details.
The chart is one measured plan: the two calls take 12 and 13 seconds but overlap, so the user waits about 14 seconds for text, not 25, and is already reading the numbers. The n8n version ran four agents in a row and took one to three minutes.`);
    const st = [["1", "Compute", "10-20 ms: debt, risk plan, projection, monthly plan, deposits"], ["2", "Screen", "1 cached market call; rules pick NIFTY 50 names"],
      ["3", "Show", "report opens with numbers, charts and computed text"], ["4", "Explain", "1 embeddings search + 2 parallel AI calls swap the text in"]];
    st.forEach(([n, h, d], i) => {
      const y = 1.25 + i * 0.92;
      s.addShape(pres.shapes.OVAL, { x: 0.5, y, w: 0.5, h: 0.5, fill: { color: i === 3 ? C.accent1 : C.text2 }, line: { color: i === 3 ? C.accent1 : C.text2 } });
      T(s, n, { x: 0.5, y, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.background1, align: "center", valign: "middle" });
      T(s, h, { x: 1.15, y: y - 0.02, w: 3.2, h: 0.28, fontSize: 13, bold: true });
      T(s, d, { x: 1.15, y: y + 0.27, w: 3.3, h: 0.45, fontSize: 10, color: C.accent6 });
    });
    card(s, 4.85, 1.2, 4.65, 3.8, { name: "time-chart-card" });
    hbars(s, { x: 5.05, y: 1.35, w: 4.3, h: 3.5, title: "One measured plan (seconds)", max: 14,
      fmt: (v) => (v < 1 ? v.toFixed(2) : v.toFixed(1)) + " s",
      items: [["Numbers + charts", 0.02, C.accent5], ["Embeddings search", 0.5, C.text2], ["report_story", 12.3, C.accent1],
              ["report_details", 13.1, C.accent1], ["Text ready (parallel)", 13.7, C.accent2]] });
  }

  // ================================================================ 8. Structured outputs + grounding
  {
    const s = slide("Concept 1: structured outputs and grounding", [["S", 1], ["trict JSON in, ", 0], ["f", 1], ["acts in", 0]], `Structured outputs force the model's reply to match a strict JSON schema: every field required, nothing extra. The chat returns one object with everything: whether the message is on topic, the reply, suggestions, any plan changes, whether live data is needed, and in v1.5 a deposit request. Code then acts on those fields, so a plan change is applied by code, never by the model.
Grounding: the facts go in as JSON, the rules say every number must come from them, the priority order is fixed, instruments are named by category, and untrusted text is treated as data.`);
    mono(s, `chat_reply = {
  "on_topic": true,
  "reply": "…",
  "suggestions": ["…", "…"],
  "plan_changes": {"monthly_sip_total": 40000},
  "needs_live_data": false,
  "live_query": null,
  "deposit_request": {
    "wanted": true,
    "initial_amount": 300000,
    "monthly_installment": 10000,
    "goal_amount": 800000,
    "goal_date": "2030-04-01" }
}`, 0.5, 1.25, 4.9, 3.7, 10.5);
    const g = [[I.file, "FACTS block", "computed numbers as JSON; every figure must come from it"], [I.list, "Fixed priorities", "emergency fund → insurance → loans > 12% → goal"],
      [I.balance, "Category, not brand", "funds by type; banks only from the deposit planner"], [I.shield, "Untrusted text = data", "goal text and web snippets never become instructions"]];
    g.forEach(([ic, h, d], i) => {
      const y = 1.25 + i * 0.95;
      card(s, 5.65, y, 3.85, 0.82, { name: `ground-${i + 1}` });
      dot(s, ic, 5.8, y + 0.16, 0.48, C.text2);
      T(s, h, { x: 6.42, y: y + 0.1, w: 3.0, h: 0.28, fontSize: 12, bold: true });
      T(s, d, { x: 6.42, y: y + 0.38, w: 3.0, h: 0.4, fontSize: 9.5, color: C.accent6 });
    });
  }

  // ================================================================ 9. RAG
  {
    const s = slide("Concept 2: retrieval-augmented generation", [["R", 1], ["AG: answers from ", 0], ["o", 1], ["ur own documents", 0]], `RAG. We curated 830 finance documents: instruments, taxation, risk profiling, NIFTY 50 methodology. They are split into 1,632 chunks; each chunk becomes a 1,536-number vector and is stored in Postgres with pgvector.
At question time all queries are embedded in one request, the nearest chunks by cosine distance come back with scores, duplicates are removed, and the passages are numbered so the model can cite them as [1], [2].
One deliberate split: exact figures such as CAGR or drawdown never come from RAG; they come from the market API. RAG is for concepts and methodology.`);
    const flow = [[I.file, "830 docs", "curated markdown"], [I.layer, "1,632 chunks", "split for retrieval"], [I.robot, "Embeddings", "1,536 numbers each"],
      [I.db, "pgvector", "one Postgres table"], [I.search, "Cosine search", "top passages + scores"], [I.chat, "Cited answer", "[1], [2] in the text"]];
    flow.forEach(([ic, h, d], i) => {
      const x = 0.5 + i * 1.53;
      card(s, x, 1.35, 1.35, 1.75, { name: `rag-${i + 1}` });
      dot(s, ic, x + 0.42, 1.5, 0.5, i >= 4 ? C.accent1 : C.text2);
      T(s, h, { x: x + 0.08, y: 2.1, w: 1.19, h: 0.3, fontSize: 11.5, bold: true, align: "center" });
      T(s, d, { x: x + 0.08, y: 2.42, w: 1.19, h: 0.55, fontSize: 9, color: C.accent6, align: "center" });
      if (i < 5) arrow(s, x + 1.36, 2.22, x + 1.52, 2.22);
    });
    card(s, 0.5, 3.4, 4.35, 1.55, { fill: C.background1, name: "rag-for" });
    T(s, "RAG is for", { x: 0.7, y: 3.5, w: 4, h: 0.3, fontSize: 12.5, bold: true, color: C.accent5 });
    T(s, "concepts, methodology, tax rules, how to read a drawdown, why an emergency fund sits in a liquid fund", { x: 0.7, y: 3.85, w: 4.0, h: 1.0, fontSize: 10.5 });
    card(s, 5.15, 3.4, 4.35, 1.55, { fill: C.background1, name: "rag-not" });
    T(s, "Exact data is not RAG", { x: 5.35, y: 3.5, w: 4, h: 0.3, fontSize: 12.5, bold: true, color: C.accent2 });
    T(s, "CAGR, volatility, drawdown and index membership come from the market-analyzer; deposit rates from the rate table", { x: 5.35, y: 3.85, w: 4.0, h: 1.0, fontSize: 10.5 });
  }

  // ================================================================ 10. Guardrails
  {
    const s = slide("Concept 3: guardrails", [["S", 1], ["afe by default, ", 0], ["f", 1], ["ree when blocked", 0]], `Guardrails, in three layers. Input: prompt-injection phrases and Indian identifiers are caught by rules before any AI call; card numbers are confirmed with the Luhn checksum so random digits are not flagged. A blocked question costs nothing and answers in about a millisecond.
Topic: the chat call itself returns on_topic, so there is no separate guardrail model call.
Output: identifiers are masked before anything is shown, stored or traced. Free text the user typed in the goal is neutralised if it looks like an instruction.`);
    const layers = [[I.shield, "1. Input rules", ["prompt injection: \"ignore previous instructions\", \"system prompt\", \"developer mode\"…", "PAN, Aadhaar, phone, passport, IFSC", "card numbers confirmed with the Luhn checksum"], C.text2],
      [I.route, "2. Topic flag", ["on_topic returned by the same chat call", "kind, specific refusal for off-topic", "no extra model call"], C.accent1],
      [I.eye, "3. Output sanitizer", ["identifiers masked before show, store or trace", "goal text that looks like an instruction is dropped", "only the goal type is kept"], C.accent4]];
    layers.forEach(([ic, h, pts, col], i) => {
      const x = 0.5 + i * 3.05;
      card(s, x, 1.3, 2.85, 2.9, { name: `guard-${i + 1}` });
      dot(s, ic, x + 0.25, 1.5, 0.5, col);
      T(s, h, { x: x + 0.25, y: 2.12, w: 2.4, h: 0.32, fontSize: 14, bold: true });
      T(s, pts.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < pts.length - 1 } })), { x: x + 0.25, y: 2.5, w: 2.45, h: 1.6, fontSize: 10, paraSpaceAfter: 3 });
    });
    [["₹0", "cost of a blocked question"], ["~1 ms", "to decide"], ["0", "extra AI calls"]].forEach(([n, l], i) => {
      const x = 0.5 + i * 3.05;
      T(s, n, { x, y: 4.35, w: 1.1, h: 0.5, fontSize: 24, bold: true, color: C.accent1, valign: "middle" });
      T(s, l, { x: x + 1.1, y: 4.35, w: 1.8, h: 0.5, fontSize: 10.5, color: C.accent6, valign: "middle" });
    });
  }

  // ================================================================ 11. Router + chat
  {
    const s = slide("Concept 4: the router and Arth", [["C", 1], ["heapest source first, ", 0], ["c", 1], ["onfirm before change", 0]], `The chat router picks where an answer's data comes from, cheapest first. Rules decide instantly: concepts and plan questions stay local; time-sensitive topics such as share prices, the NIFTY level, index changes or repo rate go live through SerpAPI, unless today's startup refresh already has the answer. Stock suggestions get the watchlist with today's prices. New in v1.5: FD and RD questions use the team's rate table, free, while repo and post-office rates stay live.
Two patterns make the chat trustworthy. Extract, compute, present: the model fills a schema, code computes, a second call presents. And confirm before change: the app previews a plan change and waits for Yes.`);
    const routes = [["local", "concepts, my plan", C.text2], ["live", "prices, NIFTY, repo, news (SerpAPI)", C.accent3], ["picks", "watchlist + today's prices", C.accent4],
      ["deposits", "FD / RD rate table + planner (v1.5)", C.accent2], ["ask model", "unclear → model's needs_live_data flag", C.accent6]];
    T(s, "Router: 5 routes", { x: 0.5, y: 1.2, w: 4, h: 0.3, fontSize: 13, bold: true });
    routes.forEach(([r, d, col], i) => {
      const y = 1.6 + i * 0.62;
      pill(s, r, 0.5, y, 1.3, { fill: col, size: 10 });
      T(s, d, { x: 1.95, y, w: 2.9, h: 0.32, fontSize: 10.5, valign: "middle" });
    });
    card(s, 5.2, 1.2, 4.3, 1.75, { name: "two-step" });
    T(s, "Extract → compute → present", { x: 5.4, y: 1.3, w: 3.9, h: 0.3, fontSize: 12.5, bold: true, color: C.accent1 });
    T(s, "\"I have 3L now and 10K a month, I need 8L by 2030\" → deposit_request → planner in code → second call presents the FD and RD sequence. Also used for live data.",
      { x: 5.4, y: 1.65, w: 3.9, h: 1.2, fontSize: 10.5 });
    card(s, 5.2, 3.15, 4.3, 1.8, { name: "confirm" });
    T(s, "Confirm before change", { x: 5.4, y: 3.25, w: 3.9, h: 0.3, fontSize: 12.5, bold: true, color: C.accent1 });
    T(s, "\"What if I invest 40K a month?\" → preview \"I'll change: SIP ₹25K → ₹40K\" → Yes → the whole pipeline re-runs → link to the updated report with a change log.",
      { x: 5.4, y: 3.6, w: 3.9, h: 1.25, fontSize: 10.5 });
  }

  // ================================================================ 12. Observability + cost
  {
    const s = slide("Concept 5: observability and cost", [["S", 1], ["ee every step, ", 0], ["p", 1], ["rice every call", 0]], `Observability. The app traces itself with OpenTelemetry, using OpenInference span kinds that Phoenix understands: chain, LLM, retriever, embedding, tool and guardrail. Each plan or chat question is one trace; LLM spans carry the prompt, the answer, tokens and cost; the bank deposit planner shows up as its own tool span. Privacy: hashed user ids, masked identifiers, and content tracing can be switched off.
Cost: every call is metered and priced. The chart shows measured costs: about 45 paise for a plan, 11 paise for a chat question, 56 for a what-if, nothing for a blocked question. A thousand typical users a month would cost about 2,100 rupees.`);
    mono(s, `Build plan (CHAIN)
├─ Compute numbers (CHAIN)
├─ Bank deposit planner (TOOL)   ← v1.5
├─ Screen NIFTY 50 (TOOL)
└─ Write explanation (CHAIN)
   ├─ Knowledge-base search (RETRIEVER)
   │   └─ embeddings (EMBEDDING)
   ├─ report_story (LLM)
   └─ report_details (LLM)`, 0.5, 1.25, 4.5, 2.25, 11);
    card(s, 0.5, 3.7, 4.5, 1.25, { name: "phoenix-note" });
    dot(s, I.eye, 0.65, 3.85, 0.45, C.accent4);
    T(s, "Phoenix", { x: 1.25, y: 3.82, w: 3.6, h: 0.28, fontSize: 12, bold: true });
    T(s, "tokens (in, cached, out, reasoning), cost per span, sessions per user · hashed ids, masked IDs, content tracing optional",
      { x: 1.25, y: 4.12, w: 3.65, h: 0.75, fontSize: 9.5, color: C.accent6 });
    card(s, 5.25, 1.2, 4.25, 3.8, { name: "cost-chart-card" });
    vbars(s, { x: 5.4, y: 1.35, w: 3.95, h: 3.5, title: "Measured AI cost (₹, gpt-5-mini)", max: 0.56, fmt: (v) => "₹" + v.toFixed(2),
      cats: ["One plan", "Chat question", "What-if", "Blocked"], series: [["₹", C.text2, [0.45, 0.11, 0.56, 0]]] });
    T(s, "₹0.00", { x: 5.4 + 3 * (3.95 / 4), y: 1.35 + 3.5 - 0.75 - 0.26, w: 3.95 / 4, h: 0.22, fontSize: 9.5, bold: true, align: "center" });
  }

  // ================================================================ 13. Risk plan
  section = "Financial models";
  pres.addSection({ title: section });
  {
    const s = slide("Financial model 1: the risk plan", [["R", 1], ["isk you choose, ", 0], ["r", 1], ["isk your goal can carry", 0]], `The risk plan is decided in code so every later step follows one rulebook. The user picks Low, Medium or High through a gut-check question. Each level has a target mix of equity, fixed income, gold and cash, and an expected return blended from long-run class returns: equity 11, fixed income 7, gold 8, cash 4 percent.
Two caps apply. The horizon: under 3 years always means Low, 3 to 5 years at most Medium. And the safety net before direct stocks: a 5-year goal, 3 months of emergency fund, health cover, no loan above 12 percent, and a level above Low.`);
    const rows = [["", "Low", "Medium", "High"], ["Equity / fixed / gold / cash", "15 / 70 / 10 / 5", "50 / 35 / 10 / 5", "70 / 20 / 7 / 3"],
      ["Direct stocks (share of goal money)", "none", "up to 10%", "up to 25%"], ["Worst fall / yearly swing limits", "-", "35% / 30%", "35% (45% if 10+ yrs) / 38%"],
      ["Expected return (blend)", "7.55%", "8.95%", "9.78%"]];
    s.addTable(rows.map((r, i) => r.map((c, j) => ({ text: c, options: { bold: i === 0 || j === 0, fontSize: 10.5, color: i === 0 ? C.background1 : C.text1,
      fill: { color: i === 0 ? C.text2 : (i % 2 ? C.background1 : C.background2) }, valign: "middle" } }))),
      { x: 0.5, y: 1.25, w: 9, colW: [3.0, 1.8, 1.8, 2.4], rowH: 0.42, border: { type: "solid", pt: 0.5, color: "D9CCE3" }, margin: 0.06 });
    card(s, 0.5, 3.55, 4.35, 1.4, { name: "horizon-cap" });
    dot(s, I.chart, 0.7, 3.72, 0.48, C.accent3);
    T(s, "Horizon cap", { x: 1.35, y: 3.68, w: 3.4, h: 0.3, fontSize: 12.5, bold: true });
    T(s, "< 3 years → Low (85% fixed income, no shares) · 3-5 years → at most Medium. The report explains any reduction.", { x: 1.35, y: 4.0, w: 3.4, h: 0.9, fontSize: 10 });
    card(s, 5.15, 3.55, 4.35, 1.4, { name: "safety-net" });
    dot(s, I.shield, 5.35, 3.72, 0.48, C.accent2);
    T(s, "Safety net before stocks", { x: 6.0, y: 3.68, w: 3.4, h: 0.3, fontSize: 12.5, bold: true });
    T(s, "5+ year goal · 3+ months emergency fund · health cover · no loan > 12%. Otherwise \"Direct stocks · not yet\" with what to fix.", { x: 6.0, y: 4.0, w: 3.4, h: 0.9, fontSize: 10 });
  }

  // ================================================================ 14. Projection + monthly plan + tax + debt
  {
    const s = slide("Financial models 2-5", [["P", 1], ["rojection, monthly plan, ", 0], ["t", 1], ["ax and debt", 0]], `Four more models. The projection is the standard future-value formula: today's corpus compounding monthly plus the monthly contribution as an annuity, at the plan's expected return. Solving for the payment gives the required monthly amount. On track if the gap is zero or more; a small gap within 15 percent of the target; otherwise a large gap.
The monthly plan tops up the emergency fund first, aiming for six months within about a year but never more than 40 percent of free cash, then splits the goal money by the target mix, rounded to 100 rupees.
In-hand pay follows the FY 2026-27 new regime including the section 87A rebate up to 12 lakh. Debt uses weighted interest, debt-to-income, and avalanche or snowball ordering.`);
    mono(s, `r = expected return / 12,  n = months
FV  = corpus·(1+r)^n + PMT·((1+r)^n − 1)/r
PMT_required = (target − corpus·(1+r)^n)
               ÷ (((1+r)^n − 1)/r)
on track: gap ≥ 0 · small gap: ≤ 15% of target`, 0.5, 1.6, 4.6, 1.3, 10.5);
    T(s, "Goal projection (future value)", { x: 0.5, y: 1.22, w: 4.6, h: 0.3, fontSize: 12.5, bold: true, color: C.accent1 });
    T(s, "The report charts today's pace vs the pace needed, year by year.", { x: 0.5, y: 3.05, w: 4.6, h: 0.3, fontSize: 10, color: C.accent6 });
    const m = [[I.rupee, "Monthly plan", "emergency fund first (6 months in ~1 year, ≤ 40% of free cash), then the goal money split by the target mix"],
      [I.file, "In-hand from CTC", "basic 40%, PF 12%, gratuity 4.81%; FY 2026-27 slabs; 87A rebate to ₹12L; marginal relief; 4% cess"],
      [I.balance, "Debt", "weighted interest, EMI ÷ in-hand; loans > 12% paid first (avalanche), else snowball"]];
    m.forEach(([ic, h, d], i) => {
      const y = 1.25 + i * 1.25;
      card(s, 5.35, y, 4.15, 1.1, { name: `model2-${i + 1}` });
      dot(s, ic, 5.5, y + 0.2, 0.48, C.text2);
      T(s, h, { x: 6.12, y: y + 0.12, w: 3.25, h: 0.28, fontSize: 12, bold: true });
      T(s, d, { x: 6.12, y: y + 0.42, w: 3.25, h: 0.62, fontSize: 9.5, color: C.accent6 });
    });
    card(s, 0.5, 3.85, 4.6, 1.1, { name: "safety-meters" });
    dot(s, I.check, 0.65, 4.05, 0.48, C.accent5);
    T(s, "Safety-net meters", { x: 1.27, y: 3.95, w: 3.7, h: 0.28, fontSize: 12, bold: true });
    T(s, "emergency fund vs 6 months · term cover vs 10× income · health cover vs ₹10L", { x: 1.27, y: 4.25, w: 3.7, h: 0.6, fontSize: 9.5, color: C.accent6 });
  }

  // ================================================================ 15. Stock screen
  {
    const s = slide("Financial model 6: the stock screen", [["G", 1], ["rowth per unit of ", 0], ["s", 1], ["wing", 0]], `The NIFTY 50 screen runs in code on one cached market call, in milliseconds. Three measures from five years of history: CAGR, the steady yearly growth; volatility, how much the price typically swings in a year; and maximum drawdown, the deepest fall from a peak.
A stock passes if its worst fall and swing are within the plan's limits and it grew at least half its swing. Passing names are ranked by growth per unit of swing, with at most two per sector and five names in total. The AI only writes the one-line reason. When stocks are not allowed yet, the same rules build a watchlist for later, with today's prices in the chat.`);
    const kpi = [["CAGR", "steady yearly growth over 5 years"], ["Volatility", "how much the price swings in a year"], ["Max drawdown", "deepest fall from a peak (▼33% = ₹1L fell to ₹67K)"]];
    kpi.forEach(([h, d], i) => {
      const x = 0.5 + i * 3.05;
      card(s, x, 1.25, 2.85, 1.15, { name: `kpi-${i + 1}` });
      T(s, h, { x: x + 0.2, y: 1.35, w: 2.5, h: 0.35, fontSize: 15, bold: true, color: C.accent1 });
      T(s, d, { x: x + 0.2, y: 1.72, w: 2.5, h: 0.6, fontSize: 10, color: C.accent6 });
    });
    const rules = ["Worst fall within the plan's limit (35%, or 45% for High with 10+ years)", "Yearly swing within 30% (Medium) or 38% (High)",
      "Growth at least half the swing (CAGR ≥ 0.5 × volatility)", "Rank by CAGR ÷ volatility; max 2 per sector; up to 5 names"];
    T(s, "Rules applied in code", { x: 0.5, y: 2.65, w: 4.5, h: 0.3, fontSize: 13, bold: true });
    rules.forEach((r, i) => {
      const y = 3.05 + i * 0.47;
      dot(s, I.check, 0.5, y, 0.34, C.accent5);
      T(s, r, { x: 0.98, y, w: 4.2, h: 0.34, fontSize: 10.5, valign: "middle" });
    });
    card(s, 5.4, 2.65, 4.1, 2.3, { fill: C.text2, line: C.text2, name: "watchlist" });
    T(s, "Not safe yet? A watchlist instead", { x: 5.6, y: 2.8, w: 3.7, h: 0.32, fontSize: 13, bold: true, color: C.background1 });
    T(s, "Same rules, shown \"for when you're ready\", with the exact unlock (amount and time). The chat adds today's prices. Figures are historical (dataset to 26 Aug 2026), never predictions.",
      { x: 5.6, y: 3.2, w: 3.7, h: 1.6, fontSize: 10.5, color: C.background1 });
  }

  // ================================================================ 16. Bank deposit planner
  {
    const s = slide("Financial model 7 · new in v1.5", [["T", 1], ["he bank deposit ", 0], ["p", 1], ["lanner", 0]], `New in v1.5: the team's bank deposit planner, ported from the LangGraph project. The rate table has 211 rates from 10 banks, parsed from the team's documents without AI.
For a lump sum, the fixed-deposit search keeps the original idea: a state of balance and date, an action of one FD renewed as many times as fits, and a depth-first search over rate-sorted schemes. For a monthly amount, the recurring-deposit plan uses the standard bank maturity formula and a dynamic programme that fills every month to the goal date with the best mix.
Low-risk plans always run it: the report gets a bank deposits section and the fixed-income row names the bank. We fixed two maths bugs from the original, shown at the bottom right.`);
    const parts = [[I.db, "Rate table", "211 rates · 10 banks · parsed from the team's documents (no AI)"],
      [I.route, "FD: goal search", "state = (balance, date); action = an FD renewed n times; depth-first over rate-sorted schemes"],
      [I.layer, "RD: best mix", "M = Σ P·(1 + r/400)^((n−k+1)/3); a dynamic programme fills every month to the goal date"],
      [I.globe, "Inflation", "today's money = value ÷ (1 + i)^years; World Bank CPI (2.4% for 2025) or 4% fallback"]];
    parts.forEach(([ic, h, d], i) => {
      const y = 1.22 + i * 0.85;
      card(s, 0.5, y, 4.9, 0.75, { name: `dep-${i + 1}` });
      dot(s, ic, 0.63, y + 0.13, 0.48, i === 2 ? C.accent2 : C.text2);
      T(s, h, { x: 1.25, y: y + 0.07, w: 4.05, h: 0.27, fontSize: 11.5, bold: true });
      T(s, d, { x: 1.25, y: y + 0.34, w: 4.05, h: 0.4, fontSize: 9, color: C.accent6 });
    });
    card(s, 5.65, 1.22, 3.85, 1.85, { name: "dep-uses" });
    T(s, "Where it shows up", { x: 5.85, y: 1.3, w: 3.5, h: 0.3, fontSize: 12.5, bold: true, color: C.accent1 });
    T(s, ["Low risk or goal < 3 yrs → report section", "Fixed-income row: \"Bank RD: HDFC Bank 36m @ 7.1%\"", "Chat: rates from the table; plans on request"]
      .map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })), { x: 5.85, y: 1.65, w: 3.5, h: 1.35, fontSize: 10, paraSpaceAfter: 3 });
    card(s, 5.65, 3.25, 3.85, 1.7, { fill: "FFF6EC", line: "F2D3AD", name: "dep-fixes" });
    dot(s, I.bug, 5.8, 3.38, 0.42, C.accent3);
    T(s, "Fixed from the original", { x: 6.32, y: 3.4, w: 3.1, h: 0.36, fontSize: 12.5, bold: true, valign: "middle" });
    T(s, [{ text: "RD maturity: ₹11,03,576 → ₹62,311", options: { bold: true, breakLine: true } }, { text: "(₹5,000 a month, 7%, 1 year)", options: { breakLine: true } },
      { text: "Inflation over the whole period: ₹1,81,963 → ₹1,22,881", options: { bold: true, breakLine: true } }, { text: "(2-year FD × 5 at 5% inflation)" }],
      { x: 5.85, y: 3.85, w: 3.5, h: 1.05, fontSize: 9.5 });
  }

  // ================================================================ 17. Testing + sample run chart
  section = "Quality and close";
  pres.addSection({ title: section });
  {
    const s = slide("Testing and quality", [["3", 1], ["0 sample plans, ", 0], ["3", 1], ["0 passed", 0]], `How we know it works. 51 unit tests cover parsing, tax, the risk plan, the projection, chat changes, guardrails and the deposit maths. A parity test makes the Python planner and the n8n JavaScript planner return identical plans. Smoke tests run end to end with a mock OpenAI server for free and then with the real model.
The sample run builds 30 plans, 10 made-up personas at each risk level, checks the rules on each and prints every report to PDF. All 30 passed; the run cost about 15 rupees. The chart shows the horizon cap working: of the people who chose High, two were planned at Low because their goal was under three years away, and one at Medium.`);
    const t = [["51", "unit tests"], ["1", "parity test (Python = n8n)"], ["2", "smoke tests (mock + real AI)"], ["₹14.57", "for 30 real plans"]];
    t.forEach(([n, l], i) => {
      const y = 1.22 + i * 0.93;
      card(s, 0.5, y, 3.6, 0.8, { name: `test-${i + 1}` });
      T(s, n, { x: 0.7, y: y + 0.08, w: 1.4, h: 0.64, fontSize: 24, bold: true, color: C.accent1, valign: "middle" });
      T(s, l, { x: 2.1, y: y + 0.08, w: 1.9, h: 0.64, fontSize: 11, valign: "middle" });
    });
    card(s, 4.35, 1.2, 5.15, 3.8, { name: "sample-chart-card" });
    vbars(s, { x: 4.55, y: 1.35, w: 4.8, h: 3.55, title: "Sample run: risk chosen vs risk planned (10 each)", max: 10, fmt: (v) => String(v),
      cats: ["Chose Low", "Chose Medium", "Chose High"],
      series: [["Planned at Low", C.accent5, [10, 2, 2]], ["Planned at Medium", C.accent1, [0, 8, 1]], ["Planned at High", C.accent2, [0, 0, 7]]] });
  }

  // ================================================================ 18. Lessons
  {
    const s = slide("Lessons learned", [["B", 1], ["ugs we found, ", 0], ["a", 1], ["nd what they taught us", 0]], `Six of the bugs we found while building v1.5 and what each taught us. The teammate's RD formula overstated returns about 18 times: test money maths against a known answer. Python rounds halves to even while JavaScript rounds up, so the two planners picked different deposits: run two implementations against each other. The full bank name found no rates while the short name did: test with the names real users type. A table that did not add up because short months were hidden: show every rupee. Low risk did not use the planner when left to the model: make important steps deterministic. And a leaked key in a shared zip had to be revoked: never ship secrets.`);
    const L = [["RD formula 18× too high", "test money maths against a known answer"], ["Python rounds half to even", "test two implementations against each other"],
      ["\"State Bank of India\" found no rates", "test with names users actually type"], ["Deposit table didn't add up", "show every rupee (cash months row)"],
      ["Low risk skipped the planner", "make important steps deterministic"], ["Key leaked in a shared zip", "never ship .env; rotate keys"]];
    L.forEach(([b, l], i) => {
      const x = 0.5 + (i % 3) * 3.05, y = 1.25 + Math.floor(i / 3) * 1.85;
      card(s, x, y, 2.85, 1.6, { name: `lesson-${i + 1}` });
      dot(s, I.bug, x + 0.2, y + 0.2, 0.42, C.accent3);
      T(s, b, { x: x + 0.75, y: y + 0.18, w: 1.95, h: 0.5, fontSize: 11.5, bold: true, valign: "middle" });
      T(s, "Lesson: " + l, { x: x + 0.2, y: y + 0.85, w: 2.45, h: 0.6, fontSize: 10.5, color: C.text2 });
    });
  }

  // ================================================================ 19. Close
  {
    const s = pres.addSlide({ masterName: "PFA Dark", sectionTitle: section });
    s.addText(hi([["Thank you · ", 0], ["Q", 1], ["uestions?", 0]]).map((r) => ({ text: r.text, options: { color: r.options.color === C.accent1 ? C.accent3 : C.background1 } })), { placeholder: "title" });
    T(s, "Next steps we propose", { x: 0.6, y: 2.85, w: 8.8, h: 0.3, fontSize: 13, bold: true, color: C.background2 });
    ["Live bank rates (weekly refresh)", "Senior persona in the sample run", "Phoenix traces from the n8n bundle", "Email verification for a public demo"].forEach((t, i) =>
      pill(s, t, 0.6 + (i % 2) * 4.45, 3.3 + Math.floor(i / 2) * 0.48, 4.25, { fill: C.background1, color: C.text2, size: 10.5, h: 0.36 }));
    T(s, "Personal Finance Advisor · Python v1.5 · Group 2 · Educational information, not licensed financial advice.", { x: 0.6, y: 5.0, w: 8.8, h: 0.3, fontSize: 9, color: C.background2 });
    s.addNotes(`Close. Thank you. Four next steps we propose: refresh bank rates weekly instead of from documents; add a senior persona with a shortfall to the sample run so senior deposit rates are exercised; get the n8n observability bundle to actually send traces; and add email verification before any public demo. Questions?`);
  }

  await pres.writeFile({ fileName: OUT });
  if (APPLY) await require(APPLY).applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
