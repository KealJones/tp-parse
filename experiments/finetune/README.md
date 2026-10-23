# Fine-tune test

Registers v2 showed that state slots updated at every word, trained without any simulator, made a 3.6M-parameter planner far more reliable, especially on messy input. Training from scratch is expensive, so this tests the same ideas on top of small pretrained models.

Two models, one notebook each, run in parallel through the Kaggle bridge: **Qwen3-0.6B** and **SmolLM2-360M-Instruct**. Four versions of each:

| version | what changes |
|---|---|
| `untouched` | the model as downloaded, given two worked examples in the prompt |
| `ft` | full fine-tune on the planning task (embedding table frozen), no examples in the prompt |
| `ft-slots` | the same, plus 8 state slots before the middle layer, updated at every token, trained only to predict the next sentence (no simulator) |
| `lora-slots` | the slots, with the model frozen and only rank-16 LoRA patches trained |

The planning task is the skins world with the harness in the loop: the model writes a plan, the checker runs each sentence, and `search` questions get answered. A quarter of training prompts have their periods removed.

Scored on:
- **Planning:** clean, messy (no periods) and filler (no periods plus "um", "like", "you know"…, never seen in training), short and long problems.
- **Honest gaps:** does it search when a fact is missing, rather than guess?
- **English kept:** ARC-Easy accuracy and WikiText-2 perplexity, before and after fine-tuning.
- **Keal's real messages** (`messages.json`, 24 typed and 21 spoken): pick what he meant out of four options by likelihood; chance is 25%.
- **4-bit:** every decoder weight rounded to 4 bits (LoRA merged first), then planning, messages and English again.

One seed per version; `messages.json` is built by `make_messages.py`; the notebooks are built from `ft.py` by `make_notebook.py`.
