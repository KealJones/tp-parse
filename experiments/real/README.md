# Simple language first, with real data

The goals experiment (run 2) showed that teaching a skill in a small, clean language first lets a small model learn it in English from far fewer examples. This experiment tries the same recipe on real text, with about 17M-parameter Llama-style models.

| | stage 1 | stage 2 (bridge) | stage 3 |
|---|---|---|---|
| `simple-first` | real toki pona: Tatoeba, Wikipedia-mined sentences, lipu kule | Tatoeba toki pona ⇄ English pairs, plus the budget's stories with about half their hub words swapped to toki pona | the English budget + 10% toki pona |
| `english` | the English budget, repeated for the same number of steps | | |
| `ceiling` | about 100M tokens of fresh SimpleStories | | |

- **English budget:** 10,000 SimpleStories plus the English side of the Tatoeba pairs. `simple-first` and `english` see exactly this English and nothing more. Each keeps its best checkpoint by English validation loss.
- **Swap table** (`hubs.json`): the Basic English → toki pona hub map from `experiments/basic-english`, widened with words whose Linku gloss points to a single toki pona word, plus simple inflections. Together that covers about 45% of the words in a typical story.
- **Tests:** English validation loss; BLiMP (67 grammar phenomena × 1,000 minimal pairs); bAbI (20 reasoning tasks, with the same 1,500-step fine-tune for every model, scored by the most likely answer).
- **Export:** `real_export.zip` holds all three models as F16 GGUF with Ollama Modelfiles, the SentencePiece tokenizer and HF weights. They continue stories rather than chat.

## Run it on Kaggle

https://www.kaggle.com/kernels/welcome?src=https://github.com/KealJones/tp-parse/blob/main/experiments/real/real.ipynb

Settings → Accelerator **GPU T4**, and **Internet on** (it downloads the datasets; this needs a phone-verified Kaggle account). Then **Save Version → Save & Run All**, so it runs in the background, about 2 hours. Download `REAL_RESULTS.md` and `real_export.zip` from the version's output.

`real.ipynb` is generated from `real.py` by `make_notebook.py`, which also inlines `hubs.json`.
