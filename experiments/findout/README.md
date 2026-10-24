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

## Results, run 1 (Kaggle T4, 2026-10-24, 108 min; full tables in `kaggle-full/FINDOUT_RESULTS.md`)

| | base (7 examples in the prompt) | LoRA | full fine-tune |
|---|---|---|---|
| the 7 trained task types | 0–78% | 98–100% | 100% |
| looked up when needed / when the answer was given | 95% / 91% | 100% / 0% | 100% / 0% |
| calculator for arithmetic / asked when info was missing | 3% / 0% | 100% / 100% | 95% / 100% |
| unfamiliar: a new kind of fact (people) | 63% | 98% | 100% |
| unfamiliar: three-way compare (chance 33%) | 25% | 63% | 60% |
| unfamiliar: cost-compare (two lookups, two sums, compare) | 22% | **0%** | **0%** |
| English perplexity (base 12.4) | 12.4 | **19.0** | 13.9 |

- **The loop is learnable at 135M parameters.** In the trained task types the model looks things up exactly when it needs to, never when the answer is already in the message, always uses the calculator, asks when only the person knows, and handles the stale-assumption case. The untrained model with examples does almost none of this.
- **It generalises to new facts, not to new plans.** A never-seen fact type (people's ages) worked at 98–100%. But on the held-out *combinations* it snapped to the nearest trained template. On cost-compare it priced one item, multiplied, and answered "10 Xs cost 830 coins", never touching the second item. On three-way compare it looked up two towns, "I need both populations", and ignored the third. The skills are there; composing them into a new plan isn't. This is the paper's open question, "can it handle a truly new kind of problem?", answered no for now.
- **LoRA did not protect English better.** Here it hurt it more (perplexity 19.0, against 13.9 for the full fine-tune). Its learning rate (2e-4, rank 32 on every layer) was much more aggressive than the full fine-tune's (5e-5), so "freeze the core, add an adapter" only protects anything if the adapter is trained gently.
- **The stale test didn't exercise the harness:** 100% with the note and 100% without it. The person's reply names the new town right next to the search, so the model re-searches without needing to be told. A real test needs the change to arrive far from what it invalidates.

Next: train on procedurally composed plans (any number of lookups, sums and comparisons, in varied orders) instead of seven fixed templates, hold out specific combinations, and test whether the model counts what a request needs before acting.
