import { WORDS, type UsageCategory } from './words.ts';

export const PARTICLES = new Set(['li', 'e', 'la', 'pi', 'o', 'en', 'anu']);
export const PREPOSITIONS = new Set(['lon', 'tawa', 'tan', 'sama', 'kepeken']);
export const PREVERBS = new Set(['wile', 'sona', 'awen', 'kama', 'ken', 'lukin', 'alasa', 'open', 'pini']);
/** Subjects that take their predicate without "li". */
export const BARE_SUBJECTS = new Set(['mi', 'sina']);

export function lookup(word: string) {
  return WORDS[word];
}

export function isKnown(word: string): boolean {
  return word in WORDS;
}

export function categoryOf(word: string): UsageCategory | undefined {
  return WORDS[word]?.category;
}

const SYLLABLES = /^(?:[aeiou]|[jklmnpstw][aeiou])(?:n(?![nm]))?(?:[jklmnpstw][aeiou](?:n(?![nm]))?)*$/;
const FORBIDDEN = /ji|ti|wo|wu/;

/**
 * Whether a word follows toki pona sound rules: (C)V(n) syllables, only
 * p t k s m n l j w and a e i o u, no ji/ti/wo/wu, no n before n or m.
 * Used to check unofficial names like "Keli" or "Kanata".
 */
export function isValidPhonotactics(word: string): boolean {
  const w = word.toLowerCase();
  return SYLLABLES.test(w) && !FORBIDDEN.test(w);
}
