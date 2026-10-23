# Registers v2

Follow-up to `experiments/registers`, same skins world, 3.6M-parameter GPT. Run 1 found that 3 taught state slots cut bookkeeping errors from 226 to 38, but seeds were noisy and periods were the only thing that triggered slot updates.

| model | slots | update when | taught by |
|---|---|---|---|
| `base` | none | | |
| `taught-ends` | 8 (4 taught) | sentence ends | the simulator: where the agent is, what it holds, the door where it stands, which item is the goal; teaching fades out between 50% and 80% of training |
| `taught-every` | 8 (4 taught) | any word | the same |
| `self-every` | 8 | any word | nothing from the simulator: from the slots alone, predict which words (by role) appear in the next sentence |

Slot update: s ← g·s + (1 − g)·c, with the keep-gate g and new content c computed from the model's state at that word (a minGRU-style gated recurrence). In `ends` mode g is forced to "keep" except on "." and "?".

New since run 1: the goal slot (aimed at "wrong choice" failures), every-word updates, the teacher-free condition, a **messy** test (every period removed from the facts, never seen in training), 5 seeds, 8,000 steps, both of Kaggle's T4s, and a pilot gate that stops the run if the registers model is clearly broken.

Run through the Kaggle bridge (`kaggle/queue/registers-v2.json`), or open `registers_v2.ipynb` on Kaggle with GPU T4 x2 and Run All. `registers_v2.ipynb` is built from `rv2.py` by `make_notebook.py`.
