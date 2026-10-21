export { parse, isValid } from './parse.ts';
export type {
  ParseResult,
  ParseOptions,
  Sentence,
  SentenceKind,
  Clause,
  Predicate,
  PrepPhrase,
  Group,
  Phrase,
  Term,
  Issue,
  IssueCode,
  Severity,
} from './parse.ts';
export { tokenize, splitSentences } from './tokenize.ts';
export { isValidPhonotactics, PARTICLES, PREPOSITIONS, PREVERBS } from './lexicon.ts';
export { WORDS } from './words.ts';
export { STRICT } from './presets.ts';
export { checkMeaning, compareEnglish, gloss, lemma } from './meaning.ts';
export type { MeaningCheck, EnglishComparison } from './meaning.ts';
