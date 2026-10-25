# Weird maths in a transformer: results

GPT, 2 layers, width 128, 7M parameters (incl. embeddings), GPT-2 tokenizer, 0M FineWeb-Edu tokens each, same batches and seed.
Baseline FineWeb val loss 10.548 ± 0.007 (std over 3 seeds); a difference smaller than about 0.014 is probably noise.

| variant | FineWeb val loss | vs baseline | WikiText-2 ppl | BLiMP | HellaSwag | tokens/s | blew up |
|---|---|---|---|---|---|---|---|
| abs before MLP | 10.514 | -0.034 | 42058 | 60.0% | 30.0% | 59k |  |
| channel max before MLP | 10.520 | -0.028 | 42218 | 66.7% | 20.0% | 57k |  |
| running mean after MLP | 10.520 | -0.028 | 42452 | 40.0% | 30.0% | 54k |  |
| baseline seed 3 | 10.544 | -0.004 | 42186 | 33.3% | 20.0% | 59k |  |
| learned power after MLP | 10.544 | -0.004 | 42998 | 40.0% | 35.0% | 47k |  |
| learned cubic after attention | 10.544 | -0.004 | 42998 | 40.0% | 35.0% | 58k |  |
| tanh cap between blocks (known-ish) | 10.544 | -0.004 | 42998 | 40.0% | 35.0% | 59k |  |
| baseline | 10.544 | -0.004 | 42998 | 40.0% | 35.0% | 20k |  |
| attention x MLP product | 10.544 | -0.004 | 42999 | 40.0% | 35.0% | 59k |  |
| sin after attention | 10.544 | -0.004 | 42999 | 40.0% | 35.0% | 58k |  |
| fourier before MLP | 10.545 | -0.004 | 42984 | 43.3% | 35.0% | 59k |  |
| log after MLP | 10.545 | -0.003 | 42997 | 43.3% | 35.0% | 58k |  |
| baseline seed 2 | 10.557 | +0.008 | 42064 | 70.0% | 35.0% | 58k |  |
| noise between blocks | 10.560 | +0.012 | 43356 | 40.0% | 35.0% | 58k |  |
| gaussian squash before attention | 10.563 | +0.014 | 43594 | 46.7% | 35.0% | 59k |  |
| swap halves between blocks | 10.564 | +0.015 | 43180 | 30.0% | 25.0% | 59k |  |
| random rotation between blocks | 10.567 | +0.019 | 44273 | 30.0% | 30.0% | 59k |  |
| rounding after MLP | 10.583 | +0.035 | 44069 | 36.7% | 30.0% | 59k |  |
| sign-sqrt after attention | 10.595 | +0.047 | 44545 | 46.7% | 40.0% | 52k |  |

HellaSwag chance is 25%; BLiMP chance is 50%. Lower loss and perplexity are better.

Total time 1 min.
