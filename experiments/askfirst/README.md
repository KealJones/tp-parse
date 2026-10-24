# Ask first: find out what someone needs before answering

The cold test of untouched Qwen3-0.6B on Keal's three recorded tasks (2026-10-24) showed what this targets:
- **Mom's birthday:** it listed generic gifts and asked nothing. Given "she used to love gardening… slowed down", it listed more gifts. It never asked why.
- **Coeliac dinner:** it planned a "rice" dish with no rice in it, offered turkey as a vegetarian option, and gave safety advice unrelated to coeliac (slow-cook to avoid bloating, drink water).
- **Boustrophedon:** it spent its whole budget thinking and never wrote any code.

None of these needs facts the model lacks. They're habits: ask when something's missing, pull on the odd detail, check the answer against what you know.

## What's here

- `scenarios.py`: vague requests with a hidden brief. A simulated person answers only what a question asks about, vaguely, and keeps the real reason back until the model pulls on the clue it gave. Families: gift, dinner and code (trained); given (everything is in the message, so don't ask); trip (never trained on); and Keal's three tasks as fixed scenarios. The checker scores the real need and catches contradictions: meat in a vegetarian meal, the wrong person's state, over budget, an oven when there isn't one. `python scenarios.py` replays 2,000 gold trajectories through the harness; all pass.
- `askfirst.py`: Qwen3-0.6B with a switchable rank-16 LoRA patch, trained on 6,000 gold trajectories. Untouched (two worked examples) and patched are scored in the same harness. Keal's three tasks are also run as plain chat, and transcripts are saved.

Runs on the Hugging Face bridge (`hf/queue/askfirst.json`).

## Result, run 1 (2026-10-24, `hf-out/`): it learned the script, not the habit

- **Trained kinds (gift, dinner, code): 100%, against 0% untouched.** But the answers are the gold templates almost word for word. It's reciting, not working things out.
- **Trip planning, never trained on: 0%.** It still asks first every time, but it asks one irrelevant question ("What is your age?"), gets "idk what you mean", and gives up.
- **"Given":** it correctly doesn't ask (0% asked) and gets 100%, again within the trained templates.
- **Keal's mom task:** it passes, with the template's exact questions and answer. Coeliac passes the same way. Boustrophedon got worse: it now explains instead of writing code.
- **Plain chat with the patch on is broken** (it repeats tag fragments), and English perplexity is 36 → 195 with the patch on. With the patch off it's exactly the untouched model.

Why: 6,000 episodes from a handful of templates with near-identical wording, so the cheapest thing to learn is the script. The keyword-matching person also rewards saying the right words rather than asking the right thing. What transferred is only "ask first" and "don't ask when it's all there". What to ask didn't transfer.
