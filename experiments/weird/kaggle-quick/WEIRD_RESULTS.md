# Weird maths in a transformer: results

GPT, 2 layers, width 128, 7M parameters (incl. embeddings), GPT-2 tokenizer, 0M FineWeb-Edu tokens each, same batches and seed.
Baseline FineWeb val loss 10.548 ± 0.007 (std over 3 seeds); a difference smaller than about 0.014 is probably noise.

| variant | FineWeb val loss | vs baseline | WikiText-2 ppl | BLiMP | HellaSwag | tokens/s | blew up |
|---|---|---|---|---|---|---|---|
| baseline seed 3 | 10.544 | -0.004 | 42186 | 33.3% | 20.0% | 59k |  |
| baseline | 10.544 | -0.004 | 42998 | 40.0% | 35.0% | 18k |  |
| baseline seed 2 | 10.557 | +0.008 | 42064 | 70.0% | 35.0% | 59k |  |

HellaSwag chance is 25%; BLiMP chance is 50%. Lower loss and perplexity are better.

Total time 1 min.
