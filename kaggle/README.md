# Kaggle bridge

Lets Claude start Kaggle GPU runs and read their results through this repo, without ever seeing the Kaggle key.

1. A job file goes in `kaggle/queue/`, for example `{"slug": "registers-v2", "notebook": "experiments/registers/registers.ipynb", "out": "experiments/registers/kaggle-out", "gpu": true, "internet": false}`.
2. Pushing it runs `kaggle-run`, which uploads the notebook to Kaggle as a private notebook and starts it, then moves the job to `kaggle/pending/`.
3. `kaggle-collect` runs every 15 minutes (or on a push to `kaggle/collect.txt`). When Kaggle says a job finished, it downloads the outputs into the job's `out` folder (files over 20 MB stay on Kaggle and are listed), writes `KAGGLE_STATUS.md` and the tail of the run log to `KAGGLE_LOG.txt`, and moves the job to `kaggle/done/`.

Needs the repo secrets `KAGGLE_USERNAME` and `KAGGLE_KEY`. Revoke the key on Kaggle to cut access at any time. Runs count against the account's weekly GPU quota.
