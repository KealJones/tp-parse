// Squiggle's own format functions over JSON lines, for Python (sqrun.AppFormat):
//   {"op":"parse","text"}   -> { thinking, text, open, calls: [{name, arguments}], looping }   (engine-wllama.js)
//   {"op":"messages","messages","tools","active"} -> gemmaMessages(...)
//   {"op":"system"}         -> agent.js LITE_SYSTEM
//   {"op":"specs"}          -> every tool the model may call: tasks.js HARNESS_SPECS + tools.js toolSpecs()
import readline from 'node:readline';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const src = (f) => pathToFileURL(path.join(path.resolve(process.env.SQUIGGLE_DIR), 'app', 'src', f)).href;
for (const k of ['log', 'info', 'debug', 'warn', 'error']) console[k] = (...a) => process.stderr.write(a.map(String).join(' ') + '\n');
const W = await import(src('engine-wllama.js'));
const agent = await import(src('agent.js'));

const rl = readline.createInterface({ input: process.stdin });
for await (const line of rl) {
  if (!line.trim()) continue;
  let value, ok = true, error;
  try {
    const q = JSON.parse(line);
    if (q.op === 'parse') {
      const p = W.splitThinking(q.text);
      const calls = p.open ? [] : W.parseToolCalls(p.text).map(c => ({ name: c.function.name, arguments: c.function.arguments }));
      value = { thinking: p.thinking, text: p.text, open: Boolean(p.open || p.pending), calls, looping: W.isLooping(q.text) };
    } else if (q.op === 'messages') value = W.gemmaMessages(q.messages, q.tools || [], new Set(q.active || []));
    else if (q.op === 'system') value = agent.LITE_SYSTEM;
    else if (q.op === 'specs') {
      const tools = await import(src('tools.js'));
      const tasks = await import(src('tasks.js'));
      value = [...Object.values(tasks.HARNESS_SPECS), ...tools.toolSpecs(null)];
    }
    else throw new Error('unknown op ' + q.op);
  } catch (e) { ok = false; error = String(e && e.stack || e); }
  process.stdout.write(JSON.stringify({ ok, value, error }) + '\n');
}
