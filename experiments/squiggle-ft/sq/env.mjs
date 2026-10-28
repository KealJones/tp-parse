// Browser pieces Squiggle's tools expect, provided in node:
//   DOMParser          linkedom, with a browser-like body.innerText (fetch_url)
//   document + iframe  run_js's sandbox: sandbox.html's own worker code, run in a worker thread
//   fetch              cached on disk (W.netCache) and polite; the relay's /api/search
//                      answers from Wikipedia's search API plus DuckDuckGo's Instant Answer
//                      API (the relay itself scrapes DuckDuckGo Lite, which blocks servers)
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { Worker } from 'node:worker_threads';
import { DOMParser as LinkeDOMParser } from 'linkedom';
import { W } from './world.mjs';
import { RELAY } from './stubs/github.mjs';

export const UA = 'squiggle-ft/1.0 (fine-tune data for an on-device agent; https://github.com/KealJones/tp-parse)';
const RELAY_UA = 'Mozilla/5.0 (compatible; squiggle-relay)';   // what the real relay sends

// ── DOMParser + innerText ────────────────────────────────────────────────
const BLOCK2 = new Set(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'table', 'figure']);
const BLOCK1 = new Set(['div', 'section', 'article', 'header', 'footer', 'nav', 'aside', 'main', 'ul', 'ol', 'li', 'dl', 'dt', 'dd',
  'tr', 'form', 'fieldset', 'address', 'figcaption', 'caption', 'details', 'summary', 'hr', 'tbody', 'thead', 'tfoot', 'center']);
function innerText(node) {
  const out = [];
  const walk = (n) => {
    if (n.nodeType === 3) { out.push(String(n.textContent).replace(/\s+/g, ' ')); return; }
    if (n.nodeType !== 1) return;
    const tag = String(n.tagName || '').toLowerCase();
    if (tag === 'br') { out.push('\n'); return; }
    const sep = BLOCK2.has(tag) ? '\n\n' : BLOCK1.has(tag) ? '\n' : '';
    if (sep) out.push(sep);
    for (const c of n.childNodes || []) walk(c);
    if (tag === 'td' || tag === 'th') out.push('\t');
    if (sep) out.push(sep);
  };
  walk(node);
  return out.join('').split('\n').map(l => l.replace(/^ +| +$/g, '')).join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
globalThis.DOMParser = class {
  parseFromString(text, type) {
    const doc = new LinkeDOMParser().parseFromString(text, type);
    if (doc.body) Object.defineProperty(doc.body, 'innerText', { get() { return innerText(this); }, configurable: true });
    return doc;
  }
};

// ── run_js sandbox (app/sandbox.html's worker, unchanged) ────────────────
let WORKER_SRC = null;
export function loadSandbox(squiggleDir) {
  const html = fs.readFileSync(path.join(squiggleDir, 'app', 'sandbox.html'), 'utf8');
  const m = html.match(/const WORKER_SRC = `([\s\S]*?)`;/);
  if (!m) throw new Error('sandbox.html: WORKER_SRC not found');
  WORKER_SRC = new Function('return `' + m[1] + '`;')();
}
const listeners = [];
globalThis.addEventListener = (type, fn) => { if (type === 'message') listeners.push(fn); };
globalThis.removeEventListener = () => {};
const dispatch = (source, data) => setImmediate(() => listeners.forEach(f => f({ source, data })));
const SHIM = `
const { parentPort } = require('node:worker_threads');
globalThis.postMessage = (d) => parentPort.postMessage(d);
for (const k of ['process', 'require', 'Buffer', 'module', 'exports', 'fetch', 'WebSocket']) { try { delete globalThis[k]; } catch {} }
parentPort.on('message', (d) => globalThis.onmessage && globalThis.onmessage({ data: d }));
`;
class SandboxFrame {
  constructor() {
    this.worker = null;
    const self = this;
    this.contentWindow = {
      postMessage(msg) {
        if (msg && msg.kill) { if (self.worker) { self.worker.terminate(); self.worker = null; } return; }
        if (!self.worker) {
          self.worker = new Worker(`(() => { ${SHIM} })(); ${WORKER_SRC}`, { eval: true, resourceLimits: { maxOldGenerationSizeMb: 256 } });
          self.worker.on('message', (d) => dispatch(self.contentWindow, d));
          self.worker.on('error', () => {});
          self.worker.unref();
        }
        self.worker.postMessage({ id: msg.id, code: msg.code, args: msg.args });
      },
    };
  }
  setAttribute() {}
  get style() { return {}; }
}
globalThis.document = {
  createElement: (tag) => (tag === 'iframe' ? new SandboxFrame() : {}),
  body: { appendChild(frame) { if (frame instanceof SandboxFrame) dispatch(frame.contentWindow, { ready: true }); } },
};

// ── fetch: disk cache, the fake relay, offline mode ──────────────────────
const realFetch = globalThis.__realFetch = globalThis.__realFetch || globalThis.fetch;
const lastHit = new Map();
async function polite(host) {
  const wait = 250 - (Date.now() - (lastHit.get(host) || 0));
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastHit.set(host, Date.now());
}
const cachePath = (key) => W.netCache && path.join(W.netCache, crypto.createHash('sha1').update(key).digest('hex').slice(0, 24) + '.json');
export const netStats = { hits: 0, misses: 0, errors: 0 };
// Web results the episode needed but couldn't fetch (no network from here): the teacher supplies them
// (teach.py tool-result), and they go in the cache under the same key. W.noNet lists keys known to be missing,
// so replays don't wait on the network again.
export const missing = [];
const noteMissing = (m) => { if (!missing.some(x => x.key === m.key)) missing.push(m); };

// GET with the cache. Returns { status, type, body, url } or throws like fetch does.
export async function cachedGet(url, headers = {}) {
  const file = cachePath(url);
  if (file && fs.existsSync(file)) { netStats.hits++; return JSON.parse(fs.readFileSync(file, 'utf8')); }
  if (W.offline || (W.noNet && W.noNet.includes(url))) { netStats.errors++; throw new TypeError(`fetch failed (offline, not cached: ${url})`); }
  netStats.misses++;
  let r;
  for (let attempt = 0; ; attempt++) {
    await polite(new URL(url).host);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 20000);
    try { r = await realFetch(url, { headers: { 'User-Agent': UA, ...headers }, redirect: 'follow', signal: ctrl.signal }); }
    catch (e) { netStats.errors++; throw new TypeError('fetch failed: ' + (e && e.message)); }
    finally { clearTimeout(timer); }
    if (r.status !== 429 && r.status < 500) break;
    // Rate-limited or a server error: back off twice, then report it missing (never cached).
    if (attempt >= 2) { netStats.errors++; throw new TypeError(`fetch failed: HTTP ${r.status}`); }
    await new Promise(res => setTimeout(res, 3000 * (attempt + 1)));
  }
  const type = r.headers.get('content-type') || '';
  let body = '';
  if (/^(text\/|application\/(json|xml|xhtml|javascript)|.*\+xml)/i.test(type) || !type) body = (await r.text()).slice(0, 3_000_000);
  else { await r.arrayBuffer().catch(() => null); body = ''; }
  const out = { status: r.status, type, body, url: r.url || url };
  if (file && (r.status === 200 || r.status === 404)) {
    const tmp = file + '.' + process.pid;
    fs.writeFileSync(tmp, JSON.stringify(out));
    fs.renameSync(tmp, file);
  }
  return out;
}

const decode = (s) => String(s || '').replace(/<[^>]*>/g, '').replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim();

let instantAnswer = null;
export function setInstantAnswer(fn) { instantAnswer = fn; }

// The relay's /api/search: { query, answer, results: [{ title, url, snippet }] }.
async function relaySearch(q, n) {
  const query = String(q || '').trim().slice(0, 300);
  if (!query) return { status: 400, body: { error: 'Pass a search query: ?q=...' } };
  const over = cachePath('search:' + query);
  if (over && fs.existsSync(over)) {
    netStats.hits++;
    const r = JSON.parse(fs.readFileSync(over, 'utf8'));
    return { status: 200, body: { query, answer: null, results: JSON.parse(r.body) } };
  }
  const wiki = `https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&srprop=snippet&srlimit=${Math.min(Math.max(n, 1), 10)}&srsearch=${encodeURIComponent(query)}`;
  const ddg = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1&t=squiggle`;
  const [w, d] = await Promise.all([
    cachedGet(wiki).catch(() => null),
    cachedGet(ddg, { 'User-Agent': RELAY_UA, Accept: 'application/json' }).catch(() => null),
  ]);
  let answer = null;
  try { answer = d && d.status === 200 && instantAnswer ? instantAnswer(JSON.parse(d.body)) : null; } catch {}
  let results = [];
  try {
    results = (JSON.parse(w.body).query.search || []).map(x => ({
      title: x.title, url: 'https://en.wikipedia.org/wiki/' + encodeURIComponent(x.title.replace(/ /g, '_')).replace(/%2F/g, '/').replace(/%3A/g, ':').replace(/%2C/g, ','),
      snippet: decode(x.snippet),
    }));
  } catch {}
  if (!w) noteMissing({ kind: 'search', key: 'search:' + query, query });
  if (!w && !answer) return { status: 503, body: { error: 'Search is not reachable right now. Try again in a little while.' } };
  return { status: 200, body: { query, answer, results } };
}

globalThis.fetch = async (input, init = {}) => {
  const url = typeof input === 'string' ? input : input.url;
  if (url.startsWith(RELAY)) {
    const u = new URL(url);
    if (u.pathname.endsWith('/search')) {
      const r = await relaySearch(u.searchParams.get('q'), Number(u.searchParams.get('n')) || 8);
      return new Response(JSON.stringify(r.body), { status: r.status, headers: { 'content-type': 'application/json' } });
    }
    return new Response(JSON.stringify({ error: 'not found' }), { status: 404, headers: { 'content-type': 'application/json' } });
  }
  if ((init.method || 'GET').toUpperCase() !== 'GET' || init.body) {
    if (W.offline) throw new TypeError('fetch failed (offline)');
    return realFetch(input, init);
  }
  let r;
  try { r = await cachedGet(url); }
  catch (e) { noteMissing({ kind: 'url', key: url, url }); throw e; }
  return new Response(r.body, { status: r.status, headers: { 'content-type': r.type } });
};
