# Weird maths in a transformer

Keal: "let's throw random math equations in front of and behind attention and MLP and just see what happens."

A nanoGPT-style model (6 layers, width 384, about 30M parameters including the GPT-2 embedding) trained on **FineWeb-Edu**, the standard corpus for small-model experiments, with the GPT-2 tokenizer. Each variant sticks one odd function at one spot. Everything else is identical: the same batches in the same order, the same seed, steps and optimiser. The baseline runs with three seeds, so the noise level is measured, not guessed.

| spot | variants |
|---|---|
| after attention | sin, sign-sqrt, learned per-channel cubic |
| after the MLP | signed log, learned per-channel power, rounding (straight-through), causal running mean |
| before the MLP | abs, max with the neighbouring channel, plus sin of a fixed random projection |
| before attention | gaussian squash, x·exp(−x²/8) |
| between blocks | tanh cap, a fixed random rotation, swapping the two halves of the channels, noise |
| the residual | an attention × MLP product term |

**Standard tests for every variant:** FineWeb-Edu validation loss, WikiText-2 perplexity, BLiMP (67 grammar tests × 100 pairs), HellaSwag (1,000; near chance at this size), throughput, and whether training blew up.

`weird_quick.ipynb` is a smoke test; `weird.ipynb` is the full run (about 3 hours on a T4). Both are built from `weird.py` by `make_notebook.py`.
