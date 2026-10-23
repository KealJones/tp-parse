# Trace: Keal solves "boustrophedon"

The first real recording of a person running the finding-out loop: about 17 minutes of screen and narration (2026-10-23), with `transcript.md` (Keal's own transcription) and `solution.ts` (the final code). The task was to print 1..n² in an n×n grid, boustrophedon. The word was unknown to him, and he hadn't written code in a long time.

## The loop, step by step (timestamps from the transcript)

| time | step | what happened | principle (Finding Out) |
|---|---|---|---|
| 0:22 | notice a gap | "No idea what boustrophedon is", so he defined it first | 3 know what you don't know |
| 0:46 | scope down and say so | mirrored letters: "I'll get close enough, then mention I can't do it" | 11 say what's missing |
| 1:10 | pick the cheapest tool | console vs a file vs JS Bin, lazy on purpose | 4 cheapest first |
| 2:50 | read the example as a clue | "the 3x3 grid makes me think it's a square" | 8 meet people as they talk |
| 3:42 | look up only exact things | for-loop syntax, `**`, joining arrays: "if it didn't know how to do this, then you should do that" | 2 do exact things exactly |
| 6:30 | knowingly settle | "I know I'm not doing the best solution" | — (satisficing) |
| 7:00 | replan | "let me think about this again": an outer loop over rows | 5 learn in pieces |
| 15:00–16:22 | run, read, fix | wrong line count, then off-by-one, then wrong rows reversed; each fixed by guessing the cause from the output | 7 check before claiming |
| 16:38 | verify | the 3×3 matches the definition; then n = 10, checking specific numbers (50, 51, 60, 61) | 7 check before claiming |

## What it suggests for training data

- **The judgment was quick; the cost was recall.** The word and the plan took about 3 minutes. Most of the rest went to syntax he once knew, all of which was lookup-able.
- **Real traces are messy, and the mess is the lesson:** false starts, "wait, no", replans and wrong guesses about bugs. Clean worked examples teach none of that.
- **He checks with escalating tests:** the given example first, then a bigger case with spot-checked values.
- **He states limits before he starts** (mirroring) instead of silently dropping them.
