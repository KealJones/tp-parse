// Run the parser over a folder of toki pona text and summarise what it finds.
// Usage: node --experimental-strip-types scripts/corpus-report.ts <dir> [--samples CODE]

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { parse, type Sentence } from '../src/parse.ts';

const dir = process.argv[2];
const sampleCode = process.argv.includes('--samples') ? process.argv[process.argv.indexOf('--samples') + 1] : null;
if (!dir) {
  console.error('usage: corpus-report.ts <dir> [--samples CODE]');
  process.exit(1);
}

function* walk(d: string): Generator<string> {
  for (const name of readdirSync(d)) {
    const p = join(d, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

const GRAMMAR_CODES = new Set([
  'particle-at-end', 'particle-at-start', 'double-particle', 'empty-predicate',
  'empty-object', 'empty-context', 'empty-pi', 'object-without-verb',
]);

let files = 0;
let total = 0;
let clean = 0; // no errors at all
let wordsOnlyKnown = 0; // sentences whose words are all known
let grammarOkGivenKnown = 0; // ...and that also have no grammar errors
const codeCounts = new Map<string, number>();
const unknownWords = new Map<string, number>();
const samples: { file: string; s: Sentence }[] = [];

for (const file of walk(dir)) {
  files++;
  const text = readFileSync(file, 'utf8');
  const res = parse(text);
  for (const s of res.sentences) {
    if (s.kind === 'interjection' && s.issues.length === 0) continue;
    total++;
    const errors = s.issues.filter((i) => i.severity === 'error');
    if (errors.length === 0) clean++;
    for (const i of s.issues) codeCounts.set(i.code, (codeCounts.get(i.code) ?? 0) + 1);
    for (const i of s.issues) {
      if (i.code === 'unknown-word') {
        const w = text.slice(i.start, i.end).toLowerCase();
        unknownWords.set(w, (unknownWords.get(w) ?? 0) + 1);
      }
    }
    const hasUnknown = s.issues.some((i) => i.code === 'unknown-word');
    if (!hasUnknown) {
      wordsOnlyKnown++;
      if (!errors.some((i) => GRAMMAR_CODES.has(i.code))) grammarOkGivenKnown++;
    }
    if (sampleCode && s.issues.some((i) => i.code === sampleCode) && !hasUnknown && samples.length < 25) {
      samples.push({ file, s });
    }
  }
}

const pct = (a: number, b: number) => `${((100 * a) / Math.max(b, 1)).toFixed(1)}%`;
console.log(`files:                     ${files}`);
console.log(`sentences:                 ${total}`);
console.log(`no errors:                 ${clean} (${pct(clean, total)})`);
console.log(`all words known:           ${wordsOnlyKnown} (${pct(wordsOnlyKnown, total)})`);
console.log(`  ...of those, grammar ok: ${grammarOkGivenKnown} (${pct(grammarOkGivenKnown, wordsOnlyKnown)})`);
console.log('\nissue counts:');
for (const [code, n] of [...codeCounts].sort((a, b) => b[1] - a[1])) console.log(`  ${code.padEnd(22)} ${n}`);
console.log('\ntop unknown words:');
console.log('  ' + [...unknownWords].sort((a, b) => b[1] - a[1]).slice(0, 40).map(([w, n]) => `${w}(${n})`).join(' '));
if (sampleCode) {
  console.log(`\nsamples with ${sampleCode}:`);
  for (const { s } of samples) {
    const iss = s.issues.find((i) => i.code === sampleCode)!;
    console.log(`  - ${s.text.replace(/\s+/g, ' ').slice(0, 140)}\n      -> ${iss.message}`);
  }
}
