#!/usr/bin/env node
// `node teach.mjs <command> …` — the step-wise teacher CLI (teach.py does the work; see TEACHER.md).
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const py = process.env.PYTHON || 'python3';
const r = spawnSync(py, [path.join(here, 'teach.py'), ...process.argv.slice(2)], { stdio: 'inherit', env: { ...process.env, SQUIGGLE_DIR: process.env.SQUIGGLE_DIR || '/home/claude/squiggle' } });
process.exit(r.status ?? 1);
