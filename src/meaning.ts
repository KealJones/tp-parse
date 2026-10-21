// A cheap, mechanical meaning check for translations.
//
// For each content word in the English source, look up which toki pona words
// can mean it (from Linku's definitions and the ku translation data). If any
// of those appear in the translation, the concept was carried over. English
// words that no toki pona word glosses directly (celebrate, thermometer) are
// "unmappable" and left out of the score instead of counting against it.
//
// It's a rough signal, not a judge: it can't tell "the dog bit the man" from
// "the man bit the dog". Use it to rank or flag translations, then spend
// back-translation on the ones that matter.

import { GLOSSES, PRIMARY_GLOSS } from './glosses.ts';
import { tokenize } from './tokenize.ts';

const IRREGULAR: Record<string, string> = {
  ran: 'run', ate: 'eat', saw: 'see', seen: 'see', went: 'go', gone: 'go', felt: 'feel', said: 'say',
  found: 'find', took: 'take', taken: 'take', gave: 'give', given: 'give', made: 'make', came: 'come',
  got: 'get', had: 'have', has: 'have', was: 'be', were: 'be', is: 'be', are: 'be', am: 'be', been: 'be',
  sat: 'sit', threw: 'throw', fell: 'fall', flew: 'fly', drank: 'drink', thought: 'think', knew: 'know',
  told: 'tell', left: 'leave', kept: 'keep', lay: 'lie', drew: 'draw', wrote: 'write', written: 'write',
  met: 'meet', children: 'child', mice: 'mouse', feet: 'foot', teeth: 'tooth', men: 'man', women: 'woman',
  people: 'person', bought: 'buy', brought: 'bring', caught: 'catch', taught: 'teach', sold: 'sell',
  heard: 'hear', held: 'hold', stood: 'stand', slept: 'sleep', swam: 'swim', sang: 'sing', won: 'win',
  lost: 'lose', hid: 'hide', hidden: 'hide', blew: 'blow', grew: 'grow', grown: 'grow', began: 'begin',
  best: 'good', better: 'good', worse: 'bad', worst: 'bad', mommy: 'mom', mummy: 'mom', mama: 'mom',
  daddy: 'dad', tummy: 'stomach', yummy: 'tasty',
};

// Common English words that toki pona expresses with a standard compound or an
// everyday construction (pilin pona = happy, jan pona = friend). The single-word
// glosses can't see these, so they're listed here. Hand-written; the compounds
// follow the ku dictionary's most common choices.
const SUPPLEMENT: Record<string, string[]> = {
  happy: ['pona', 'pilin'], glad: ['pona', 'pilin'], sad: ['ike', 'pilin'], upset: ['ike', 'pilin'],
  angry: ['utala', 'pilin'], scared: ['monsuta', 'pilin'], afraid: ['monsuta'], excite: ['wawa', 'pilin'],
  proud: ['suli', 'pilin'], tired: ['lape'], tire: ['lape'], hungry: ['wile', 'moku'], careful: ['awen', 'pona'],
  friend: ['jan', 'pona'], boy: ['mije', 'jan'], girl: ['meli', 'jan'], kid: ['jan', 'lili'], child: ['jan', 'lili'],
  baby: ['jan', 'lili'], brother: ['sama', 'jan'], sister: ['sama', 'jan'], family: ['kulupu', 'mama'],
  everyone: ['jan', 'ale'], everybody: ['jan', 'ale'], someone: ['jan'], something: ['ijo'], everything: ['ijo', 'ale'],
  play: ['musi'], fun: ['musi'], toy: ['ilo', 'musi'], game: ['musi'], laugh: ['kalama', 'musi'], dance: ['tawa', 'musi'],
  sing: ['kalama', 'musi'], song: ['kalama', 'musi'], music: ['kalama', 'musi'], smile: ['pona', 'pilin', 'uta'],
  help: ['pona', 'pana'], helpful: ['pona'], share: ['pana'], give: ['pana'], gift: ['pana'],
  want: ['wile'], need: ['wile'], wish: ['wile'], like: ['olin', 'pona', 'wile'], love: ['olin'], decide: ['wile', 'pilin'],
  ask: ['toki', 'wile', 'sona'], tell: ['toki'], talk: ['toki'], say: ['toki'], call: ['toki', 'nimi'],
  look: ['lukin'], watch: ['lukin'], see: ['lukin'], find: ['lukin', 'alasa', 'jo'], search: ['alasa'], try: ['alasa', 'lukin'],
  meet: ['kama', 'lukin', 'sona'], learn: ['kama', 'sona'], know: ['sona'], think: ['pilin', 'sona'], idea: ['sona'],
  take: ['jo', 'kama', 'tawa'], get: ['jo', 'kama'], carry: ['jo', 'tawa'], bring: ['tawa', 'pana'], hold: ['jo'],
  keep: ['awen', 'jo'], put: ['pana'], make: ['pali'], build: ['pali'], fix: ['pona', 'pali'], repair: ['pona'],
  cook: ['pali', 'seli', 'moku'], eat: ['moku'], drink: ['moku', 'telo'], tasty: ['pona', 'suwi'], delicious: ['pona', 'suwi'],
  run: ['tawa', 'wawa'], walk: ['tawa', 'noka'], jump: ['tawa', 'sewi'], fly: ['tawa', 'kon', 'waso'], climb: ['tawa', 'sewi'],
  swim: ['tawa', 'telo'], fall: ['anpa', 'tawa'], go: ['tawa'], come: ['kama'], leave: ['weka', 'tawa'], stop: ['pini'],
  start: ['open'], begin: ['open'], finish: ['pini'], end: ['pini'], sit: ['awen', 'supa'], rest: ['lape', 'awen'],
  sleep: ['lape'], bed: ['supa', 'lape'], house: ['tomo'], home: ['tomo'], room: ['tomo'], store: ['tomo', 'esun'],
  shop: ['esun'], buy: ['esun'], sell: ['esun'], money: ['mani'], coin: ['mani'], park: ['ma', 'kasi'],
  forest: ['ma', 'kasi'], garden: ['ma', 'kasi'], tree: ['kasi'], flower: ['kasi', 'kule'], grass: ['kasi'],
  river: ['telo'], sea: ['telo'], beach: ['telo', 'ko'], rain: ['telo', 'sewi'], snow: ['ko', 'lete'], cloud: ['kon', 'sewi'],
  night: ['pimeja', 'tenpo'], morning: ['suno', 'tenpo'], today: ['tenpo', 'suno'], soon: ['tenpo', 'lili'],
  floor: ['anpa', 'ma', 'supa'], car: ['tomo', 'tawa'], boat: ['tomo', 'tawa', 'telo'], cake: ['pan', 'suwi'],
  thing: ['ijo'], animal: ['soweli', 'waso', 'kala', 'pipi'], pet: ['soweli'], pretty: ['pona', 'lukin'],
  beautiful: ['pona', 'lukin'], ugly: ['ike', 'lukin'], shiny: ['suno'], loud: ['kalama', 'wawa'],
  quiet: ['kalama', 'ala'], fast: ['wawa', 'tawa'], slow: ['lili', 'tawa'], hurt: ['pakala', 'ike'], sorry: ['pakala'],
  kind: ['pona'], nice: ['pona'], mean: ['ike'], rude: ['ike'], brave: ['wawa'], strong: ['wawa'],
  safe: ['awen', 'pona'], dangerous: ['ike', 'monsuta'], special: ['suli', 'pona'], favorite: ['pona', 'nanpa', 'wan'],
  surprise: ['nasa'], unexpected: ['nasa'], lose: ['weka'], forget: ['weka', 'sona'], remember: ['awen', 'sona'],
  together: ['sama', 'tenpo', 'kulupu'], alone: ['wan', 'taso'], big: ['suli'], little: ['lili'], small: ['lili'],
  man: ['mije', 'jan'], woman: ['meli', 'jan'], lady: ['meli', 'jan'], mom: ['mama', 'meli'], dad: ['mama', 'mije'],
};

const STOP = new Set(`
a an the and or but if then so to of in on at by for with from up down out over into onto off about
around through after before again once upon while when where why how what who whom which that this these
those there here he she it they we you i me him her them his hers its their theirs my mine your yours our
ours be do have will would can could should shall may might must not no yes very too also just really all
some any many much more most other another each every both either such only own same than as one two
let lets let's okay oh wow hi hello thank thanks please the end ever after day one-day time happily
name named
`.split(/\s+/).filter(Boolean));

// English word -> toki pona words that can express it.
const INDEX = new Map<string, Set<string>>();
const addIndex = (english: string, tp: string) => {
  if (!INDEX.has(english)) INDEX.set(english, new Set());
  INDEX.get(english)!.add(tp);
};
for (const [tp, glosses] of Object.entries(GLOSSES)) for (const g of glosses) addIndex(g, tp);
for (const [english, tps] of Object.entries(SUPPLEMENT)) for (const tp of tps) addIndex(english, tp);

const KNOWN_FORMS = new Set([...INDEX.keys(), ...Object.values(IRREGULAR), ...STOP]);

/**
 * Small English lemmatiser for children's stories. Strips common endings and,
 * where several stems are possible (wanted -> want, loved -> love,
 * running -> run, baking -> bake), prefers the one that's a known word.
 */
export function lemma(word: string): string {
  let w = word.toLowerCase().replace(/[’']s$/, '').replace(/[’']/g, '');
  if (IRREGULAR[w]) return IRREGULAR[w];
  if (w.length <= 3) return w;
  const pick = (...candidates: string[]) => candidates.find((c) => KNOWN_FORMS.has(c)) ?? candidates[0];
  const undouble = (s: string) => (/([bdgklmnprt])\1$/.test(s) ? s.slice(0, -1) : s);
  if (w.endsWith('ily') && w.length > 5) return pick(w.slice(0, -3) + 'y', w); // happily -> happy
  if (w.endsWith('ly') && w.length > 5) return pick(w.slice(0, -2), w); // quickly -> quick
  if (w.endsWith('ies') && w.length > 4) return w.slice(0, -3) + 'y';
  if (w.endsWith('ied') && w.length > 4) return w.slice(0, -3) + 'y';
  if (w.endsWith('ing') && w.length > 5) {
    const stem = w.slice(0, -3);
    return pick(stem, undouble(stem), stem + 'e');
  }
  if (w.endsWith('ed') && w.length > 4) {
    const stem = w.slice(0, -2);
    return pick(stem, undouble(stem), w.slice(0, -1));
  }
  if (/(ss|sh|ch|x)es$/.test(w)) return w.slice(0, -2);
  if (w.endsWith('s') && !w.endsWith('ss') && !w.endsWith('us')) return pick(w.slice(0, -1), w);
  return w;
}

export interface MeaningCheck {
  /** covered / mappable, from 0 to 1. Null when nothing in the English could be mapped. */
  coverage: number | null;
  /** English concepts (lemmas) a toki pona word could express. */
  mappable: string[];
  /** ...of those, ones the translation does express. */
  covered: string[];
  /** ...and ones it doesn't. These are the ones to look at. */
  missing: { english: string; couldUse: string[] }[];
  /** English words no single toki pona word glosses (left out of the score). */
  unmappable: string[];
  /** Capitalised words skipped as names. */
  names: string[];
}

/** Which English words in the source are names (capitalised mid-sentence). */
function findNames(english: string): Set<string> {
  const names = new Set<string>();
  const re = /([.!?:"“]\s*|^\s*)?\b([A-Z][a-z]+)\b/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(english))) if (!m[1]) names.add(m[2].toLowerCase());
  return names;
}

export function checkMeaning(english: string, tokiPona: string): MeaningCheck {
  const tpWords = new Set(tokenize(tokiPona).filter((t) => t.kind === 'word').map((t) => t.norm));
  const names = findNames(english);
  const seen = new Set<string>();
  const result: MeaningCheck = { coverage: null, mappable: [], covered: [], missing: [], unmappable: [], names: [...names] };

  for (const raw of english.match(/[A-Za-z][A-Za-z'’-]*/g) ?? []) {
    const lower = raw.toLowerCase();
    if (names.has(lower)) continue;
    const l = lemma(lower);
    if (STOP.has(lower) || STOP.has(l) || seen.has(l)) continue;
    seen.add(l);
    const options = INDEX.get(l) ?? INDEX.get(lower);
    if (!options) {
      result.unmappable.push(l);
      continue;
    }
    result.mappable.push(l);
    if ([...options].some((tp) => tpWords.has(tp))) result.covered.push(l);
    else result.missing.push({ english: l, couldUse: [...options].slice(0, 6) });
  }
  result.coverage = result.mappable.length ? result.covered.length / result.mappable.length : null;
  return result;
}

/** Word-by-word English reading of toki pona text, e.g. "person / good / me / li / eat". */
export function gloss(tokiPona: string): string {
  return tokenize(tokiPona)
    .filter((t) => t.kind !== 'comma')
    .map((t) => (t.kind === 'word' ? (/^[A-Z]/.test(t.text) && !(t.norm in PRIMARY_GLOSS) ? t.text : PRIMARY_GLOSS[t.norm] ?? t.text) : t.text))
    .join(' ')
    .replace(/ ([.!?:,])/g, '$1');
}

const GENERIC = new Set(
  'jan pilin tenpo ma ijo kama lon tawa pana jo toki lukin sona wile pali ala sama kulupu ilo tomo kasi telo lili suli mute wan ken awen open pini'.split(' '),
);

export interface EnglishComparison {
  /** Share of the original's concepts found again in the back-translation, 0 to 1. */
  recall: number | null;
  /** Concepts from the original that came back (exactly or as a toki pona synonym). */
  kept: string[];
  /** Concepts from the original that didn't come back. */
  lost: string[];
}

function contentLemmas(text: string): Set<string> {
  const names = findNames(text);
  const out = new Set<string>();
  for (const raw of text.match(/[A-Za-z][A-Za-z'’-]*/g) ?? []) {
    const lower = raw.toLowerCase();
    if (names.has(lower)) continue;
    const l = lemma(lower);
    if (!STOP.has(lower) && !STOP.has(l)) out.add(l);
  }
  return out;
}

/**
 * Compare an original English story with its back-translation. A concept counts
 * as kept if the same word comes back, or a word that toki pona expresses the
 * same way (so "dog" coming back as "animal", or "glad" as "happy", still counts).
 */
export function compareEnglish(original: string, backTranslation: string): EnglishComparison {
  const a = contentLemmas(original);
  const b = contentLemmas(backTranslation);
  // Matching through a very general word would make "happy" equal "sad" (both use pilin),
  // so synonyms only count when they share a specific toki pona word.
  const specific = (w: string) => [...(INDEX.get(w) ?? [])].filter((tp) => !GENERIC.has(tp));
  const bTp = new Set<string>();
  for (const w of b) for (const tp of specific(w)) bTp.add(tp);
  const kept: string[] = [];
  const lost: string[] = [];
  for (const w of a) {
    const same = b.has(w) || specific(w).some((tp) => bTp.has(tp));
    (same ? kept : lost).push(w);
  }
  return { recall: a.size ? kept.length / a.size : null, kept, lost };
}
