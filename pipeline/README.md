# Translation pipeline

Turns English TinyStories into checked toki pona training data. Each step reads the previous step's file and can be re-run safely: finished stories are skipped, so an interrupted run picks up where it stopped.

```
sample  →  translate  →  check  →  back  →  report
          (API, with      (grammar +   (API)    (calibrates the cutoff,
          self-repair)    meaning)              writes the kept set)
```

## Running it

You need Node 22.6+ and an API key from console.anthropic.com.

```sh
export ANTHROPIC_API_KEY=sk-ant-...
R="node --experimental-strip-types --no-warnings pipeline/run.ts"

$R sample    --input TinyStoriesV2-GPT4-train.txt --out run/stories.jsonl --n 10000
$R translate --in run/stories.jsonl    --out run/translated.jsonl
$R check     --in run/translated.jsonl --out run/checked.jsonl
$R back      --in run/checked.jsonl    --out run/back.jsonl
$R report    --checked run/checked.jsonl --back run/back.jsonl --keep run/kept.jsonl
```

Get the TinyStories text from https://huggingface.co/datasets/roneneldan/TinyStories (`TinyStoriesV2-GPT4-train.txt` or the smaller `-valid.txt`).

Start with `--n 100` and look at the report before paying for 10,000.

## What each step does

**sample** picks stories between `--min` and `--max` words (default 50–100) and skips fragments.

**translate** sends each story to the model with the rules in `prompts.ts` (allowed vocabulary, pu grammar, name rules, no quotation marks) and two worked examples. If the strict grammar checker finds errors, the model is shown the exact problems and asked to rewrite, up to `--repairs` times (default 2). The default model is `claude-sonnet-5-5`; change it with `--model`. `--concurrency` (default 4) sets how many requests run at once.

**check** runs two free, offline checks on every translation:
- grammar, using tp-parse's `STRICT` mode
- meaning coverage: the share of the English story's concepts that some toki pona word in the translation can express (from Linku's glosses plus a list of common compounds like *pilin pona* = happy). The default cutoff is 85%.

**back** asks the model to translate the toki pona back into English, without showing it the original, then measures how many of the original's concepts came back. Only stories that passed **check** are sent, so you don't pay to back-translate rejects.

**report** prints why stories were rejected and writes the survivors to `--keep`. It also calibrates: it scores every translation against a *different* story's English to see what a wrong translation looks like, and with `--min-recall auto` (the default) picks the lowest back-translation cutoff that lets at most 5% of those wrong pairs through.

## Pilot results (50 stories)

`pilot/translated.jsonl` has 50 TinyStories translated by Claude in a chat (no API), following the same rules as the prompt.

- **Grammar:** 49 of 50 passed strict mode on the first try. The failure was a real mistake: the name *Peti* (for Betty) uses the illegal syllable *ti*. In a test run against a mock API, the self-repair step fixed it.
- **Meaning coverage:** every real translation scored at least 87%, median 100%. Pairing each translation with the *wrong* story scored a median of about 70%. At the 85% cutoff, all 50 real translations pass and 5 of 50 wrong-story pairs slip through, so this check catches gross failures (wrong story, truncated or garbled output) but not subtle ones. That's what back-translation is for.
- **Back-translation:** not measured yet. It needs a real model, and the mock server only produces a word-by-word gloss.

The pilot also turned up three bugs, now fixed: capitalised names that happen to be rare dictionary words (*San*, *Su*) were read as words; *sina sona ala sona e X* lost its verb in the tree; and the meaning check's English stemmer turned "wanted" into "wante".

## Testing without a key

`mock-server.ts` imitates the API: it answers translation requests from a JSONL file, applies scripted fixes to repair requests, back-translates with a word-by-word gloss, and returns one "overloaded" error first so the retry logic runs.

```sh
MOCK_TRANSLATIONS=pipeline/pilot/translated.jsonl MOCK_FIXES="Peti=>Pesi" \
  node --experimental-strip-types pipeline/mock-server.ts 8787 &
export ANTHROPIC_API_KEY=mock ANTHROPIC_BASE_URL=http://localhost:8787
# then run the steps above with --model mock
```

## Cost

Estimated from the pilot at four characters per token, translation takes roughly 900 input tokens and 135 output tokens per story (the prompt and examples are most of the input), before any repairs. The first real run's report will give exact numbers. Back-translation adds a smaller request per story that passes. Check current per-token prices at https://www.anthropic.com/pricing and multiply. For a large run, the Message Batches API and prompt caching (the system prompt is the same on every request) would both cut the cost; the pipeline doesn't use them yet.
