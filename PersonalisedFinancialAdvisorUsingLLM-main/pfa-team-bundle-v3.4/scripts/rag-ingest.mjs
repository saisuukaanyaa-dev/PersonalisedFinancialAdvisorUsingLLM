// Fast, parallel, resumable RAG ingestion for the PFA knowledge base.
//
// Writes exactly the rows n8n's "Postgres PGVector Store" node reads (table finance_kb_embeddings:
// id uuid, text, metadata jsonb, embedding vector; cosine distance), so Knowledge_Base_Search works unchanged.
//
// Runs inside the n8n image (Node 24 + the `pg` driver n8n already ships) - no extra dependencies.
// Why it is fast: n8n's Store node embeds + inserts one FILE at a time (830 sequential API calls, no timeout).
// This script embeds ~96 CHUNKS per request, runs 4 requests in parallel, retries with back-off, times out
// hung calls, and skips files that are already loaded - so a stopped run simply resumes.
//
// Env: OPENAI_API_KEY (required), OPENAI_BASE_URL, EMBED_MODEL, KB_DIR, KB_TABLE, DB_POSTGRESDB_* (from n8n env)
// Args: --force (wipe and reload)  --concurrency N  --batch N  --dry-run
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const pg = require('/usr/local/lib/node_modules/n8n/node_modules/pg');

const arg = (name, dflt) => {
  const i = process.argv.indexOf(name);
  return i === -1 ? dflt : (process.argv[i + 1] && !process.argv[i + 1].startsWith('--') ? process.argv[i + 1] : true);
};
const FORCE = process.argv.includes('--force');
const DRY = process.argv.includes('--dry-run');
const CONCURRENCY = Math.max(1, Number(arg('--concurrency', process.env.RAG_CONCURRENCY || 4)));
const BATCH = Math.max(1, Number(arg('--batch', process.env.RAG_BATCH || 96)));      // chunks per embeddings request
const MODEL = process.env.EMBED_MODEL || 'text-embedding-3-small';
const BASE = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '');
const KEY = process.env.OPENAI_API_KEY || '';
const KB_DIR = process.env.KB_DIR || '/home/node/knowledge-base';
const TABLE = process.env.KB_TABLE || 'finance_kb_embeddings';
const CHUNK = 800, OVERLAP = 100;                                                    // same as the n8n splitter
const TIMEOUT_MS = 60_000, MAX_RETRIES = 6;

if (!/^[a-z_][a-z0-9_]*$/.test(TABLE)) throw new Error('KB_TABLE must be a plain identifier');
if (!KEY && !DRY) { console.error('OPENAI_API_KEY is not set.'); process.exit(2); }

// ---------------------------------------------------------------- splitting (LangChain RecursiveCharacterTextSplitter)
function splitRecursive(text, separators = ['\n\n', '\n', ' ', '']) {
  let sep = separators[separators.length - 1], rest = [];
  for (let i = 0; i < separators.length; i++) {
    if (separators[i] === '' || text.includes(separators[i])) { sep = separators[i]; rest = separators.slice(i + 1); break; }
  }
  const pieces = (sep ? text.split(sep) : [...text]).filter(p => p !== '');
  const out = [], good = [];
  const flush = () => { if (good.length) { out.push(...merge(good.splice(0), sep)); } };
  for (const p of pieces) {
    if (p.length < CHUNK) good.push(p);
    else { flush(); out.push(...(rest.length ? splitRecursive(p, rest) : [p])); }
  }
  flush();
  return out;
}
function merge(splits, sep) {
  const docs = []; let cur = []; let total = 0;
  for (const d of splits) {
    const add = d.length + (cur.length ? sep.length : 0);
    if (total + add > CHUNK && cur.length) {
      const doc = cur.join(sep).trim(); if (doc) docs.push(doc);
      while (total > OVERLAP || (total + add > CHUNK && total > 0)) {
        total -= cur[0].length + (cur.length > 1 ? sep.length : 0); cur.shift();
      }
    }
    cur.push(d); total += d.length + (cur.length > 1 ? sep.length : 0);
  }
  const doc = cur.join(sep).trim(); if (doc) docs.push(doc);
  return docs;
}

// ---------------------------------------------------------------- OpenAI embeddings with timeout + retry
const sleep = ms => new Promise(r => setTimeout(r, ms));
let retries = 0;
async function embed(texts) {
  for (let attempt = 0; ; attempt++) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    try {
      const res = await fetch(`${BASE}/embeddings`, {
        method: 'POST', signal: ctrl.signal,
        headers: { 'content-type': 'application/json', authorization: `Bearer ${KEY}` },
        // n8n's embeddings node strips newlines before embedding (stripNewLines: true)
        body: JSON.stringify({ model: MODEL, input: texts.map(s => s.replace(/\n/g, ' ')) }),
      });
      if (res.ok) {
        const j = await res.json();
        return j.data.sort((a, b) => a.index - b.index).map(d => d.embedding);
      }
      const body = await res.text();
      if (res.status === 401) throw Object.assign(new Error('OpenAI rejected the API key (401).'), { fatal: true });
      if (res.status === 400 || res.status === 404) throw Object.assign(new Error(`OpenAI ${res.status}: ${body.slice(0, 200)}`), { fatal: true });
      if (res.status === 429 && /insufficient_quota/.test(body)) throw Object.assign(new Error('OpenAI quota exhausted (429 insufficient_quota) - check billing.'), { fatal: true });
      if (attempt >= MAX_RETRIES) throw new Error(`OpenAI ${res.status} after ${MAX_RETRIES} retries: ${body.slice(0, 200)}`);
      const ra = Number(res.headers.get('retry-after'));
      await sleep(Number.isFinite(ra) && ra > 0 ? ra * 1000 : Math.min(30_000, 1000 * 2 ** attempt) + Math.random() * 500);
      retries++;
    } catch (e) {
      if (e.fatal || attempt >= MAX_RETRIES) throw e;
      retries++;
      await sleep(Math.min(30_000, 1000 * 2 ** attempt) + Math.random() * 500);           // timeout / network error
    } finally { clearTimeout(t); }
  }
}

// ---------------------------------------------------------------- main
const pool = new pg.Pool({
  host: process.env.DB_POSTGRESDB_HOST || 'postgres', port: Number(process.env.DB_POSTGRESDB_PORT || 5432),
  database: process.env.DB_POSTGRESDB_DATABASE, user: process.env.DB_POSTGRESDB_USER,
  password: process.env.DB_POSTGRESDB_PASSWORD, max: CONCURRENCY + 1,
});

const t0 = Date.now();
try {
  await pool.query('CREATE EXTENSION IF NOT EXISTS vector');
  const exists = (await pool.query('select to_regclass($1) is not null as e', [`public.${TABLE}`])).rows[0].e;
  if (!exists) {
    await pool.query(`CREATE TABLE ${TABLE} (
      "id" uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY, "text" text, "metadata" jsonb, "embedding" vector(1536))`);
    await pool.query(`CREATE INDEX IF NOT EXISTS ${TABLE}_hnsw ON ${TABLE} USING hnsw ("embedding" vector_cosine_ops)`);
  }
  if (FORCE) { await pool.query(`TRUNCATE ${TABLE}`); console.log('Cleared existing chunks (--force).'); }

  // What is already loaded? (file -> sha). A changed file is reloaded; an unchanged one is skipped.
  const loaded = new Map((await pool.query(
    `select metadata->>'file' as f, min(metadata->>'sha') as s from ${TABLE} group by 1`)).rows.map(r => [r.f, r.s]));

  const files = fs.readdirSync(KB_DIR).filter(f => f.endsWith('.md')).sort();
  const todo = [];
  let skipped = 0, legacy = 0;
  for (const f of files) {
    const text = fs.readFileSync(path.join(KB_DIR, f), 'utf8');
    const sha = crypto.createHash('sha1').update(text).digest('hex');
    if (loaded.get(f) === sha) { skipped++; continue; }
    if (loaded.has(f)) await pool.query(`delete from ${TABLE} where metadata->>'file' = $1`, [f]);
    const chunks = splitRecursive(text);
    todo.push({ f, sha, chunks });
  }
  // rows written by the n8n Store node (no 'file' key) cannot be matched - warn, never mix silently
  legacy = Number((await pool.query(`select count(*) from ${TABLE} where metadata->>'file' is null`)).rows[0].count);
  if (legacy && !FORCE) {
    console.error(`Found ${legacy} chunks from an earlier n8n-node ingestion (possibly a different embedding model).`);
    console.error('Mixing them with new chunks would degrade search. Run: ./scripts/ingest-rag.sh --force');
    await pool.end(); process.exit(1);
  }

  const totalChunks = todo.reduce((s, x) => s + x.chunks.length, 0);
  const estTokens = Math.round(todo.reduce((s, x) => s + x.chunks.join('').length, 0) / 4);
  console.log(`${files.length} files: ${skipped} already loaded, ${todo.length} to embed (${totalChunks} chunks, ~${estTokens.toLocaleString()} tokens).`);
  console.log(`Model ${MODEL} · ${BATCH} chunks/request · ${CONCURRENCY} requests in parallel`);
  if (DRY || !todo.length) { await pool.end(); process.exit(0); }

  // Pack whole files into jobs of ~BATCH chunks, so each job commits complete files (clean resume).
  const jobs = []; let cur = [];
  for (const x of todo) {
    if (cur.length && cur.reduce((s, y) => s + y.chunks.length, 0) + x.chunks.length > BATCH) { jobs.push(cur); cur = []; }
    cur.push(x);
  }
  if (cur.length) jobs.push(cur);

  let doneFiles = 0, doneChunks = 0, next = 0, failed = null;
  const progress = () => {
    const s = (Date.now() - t0) / 1000, rate = doneChunks / Math.max(s, 0.001);
    const eta = rate > 0 ? Math.round((totalChunks - doneChunks) / rate) : 0;
    process.stdout.write(`\r  ${doneFiles}/${todo.length} files · ${doneChunks}/${totalChunks} chunks · ${rate.toFixed(0)} chunks/s · ETA ${eta}s · retries ${retries}   `);
  };
  async function worker() {
    while (!failed && next < jobs.length) {
      const job = jobs[next++];
      const rows = job.flatMap(x => x.chunks.map((c, i) => ({ text: c, meta: {
        source: path.join(KB_DIR, x.f), file: x.f, sha: x.sha, chunk: i, chunks: x.chunks.length, loader: 'rag-ingest.mjs' } })));
      try {
        const vecs = [];
        for (let i = 0; i < rows.length; i += 2048) vecs.push(...await embed(rows.slice(i, i + 2048).map(r => r.text)));
        const client = await pool.connect();
        try {
          await client.query('BEGIN');
          for (let i = 0; i < rows.length; i += 200) {                                 // bounded statement size
            const part = rows.slice(i, i + 200), vals = [], ph = [];
            part.forEach((r, j) => { ph.push(`($${3 * j + 1}, $${3 * j + 2}::jsonb, $${3 * j + 3}::vector)`);
              vals.push(r.text, JSON.stringify(r.meta), `[${vecs[i + j].join(',')}]`); });
            await client.query(`INSERT INTO ${TABLE} ("text", "metadata", "embedding") VALUES ${ph.join(',')}`, vals);
          }
          await client.query('COMMIT');
        } catch (e) { await client.query('ROLLBACK'); throw e; } finally { client.release(); }
        doneFiles += job.length; doneChunks += rows.length; progress();
      } catch (e) { failed = e; }
    }
  }
  progress();
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, jobs.length) }, worker));
  console.log('');
  if (failed) throw failed;
  const n = (await pool.query(`select count(*) from ${TABLE}`)).rows[0].count;
  console.log(`Done in ${((Date.now() - t0) / 1000).toFixed(1)}s - ${n} chunks in ${TABLE}.`);
  await pool.end();
} catch (e) {
  console.log('');
  console.error(`Ingestion stopped: ${e.message}`);
  console.error('Everything committed so far is kept - run the same command again to resume.');
  await pool.end().catch(() => {});
  process.exit(1);
}
