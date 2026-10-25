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

## Results, run 1 (Kaggle T4, 2026-10-24, 251 min; full table in `kaggle-full/WEIRD_RESULTS.md`)

Baseline FineWeb-Edu val loss: **4.958 ± 0.008** over 3 seeds (range 4.950–4.965), so anything within about ±0.016 is noise.

| | variant | val loss vs baseline | WikiText-2 ppl (baseline 507–545) |
|---|---|---|---|
| possibly better | signed log after the MLP, sign(x)·log(1+\|x\|) | **−0.027** | **474** |
| possibly better | learned per-channel cubic after attention | **−0.027** | 508 |
| noise | swap halves, noise, tanh cap, learned power, attention × MLP, running mean, fourier, random rotation, gaussian squash | −0.013 to +0.015 | 533–587 |
| worse | rounding after the MLP | +0.028 | 616 |
| worse | sin after attention | +0.033 | 615 |
| worse | sign-sqrt after attention | +0.056 | 680 |
| clearly worse | max with the neighbouring channel before the MLP | +0.116 | 704 |
| clearly worse | abs before the MLP | +0.267 | 861 |

- **Two variants beat the baseline by about three times its seed spread.** Both are one run each, so they're candidates, not findings. The signed log is a soft squash on how big each MLP update can be, a cousin of known stabilising tricks. It also had the best WikiText-2 perplexity of the whole run. The learned cubic gives each channel a little extra curvature to play with.
- **Throwing information away hurts, roughly in proportion.** abs (loses the sign), channel max, sign-sqrt and rounding all lose information about the MLP's input or the attention output, and they're the worst.
- **Nothing blew up.** Even the oddest ones (random rotations, swapped channels, noise) trained fine: training is far more robust to weird maths than you'd guess.
- **BLiMP (60–63%) and HellaSwag (27–28%, chance 25%) don't separate anything at this size.** They sit within noise for every variant. Loss and WikiText-2 perplexity are the tests that discriminate.

Next: rerun the two candidates with three seeds each and longer training, before believing either one.
