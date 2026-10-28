"""Moves big files between jobs through a private HF dataset repo (they stay out of git).
  python hub.py up   <repo> <path_in_repo_prefix> <file>...
  python hub.py down <repo> <path_in_repo>... --to <dir>
"""
import os, sys
from huggingface_hub import HfApi, hf_hub_download

api = HfApi(token=os.environ.get("HF_TOKEN"))
cmd, repo = sys.argv[1], sys.argv[2]
if cmd == "up":
    prefix, files = sys.argv[3], sys.argv[4:]
    api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
    for f in files:
        api.upload_file(path_or_fileobj=f, path_in_repo=prefix.rstrip("/") + "/" + os.path.basename(f), repo_id=repo, repo_type="dataset")
        print("uploaded", f, "->", f"{repo}/{prefix}")
else:
    to = sys.argv[sys.argv.index("--to") + 1]
    for p in sys.argv[3:sys.argv.index("--to")]:
        print(hf_hub_download(repo, p, repo_type="dataset", local_dir=to, token=os.environ.get("HF_TOKEN")))
