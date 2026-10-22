# Registers: a state table inside a small model

A planner has to know where the agent is, what it's holding and which doors are open. A plain transformer has no table for that, so it rebuilds the state at every word by looking back over the whole plan. This run gives the model **state registers**: 8 small slots carried alongside the text.

- **Write:** at the end of every sentence, a small GRU updates the slots from the model's state halfway up. The state is passed forward from sentence to sentence, not re-derived.
- **Read:** every later word attends over the slots and adds what it read back into its state.

The registers add about 1% to the model's size. Only the lower half of the model feeds them, so training stays parallel apart from the tiny GRU step.

It uses the same skins world as `experiments/skins`: plans in home, computer, ship and kitchen, while farm and space only appear as loose sentences.

## Conditions

- `base`: a plain small GPT (about 3.6M parameters, the same as `base` in the skins run).
- `registers`: 8 slots, no teaching. Does the shape alone help?
- `taught`: the same 8 slots, with 3 of them lightly taught from the simulator's true state after each sentence: where the agent is, what it holds, and the door where it stands. The other 5 stay free. Teaching fades out between 50% and 80% of training, so the model keeps the habit but can change how it uses the slots. The labels are skin-free (place 3, holding the key), so one table fits every skin.

## Tests

- Plans in seen and unseen skins, `short` (1–3 obstacles) and `long` (4–5, longer than any training plan), run in the world.
- **Bookkeeping failures:** going where the agent already is, taking something that isn't there, opening the wrong door, false claims. These are what a state table should prevent.
- **Slot readout** after training: do the taught slots still hold the true state, in seen and unseen skins, after the teaching stopped?

## Run it on Kaggle

1. Open https://www.kaggle.com/kernels/welcome?src=https://github.com/KealJones/tp-parse/blob/main/experiments/registers/registers.ipynb
2. Settings → Accelerator → **GPU T4**. Internet can stay off.
3. Run All. About 1.5–2 hours. It writes `REGISTERS_RESULTS.md` and `registers_results.json`.

`registers.ipynb` is generated from `registers.py` by `make_notebook.py`. The world, skins and checker are copied from `skins.py`.
