// Stand-in for app/src/storage.js: the storage repo as an in-memory map of
// files (W.files). Same read/list/write/remove contract; no git, no sync.
import { W } from '../world.mjs';

const emitter = () => { const h = {}; return { on: (e, f) => ((h[e] ||= []).push(f), () => {}), off() {}, emit: (e, ...a) => (h[e] || []).forEach(f => f(...a)) }; };
export const events = emitter();
const clean = (rel) => String(rel || '').replace(/^\/+/, '');

export const storageConfig = () => ({ owner: 'squiggle-user', name: 'squiggle-storage', root: '' });
export const syncStatus = () => ({ syncing: false, lastSync: Date.now(), lastError: null, pending: 0 });
export async function loadStorageConfig() { return storageConfig(); }
export async function findExistingStorage() { return null; }
export async function createStorageRepo() { throw new Error('not in node'); }
export function newRepoUrl() { return ''; }
export async function inspectRepo() { return null; }
export async function useStorage() {}
export async function forgetStorage() {}
export async function open() {}
export function sync() { return Promise.resolve(); }

export async function read(rel) {
  const k = clean(rel);
  return W.files.has(k) ? W.files.get(k) : null;
}

// Like git.js walk(): files under relDir, relative paths, sorted, with sizes.
export async function list(relDir) {
  const dir = clean(relDir).replace(/\/$/, '');
  const pre = dir ? dir + '/' : '';
  return [...W.files.keys()].filter(k => k.startsWith(pre)).sort()
    .map(k => ({ path: k.slice(pre.length), size: Buffer.byteLength(W.files.get(k)) }));
}

export function write(rel, content) {
  W.files.set(clean(rel), String(content));
  events.emit('changed', rel);
  return Promise.resolve();
}

export function remove(rel) {
  const k = clean(rel);
  for (const f of [...W.files.keys()]) if (f === k || f.startsWith(k + '/')) W.files.delete(f);
  events.emit('changed', rel);
  return Promise.resolve();
}
