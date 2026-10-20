import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parse, isValid } from '../src/parse.ts';
import { isValidPhonotactics } from '../src/lexicon.ts';

const codes = (text: string) => parse(text).issues.map((i) => i.code);
const errorCodes = (text: string) => parse(text).issues.filter((i) => i.severity === 'error').map((i) => i.code);

test('accepts well-formed sentences', () => {
  for (const s of [
    'mi moku e kili.',
    'jan pona mi li pali e tomo lon ma kasi.',
    'sina pona anu seme?',
    'tenpo pini la mi lape.',
    'tenpo ni la mi wile lape la mi tawa tomo.',
    'jan Keli o, sina pona!',
    'jan pona o, jan ike o, o kute e sona ni!',
    'jan ale o toki!',
    'o kama!',
    'o!',
    'mi wile ala wile moku?',
    'jan li moku ala moku?',
    'jan pona mi!',
    'mi lukin e ona li pilin e ni.',
    'ona mute o pana e moku li pona e ona.',
    'meli li tawa en tan lon palisa.',
    'ni li lon sitelen lape anu lon ma sewi.',
    'jan lawa pi ma A en pi ma B li toki.',
    'pona a, mi wile pini e ni.',
    'taso mi wile ala.',
    'mi tawa tomo sina.',
    'ona li kepeken e ilo.',
    'Mi moku.',
    'jan Li li pona.',
    'jan Sonja li toki e ni: "toki!"',
    'a a a!',
  ]) {
    assert.deepEqual(errorCodes(s), [], s);
  }
});

test('builds the expected tree', () => {
  const s = parse('tenpo pini la jan pona mi li wile pali e tomo pi kiwen mute lon ma kasi.').sentences[0];
  assert.equal(s.kind, 'clause');
  assert.equal(s.contexts.length, 1);
  const clause = s.clause!;
  assert.deepEqual(clause.subject!.items[0].modifiers.map((m) => m.norm), ['pona', 'mi']);
  const pred = clause.predicates[0];
  assert.equal(pred.marker, 'li');
  assert.deepEqual(pred.preverbs.map((p) => p.norm), ['wile']);
  assert.equal(pred.verb.items[0].head.norm, 'pali');
  assert.equal(pred.objects[0].items[0].head.norm, 'tomo');
  assert.deepEqual(pred.objects[0].items[0].pi[0].map((t) => t.norm), ['kiwen', 'mute']);
  assert.equal(pred.preps[0].prep.norm, 'lon');
});

test('marks yes/no questions and tag questions', () => {
  assert.equal(parse('jan li moku ala moku?').sentences[0].clause!.predicates[0].xAlaX, true);
  assert.equal(parse('mi wile ala wile moku?').sentences[0].clause!.predicates[0].xAlaX, true);
  assert.equal(parse('sina pona anu seme?').sentences[0].tag, 'anu seme');
});

test('catches a missing li', () => {
  assert.ok(errorCodes('jan moku e kili.').includes('object-without-verb'));
  assert.ok(errorCodes('ona lukin e ni.').includes('object-without-verb'));
});

test('catches misplaced and dangling particles', () => {
  assert.ok(errorCodes('mi moku e.').includes('particle-at-end'));
  assert.ok(errorCodes('jan li li moku.').includes('double-particle'));
  assert.ok(errorCodes('la mi moku.').includes('empty-context'));
  assert.ok(errorCodes('mi moku la.').includes('particle-at-end'));
  assert.ok(errorCodes('tomo pi.').includes('particle-at-end'));
});

test('catches unknown words but allows capitalised names', () => {
  assert.deepEqual(errorCodes('mi moku e blorp.'), ['unknown-word']);
  assert.deepEqual(errorCodes('jan Keli li pona.'), []);
});

test('warns on style issues without rejecting', () => {
  assert.ok(isValid('mi li moku.'));
  assert.ok(codes('mi li moku.').includes('li-after-mi-sina'));
  assert.ok(codes('tomo pi telo li suli.').includes('pi-single-word'));
  assert.ok(codes('mi moku e kili en telo.').includes('en-outside-subject'));
  assert.ok(codes('Sonja li pona.').includes('bare-name'));
  assert.ok(codes('jan Bob li pona.').includes('name-phonotactics'));
  assert.deepEqual(codes('toki-pona li pona.'), ['hyphenated']);
  assert.ok(codes('ni li pi mi.').includes('pi-without-head'));
});

test('uncommon words are warnings by default and can be made errors', () => {
  assert.ok(isValid('mi lanpan e ni.'));
  assert.ok(codes('mi lanpan e ni.').includes('uncommon-word'));
  assert.ok(!isValid('mi lanpan e ni.', { severityOverrides: { 'uncommon-word': 'error' } }));
});

test('allowedCategories widens what counts as normal vocabulary', () => {
  const r = parse('mi lanpan e ni.', { allowedCategories: ['core', 'common', 'uncommon', 'obscure'] });
  assert.equal(r.issues.length, 0);
});

test('splits text into sentences, keeping quotes intact', () => {
  const r = parse('mi toki e ni: "a. b. c." sina kute.');
  // The colon ends the first sentence; the periods inside the quote don't split anything.
  assert.equal(r.sentences.length, 2);
  assert.ok(r.sentences[1].text.startsWith('"a. b. c."'));
  assert.ok(r.ok);
});

test('phonotactics', () => {
  for (const ok of ['Keli', 'Kanata', 'Sonja', 'Ijo', 'Ana', 'Lanpan']) assert.ok(isValidPhonotactics(ok), ok);
  for (const bad of ['Bob', 'Tim', 'Wowa', 'Kanmi', 'Anna', 'Ji']) assert.ok(!isValidPhonotactics(bad), bad);
});
