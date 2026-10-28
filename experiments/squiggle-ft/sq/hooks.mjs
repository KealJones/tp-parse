// Module hooks: Squiggle's own app/src modules load unchanged, except the four
// that touch the browser's storage, network or GPU, which are swapped for
// node stand-ins (sq/stubs/). wllama's CDN module becomes a fake whose chat
// completion asks the episode's model (teacher, student or script).
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const STUB = (n) => pathToFileURL(path.join(HERE, 'stubs', n)).href;
const SWAP = { 'storage.js': 'storage.mjs', 'git.js': 'git.mjs', 'github.js': 'github.mjs', 'embed.js': 'embed.mjs' };
let appSrc = null;   // file URL of <squiggle>/app/src/

export async function initialize(data) { appSrc = data && data.appSrc; }

export async function resolve(specifier, context, next) {
  if (/^https:\/\/cdn\.jsdelivr\.net\/npm\/@wllama\/wllama@/.test(specifier)) return { url: STUB('wllama.mjs'), shortCircuit: true };
  if (/^https?:\/\//.test(specifier)) throw new Error(`squiggle-ft: network import not available in node: ${specifier}`);
  const r = await next(specifier, context);
  if (appSrc && r.url.startsWith(appSrc)) {
    const name = r.url.slice(appSrc.length);
    if (SWAP[name]) return { url: STUB(SWAP[name]), shortCircuit: true };
  }
  return r;
}
