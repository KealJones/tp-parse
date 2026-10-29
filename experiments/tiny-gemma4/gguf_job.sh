#!/bin/bash
# Convert a tiny-Gemma-4 checkpoint to a Q4_0 GGUF with llama.cpp b11364 (the build inside wllama 3.8.1),
# smoke-test it with llama.cpp itself, and upload it to a public model repo for the Squiggle app.
#   CKPT=repo:path/to/ckpt REPO=kealjones/tiny-gemma4-test NAME=tiny-gemma4-heal2 bash gguf_job.sh OUT_DIR
set -euo pipefail
OUT=${1:-out}; mkdir -p "$OUT"
(command -v gcc && command -v cmake && command -v git) >/dev/null || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gcc g++ make cmake git >/dev/null)

python - <<EOF
import os
from huggingface_hub import snapshot_download
repo, path = os.environ["CKPT"].split(":", 1)
d = snapshot_download(repo, repo_type="dataset", allow_patterns=[f"{path}/*"], token=os.environ.get("HF_TOKEN"))
os.symlink(os.path.join(d, path), "ckpt")
EOF
python to_gguf.py ckpt pkg

git clone -q --depth 1 --branch b11364 https://github.com/ggml-org/llama.cpp
pip install -q -e llama.cpp/gguf-py
python llama.cpp/convert_hf_to_gguf.py pkg --outtype f16 --outfile f16.gguf 2>&1 | tail -20

cmake -S llama.cpp -B build -DLLAMA_CURL=OFF -DGGML_NATIVE=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF >/dev/null
cmake --build build --target llama-quantize llama-simple -j "$(nproc)" 2>&1 | tail -3
# The per-layer embedding table is half the model and only looked up, never multiplied: 4-bit is enough.
./build/bin/llama-quantize --tensor-type per_layer_token_embd=q4_0 f16.gguf "$OUT/$NAME-Q4_0.gguf" Q4_0 2>&1 | tail -5
ls -la "$OUT"

# Smoke test: llama.cpp loads it and writes something (raw prompt, greedy).
./build/bin/llama-simple -m "$OUT/$NAME-Q4_0.gguf" -n 40 "The capital of France is" 2>&1 | tail -8 | tee "$OUT/smoke.txt"

python - <<EOF
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
repo, name, out = os.environ["REPO"], os.environ["NAME"], "$OUT"
api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
readme = f"""---
license: apache-2.0
base_model: google/gemma-4-E2B-it
tags: [gguf, gemma4, pruned, distilled, experimental]
---
# Tiny Gemma 4 (experimental test builds)

Gemma 4 E2B-it cut down for phones (80K-token vocabulary, hidden 1024, FFN 42%, 31 of 35 layers: ~0.6B body)
and partly healed by distillation from the uncut model. **Barely healed: it rambles and repeats.** Built to
measure memory and speed in a browser tab (wllama / llama.cpp b11364). Experiment notes:
https://github.com/KealJones/tp-parse/tree/main/experiments/tiny-gemma4

Files: `{name}-Q4_0.gguf`.
"""
api.upload_file(path_or_fileobj=readme.encode(), path_in_repo="README.md", repo_id=repo)
api.upload_file(path_or_fileobj=f"{out}/{name}-Q4_0.gguf", path_in_repo=f"{name}-Q4_0.gguf", repo_id=repo)
print("uploaded", f"https://huggingface.co/{repo}/resolve/main/{name}-Q4_0.gguf", os.path.getsize(f"{out}/{name}-Q4_0.gguf"))
EOF
# The GGUF is on the model repo; don't also copy it into the results repo.
mv "$OUT/$NAME-Q4_0.gguf" . || true
