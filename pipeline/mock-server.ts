// A stand-in for the Anthropic API so the pipeline can be tested without a key.
//
//   MOCK_TRANSLATIONS=translated.jsonl node --experimental-strip-types pipeline/mock-server.ts [port]
//
// - translate: answers with the toki pona from MOCK_TRANSLATIONS for the matching English story
// - repair: applies MOCK_FIXES ("bad=>good;bad2=>good2") to the text it was shown
// - back-translate: answers with a word-by-word gloss (a crude stand-in for a real model)
// - the very first request gets a 529 "overloaded" so the retry path is exercised

import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { gloss } from '../src/meaning.ts';
import { BACK_SYSTEM } from './prompts.ts';

const port = Number(process.argv[2] ?? 8787);
const rows = readFileSync(process.env.MOCK_TRANSLATIONS!, 'utf8').trim().split('\n').map((l) => JSON.parse(l));
const byEnglish = new Map(rows.map((r) => [r.en.trim(), r.tp]));
const fixes = (process.env.MOCK_FIXES ?? '').split(';').filter(Boolean).map((p) => p.split('=>'));
let first = true;

createServer((req, res) => {
  let body = '';
  req.on('data', (c) => (body += c));
  req.on('end', () => {
    if (first) {
      first = false;
      res.writeHead(529, { 'content-type': 'application/json', 'retry-after': '1' });
      res.end(JSON.stringify({ type: 'error', error: { type: 'overloaded_error', message: 'mock overload' } }));
      return;
    }
    const { system, messages } = JSON.parse(body);
    const user: string = messages[0].content;
    let text: string;
    if (system === BACK_SYSTEM) {
      text = gloss(user.split('toki pona:\n')[1].split('\n\nEnglish:')[0]);
    } else if (user.includes('A grammar checker found these problems')) {
      text = user.split('Your toki pona translation:\n')[1].split('\n\nA grammar checker')[0];
      for (const [bad, good] of fixes) text = text.split(bad).join(good);
    } else {
      const en = user.split('English:\n').pop()!.split('\n\ntoki pona:')[0].trim();
      text = byEnglish.get(en) ?? 'mi sona ala.';
    }
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({
      type: 'message', role: 'assistant', content: [{ type: 'text', text }],
      stop_reason: 'end_turn', usage: { input_tokens: Math.ceil(body.length / 4), output_tokens: Math.ceil(text.length / 4) },
    }));
  });
}).listen(port, () => console.log(`mock API on http://localhost:${port}`));
