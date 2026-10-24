# Harness v3 (smarter search, thinking on): hand grades

Graded strictly against each task's rule in tasks.json.

| model | v3 | v2 (native tools) | no tools |
|---|---|---|---|
| Qwen3-0.6B, thinking | 0/18 | 0/18 | 2/18 |
| Qwen3-1.7B, thinking | 5/18 | 7/18 | 7/18 |

1.7B passes: #8 kraggle→Kaggle API, #10 CORS, #11 proxy not WASM, #14 why models improve, #15 GPU providers.
Near misses: #2 Chinchilla (right idea, no 20 tokens/param), #3 training time (said "multiple GPUs in parallel", not thousands; added a false claim).
0.6B auto-passes on #6 and #17 were wrong on reading (REN called a "Reinforcement Learning Engine"; #17 talks about a "Kept" indicator).

## What the search fix showed
- Passages did reach the model (2 pages per search), but three bugs hurt:
  1. URLs with parentheses got cut (`Chinchilla_(language_model` → fetch failed).
  2. Snippet lines come first and the 3500-char cap often cut off the passages.
  3. Word-overlap scoring picks junk: "Opus 5.5" → Opus the Penguin; "small model trained on trillions" → T-gauge model trains; "200-500 MB" → a 3D-file-size estimator.
- When the model got real text it copied it in, wrong or not (#5 repeated pricing from a page instead of saying the details aren't public; #7 and #4 answered about 3D printing and model trains).
- Its own queries are often off-target, and it doesn't notice irrelevant results.
