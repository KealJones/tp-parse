"""Real data the episodes are built from, fetched once and cached under <work>/data/.

  nq_open      google-research-datasets/nq_open (CC BY-SA 3.0): real Google search questions, short answers
  hotpot       hotpotqa/hotpot_qa distractor (CC BY-SA 4.0): two-hop questions (comparison and bridge)
  gsm8k        openai/gsm8k (MIT): grade-school word problems with numeric answers
  hermes       interstellarninja/hermes_reasoning_tool_use (Apache-2.0): user requests + whether the reference
               model called a tool or asked for missing info (see hermes.py for what is used and why)
  repos        facts read straight out of real public GitHub repos (sq/repofacts.mjs)
"""
import json, os, subprocess, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = "https://datasets-server.huggingface.co/rows"
UA = "squiggle-ft/1.0 (https://github.com/KealJones/tp-parse)"

TRAIN_REPOS = ["KealJones/squiggle", "KealJones/tp-parse", "sindresorhus/slugify", "sindresorhus/p-limit", "lukeed/clsx",
               "lukeed/kleur", "developit/mitt", "ai/nanoid", "vercel/ms", "chalk/chalk", "expressjs/cors", "motdotla/dotenv",
               "pallets/itsdangerous", "pallets/markupsafe", "python-humanize/humanize", "sindresorhus/execa",
               "yargs/yargs-parser", "uuidjs/uuid"]
EVAL_REPOS = ["lukeed/dequal", "developit/dlv", "tj/commander.js", "jprichardson/node-fs-extra", "simonw/sqlite-utils"]


def _get(url, tries=6):
    headers = {"User-Agent": UA}
    if os.environ.get("HF_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["HF_TOKEN"]
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == tries - 1:
                raise
            ra = getattr(e, "headers", None) and e.headers.get("Retry-After")
            time.sleep(min(60, float(ra) if ra and str(ra).isdigit() else 3 * 2 ** i))


def rows(dataset, config, split, n, offset=0, cache=None):
    """Up to n rows via the datasets-server API (100 per request), cached as JSON. The slices this experiment uses are
    committed (trimmed) in data/sources/, so jobs don't depend on the API."""
    committed = HERE / "data" / "sources" / Path(cache).name if cache else None
    if cache and not Path(cache).exists() and committed and committed.exists():
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(committed.read_text())
    if cache and Path(cache).exists():
        got = json.loads(Path(cache).read_text())
        if len(got) >= n:
            return got[:n]
    out = []
    while len(out) < n:
        q = urllib.parse.urlencode({"dataset": dataset, "config": config, "split": split, "offset": offset + len(out), "length": min(100, n - len(out))})
        d = _get(f"{ROWS}?{q}")
        batch = [r["row"] for r in d.get("rows", [])]
        if not batch:
            break
        out.extend(batch)
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        Path(cache).write_text(json.dumps(out))
    return out


def nq_open(work, n=600, split="validation", offset=0):
    return rows("google-research-datasets/nq_open", "nq_open", split, n, offset, Path(work) / "data" / f"nq_{split}_{offset}_{n}.json")


def hotpot(work, n=1500, split="validation", offset=0):
    raw = rows("hotpotqa/hotpot_qa", "distractor", split, n, offset, Path(work) / "data" / f"hotpot_{split}_{offset}_{n}.json")
    import html
    return [{"id": r["id"], "question": html.unescape(r["question"]), "answer": html.unescape(r["answer"]), "type": r["type"], "level": r["level"],
             "titles": sorted(set(html.unescape(t) for t in r["supporting_facts"]["title"]))} for r in raw]


def gsm8k(work, n=800, split="test", offset=0):
    raw = rows("openai/gsm8k", "main", split, n, offset, Path(work) / "data" / f"gsm8k_{split}_{offset}_{n}.json")
    out = []
    for r in raw:
        ans = r["answer"].split("####")[-1].strip().replace(",", "")
        out.append({"question": r["question"], "answer": ans})
    return out


HERMES_URL = "https://huggingface.co/datasets/interstellarninja/hermes_reasoning_tool_use/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"


def hermes_rows(work):
    path = Path(work) / "data" / "hermes.parquet"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(HERMES_URL, headers={"User-Agent": UA, **({"Authorization": "Bearer " + os.environ["HF_TOKEN"]} if os.environ.get("HF_TOKEN") else {})})
        with urllib.request.urlopen(req, timeout=600) as r, open(str(path) + ".part", "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        os.replace(str(path) + ".part", path)
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()


def repo_facts(work, repos):
    """{repo: facts} for each repo (cloned once into <work>/repo-cache)."""
    cache = Path(work) / "data" / "repofacts.json"
    have = json.loads(cache.read_text()) if cache.exists() else {}
    need = [r for r in repos if r not in have]
    if need:
        env = dict(os.environ, NODE_NO_WARNINGS="1")
        if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
            env["NODE_USE_ENV_PROXY"] = "1"
        p = subprocess.run(["node", str(HERE / "sq" / "repofacts.mjs"), str(Path(work) / "repo-cache"), *need],
                           capture_output=True, text=True, env=env, cwd=str(HERE), timeout=1800)
        for line in p.stdout.splitlines():
            d = json.loads(line)
            if "error" not in d:
                have[d["repo"]] = d
            else:
                print("repo facts failed:", d["repo"], d["error"])
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(have))
    return {r: have[r] for r in repos if r in have}
