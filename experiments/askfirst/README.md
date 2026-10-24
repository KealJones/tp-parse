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
