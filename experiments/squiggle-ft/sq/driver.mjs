// Runs ONE episode through Squiggle's real agent loop (app/src/agent.js
// runTurn, unchanged) on the phone settings: Gemma 3 270M engine
// (engine-wllama.js), 4096-token context, smart context, no embeddings.
//
//   SQUIGGLE_DIR=… node --import ./sq/register.mjs sq/driver.mjs
//
// JSON lines on stdin/stdout (console output goes to stderr):
//   in   {"t":"episode", ...spec}            first line (see README "Episode spec")
//   out  {"t":"gen", "id", "kind", "messages", "max_tokens"}   the model must write a reply
//   in   {"t":"out", "id", "text"}           …its raw text (thinking + call, or a reply)
//   out  {"t":"turn", "n", "reply", "tools", "task", "waiting"}  a user turn finished
//   in   {"t":"user", "text", "session"?} | {"t":"end"}    next user message, or stop
//   out  {"t":"done", "calls", "sessions", "recipes", "facts", "net"}
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';
import { W } from './world.mjs';
import { loadSandbox, setInstantAnswer, netStats, missing } from './env.mjs';

// Resolves once the line is handed to the OS (process.exit would drop a pending pipe write).
const out = (o) => new Promise(r => process.stdout.write(JSON.stringify(o) + '\n', r));
for (const k of ['log', 'info', 'debug', 'warn', 'error']) console[k] = (...a) => process.stderr.write(a.map(String).join(' ') + '\n');

const rl = readline.createInterface({ input: process.stdin });
const queue = [];
const waiters = [];
rl.on('line', (line) => {
  if (!line.trim()) return;
  const msg = JSON.parse(line);
  const w = waiters.findIndex(x => x.match(msg));
  if (w >= 0) waiters.splice(w, 1)[0].resolve(msg); else queue.push(msg);
});
rl.on('close', () => { for (const w of waiters.splice(0)) w.resolve({ t: 'end' }); });
function next(match) {
  const i = queue.findIndex(match);
  if (i >= 0) return Promise.resolve(queue.splice(i, 1)[0]);
  return new Promise(resolve => waiters.push({ match, resolve }));
}

// What kind of model call this is (docs/harness.md: chat phase, step, final reply; or a background job).
const BACKGROUND = /^(You write short titles|You maintain a running summary|You summarize side discussions|You extract lasting facts|You turn a finished task into a reusable recipe)/;
function kindOf(messages) {
  const sys = messages[0] && messages[0].role === 'system' ? String(messages[0].content) : '';
  const firstUser = (messages.find(m => m.role === 'user') || {}).content || '';
  if (BACKGROUND.test(sys)) return 'background';
  if (/\n\nWork on step \d+ now: /.test(firstUser)) return 'step';
  if (/\n\nEvery step is done\. Write the reply to this request now/.test(firstUser)) return 'final';
  return 'chat';
}

let genId = 0;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function main() {
  const spec = await next(m => m.t === 'episode');
  // A different "today" per episode (spec.dateShiftDays), so prompts don't all carry the same date line.
  if (spec.dateShiftDays) {
    const RealDate = Date, shift = spec.dateShiftDays * 86400000;
    class ShiftedDate extends RealDate {
      constructor(...a) { if (a.length) super(...a); else super(RealDate.now() + shift); }
      static now() { return RealDate.now() + shift; }
    }
    globalThis.Date = ShiftedDate;
  }
  const squiggle = path.resolve(process.env.SQUIGGLE_DIR);
  W.root = spec.root || fs.mkdtempSync(path.join(os.tmpdir(), 'sqep-'));
  W.repoCache = spec.repoCache || path.join(os.tmpdir(), 'sq-repo-cache');
  W.netCache = spec.netCache || null;
  W.offline = Boolean(spec.offline);
  W.approve = spec.approve || 'deny';
  W.noNet = spec.noNet || [];
  fs.mkdirSync(W.repoCache, { recursive: true });
  if (W.netCache) fs.mkdirSync(W.netCache, { recursive: true });
  fs.mkdirSync(path.join(W.root, 'repos'), { recursive: true });
  loadSandbox(squiggle);
  const world = spec.world || {};
  W.repos = world.repos || [];

  W.generate = async ({ messages, max_tokens, temperature }) => {
    const kind = kindOf(messages);
    const entry = W.log[W.log.length - 1];
    entry.kind = kind;
    if (kind === 'background') return '';          // titles, summaries, facts: not this experiment's job
    const id = ++genId;
    out({ t: 'gen', id, kind, messages, max_tokens, temperature, missing: missing.splice(0) });
    const r = await next(m => m.t === 'out' && m.id === id);
    if (r.meta) entry.meta = r.meta;
    if (r.error) { entry.error = r.error; throw new Error(r.error); }   // like wllama when the prompt overflows n_ctx
    return r.text;
  };

  // Seed the storage repo: home files, past chats, recipes. Facts go through memory.add.
  for (const [rel, text] of Object.entries(world.home || {})) W.files.set('home/' + rel.replace(/^\/+/, ''), String(text));
  for (const s of world.sessions || []) W.files.set(`sessions/${s.id}.json`, JSON.stringify(s));
  if (world.recipes && world.recipes.length) W.files.set('memory/recipes.jsonl', world.recipes.map(r => JSON.stringify(r)).join('\n') + '\n');

  const src = (f) => pathToFileURL(path.join(squiggle, 'app', 'src', f)).href;
  const worker = await import(pathToFileURL(path.join(squiggle, 'worker', 'index.js')).href);
  setInstantAnswer(worker.instantAnswer);
  const engine = await import(src('engine.js'));
  const agent = await import(src('agent.js'));
  const sessions = await import(src('sessions.js'));
  const memory = await import(src('memory.js'));
  const recipes = await import(src('recipes.js'));
  await sessions.loadAll();
  await memory.load();
  await recipes.load();
  for (const f of world.facts || []) memory.add({ s: f.s, p: f.p, o: f.o, note: f.note });

  const ctx = (spec.settings && spec.settings.contextSize) || 4096;
  await engine.load('G3', ctx, { fast: false });
  Object.assign(agent.settings, { model: 'G3', contextSize: ctx, fastDecode: false, contextMode: 'smart', semantic: false, learn: false, tools: null }, spec.agentSettings || {});

  const chats = new Map();
  const chat = (key = 'main') => {
    if (!chats.has(key)) chats.set(key, sessions.newSession());
    return chats.get(key);
  };
  let msg = { t: 'user', text: spec.first, session: spec.firstSession || 'main' };
  let n = 0;
  while (msg && msg.t === 'user') {
    const session = chat(msg.session || 'main');
    // The app names a new chat in the background with the model; skip that call.
    if (session.title === 'New chat') session.title = String(msg.text).replace(/\s+/g, ' ').slice(0, 60);
    const before = W.log.length;
    const reply = await agent.runTurn({ session, threadId: null, text: msg.text, ui: { onApproval: (req, decide) => decide(W.approve) } });
    await sleep(1700);   // afterTurn's background work (recipe saving) runs 1.5 s after the turn
    const task = reply.task && session.tasks[reply.task];
    out({ t: 'turn', n: n++, session: msg.session || 'main', reply: reply.content, tools: reply.tools || [],
      task: task ? JSON.parse(JSON.stringify(task)) : null, waiting: Boolean(task && task.waiting), calls: W.log.length - before,
      asked: (reply.tools || []).some(t => t.name === 'need' && /^asked you/.test(t.label || '')) });
    msg = await next(m => m.t === 'user' || m.t === 'end');
  }
  await sessions.flush({ sync: false });
  await out({ t: 'done', calls: W.log, sessions: [...chats.entries()].map(([key, s]) => ({ key, session: JSON.parse(JSON.stringify(s)) })),
    recipes: recipes.list(), facts: memory.all(), net: netStats, missing: missing.splice(0) });
  if (!spec.keepRoot && !spec.root) fs.rmSync(W.root, { recursive: true, force: true });
}

main().then(() => process.exit(0), async (e) => {
  await out({ t: 'error', error: String(e && e.stack || e) });
  process.exit(1);
});
