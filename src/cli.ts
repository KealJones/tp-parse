#!/usr/bin/env node
// tp-parse command line.
//
//   tp-parse "mi moku e kili."          check text, print problems
//   echo "jan moku e kili." | tp-parse  same, from stdin
//   tp-parse --json "..."               full parse tree as JSON
//   tp-parse --strict ...               training-data mode (see presets.ts)
//   tp-parse --filter [--field tp] < in.jsonl > out.jsonl
//       keep only lines / JSONL records whose text is valid; with --field,
//       each line is JSON and the text is read from that key.
//   tp-parse --stats < file             counts of issues instead of details

import { readFileSync } from 'node:fs';
import { parse, type ParseOptions, type ParseResult } from './parse.ts';
import { STRICT } from './presets.ts';

const args = process.argv.slice(2);
const flag = (name: string) => args.includes(name);
const value = (name: string) => (args.includes(name) ? args[args.indexOf(name) + 1] : undefined);
const positional = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--field');

if (flag('--help') || flag('-h')) {
  console.log(readFileSync(new URL(import.meta.url), 'utf8').split('\n').slice(1, 12).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'));
  process.exit(0);
}

const options: ParseOptions = flag('--strict') ? STRICT : {};
const input = positional.length ? positional.join(' ') : readFileSync(0, 'utf8');

if (flag('--filter')) {
  const field = value('--field');
  let kept = 0;
  let dropped = 0;
  for (const line of input.split('\n')) {
    if (!line.trim()) continue;
    let text = line;
    if (field) {
      try {
        text = String(JSON.parse(line)[field] ?? '');
      } catch {
        dropped++;
        continue;
      }
    }
    if (parse(text, options).ok) {
      process.stdout.write(line + '\n');
      kept++;
    } else {
      dropped++;
    }
  }
  console.error(`kept ${kept}, dropped ${dropped}`);
  process.exit(0);
}

const result = parse(input, options);

if (flag('--json')) {
  console.log(JSON.stringify(result, null, 2));
} else if (flag('--stats')) {
  printStats(result);
} else {
  printReport(input, result);
}
process.exit(result.ok ? 0 : 1);

function printReport(text: string, r: ParseResult) {
  const color = process.stdout.isTTY;
  const red = (s: string) => (color ? `\x1b[31m${s}\x1b[0m` : s);
  const yellow = (s: string) => (color ? `\x1b[33m${s}\x1b[0m` : s);
  const green = (s: string) => (color ? `\x1b[32m${s}\x1b[0m` : s);
  const dim = (s: string) => (color ? `\x1b[2m${s}\x1b[0m` : s);
  for (const s of r.sentences) {
    const errors = s.issues.filter((i) => i.severity === 'error');
    const mark = errors.length ? red('✗') : s.issues.length ? yellow('!') : green('✓');
    console.log(`${mark} ${s.text.replace(/\s+/g, ' ')}  ${dim(`(${s.kind})`)}`);
    for (const i of s.issues) {
      const tag = i.severity === 'error' ? red('error') : yellow('warn ');
      console.log(`    ${tag} ${dim(i.code)}  ${i.message}  ${dim(`"${text.slice(i.start, i.end)}"`)}`);
    }
  }
  const summary = `${r.sentences.length} sentence(s), ${r.errorCount} error(s), ${r.warningCount} warning(s)`;
  console.log(r.ok ? green(summary) : red(summary));
}

function printStats(r: ParseResult) {
  const counts = new Map<string, number>();
  for (const i of r.issues) counts.set(`${i.severity} ${i.code}`, (counts.get(`${i.severity} ${i.code}`) ?? 0) + 1);
  const bad = r.sentences.filter((s) => s.issues.some((i) => i.severity === 'error')).length;
  console.log(`sentences: ${r.sentences.length}, with errors: ${bad}`);
  for (const [k, n] of [...counts].sort((a, b) => b[1] - a[1])) console.log(`  ${k.padEnd(30)} ${n}`);
}
