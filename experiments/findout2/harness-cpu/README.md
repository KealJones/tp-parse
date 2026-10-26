# Plain vs smart harness, no training, CPU (Mon 26 Oct 2026, $0)

Same models, same held-out test (world2 v3, `fair_score`), two harnesses (`harness_eval.py`). The smart harness uses no
answer key: search results filtered to the asked-about entities, a one-time nudge when a new name appears, and an answer
gate (looked nothing up / number no tool gave / fewer lookups than its own plan / no Answer line; at most twice).

| model | episodes | plain: right / strict | smart: right / strict | never answered (hit 10-turn cap) plain → smart |
| --- | --- | --- | --- | --- |
| LFM2.5-350M (raw) | 120 | 18% / 1% | 12% / 1% | — |
| Qwen3.5-0.8B (raw) | 40 (8 per type) | 15% / 5% | 18% / 8% | 26 → 22 |

Read: no meaningful effect. The raw 350M rarely searches properly (it searches the whole sentence or not at all), so its
"right" answers are mostly coin flips on two-option questions and the harness has nothing to steer. Qwen3.5-0.8B's main
failure is looping (repeating the same call until the cap, e.g. asking the person "Which costs more?" five times), which
these three changes don't target. The scorer still fails correct answers that name both items ("11 fogwhistles are more
expensive than 12 quillcases") under both harnesses.
