// Clones (into the shared cache) and reads facts out of real public repos, for
// questions with checkable answers. Facts come straight from the repo: package
// metadata, the newest commits, files, and names defined exactly once.
//   node sq/repofacts.mjs <repoCache> owner/name …   -> one JSON object per line
import fs from 'node:fs';
import path from 'node:path';
import * as iso from 'isomorphic-git';
import { W } from './world.mjs';
import './env.mjs';
import { cachedClone } from './stubs/git.mjs';

W.repoCache = process.argv[2];
fs.mkdirSync(W.repoCache, { recursive: true });
const SKIP_DIR = /(^|\/)(node_modules|dist|build|vendor|\.github|coverage|fixtures?|__snapshots__|docs?\/api|site-packages)(\/|$)/;
const SRC = /\.(m?js|cjs|ts|py)$/;
const TEST = /(^|\/)(tests?|__tests__|spec|benchmarks?|bench|examples?)(\/|$)|\.(test|spec|d|test-d)\.(m?js|ts)$|(^|\/)test_[^/]*\.py$|_test\.py$/;

function walk(dir, base = '') {
  const out = [];
  for (const name of fs.readdirSync(dir).sort()) {
    if (name === '.git') continue;
    const full = path.join(dir, name), rel = base ? `${base}/${name}` : name;
    const st = fs.statSync(full);
    if (st.isDirectory()) out.push(...walk(full, rel)); else out.push({ path: rel, size: st.size });
  }
  return out;
}

function defs(dir, files) {
  const seen = new Map();
  for (const f of files) {
    if (!SRC.test(f.path) || SKIP_DIR.test(f.path) || TEST.test(f.path) || /\.min\.js$/.test(f.path) || f.size > 300000) continue;
    const lines = fs.readFileSync(path.join(dir, f.path), 'utf8').split('\n');
    lines.forEach((line, i) => {
      const m = line.match(/^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]{3,})\s*\(/)
        || line.match(/^\s*export\s+(?:const|let|class)\s+([A-Za-z_$][\w$]{3,})\b/)
        || line.match(/^(?:async\s+)?def\s+([A-Za-z_]\w{3,})\s*\(/) || line.match(/^class\s+([A-Za-z_]\w{3,})\b/)
        || line.match(/^\s+def\s+([a-z_]\w{4,})\s*\(self/);
      if (m) { const k = m[1]; if (!seen.has(k)) seen.set(k, []); seen.get(k).push({ path: f.path, line: i + 1 }); }
    });
  }
  return [...seen.entries()].filter(([k, v]) => v.length === 1 && !/^(main|init|test|setup|__\w+__)$/.test(k) && !/\d{2,}$/.test(k) && /[a-z]{3}/.test(k)).map(([name, [d]]) => ({ name, ...d }));
}

for (const repo of process.argv.slice(3)) {
  try {
    const dir = await cachedClone(`https://github.com/${repo}.git`);
    const files = walk(dir);
    const read = (p) => { try { return fs.readFileSync(path.join(dir, p), 'utf8'); } catch { return null; } };
    let pkg = null;
    try { pkg = JSON.parse(read('package.json') || 'null'); } catch {}
    const pyproject = read('pyproject.toml');
    const py = pyproject ? {
      name: (pyproject.match(/^name\s*=\s*"([^"]+)"/m) || [])[1] || null,
      version: (pyproject.match(/^version\s*=\s*"([^"]+)"/m) || [])[1] || null,
      requires_python: (pyproject.match(/^requires-python\s*=\s*"([^"]+)"/m) || [])[1] || null,
    } : null;
    const log = await iso.log({ fs, dir, depth: 8 });
    const branch = await iso.currentBranch({ fs, dir });
    const commits = log.map(c => ({ oid: c.oid.slice(0, 8), date: new Date(c.commit.author.timestamp * 1000).toISOString().slice(0, 10), author: c.commit.author.name, subject: c.commit.message.split('\n')[0] }));
    const readme = files.find(f => /^readme(\.md|\.rst|\.txt)?$/i.test(f.path));
    const licenseFile = files.find(f => /^(license|licence|copying)(\.md|\.txt|\.rst)?$/i.test(f.path));
    const licenseText = licenseFile ? read(licenseFile.path).slice(0, 400) : '';
    const licenseName = (pkg && typeof pkg.license === 'string' && pkg.license)
      || (/MIT License|Permission is hereby granted, free of charge/i.test(licenseText) ? 'MIT'
        : /Apache License/i.test(licenseText) ? 'Apache-2.0' : /BSD|Redistribution and use in source and binary forms/i.test(licenseText) ? 'BSD' : /ISC License|Permission to use, copy, modify, and\/or distribute/i.test(licenseText) ? 'ISC' : null);
    const description = (pkg && pkg.description) || (readme ? (read(readme.path).split('\n').find(l => l.trim() && !/^[#=\-\[!<]/.test(l.trim())) || '').trim().slice(0, 200) : '');
    process.stdout.write(JSON.stringify({
      repo, name: repo.split('/')[1], branch, files: files.length, top: [...new Set(files.map(f => f.path.split('/')[0]))].slice(0, 40),
      package: pkg ? { name: pkg.name || null, version: pkg.version || null, license: pkg.license || null, deps: Object.keys(pkg.dependencies || {}), devDeps: Object.keys(pkg.devDependencies || {}), node: (pkg.engines && pkg.engines.node) || null, main: pkg.main || pkg.exports && typeof pkg.exports === 'string' && pkg.exports || null } : null,
      pyproject: py, license: licenseName, readme: readme ? readme.path : null, description,
      commits, defs: defs(dir, files),
    }) + '\n');
  } catch (e) {
    process.stdout.write(JSON.stringify({ repo, error: String(e && e.message || e) }) + '\n');
  }
}
