"""Makes kealjones/squiggle-small public (Keal approved: "make squiggle-small public when you have a model worth
trying"): model-card front matter on README.md, an "experimental" line at the top, visibility public, then checks the
GGUF downloads without a token. Touches only this repo. Run as a tiny HF job (the token lives there)."""
import os, re, sys, urllib.error, urllib.parse, urllib.request

from huggingface_hub import HfApi, hf_hub_download

REPO = "kealjones/squiggle-small"
GGUF = "squiggle-small-lfm25-Q4_0.gguf"
FRONT = """---
license: other
license_name: lfm1.0
license_link: https://huggingface.co/LiquidAI/LFM2.5-350M/blob/main/LICENSE
base_model: LiquidAI/LFM2.5-350M
tags:
- gguf
- squiggle
---
"""
LINE = "Experimental v1. See the results below; not production quality."

api = HfApi(token=os.environ["HF_TOKEN"])
files = api.list_repo_files(REPO)
print("files:", files)
if GGUF not in files:
    sys.exit(f"{GGUF} is not in {REPO}; stopping before changing anything")
readme = open(hf_hub_download(REPO, "README.md", token=os.environ["HF_TOKEN"])).read() if "README.md" in files else ""
body = re.sub(r"\A---\n.*?\n---\n", "", readme, flags=re.S).lstrip("\n")     # replace any earlier front matter
if not body.startswith(LINE):
    body = LINE + "\n\n" + body
new = FRONT + "\n" + body
if new != readme:
    api.upload_file(path_or_fileobj=new.encode(), path_in_repo="README.md", repo_id=REPO,
                    commit_message="Model card: license (LFM 1.0), base model, tags; marked experimental v1")
    print("README.md updated")
print(new[:900])
api.update_repo_settings(REPO, private=False)
print("visibility:", "private" if api.model_info(REPO).private else "public")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


url = f"https://huggingface.co/{REPO}/resolve/main/{GGUF}"
op = urllib.request.build_opener(NoRedirect)
try:
    r = op.open(urllib.request.Request(url, method="HEAD"))
    first, loc = r.status, r.headers.get("Location")
except urllib.error.HTTPError as e:
    first, loc = e.code, e.headers.get("Location")
print("anonymous HEAD", url, "->", first, (loc or "")[:120])
second = None
if loc:
    loc = urllib.parse.urljoin(url, loc)
    try:
        second = urllib.request.urlopen(urllib.request.Request(loc, method="HEAD")).status
    except urllib.error.HTTPError as e:
        second = e.code
print("anonymous HEAD redirect target ->", second)
ok = first in (301, 302, 307, 308) and second == 200
print("ANONYMOUS ACCESS", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
