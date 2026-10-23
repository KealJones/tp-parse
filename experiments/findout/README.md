# Finding out: teach a small borrowed model the loop, not the facts

The "Finding Out" paper's thesis, tested directly. We take a small pretrained model, **SmolLM2-135M-Instruct**, which already reads English, and teach it only the loop: notice a gap, look it up, note what it found, calculate exactly, ask the person, catch a stale assumption, check, answer.

**Nothing can be memorised.** Every episode happens in a freshly invented world, with made-up towns, creatures, items and people (`world.py`). The only way to be right is to find out.

## Tools and working picture

`<search>`, `<calc>` and `<ask>` go to the harness. `<fact key>` and `<assume key>` keep the working picture. When a fact replaces an assumption, the harness lists the earlier searches that rested on the old value. This is the dependency tracking that would have caught the stale Phoenix result in the birthday trace.

## Tasks

| trained on | held out (never seen in training) |
|---|---|
| lookup: "what does a ummi eat?" | cost-compare: lookup + calculator + compare, combined |
| given: the answer is already in the message (don't search) | three-way: compare three towns, not two |
| calc and lookup+calc: exact arithmetic with the calculator | new kind: questions about people, a fact type never trained on |
| compare: two lookups, then a comparison | |
| ask: missing information only the person has | |
| stale: an assumption overturned halfway through | |
| whose: two people, two towns, answer about the right one | |

Requests come tidy or messy ("uhh is dravor bigger than ralvorum lol"). Two filler prefixes ("quick q", "random but") appear only in testing; the templates themselves are shared.

## Conditions and measures

- `base`: untrained, with one worked example per trained task type in the prompt (answers without tags still count). `lora`: LoRA adapters, core frozen. `full`: the whole model fine-tuned.
- Measures: success per task; looked up when needed; looked up when the answer was given (lower is better); calculator use; asking; stale with the harness note on and off; and English kept, measured as perplexity on held-out SimpleStories.

## Run

The Kaggle bridge runs it from the repo (`kaggle/queue/`). `findout_quick.ipynb` is a few-minute smoke test; `findout.ipynb` is the full run (GPU T4, internet on, about 1 to 1.5 hours). Both are generated from `findout.py` + `world.py` by `make_notebook.py`.

To try the trained model, put the exported `findout.gguf` next to the Modelfile, run `ollama create findout -f Modelfile`, then `python3 chat.py`. The script invents a world and acts as the harness.
