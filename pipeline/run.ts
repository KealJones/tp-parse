// Translation pipeline: English stories -> checked toki pona training data.
//
//   node --experimental-strip-types pipeline/run.ts <step> [options]
//
// Steps (each reads the previous step's file and can be re-run; finished ids are skipped):
//   sample     --input TinyStories.txt --out stories.jsonl [--n 10000] [--min 50] [--max 100]
//   translate  --in stories.jsonl --out translated.jsonl [--model M] [--repairs 2] [--concurrency 4]
//   check      --in translated.jsonl --out checked.jsonl [--min-coverage 0.85]
//   back       --in checked.jsonl --out back.jsonl [--model M] [--concurrency 4]   (only rows that passed check)
//   report     --checked checked.jsonl [--back back.jsonl] [--keep kept.jsonl] [--min-recall auto|0.7]
//
// report also calibrates: it scores every translation against a *different*
// story's English to see what a wrong translation scores, and with
// --min-recall auto picks the lowest cutoff that lets at most 5% of those through.
//
// translate and back need ANTHROPIC_API_KEY.

import { existsSync, readFileSync, appendFileSync, writeFileSync } from 'node:fs';
import { parse, STRICT, checkMeaning, compareEnglish } from '../src/index.ts';
import { callClaude } from './llm.ts';
import { TRANSLATE_SYSTEM, translateUser, repairUser, BACK_SYSTEM, backUser } from './prompts.ts';

const [step, ...rest] = process.argv.slice(2);
const opt = (name: string, fallback?: string) => {
  const i = rest.indexOf(`--${name}`);
  return i >= 0 ? rest[i + 1] : fallback;
};
const need = (name: string) => {
  const v = opt(name);
  if (!v) {
    console.error(`missing --${name}`);
    process.exit(1);
  }
  return v;
};
const DEFAULT_MODEL = 'claude-sonnet-5-5';

type Row = Record<string, any> & { id: string };
const readJsonl = (path: string): Row[] =>
  existsSync(path) ? readFileSync(path, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l)) : [];
const doneIds = (path: string) => new Set(readJsonl(path).map((r) => r.id));
const append = (path: string, row: Row) => appendFileSync(path, JSON.stringify(row) + '\n');

/** Run `fn` over `items` with at most `n` in flight. */
async function pool<T>(items: T[], n: number, fn: (item: T, i: number) => Promise<void>) {
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(n, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        await fn(items[i], i);
      }
    }),
  );
}

function problems(tp: string): string[] {
  const res = parse(tp, STRICT);
  return res.issues.filter((i) => i.severity === 'error').map((i) => `${i.message} (at "${tp.slice(i.start, i.end)}")`);
}

async function main() {
  switch (step) {
    case 'sample': {
      const raw = readFileSync(need('input'), 'utf8');
      const n = Number(opt('n', '10000'));
      const min = Number(opt('min', '50'));
      const max = Number(opt('max', '100'));
      const out = need('out');
      const stories = raw.split('<|endoftext|>').map((s) => s.trim().replace(/\s+/g, ' '));
      let count = 0;
      writeFileSync(out, '');
      stories.forEach((en, i) => {
        const words = en.split(' ').length;
        // Skip fragments (a story cut off at the start begins mid-sentence, in lowercase).
        if (count < n && /^[A-Z"“]/.test(en) && words >= min && words <= max) {
          append(out, { id: `ts-${i}`, en });
          count++;
        }
      });
      console.log(`sampled ${count} stories of ${min}-${max} words into ${out}`);
      break;
    }

    case 'translate': {
      const input = readJsonl(need('in'));
      const out = need('out');
      const model = opt('model', DEFAULT_MODEL)!;
      const repairs = Number(opt('repairs', '2'));
      const done = doneIds(out);
      const todo = input.filter((r) => !done.has(r.id));
      let tokensIn = 0;
      let tokensOut = 0;
      let finished = 0;
      console.log(`translating ${todo.length} stories with ${model} (${done.size} already done)`);
      await pool(todo, Number(opt('concurrency', '4')), async (row) => {
        try {
          let res = await callClaude({ system: TRANSLATE_SYSTEM, user: translateUser(row.en), model });
          tokensIn += res.inputTokens;
          tokensOut += res.outputTokens;
          let tp = res.text;
          let attempts = 0;
          // Self-repair: show the model the checker's complaints and let it fix them.
          for (let p = problems(tp); p.length && attempts < repairs; p = problems(tp)) {
            attempts++;
            res = await callClaude({ system: TRANSLATE_SYSTEM, user: repairUser(row.en, tp, p), model });
            tokensIn += res.inputTokens;
            tokensOut += res.outputTokens;
            tp = res.text;
          }
          append(out, { ...row, tp, model, repairs: attempts, truncated: res.stopReason === 'max_tokens' });
        } catch (err) {
          console.error(`${row.id}: ${(err as Error).message}`);
        }
        if (++finished % 25 === 0) console.log(`  ${finished}/${todo.length}`);
      });
      console.log(`done. tokens: ${tokensIn} in, ${tokensOut} out`);
      break;
    }

    case 'check': {
      const input = readJsonl(need('in'));
      const out = need('out');
      const minCoverage = Number(opt('min-coverage', '0.85'));
      writeFileSync(out, '');
      for (const row of input) {
        const grammar = parse(row.tp, STRICT);
        const meaning = checkMeaning(row.en, row.tp);
        const reasons: string[] = [];
        if (row.truncated) reasons.push('truncated');
        if (!grammar.ok) reasons.push('grammar');
        if (meaning.coverage !== null && meaning.coverage < minCoverage) reasons.push('coverage');
        append(out, {
          ...row,
          grammarErrors: grammar.issues.filter((i) => i.severity === 'error').map((i) => `${i.code}: ${row.tp.slice(i.start, i.end)}`),
          coverage: meaning.coverage,
          missing: meaning.missing.map((m) => m.english),
          passed: reasons.length === 0,
          rejectedFor: reasons,
        });
      }
      console.log(`checked ${input.length} rows into ${out}`);
      break;
    }

    case 'back': {
      const input = readJsonl(need('in')).filter((r) => r.passed);
      const out = need('out');
      const model = opt('model', DEFAULT_MODEL)!;
      const done = doneIds(out);
      const todo = input.filter((r) => !done.has(r.id));
      console.log(`back-translating ${todo.length} rows with ${model} (${done.size} already done)`);
      await pool(todo, Number(opt('concurrency', '4')), async (row) => {
        try {
          const res = await callClaude({ system: BACK_SYSTEM, user: backUser(row.tp), model, temperature: 0 });
          const cmp = compareEnglish(row.en, res.text);
          append(out, { ...row, back: res.text, recall: cmp.recall, lost: cmp.lost });
        } catch (err) {
          console.error(`${row.id}: ${(err as Error).message}`);
        }
      });
      break;
    }

    case 'report': {
      const checked = readJsonl(need('checked'));
      const backPath = opt('back');
      const back = new Map(backPath ? readJsonl(backPath).map((r) => [r.id, r]) : []);
      const rows = checked.map((r) => ({ ...r, ...(back.get(r.id) ?? {}) }));
      const pct = (a: number, b = rows.length) => `${((100 * a) / Math.max(b, 1)).toFixed(0)}%`;
      const dist = (xs: number[]) => {
        const s = xs.filter((x) => typeof x === 'number').sort((a, b) => a - b);
        return s.length ? `median ${pct(s[s.length >> 1], 1)}, lowest ${pct(s[0], 1)}` : 'n/a';
      };
      // What does a wrong translation score? Pair each row with another row's English.
      const shift = Math.max(1, Math.floor(rows.length / 3));
      const wrongCoverage = rows.map((r, i) => checkMeaning(rows[(i + shift) % rows.length].en, r.tp).coverage ?? 0);
      const backRows = rows.filter((r) => typeof r.recall === 'number');
      const wrongRecall = backRows.map((r, i) => compareEnglish(backRows[(i + shift) % backRows.length].en, r.back).recall ?? 0);

      let minRecall = 0;
      const recallOpt = opt('min-recall', 'auto')!;
      if (backRows.length) {
        if (recallOpt === 'auto') {
          const sorted = [...wrongRecall].sort((a, b) => a - b);
          minRecall = sorted[Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95))] ?? 0;
        } else minRecall = Number(recallOpt);
      }

      const kept = rows.filter((r) => r.passed && (!backRows.length || (r.recall ?? 0) >= minRecall));
      console.log(`stories: ${rows.length}, kept: ${kept.length} (${pct(kept.length)})`);
      const reasons = new Map<string, number>();
      for (const r of rows) for (const why of r.rejectedFor ?? []) reasons.set(why, (reasons.get(why) ?? 0) + 1);
      if (backRows.length) reasons.set('back-translation', backRows.filter((r) => r.passed && r.recall < minRecall).length);
      for (const [why, n] of reasons) if (n) console.log(`  rejected for ${why}: ${n}`);
      const repaired = rows.filter((r) => r.repairs > 0).length;
      if (repaired) console.log(`  fixed by self-repair: ${repaired}`);
      console.log(`coverage: real ${dist(rows.map((r) => r.coverage))}; wrong-story pairs ${dist(wrongCoverage)}`);
      if (backRows.length) {
        console.log(`back-translation recall: real ${dist(backRows.map((r) => r.recall))}; wrong-story pairs ${dist(wrongRecall)}`);
        console.log(`recall cutoff: ${pct(minRecall, 1)}${recallOpt === 'auto' ? ' (auto: lets at most 5% of wrong-story pairs through)' : ''}`);
      }
      const keepPath = opt('keep');
      if (keepPath) {
        writeFileSync(keepPath, kept.map((r) => JSON.stringify({ id: r.id, en: r.en, tp: r.tp })).join('\n') + '\n');
        console.log(`wrote ${kept.length} kept stories to ${keepPath}`);
      }
      break;
    }

    default:
      console.log(readFileSync(new URL(import.meta.url), 'utf8').split('\n').slice(0, 13).join('\n'));
  }
}

main();
