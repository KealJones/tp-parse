# tp-parse

**Try it in your browser: https://kealjones.github.io/tp-parse/**

A forgiving parser and validator for toki pona, written in TypeScript with no dependencies. Give it text, and it returns a parse tree for every sentence plus a list of problems, each with a code, a severity, a plain-English message, and the exact character range. It never throws on bad input.

It was built as the grammar-check step for a training-data pipeline (translate English into toki pona with an LLM, then keep only the translations that hold up), but it works anywhere: Node, a browser, or the command line.

## Quick start

Needs Node 22.6 or newer. TypeScript runs directly, with no build step.

```sh
npm run cli -- "jan pona mi li moku e kili. jan moku e telo."
```

```
✓ jan pona mi li moku e kili.  (clause)
✗ jan moku e telo.  (clause)
    error object-without-verb  "e" marks an object, but there is no li, o, mi or sina before it to introduce a verb.  "e"
2 sentence(s), 1 error(s), 0 warning(s)
```

### As a library

```ts
import { parse, isValid, STRICT } from './src/index.ts';

const result = parse('tenpo pini la jan pona mi li wile pali e tomo pi kiwen mute lon ma kasi.');
result.ok;                                  // true
result.sentences[0].contexts;               // [tenpo pini]
result.sentences[0].clause.predicates[0];   // preverb wile, verb pali, object tomo pi kiwen mute, prep lon ma kasi

isValid('jan moku e kili.');                // false (missing li)
isValid('mi lanpan e ni.', STRICT);         // false (lanpan is an "uncommon" word)
```

### Filtering a dataset

Keep only the JSONL records whose `tp` field is clean, modern toki pona:

```sh
npm run cli -- --filter --field tp --strict < translations.jsonl > clean.jsonl
# prints "kept N, dropped M" to stderr
```

Without `--field`, each line is treated as plain text.

## What it checks

**Errors** (the sentence is rejected):

| code | example | why |
| --- | --- | --- |
| `unknown-word` | mi moku e *blorp* | not in the dictionary, and not capitalised as a name |
| `object-without-verb` | jan moku *e* kili | `e` with no `li`, `o`, `mi` or `sina` before it — the classic missing-li mistake |
| `particle-at-end` | mi moku *e* | `li`, `e`, `pi`, `la`, `en`, `anu` with nothing after |
| `particle-at-start` | *pi* ijo | a particle where a word should be |
| `double-particle` | jan *li li* moku | two particles in a row |
| `empty-context` | *la* mi moku | `la` with nothing before it |
| `empty-predicate`, `empty-object`, `empty-pi` | | a marker with nothing in its slot |

**Warnings** (accepted by default; `STRICT` turns them into errors):

| code | example | note |
| --- | --- | --- |
| `uncommon-word` | mi *lanpan* e ni | outside Linku's core + common words |
| `deprecated-word` | | marked deprecated in Linku |
| `li-after-mi-sina` | *mi li* moku | li is normally dropped after a lone mi or sina |
| `en-outside-subject` | mi moku e kili *en* telo | en joins subjects; repeat `e` for objects |
| `pi-single-word` | tomo *pi telo* | pi normally takes 2+ words |
| `pi-without-head` | ni li *pi* mi | older colloquial "belongs to" |
| `bare-name` | *Sonja* li pona | names usually follow a head word: jan Sonja |
| `name-phonotactics` | jan *Bob* | breaks toki pona sound rules |
| `hyphenated` | *toki-pona* | old style compound |
| `stray-symbol` | | a character that isn't toki pona text |

`STRICT` keeps unofficial names allowed (they're needed for translated stories) but requires them to follow toki pona sound rules.

## What it understands

- `la` contexts, including several in a row
- vocatives (`jan Keli o,`), including several in a row, and bare `o` commands
- `mi`/`sina` taking a predicate without `li`, then more predicates with `li`
- preverbs (`wile`, `ken`, `sona`, `kama`, `awen`, `lukin`, `alasa`, `open`, `pini`)
- trailing prepositional phrases (`lon`, `tawa`, `tan`, `sama`, `kepeken`), joined ones like `tawa en tan`
- `pi` groups, including `X pi A en pi B`
- `en` and `anu` groups, `X ala X` questions, `anu seme` tag questions
- sentence-initial `taso`, leading exclamations (`pona a, mi ...`), emphatic `a`
- quoted text as a single opaque word, so punctuation inside quotes never splits sentences
- capitalised particles mid-sentence are names (`jan Li`, `nimi A`)

Colons end a sentence, so `mi toki e ni: sina pona` is checked as two sentences.

## How well it does

Run over the [nltk-tp](https://github.com/davidar/nltk-tp) corpus (about 880,000 words of real toki pona from 2001 onward, 114,000 sentences), it accepts **95.8%** of the sentences whose words are all known. A random sample of the rest is almost entirely genuine mistakes in that older, learner-heavy corpus (mostly a missing `li`, like *ona lukin e ni*), plus metadata lines the corpus picked up (usernames and post numbers in front of sentences). The whole corpus parses in about two seconds.

```sh
npm run corpus -- path/to/nltk-tp/Corpus
npm run corpus -- path/to/nltk-tp/Corpus --samples object-without-verb
```

## Limits

- It checks **structure, not meaning**. *kili li moku e jan* (the fruit eats the person) is perfectly grammatical. For translation quality you still need a meaning check such as back-translation.
- toki pona is ambiguous by design. Where a sentence has two valid readings, the tree picks one (for example, *mi moku li lape* is read as subject *mi moku*). Validity doesn't depend on which.
- It accepts some looser community usage as warnings rather than errors. Use `STRICT` or `severityOverrides` to tighten it.

## Meaning check

`checkMeaning(english, tokiPona)` estimates how much of an English source a translation carries over, using Linku's English glosses for each word plus common compounds (*pilin pona* = happy, *jan pona* = friend). `compareEnglish(original, backTranslation)` scores a back-translation the same way, and `gloss(tokiPona)` gives a word-by-word English reading. These are rough signals for ranking and flagging, not judges of translation quality.

```ts
checkMeaning('The dog ate the bread.', 'soweli li moku e pan.').coverage; // 1
gloss('soweli li moku e pan.'); // "fuzzy creature li eat e grains."
```

## Translation pipeline

`pipeline/` turns English TinyStories into checked toki pona training data: translate with an LLM (with self-repair from the checker's errors), check grammar and meaning, back-translate, and keep what survives. See [pipeline/README.md](pipeline/README.md), including results from a 50-story pilot.

## Browser

`scripts/build-demo.sh` bundles the parser (about 20 KB) into a single self-contained page that runs entirely in the browser: `docs/index.html` is the full page served by GitHub Pages, and `demo/index.html` is the same page without its document wrapper. The bundle exposes a global `TP` with the same API.

## Project layout

```
src/
  parse.ts      parser and validator
  tokenize.ts   tokens and sentence splitting
  lexicon.ts    particles, prepositions, preverbs, phonotactics
  words.ts      generated word list (from lipu Linku)
  presets.ts    STRICT options
  cli.ts        command line
test/           unit tests (npm test)
src/meaning.ts  meaning coverage, back-translation comparison, glossing
src/glosses.ts  generated English glosses (from lipu Linku)
pipeline/       LLM translation pipeline and pilot data
scripts/        corpus report, word-list, gloss and demo builders
demo/           browser page source (template.html)
docs/           built page served by GitHub Pages
```

To refresh the word list from Linku: clone https://github.com/lipu-linku/sona and run `python3 scripts/build-words.py path/to/sona`.

## Credits and licence

Code: MIT, © 2026 Keal Jones.

The word list in `src/words.ts` and the glosses in `src/glosses.ts` come from [lipu Linku](https://linku.la/) (the `sona` repository) and is licensed CC BY-SA 4.0.

This is a fresh implementation written from the toki pona grammar. It doesn't include code from matthewdeanmartin/tokipona.parser, which has no licence.
