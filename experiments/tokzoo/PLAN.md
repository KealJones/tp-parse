# Tokenizer zoo: plan (not built yet)

The same model and tests as `experiments/weird` (a 6-layer GPT on FineWeb-Edu), changing only how text is cut into tokens. Lossless tokenizers are compared on bits per byte of the original text. Lossy ones predict different text, so they're compared on tests transformed the same way (BLiMP, plus next-word tests where BLiMP breaks).

| # | tokenizer | idea from | lossy? |
|---|---|---|---|
| 1 | bytes | baseline | no |
| 2 | characters | baseline | no |
| 3 | GPT-2-style BPE, small vocab | baseline | no |
| 4 | GPT-2-style BPE, large vocab | baseline | no |
| 5 | BPE with digits split one by one | baseline | no |
| 6 | seam tokens: last letter + space + first letter of the next word | Keal | no |
| 7 | first letter, last letter and length, middle letters unordered ("reading" = "raednig") | Keal | yes (anagrams merge) |
| 8 | first and last letter only ("reading" → "rg") | Keal | yes |
| 9 | every third letter, spaces kept ("reading" → "rdg") | Keal | yes |
| 10 | every second letter shifted one place in the alphabet | Keal | no |
| 11 | sense-tagged: words tagged with their WordNet supersense ("bank" by a river vs "bank" with money) | Keal (Napkin's senses) | no |
| 12 | real roots: morpheme splits (MorphyNet) | Keal | no |
| 13 | 3-word chunks: the most common 3-word phrases as single tokens (compare SuperBPE, 2025) | Keal | no |
| 14 | by sound: phonetic spelling ("knight" = "night") | Claude | yes |
| 15 | vowels dropped ("cat" → "ct") | Claude | yes |
| 16 | every word written backwards | Claude | no |
| 17 | keyboard position: letters near each other on the keyboard share tokens | Claude | yes |
| 18 | only verbs | Keal | yes |
| 19 | only nouns | Keal | yes |
| 20 | telegraphic: function words dropped ("the", "of", "and") | Keal | yes |

Also queued, for a weird-maths sequel: geometry in the residual stream (hyperbolic, sphere as an nGPT sanity check, torus, learned reflections).

Probably two runs (or Hugging Face hardware). Sense tags, roots, verbs and nouns need a tagging pass over the training text first.
