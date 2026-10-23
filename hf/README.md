# Hugging Face Jobs bridge

Runs experiments on Hugging Face's paid GPUs from this repo, in parallel, billed by the minute.

1. A job file goes in `hf/queue/` (see `hf/ready/` for examples). Pushing it runs `hf-run`, which launches the job with a hard time limit (capped at 180 min) and moves it to `hf/pending/`.
2. Inside the job, `hf/runner.py` fetches the listed files from GitHub at the pushed commit, runs the command, and always uploads the outputs, the log and the exit code to the private dataset repo `<you>/tp-parse-runs`, even if the run crashed.
3. `hf-collect` (every 15 minutes, or on a push to `hf/collect.txt`) copies finished results into the job's `out` folder with `HF_STATUS.md` (status, minutes, rough cost) and moves the job to `hf/done/`.

Setup: a Hugging Face token with write access and permission to run Jobs, saved as the secret `HF_TOKEN` in a GitHub environment named `HUGGINGFACE`, and a positive credit balance on the Hugging Face account.

Prices per hour (from the Jobs docs): t4-small $0.40, l4x1 $0.80, a10g-small $1.00, a10g-large $1.50, a100-large $2.50.
