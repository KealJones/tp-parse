// Stand-in for app/src/git.js: the same exports, on node's filesystem instead
// of LightningFS. Agent paths (/repos/<name>/…) live under the episode's temp
// folder W.root. Clones are real (isomorphic-git over HTTPS from GitHub) but
// cached in W.repoCache, so each repo is fetched once and copied per episode.
// Pushes never leave the machine: the episode world refuses them like GitHub
// would for a repo Squiggle has no write access to.
import nodefs from 'node:fs';
import path from 'node:path';
import * as iso from 'isomorphic-git';
import { W } from '../world.mjs';

const real = (p) => path.join(W.root, String(p));
const P = nodefs.promises;
const map1 = (fn) => (p, ...a) => fn(real(p), ...a);
export const pfs = {
  readFile: map1(P.readFile), writeFile: map1(P.writeFile), unlink: map1(P.unlink), readdir: map1(P.readdir),
  mkdir: map1(P.mkdir), rmdir: map1(P.rmdir), stat: map1(P.stat), lstat: map1(P.lstat), readlink: map1(P.readlink),
  symlink: (t, p) => P.symlink(t, real(p)), chmod: map1(P.chmod), rename: (a, b) => P.rename(real(a), real(b)),
};
export const fs = { promises: pfs };

// isomorphic-git's HTTP client, on the real fetch (env.mjs wraps the global one with a text cache).
const webHttp = {
  async request({ url, method = 'GET', headers = {}, body }) {
    let data;
    if (body) { const parts = []; for await (const c of body) parts.push(c); data = Buffer.concat(parts.map(c => Buffer.from(c))); }
    const res = await (globalThis.__realFetch || fetch)(url, { method, headers, body: data });
    return { url: res.url, method, statusCode: res.status, statusMessage: res.statusText, body: [new Uint8Array(await res.arrayBuffer())], headers: Object.fromEntries(res.headers.entries()) };
  },
};

const offline = () => { const e = new Error('HttpError: network is off in this test world'); e.code = 'HttpError'; throw e; };
const refused = () => { const e = new Error('HttpError: HTTP Error: 403 Forbidden'); e.code = 'HttpError'; throw e; };

const cacheKey = (url, ref) => String(url).replace(/^https:\/\/github\.com\//, '').replace(/\.git$/, '').replace(/[^A-Za-z0-9_.-]+/g, '__') + (ref ? '@' + String(ref).replace(/[^A-Za-z0-9_.-]+/g, '_') : '');

// Fills the shared clone cache (also used by prefetch.mjs before a run).
export async function cachedClone(url, ref) {
  const dest = path.join(W.repoCache, cacheKey(url, ref));
  if (nodefs.existsSync(path.join(dest, '.git'))) return dest;
  if (W.offline) offline();
  const tmp = `${dest}.tmp-${process.pid}-${Date.now()}`;
  await iso.clone({ fs: nodefs, http: webHttp, dir: tmp, url, ref: ref || undefined, singleBranch: false, depth: 50 });
  try { nodefs.renameSync(tmp, dest); } catch { nodefs.rmSync(tmp, { recursive: true, force: true }); }
  return dest;
}

export const git = {
  ...iso,
  async clone({ dir, url, ref }) {
    const src = await cachedClone(url, ref);
    nodefs.cpSync(src, real(dir), { recursive: true });
  },
  async fetch() { offline(); },
  async pull() { offline(); },
  async push() { refused(); },
};

export const corsProxy = () => '';
export const remoteUrl = (owner, name) => `https://github.com/${owner}/${name}.git`;
export const net = () => ({});
export async function author() { return { name: 'Squiggle User', email: '1+squiggle-user@users.noreply.github.com' }; }

// ── The rest is app/src/git.js as written (it only uses pfs and git). ──
export async function exists(p) {
  try { await pfs.stat(p); return true; } catch { return false; }
}

export async function isDir(p) {
  try { return (await pfs.stat(p)).isDirectory(); } catch { return false; }
}

export async function mkdirp(p) {
  const parts = p.split('/').filter(Boolean);
  let cur = '';
  for (const x of parts) {
    cur += '/' + x;
    try { await pfs.mkdir(cur); } catch (e) { if (e.code !== 'EEXIST') throw e; }
  }
}

export async function rmrf(p) {
  let st;
  try { st = await pfs.lstat(p); } catch { return; }
  if (st.isDirectory()) {
    for (const name of await pfs.readdir(p)) await rmrf(p + '/' + name);
    await pfs.rmdir(p);
  } else {
    await pfs.unlink(p);
  }
}

export async function writeFile(p, data) {
  await mkdirp(p.split('/').slice(0, -1).join('/'));
  await pfs.writeFile(p, data, typeof data === 'string' ? 'utf8' : undefined);
}

export async function readText(p) {
  return pfs.readFile(p, 'utf8');
}

export async function walk(dir, base = '') {
  const out = [];
  let names;
  try { names = await pfs.readdir(dir); } catch { return out; }
  for (const name of names.sort()) {
    if (name === '.git') continue;
    const full = dir + '/' + name;
    const rel = base ? base + '/' + name : name;
    const st = await pfs.stat(full);
    if (st.isDirectory()) out.push(...await walk(full, rel));
    else out.push({ path: rel, size: st.size });
  }
  return out;
}

export async function currentBranch(dir) {
  return git.currentBranch({ fs, dir, fullname: false }).catch(() => null);
}

export async function stageAll(dir) {
  const matrix = await git.statusMatrix({ fs, dir });
  let changed = 0;
  for (const [filepath, head, work, stage] of matrix) {
    if (head === 1 && work === 1 && stage === 1) continue;
    changed++;
    if (work === 0) await git.remove({ fs, dir, filepath });
    else await git.add({ fs, dir, filepath });
  }
  return changed;
}

export async function statusLines(dir) {
  const matrix = await git.statusMatrix({ fs, dir });
  const lines = [];
  for (const [f, head, work, stage] of matrix) {
    if (head === 1 && work === 1 && stage === 1) continue;
    let code = '?';
    if (head === 0 && work === 2) code = stage === 0 ? '??' : 'A';
    else if (head === 1 && work === 0) code = 'D';
    else if (head === 1 && work === 2) code = 'M';
    else if (head === 1 && work === 1 && stage !== 1) code = 'M';
    lines.push(`${code} ${f}`);
  }
  return lines;
}
