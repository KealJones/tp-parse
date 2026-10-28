// Stand-in for the wllama 3.8.1 CDN module that engine-wllama.js imports.
// createChatCompletion receives exactly the messages Squiggle sends to the
// phone model (engine-wllama.js gemmaMessages) and streams back whatever the
// episode's model (W.generate: teacher, student or a script) writes.
import { W } from '../world.mjs';

const PIECE = 6;   // characters per streamed chunk (the engine checks for loops at sentence ends)

export class CacheManager {
  async open() { return { size: 1 }; }
  async download() {}
  async delete() {}
}

export class Wllama {
  constructor(paths, opts) { this.paths = paths; this.opts = opts; }
  async loadModelFromUrl(url, opts) { this.url = url; this.ctx = opts && opts.n_ctx; }
  async exit() {}
  async createChatCompletion(opts) {
    const { messages, max_tokens, temperature, abortSignal } = opts;
    const entry = { messages: JSON.parse(JSON.stringify(messages)), max_tokens, temperature, output: null };
    W.log.push(entry);
    const text = String(await W.generate({ messages: entry.messages, max_tokens, temperature }) ?? '');
    entry.output = text;
    if (!opts.stream) return { choices: [{ message: { role: 'assistant', content: text } }] };
    return (async function* () {
      for (let i = 0; i < text.length; i += PIECE) {
        if (abortSignal && abortSignal.aborted) { entry.cut = i; return; }
        yield { choices: [{ delta: { content: text.slice(i, i + PIECE) } }] };
        if (i % 600 === 0) await new Promise(r => setImmediate(r));
      }
    })();
  }
}
export default { Wllama, CacheManager };
