# Weird maths in a transformer: results

GPT, 6 layers, width 384, 30M parameters (incl. embeddings), GPT-2 tokenizer, 33M FineWeb-Edu tokens each, same batches and seed.
Baseline FineWeb val loss 4.958 ± 0.008 (std over 3 seeds); a difference smaller than about 0.016 is probably noise.

| variant | FineWeb val loss | vs baseline | WikiText-2 ppl | BLiMP | HellaSwag | tokens/s | blew up |
|---|---|---|---|---|---|---|---|
| log after MLP | 4.931 | -0.027 | 474 | 63.2% | 27.3% | 43k |  |
| learned cubic after attention | 4.931 | -0.027 | 508 | 62.1% | 27.7% | 40k |  |
| swap halves between blocks | 4.945 | -0.013 | 542 | 61.3% | 27.1% | 44k |  |
| baseline | 4.950 | -0.008 | 507 | 61.8% | 27.8% | 45k |  |
| noise between blocks | 4.955 | -0.003 | 561 | 61.4% | 27.6% | 44k |  |
| tanh cap between blocks (known-ish) | 4.955 | -0.003 | 533 | 62.0% | 28.5% | 44k |  |
| baseline seed 3 | 4.958 | +0.000 | 545 | 63.3% | 27.9% | 45k |  |
| learned power after MLP | 4.960 | +0.002 | 575 | 62.0% | 26.7% | 41k |  |
| attention x MLP product | 4.963 | +0.005 | 539 | 61.3% | 28.3% | 44k |  |
| running mean after MLP | 4.964 | +0.006 | 533 | 62.6% | 28.5% | 42k |  |
| fourier before MLP | 4.965 | +0.007 | 550 | 62.2% | 26.8% | 43k |  |
| baseline seed 2 | 4.965 | +0.007 | 538 | 60.4% | 27.6% | 45k |  |
| random rotation between blocks | 4.972 | +0.014 | 536 | 62.5% | 27.3% | 44k |  |
| gaussian squash before attention | 4.973 | +0.015 | 587 | 60.4% | 27.2% | 42k |  |
| rounding after MLP | 4.986 | +0.028 | 616 | 61.4% | 27.3% | 44k |  |
| sin after attention | 4.991 | +0.033 | 615 | 62.4% | 27.5% | 45k |  |
| sign-sqrt after attention | 5.014 | +0.056 | 680 | 60.9% | 27.4% | 43k |  |
| channel max before MLP | 5.074 | +0.116 | 704 | 61.4% | 27.5% | 42k |  |
| abs before MLP | 5.225 | +0.267 | 861 | 60.4% | 27.3% | 44k |  |

HellaSwag chance is 25%; BLiMP chance is 50%. Lower loss and perplexity are better.

Total time 251 min.
