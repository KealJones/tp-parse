// A recursive-descent parser and validator for toki pona sentences.
//
// It never throws on bad input. Every problem becomes an Issue with a code,
// a severity, and the character range it applies to, and the parser keeps
// going so you get the best tree it can build plus everything it noticed.

import { BARE_SUBJECTS, PARTICLES, PREPOSITIONS, PREVERBS, categoryOf, isKnown, isValidPhonotactics, lookup } from './lexicon.ts';
import { splitSentences, tokenize, type RawSentence, type Token } from './tokenize.ts';
import type { UsageCategory } from './words.ts';

// ---------------------------------------------------------------- types

export type Severity = 'error' | 'warning';

export type IssueCode =
  | 'unknown-word' // lowercase word not in the dictionary
  | 'uncommon-word' // known word outside the allowed usage categories
  | 'deprecated-word'
  | 'name-phonotactics' // capitalised name that breaks toki pona sound rules
  | 'bare-name' // name used as a head with no head noun ("Sonja li" vs "jan Sonja li")
  | 'hyphenated' // old style compound like toki-pona
  | 'stray-symbol'
  | 'particle-at-end' // li / e / pi / la / en / anu with nothing after it
  | 'particle-at-start' // a phrase that starts with li / e / pi / en / anu
  | 'double-particle' // li li, e e, pi pi ...
  | 'empty-predicate'
  | 'empty-object'
  | 'empty-context' // "la" with nothing before it
  | 'empty-pi'
  | 'pi-single-word' // pi followed by one word (style: usually just drop pi)
  | 'pi-without-head' // "ni li pi mi" — older colloquial "belongs to"; pu-style text avoids it
  | 'object-without-verb' // "e" with no li / o / mi / sina before it
  | 'li-after-mi-sina' // "mi li" / "sina li"
  | 'en-outside-subject'; // en only joins subjects; objects repeat e

export interface Issue {
  code: IssueCode;
  severity: Severity;
  message: string;
  start: number;
  end: number;
}

export interface Term {
  kind: 'word' | 'name' | 'quote' | 'number';
  text: string;
  /** Lowercase form for words. */
  norm: string;
  start: number;
  end: number;
}

/** One noun phrase: a head, its modifiers, and any "pi" groups. */
export interface Phrase {
  type: 'phrase';
  head: Term;
  modifiers: Term[];
  pi: Term[][];
  /** Trailing emphatic "a". */
  emphasis: boolean;
}

/** Phrases joined by "en" (subjects) or "anu" (alternatives). */
export interface Group {
  type: 'group';
  joiner: 'en' | 'anu' | null;
  items: Phrase[];
}

export interface PrepPhrase {
  type: 'prep';
  prep: Term;
  object: Group;
}

export interface Predicate {
  type: 'predicate';
  /** The marker that introduced it: li, o, or none (after mi / sina). */
  marker: 'li' | 'o' | null;
  preverbs: Term[];
  verb: Group;
  /** "X ala X" yes/no question. */
  xAlaX: boolean;
  objects: Group[];
  preps: PrepPhrase[];
}

export interface Clause {
  type: 'clause';
  mood: 'statement' | 'imperative';
  subject: Group | null;
  predicates: Predicate[];
}

export type SentenceKind = 'clause' | 'fragment' | 'vocative' | 'interjection';

export interface Sentence {
  text: string;
  start: number;
  end: number;
  terminator: string | null;
  kind: SentenceKind;
  /** Sentence-initial "taso" (but). */
  conjunction: 'taso' | null;
  /** Everything before each "la". */
  contexts: (Clause | Group)[];
  /** "jan Keli o" — the person being addressed. */
  vocative: Group | null;
  clause: Clause | null;
  /** A sentence with no predicate, like "jan pona mi!" */
  fragment: Group | null;
  /** Closing "anu seme?" tag question. */
  tag: 'anu seme' | null;
  /** Leading exclamation before the main clause: "pona a, mi ...". */
  interjection: Group | null;
  issues: Issue[];
}

export interface ParseOptions {
  /**
   * Usage categories that count as fully valid. Words from other categories
   * are reported as 'uncommon-word' warnings. Default: core + common.
   */
  allowedCategories?: UsageCategory[];
  /**
   * Treat these codes as errors instead of warnings (or vice versa).
   * Useful for a strict training-data filter.
   */
  severityOverrides?: Partial<Record<IssueCode, Severity>>;
}

export interface ParseResult {
  ok: boolean;
  sentences: Sentence[];
  issues: Issue[];
  errorCount: number;
  warningCount: number;
}

const DEFAULT_SEVERITY: Record<IssueCode, Severity> = {
  'unknown-word': 'error',
  'uncommon-word': 'warning',
  'deprecated-word': 'warning',
  'name-phonotactics': 'warning',
  'bare-name': 'warning',
  hyphenated: 'warning',
  'stray-symbol': 'warning',
  'particle-at-end': 'error',
  'particle-at-start': 'error',
  'double-particle': 'error',
  'empty-predicate': 'error',
  'empty-object': 'error',
  'empty-context': 'error',
  'empty-pi': 'error',
  'pi-single-word': 'warning',
  'pi-without-head': 'warning',
  'object-without-verb': 'error',
  'li-after-mi-sina': 'warning',
  'en-outside-subject': 'warning',
};

// ---------------------------------------------------------------- entry points

export function parse(text: string, options: ParseOptions = {}): ParseResult {
  const tokens = tokenize(text);
  const sentences = splitSentences(text, tokens).map((raw) => parseRawSentence(text, raw, options));
  const issues = sentences.flatMap((s) => s.issues);
  const errorCount = issues.filter((i) => i.severity === 'error').length;
  return { ok: errorCount === 0, sentences, issues, errorCount, warningCount: issues.length - errorCount };
}

/** Convenience check for a filter pipeline. */
export function isValid(text: string, options: ParseOptions = {}): boolean {
  return parse(text, options).ok;
}

// ---------------------------------------------------------------- sentence level

class Ctx {
  issues: Issue[] = [];
  options: ParseOptions;
  constructor(options: ParseOptions) {
    this.options = options;
  }
  report(code: IssueCode, message: string, start: number, end: number) {
    const severity = this.options.severityOverrides?.[code] ?? DEFAULT_SEVERITY[code];
    // One issue per code per location is enough.
    if (this.issues.some((i) => i.code === code && i.start === start)) return;
    this.issues.push({ code, severity, message, start, end });
  }
  get allowed(): Set<string> {
    return new Set(this.options.allowedCategories ?? ['core', 'common']);
  }
}

function parseRawSentence(text: string, raw: RawSentence, options: ParseOptions): Sentence {
  const ctx = new Ctx(options);
  const terms = toTerms(raw.tokens, ctx);

  const sentence: Sentence = {
    text: text.slice(raw.start, raw.end),
    start: raw.start,
    end: raw.end,
    terminator: raw.terminator,
    kind: 'fragment',
    conjunction: null,
    contexts: [],
    vocative: null,
    clause: null,
    fragment: null,
    tag: null,
    interjection: null,
    issues: ctx.issues,
  };
  if (terms.length === 0) {
    sentence.kind = 'interjection';
    return sentence;
  }

  let rest = terms;

  // Pure interjections: "a!", "a a a", "mu", "n".
  if (rest.every((t) => t.norm === 'a' || t.norm === 'mu' || t.norm === 'n')) {
    sentence.kind = 'interjection';
    return sentence;
  }

  // Sentence-initial "taso" = "but".
  if (rest[0].norm === 'taso' && rest.length > 1 && !PARTICLES.has(rest[1].norm)) {
    sentence.conjunction = 'taso';
    rest = rest.slice(1);
  }

  // Leading exclamation: "pona a, mi wile pini e ni." The "a" closes it when what
  // follows is a clause of its own.
  const aIdx = rest.findIndex((t, i) => t.norm === 'a' && i > 0 && i < rest.length - 1);
  if (aIdx > 0) {
    const before = rest.slice(0, aIdx);
    const after = rest.slice(aIdx + 1);
    const beforeIsPlain = before.every((t) => !(t.kind === 'word' && PARTICLES.has(t.norm)));
    const afterIsClause = (BARE_SUBJECTS.has(after[0].norm) && after.length > 1) || after.some((t) => t.norm === 'li' || t.norm === 'o' || t.norm === 'la');
    if (beforeIsPlain && afterIsClause) {
      sentence.interjection = parseGroup(before, ctx, 'subject');
      rest = after;
    }
  }

  // Closing "anu seme" tag question.
  if (rest.length >= 3 && rest[rest.length - 2].norm === 'anu' && rest[rest.length - 1].norm === 'seme') {
    sentence.tag = 'anu seme';
    rest = rest.slice(0, -2);
  }

  checkDoubleParticles(rest, ctx);

  // Contexts: everything before each "la".
  const segments = splitOn(rest, (t) => t.norm === 'la');
  for (let i = 0; i < segments.length - 1; i++) {
    const seg = segments[i];
    if (seg.items.length === 0) {
      ctx.report('empty-context', '"la" needs something before it to set the context.', seg.splitter!.start, seg.splitter!.end);
      continue;
    }
    sentence.contexts.push(parseClauseOrGroup(seg.items, ctx));
  }
  const main = segments[segments.length - 1];
  if (main.items.length === 0) {
    const la = segments[segments.length - 2]?.splitter;
    if (la) ctx.report('particle-at-end', 'Sentence ends with "la" — the main clause is missing.', la.start, la.end);
    return sentence;
  }

  let body = main.items;

  // A lone "o!" is an exclamation.
  if (body.length === 1 && body[0].norm === 'o') {
    sentence.kind = 'interjection';
    return sentence;
  }

  // Vocatives: "jan Keli o," followed by a clause, "jan Keli o!" alone,
  // or several in a row: "jan pona o, jan ike o, o kute!"
  for (let vocIdx = findVocative(body); vocIdx >= 0; vocIdx = findVocative(body)) {
    const addressed = parseGroup(body.slice(0, vocIdx), ctx, 'subject');
    if (sentence.vocative) sentence.vocative.items.push(...addressed.items);
    else sentence.vocative = addressed;
    body = body.slice(vocIdx + 1);
    if (body.length === 0) {
      sentence.kind = 'vocative';
      return sentence;
    }
  }

  const parsed = parseClauseOrGroup(body, ctx);
  if (parsed.type === 'clause') {
    sentence.kind = 'clause';
    sentence.clause = parsed;
  } else {
    sentence.kind = 'fragment';
    sentence.fragment = parsed;
  }
  return sentence;
}

/**
 * "X o" is a vocative when nothing follows it, or when what follows is a
 * clause of its own (has li, or starts with mi / sina). Otherwise "X o Y"
 * is an imperative: "X should Y".
 */
function findVocative(terms: Term[]): number {
  const idx = terms.findIndex((t, i) => t.norm === 'o' && i > 0);
  if (idx < 0) return -1;
  if (terms.slice(0, idx).some((t) => t.norm === 'li')) return -1;
  const after = terms.slice(idx + 1);
  if (after.length === 0) return idx;
  // "jan ike o, o kute!" — another command follows.
  if (after[0].norm === 'o') return idx;
  if (BARE_SUBJECTS.has(after[0].norm) && after.length > 1 && !['en', 'pi', 'anu'].includes(after[1].norm)) return idx;
  // "jan Keli o, ona li pona": only a vocative if what comes before that li
  // could be a subject. In "ona mute o pana e ijo li ..." it can't, so the o
  // is an imperative marker instead.
  const li = after.findIndex((t) => t.norm === 'li');
  if (li > 0 && !after.slice(0, li).some((t) => t.norm === 'e' || t.norm === 'o')) return idx;
  return -1;
}

function checkDoubleParticles(terms: Term[], ctx: Ctx) {
  for (let i = 1; i < terms.length; i++) {
    const a = terms[i - 1];
    const b = terms[i];
    if (a.kind !== 'word' || b.kind !== 'word') continue;
    const pa = PARTICLES.has(a.norm);
    const pb = PARTICLES.has(b.norm);
    // Allowed pairs: "la o" (context then command), "o o" (vocative then command),
    // "li pi" (colloquial "belongs to", warned elsewhere), "en pi" / "anu pi"
    // ("pi ma A en pi ma B").
    const allowedPair =
      (a.norm === 'la' && b.norm === 'o') ||
      (a.norm === 'o' && b.norm === 'o') ||
      (b.norm === 'pi' && (a.norm === 'li' || a.norm === 'en' || a.norm === 'anu'));
    if (pa && pb && !allowedPair) {
      ctx.report('double-particle', `"${a.norm} ${b.norm}" — two grammar particles in a row.`, a.start, b.end);
    }
  }
}

// ---------------------------------------------------------------- clauses

function parseClauseOrGroup(terms: Term[], ctx: Ctx): Clause | Group {
  const markerIdx = terms.findIndex((t) => t.norm === 'li' || t.norm === 'o');

  // "o moku!" — command with no subject.
  if (markerIdx === 0 && terms[0].norm === 'o') {
    return { type: 'clause', mood: 'imperative', subject: null, predicates: parsePredicates(terms, ctx) };
  }
  if (markerIdx === 0) {
    ctx.report('particle-at-start', '"li" needs a subject before it.', terms[0].start, terms[0].end);
    return { type: 'clause', mood: 'statement', subject: null, predicates: parsePredicates(terms, ctx) };
  }

  // "mi lukin e ona li pilin e ni" — mi/sina takes its first predicate with no li,
  // then further predicates with li. We only read it this way when the part before
  // the first li has an object; otherwise "mi mute li ..." is a subject ("we").
  if (markerIdx > 1 && BARE_SUBJECTS.has(terms[0].norm) && !['en', 'pi', 'anu'].includes(terms[1].norm)) {
    const firstPred = terms.slice(1, markerIdx);
    if (firstPred.some((t) => t.norm === 'e')) {
      const subject = parseGroup([terms[0]], ctx, 'subject');
      const first = parsePredicate(firstPred, null, ctx, terms[0]);
      return {
        type: 'clause',
        mood: terms[markerIdx].norm === 'o' ? 'imperative' : 'statement',
        subject,
        predicates: [first, ...parsePredicates(terms.slice(markerIdx), ctx)],
      };
    }
  }

  if (markerIdx > 0) {
    const subjTerms = terms.slice(0, markerIdx);
    const marker = terms[markerIdx];
    if (subjTerms.length === 1 && BARE_SUBJECTS.has(subjTerms[0].norm) && marker.norm === 'li') {
      ctx.report('li-after-mi-sina', `"${subjTerms[0].norm} li" — after a lone mi or sina, li is normally dropped.`, subjTerms[0].start, marker.end);
    }
    const subject = parseGroup(subjTerms, ctx, 'subject');
    warnBareName(subject, ctx);
    return {
      type: 'clause',
      mood: marker.norm === 'o' ? 'imperative' : 'statement',
      subject,
      predicates: parsePredicates(terms.slice(markerIdx), ctx),
    };
  }

  // No li / o. "mi moku" and "sina pona" are clauses without li.
  if (BARE_SUBJECTS.has(terms[0].norm) && terms.length > 1 && !['en', 'pi', 'anu'].includes(terms[1].norm)) {
    const subject = parseGroup([terms[0]], ctx, 'subject');
    const pred = parsePredicate(terms.slice(1), null, ctx, terms[0]);
    return { type: 'clause', mood: 'statement', subject, predicates: [pred] };
  }

  // A fragment. If it has "e" in it, someone forgot li.
  const eTok = terms.find((t) => t.norm === 'e');
  if (eTok) {
    ctx.report('object-without-verb', '"e" marks an object, but there is no li, o, mi or sina before it to introduce a verb.', eTok.start, eTok.end);
    const pred = parsePredicate(terms, null, ctx, terms[0]);
    return { type: 'clause', mood: 'statement', subject: null, predicates: [pred] };
  }
  return parseGroup(terms, ctx, 'subject');
}

/** Split "li A li B" / "o A" into predicates. `terms` starts with a marker. */
function parsePredicates(terms: Term[], ctx: Ctx): Predicate[] {
  const segs = splitOn(terms, (t) => t.norm === 'li' || t.norm === 'o');
  const preds: Predicate[] = [];
  // segs[0] is empty (terms starts with the marker).
  for (let i = 1; i < segs.length; i++) {
    const marker = segs[i - 1].splitter!;
    // A middle predicate that's empty ("li li") is already reported as a double particle.
    if (segs[i].items.length === 0 && i < segs.length - 1) continue;
    preds.push(parsePredicate(segs[i].items, marker.norm as 'li' | 'o', ctx, marker));
  }
  return preds;
}

function parsePredicate(terms: Term[], marker: 'li' | 'o' | null, ctx: Ctx, anchor: Term): Predicate {
  const pred: Predicate = { type: 'predicate', marker, preverbs: [], verb: emptyGroup(), xAlaX: false, objects: [], preps: [] };
  if (terms.length === 0) {
    ctx.report(marker ? 'particle-at-end' : 'empty-predicate', `"${anchor.norm}" needs a verb or description after it.`, anchor.start, anchor.end);
    return pred;
  }

  const chunks = splitOn(terms, (t) => t.norm === 'e');
  let verbTerms = chunks[0].items;
  if (verbTerms.length === 0) {
    const e = chunks[0].splitter!;
    ctx.report('empty-predicate', '"e" comes straight after the predicate marker — the verb is missing.', e.start, e.end);
  }

  // Preverbs: wile / sona / ken ... directly followed by another content word.
  while (verbTerms.length > 1 && PREVERBS.has(verbTerms[0].norm) && isContent(verbTerms[1]) && !(verbTerms[1].norm === 'ala' && verbTerms.length === 2)) {
    pred.preverbs.push(verbTerms[0]);
    verbTerms = verbTerms.slice(1);
    // "wile ala wile" — skip the negation/question so the next word is checked as a preverb too.
    if (verbTerms[0]?.norm === 'ala' && verbTerms[1]?.norm === pred.preverbs[pred.preverbs.length - 1].norm) {
      pred.xAlaX = true;
      verbTerms = verbTerms.slice(2);
    }
  }

  // "X ala X" yes/no question on the verb.
  if (verbTerms.length >= 3 && verbTerms[1].norm === 'ala' && verbTerms[0].norm === verbTerms[2].norm) {
    pred.xAlaX = true;
    verbTerms = [verbTerms[0], ...verbTerms.slice(3)];
  }

  const { main, preps } = splitPreps(verbTerms, ctx);
  pred.verb = main.length ? parseGroup(main, ctx, 'predicate') : pred.verb;
  pred.preps.push(...preps);

  for (let i = 1; i < chunks.length; i++) {
    const e = chunks[i - 1].splitter!;
    const objTerms = chunks[i].items;
    if (objTerms.length === 0) {
      ctx.report(i === chunks.length - 1 ? 'particle-at-end' : 'empty-object', '"e" needs an object after it.', e.start, e.end);
      continue;
    }
    const split = splitPreps(objTerms, ctx);
    if (split.main.length) pred.objects.push(parseGroup(split.main, ctx, 'object'));
    pred.preps.push(...split.preps);
  }
  return pred;
}

/**
 * Pull trailing prepositional phrases off a predicate or object:
 * "moku e kili lon tomo" -> object "kili", prep "lon tomo".
 * A preposition at the very start is the verb itself ("mi lon tomo"),
 * and one with nothing after it is just a modifier ("jan sama").
 */
function splitPreps(terms: Term[], ctx: Ctx): { main: Term[]; preps: PrepPhrase[] } {
  const preps: PrepPhrase[] = [];
  const startsPrep = (ts: Term[], i: number) =>
    PREPOSITIONS.has(ts[i].norm) &&
    !['pi', 'en', 'anu'].includes(ts[i - 1].norm) && // "tawa en tan", "lon A anu lon B"
    i + 1 < ts.length &&
    isContent(ts[i + 1]);
  let cut = -1;
  for (let i = 1; i < terms.length; i++) {
    if (startsPrep(terms, i)) {
      cut = i;
      break;
    }
  }
  if (cut < 0) return { main: terms, preps };
  const main = terms.slice(0, cut);
  let rest = terms.slice(cut);
  while (rest.length) {
    let next = -1;
    for (let i = 1; i < rest.length; i++) {
      if (startsPrep(rest, i)) {
        next = i;
        break;
      }
    }
    const chunk = next < 0 ? rest : rest.slice(0, next);
    preps.push({ type: 'prep', prep: chunk[0], object: parseGroup(chunk.slice(1), ctx, 'object') });
    rest = next < 0 ? [] : rest.slice(next);
  }
  return { main, preps };
}

// ---------------------------------------------------------------- phrases

type Role = 'subject' | 'predicate' | 'object';

function parseGroup(terms: Term[], ctx: Ctx, role: Role): Group {
  if (terms.length === 0) return emptyGroup();
  const hasEn = terms.some((t) => t.norm === 'en');
  const hasAnu = terms.some((t) => t.norm === 'anu');
  const joiner: Group['joiner'] = hasEn ? 'en' : hasAnu ? 'anu' : null;

  if (hasEn && role !== 'subject') {
    const en = terms.find((t) => t.norm === 'en')!;
    ctx.report('en-outside-subject', '"en" only joins subjects. For several objects repeat "e"; for several predicates repeat "li".', en.start, en.end);
  }

  const parts = splitOn(terms, (t) => t.norm === 'en' || t.norm === 'anu');
  const items: Phrase[] = [];
  parts.forEach((part, i) => {
    // "jan lawa pi ma A en pi ma B" — the second pi group belongs to the previous phrase.
    if (part.items[0]?.norm === 'pi' && items.length > 0 && part.items.length > 1) {
      const prevPhrase = items[items.length - 1];
      for (const g of splitOn(part.items.slice(1), (t) => t.norm === 'pi')) if (g.items.length) prevPhrase.pi.push(g.items);
      return;
    }
    if (part.items.length === 0) {
      const sp = i === 0 ? part.splitter : parts[i - 1].splitter;
      if (sp) {
        const atEnd = i === parts.length - 1;
        ctx.report(atEnd ? 'particle-at-end' : 'particle-at-start', `"${sp.norm}" needs a phrase on both sides.`, sp.start, sp.end);
      }
      return;
    }
    const ph = parsePhrase(part.items, ctx, role);
    if (ph) items.push(ph);
  });
  return { type: 'group', joiner, items };
}

function parsePhrase(terms: Term[], ctx: Ctx, role: Role): Phrase | null {
  let ts = terms;
  let emphasis = false;
  while (ts.length > 1 && ts[ts.length - 1].norm === 'a') {
    emphasis = true;
    ts = ts.slice(0, -1);
  }

  // Any stray grammar particle left inside a phrase is misplaced.
  for (const t of ts) {
    if (t.kind === 'word' && PARTICLES.has(t.norm) && t.norm !== 'pi') {
      ctx.report('particle-at-start', `"${t.norm}" is a grammar particle and can't sit inside a phrase here.`, t.start, t.end);
    }
  }

  const piSegs = splitOn(ts, (t) => t.norm === 'pi');
  const headPart = piSegs[0].items;
  if (headPart.length === 0) {
    const pi = piSegs[0].splitter!;
    const after = piSegs[1]?.items ?? [];
    if (role === 'predicate' && after.length > 0) {
      ctx.report('pi-without-head', '"li pi ..." (meaning "belongs to") is older colloquial style; modern text usually writes "li ijo pi ..." or rephrases.', pi.start, pi.end);
      return { type: 'phrase', head: after[0], modifiers: after.slice(1), pi: piSegs.slice(2).map((g) => g.items), emphasis };
    }
    ctx.report('particle-at-start', '"pi" needs a word before it to modify.', pi.start, pi.end);
    return null;
  }
  const pi: Term[][] = [];
  for (let i = 1; i < piSegs.length; i++) {
    const marker = piSegs[i - 1].splitter!;
    const group = piSegs[i].items;
    if (group.length === 0) {
      ctx.report(i === piSegs.length - 1 ? 'particle-at-end' : 'empty-pi', '"pi" needs words after it.', marker.start, marker.end);
      continue;
    }
    if (group.length === 1) {
      ctx.report('pi-single-word', `"pi ${group[0].text}" — pi is normally followed by two or more words; with one, just drop pi.`, marker.start, group[0].end);
    }
    pi.push(group);
  }
  return { type: 'phrase', head: headPart[0], modifiers: headPart.slice(1), pi, emphasis };
}

function warnBareName(subject: Group, ctx: Ctx) {
  for (const p of subject.items) {
    if (p.head.kind === 'name') {
      ctx.report('bare-name', `"${p.head.text}" is used on its own; names usually follow a head word, like "jan ${p.head.text}" or "ma ${p.head.text}".`, p.head.start, p.head.end);
    }
  }
}

// ---------------------------------------------------------------- tokens -> terms

function toTerms(tokens: Token[], ctx: Ctx): Term[] {
  const terms: Term[] = [];
  const allowed = ctx.allowed;
  let prev: Token | undefined;
  for (const tok of tokens) {
    const continuesHyphen = !!(tok.fromHyphen && prev?.fromHyphen && prev.end + 1 === tok.start);
    prev = tok;
    if (tok.kind === 'comma') continue;
    if (tok.kind === 'symbol') {
      ctx.report('stray-symbol', `Unexpected character "${tok.text}".`, tok.start, tok.end);
      continue;
    }
    if (tok.kind === 'quote' || tok.kind === 'number') {
      terms.push({ kind: tok.kind, text: tok.text, norm: tok.norm, start: tok.start, end: tok.end });
      continue;
    }
    // Words
    if (tok.fromHyphen && !continuesHyphen) {
      ctx.report('hyphenated', 'Hyphenated compounds (like toki-pona) are old style; modern text writes the words separately.', tok.start, tok.end);
    }
    const lower = tok.norm;
    const capitalised = /^[A-Z]/.test(tok.text);
    // A capitalised grammar particle mid-sentence is a name, never the particle:
    // "jan Li", "nimi A", "nanpa Pi".
    const particleAsName = capitalised && !tok.sentenceInitial && (PARTICLES.has(lower) || lower === 'a');
    if (isKnown(lower) && !particleAsName) {
      const info = lookup(lower)!;
      if (!allowed.has(info.category)) {
        ctx.report('uncommon-word', `"${lower}" is a ${info.category} word.`, tok.start, tok.end);
      }
      if (info.deprecated) ctx.report('deprecated-word', `"${lower}" is deprecated.`, tok.start, tok.end);
      terms.push({ kind: 'word', text: tok.text, norm: lower, start: tok.start, end: tok.end });
    } else if (capitalised) {
      if (!isValidPhonotactics(tok.text)) {
        ctx.report('name-phonotactics', `The name "${tok.text}" doesn't follow toki pona sound rules.`, tok.start, tok.end);
      }
      terms.push({ kind: 'name', text: tok.text, norm: lower, start: tok.start, end: tok.end });
    } else {
      ctx.report('unknown-word', `"${tok.text}" isn't a toki pona word. Names must be capitalised.`, tok.start, tok.end);
      terms.push({ kind: 'word', text: tok.text, norm: lower, start: tok.start, end: tok.end });
    }
  }
  return terms;
}

// ---------------------------------------------------------------- helpers

function isContent(t: Term | undefined): boolean {
  return !!t && !(t.kind === 'word' && PARTICLES.has(t.norm));
}

function emptyGroup(): Group {
  return { type: 'group', joiner: null, items: [] };
}

interface Segment {
  items: Term[];
  /** The term that ended this segment (absent on the last one). */
  splitter?: Term;
}

function splitOn(terms: Term[], pred: (t: Term) => boolean): Segment[] {
  const out: Segment[] = [];
  let cur: Term[] = [];
  for (const t of terms) {
    if (t.kind === 'word' && pred(t)) {
      out.push({ items: cur, splitter: t });
      cur = [];
    } else {
      cur.push(t);
    }
  }
  out.push({ items: cur });
  return out;
}

export { categoryOf };
