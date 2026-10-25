# Resume: findout pilot (as of Sun Oct 25 2026, 10:05 Arizona time)

Paste this into a new chat, with the repo https://github.com/KealJones/tp-parse attached.

## Goal
A small (≤ 500 MB) "figure-it-out" model. It notices gaps and uses tools (search, calculator, ask the person, memory) instead of guessing. It checks that what it finds is about the right thing, and it handles Keal's messy writing.

- Full plan doc: https://claude.ai/artifact/G6ciovi1M9LaqeftgCUnhh ("Figure-it-out model plan").
- Base model: LFM2.5-350M (379 MB at Q8_0).
- Key research finding: small models should always search for facts, not decide when to.
- Budget: Keal has ~$46 on Hugging Face. Use it, but keep it lean.

## What the pilot is testing
Run 1 (SmolLM2-135M, `experiments/findout/`) learned the tool loop. But it scored 0% on plans it hadn't seen, like comparing the cost of two items. The pilot asks whether LFM2.5-350M composes plans when trained on ~2,000 episodes. If yes, the $20–40 full plan goes ahead.

## Code (all in `experiments/findout2/`)
- **`world2.py`** (invented worlds and tools):
  - Ten trained task types.
  - Five held-out combinations of trained parts: cost-compare, argmax4, bridge-compare, ask-diff, basket3.
  - Keal-style noise: false starts, self-corrections, repeats.
  - Gold episodes, scoring (`ok` and `strict`), and the LFM render/parse.
  - `python world2.py` self-tests 4,500 gold episodes.
- **`teacher.py`**: Qwen3-4B-Instruct-2507 solves tasks with the real tools and no answer key.
  - Only fully right episodes are kept (`kept`).
  - If the teacher stops after writing its plan, the reply is cut at "Answer:" and continued from "Starting with 1."
  - Arguments: `--shard=i/n --batch --hours --out`.
- **`pilot.py`** runs three arms:
  - `untouched`: two worked examples in the prompt.
  - `gold`: full fine-tune on template episodes.
  - `teacher`: full fine-tune on teacher episodes.
  - Every trained arm gets 20% replay of the base model's own answers, lr 2e-5, 2 epochs.
  - Tests: held-out types, messy vs clean requests, English perplexity (three ways), and plain chat.
  - Writes `out/PILOT_RESULTS.md` with the go/no-go verdict. `--export` uploads a Q8_0 GGUF to the private HF repo `kealjones/findout-pilot`.

## How jobs run (GitHub Actions bridge)
- **Hugging Face:** put a JSON job in `hf/queue/` and push to main. The `hf-run` workflow launches it. Results land in the job's `out` folder via `hf-collect`.
- **Triggering collect:** the cron is slow, so trigger it with `gh api -X POST repos/KealJones/tp-parse/actions/workflows/hf-collect.yml/dispatches -f ref=main`. Use the REST API; GraphQL `gh workflow run` is blocked.
- **Kaggle:** `kaggle/queue/` works the same way. It's free, has 2 sessions, and is slower.
- **Commit trailers:** commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01Ng32kqY3wCWfURqkF13BZc`.

## Where it stands
- **Smoke test:** passed end to end, GGUF export included.
- **First real run, `hf-pilot-gold`** (old scoring, before the leak fix):
  - Trained types: 97%. Held-out right answer: 53%.
  - Mostly luck or template-snapping. Cost-compare compared unit prices and ignored the quantities. Bridge-compare compared someone's age with a population. Ask-diff never asked.
  - Cause: gold needs-lists leaked the hidden town name. **Fixed** (`hidden` field), and strict scoring was added.
- **English perplexity still unexplained:** base came out 2,134, which can't be right. It's now measured three ways (raw, raw masked, as an assistant reply), and the verdict uses "as an assistant reply".
- **Teacher v1:** almost nothing kept, because the model stopped after its plan. Fixed in v2.
- **Running now** (started 9:55 Arizona time, ~30 min internal cap each): `hf/queue` jobs `findout2-teacher-v2-0` and `-1` on A100s. Outputs go to `experiments/findout2/hf-teacher-v2-{0,1}/teacher_episodes_{0,1}.jsonl` plus `TEACHER_RESULTS_{0,1}.md`.

## Next steps
1. **Teacher check.** When both teacher halves finish, read `TEACHER_RESULTS_*.md`. The keep rate should be well above 30%. If it's low, look at the failure reasons and fix `teacher.py`.
2. **Final run.** Launch it with all three arms, using the scoring fixes:

   ```json
   {"slug": "findout2-pilot-all", "flavor": "l4x1", "timeout": "90m",
    "files": ["experiments/findout2/world2.py", "experiments/findout2/pilot.py",
              "experiments/findout2/hf-teacher-v2-0/teacher_episodes_0.jsonl", "experiments/findout2/hf-teacher-v2-1/teacher_episodes_1.jsonl"],
    "cmd": "python pilot.py --arms untouched,gold,teacher --teacher teacher_episodes_0.jsonl,teacher_episodes_1.jsonl --export",
    "pip": ["transformers>=4.57", "datasets"], "outdir": "out", "out": "experiments/findout2/hf-pilot-all"}
   ```

   Save it as `hf/queue/findout2-pilot-all.json` and push. It takes ~25 min on L4 and costs ~$0.40.
3. **Report.** Read `experiments/findout2/hf-pilot-all/PILOT_RESULTS.md`. The go/no-go:
   - held-out **strict** mean ≥ 50% and no held-out type below 20%;
   - perplexity as an assistant reply rises by at most 15%;
   - at most 1 broken plain-chat reply;
   - messy requests score within 10 points of clean.
4. **Write it up.** Add the results to `experiments/findout2/README.md` and tell Keal in plain words: whether to spend $20–40 on the full plan, and what the failures show.
5. **Pending sanity check:** if the raw-masked perplexity is sane (~20–60) while raw is ~2,000, the first method was buggy (no attention mask or cache).

## Keal's preferences
- Give times in his local time (Arizona, UTC-7). Never UTC alone.
- Plain words, short updates, honest about failures.
- Keep the maths in the calculator, not the weights. He doesn't care about toki pona.
