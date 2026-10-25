# Findout pilot (v2)

A cheap test, before spending $20–40 on the full plan ([Figure-it-out model plan](https://claude.ai/artifact/G6ciovi1M9LaqeftgCUnhh)), of the thing run 1 failed at: putting known steps together into a plan it has never seen.

- **World v2** (`world2.py`): tasks are small plans built from parts (look up, use what's given, ask, calculate, compare, follow a link). Ten task types are trained on. Five combinations of those same parts are held out for testing: comparing two costs, a four-way comparison, a link inside a comparison, the person's answer feeding a calculation, and a three-item basket. Half the requests are rewritten in Keal's style, with false starts, self-corrections and repeats. Search results include a fact about a different thing, which has to be ignored. `python world2.py` replays 4,500 gold episodes through the harness; all pass.
- **Teacher** (`teacher.py`, Kaggle 2×T4, free): Qwen3-4B-Instruct-2507 works through 3,000 tasks with the real tools and no answer key. Only fully right episodes are kept. Template-written examples taught the askfirst model to recite, so the teacher's own wording is the main training set.
- **Pilot** (`pilot.py`, Hugging Face L4, about $1 in total): LFM2.5-350M, untouched (two worked examples in the prompt), then fully fine-tuned on about 2,000 template episodes (`gold`) or 2,000 teacher episodes (`teacher`). Each trained arm also replays 20% of the base model's own everyday answers. Tests: the trained types on fresh worlds, the held-out combinations, clean against messy requests, WikiText-2 perplexity, and plain chat with and without tools.

**Go/no-go** (computed in `PILOT_RESULTS.md`): held-out mean at least 50% with no held-out type under 20% (run 1 scored 0% on cost-compare), English perplexity up at most 15%, at most 1 broken plain-chat reply, and messy requests within 10 points of clean ones.

## Results (Sun 25 Oct 2026, run `findout2-pilot-all-2`, full numbers in `hf-pilot-all-2/PILOT_RESULTS.md`)

**Verdict: NOT YET for both trained arms.** Held-out strict mean was 26% (gold) and 28% (teacher) against the 50% bar, with at least one held-out type at 0% in each. The untouched model scored 0% strict. Run 1 (SmolLM2-135M) also scored 0% on unseen plans, so this is progress, but short of the bar.

| strict score | untouched | gold | teacher |
| --- | --- | --- | --- |
| trained types, mean | 4% | 99% | 88% |
| held-out: cost-compare | 0% | 58% | 62% |
| held-out: basket3 | 0% | 46% | 46% |
| held-out: argmax4 | 0% | 25% | 12% |
| held-out: ask-diff | 0% | 0% | 21% |
| held-out: bridge-compare | 0% | 0% | 0% |
| **held-out, mean** | 0% | 26% | 28% |
| held-out, right answer only | 16% | 38% | 45% |
| English perplexity as an assistant reply (base 75.8) | 75.8 | 62.8 | 65.5 |

Other gates: English perplexity passed for both (it went down). Plain chat without tools: gold 0 broken, teacher 2 broken (the teacher arm looped on "hey whats up lol"), and the bar is at most 1. Messy vs clean on trained types: gold +0, teacher +10 points (at the limit).

**What the failures show**
- **Chains stop early.** In bridge-compare ("which is bigger: Kobripel's town or Drasor?") both arms look up the link (where Kobripel lives) but skip the search for that town's population, then compare against an invented or unrelated number. Gold compared an age with a made-up 10.
- **It doesn't check that a found fact is about the right thing.** In ask-diff the teacher arm asked for the person's town correctly, then used another town's population from an unrelated line as the second number. Gold often searched "my town population" instead of asking, then made up 1234. Both arms asked when they needed to only 54% of the time.
- **Plans are mostly right when the parts are familiar, wrong on the glue.** Held-out cost-compare and basket3 work about half the time. On held-out types it searched every needed thing 77% of the time and used the calculator 72% (gold) / 84% (teacher).
- **The teacher data is thin where the teacher skipped the calculator.** Only 30 compare2 and 9 argmax3 episodes were kept (of 188 and 156), so the teacher arm is weaker on those (62% and 46%) and on the held-out argmax4 that builds on argmax3 (12% vs gold's 25%).
- **Chitchat is fragile once trained.** "hey whats up lol" got a made-up needs list from gold when tools were offered, and repeated broken tool-call text from the teacher arm without tools (the 2 broken replies).

**Not resolved:** raw-text WikiText perplexity is 2,134 for the base model and identical with and without the attention mask, so the first measurement is not an attention-mask bug. It is still unexplained (trained models score 426 and 523). The verdict uses the as-an-assistant-reply number, which is sane (about 63 to 76).

**Run notes:** the first attempt (`hf-pilot-all`) died in the teacher arm with an out-of-memory error (teacher episodes are longer than template ones). `pilot.py` now packs training micro-batches up to 2,048 tokens instead of a fixed 8 examples; the gradient is unchanged. Teacher v2 kept 1,143 of 1,720 episodes (66%). Models are in the private repo `kealjones/findout-pilot`.
