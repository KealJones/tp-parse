"""Hugging Face Jobs bridge, run by GitHub Actions (needs HF_TOKEN).

  python hf/bridge.py start      launch every job in hf/queue/ (moved to hf/pending/)
  python hf/bridge.py collect    check pending jobs; pull finished results into each job's "out" folder

A job file in hf/queue/:
  {"slug": "followup-read-keal", "flavor": "a10g-small", "timeout": "60m",
   "files": ["experiments/finetune/ft.py", ...], "cmd": "python followup.py", "outdir": "out",
   "out": "experiments/finetune/hf-out-followup", "pip": ["transformers>=4.51", "datasets"]}
"""
import datetime as dt, json, os, re, shutil, sys, tempfile
from pathlib import Path
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
Q, PENDING, DONE = (ROOT / "hf" / d for d in ("queue", "pending", "done"))
IMAGE = "pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime"
PRICE = {"cpu-basic": 0.01, "cpu-upgrade": 0.03, "t4-small": 0.40, "t4-medium": 0.60, "l4x1": 0.80, "a10g-small": 1.00,
         "a10g-large": 1.50, "l40sx1": 1.80, "a100-large": 2.50, "rtx-pro-6000": 2.75, "h200": 5.00}
MAX_TIMEOUT_MIN = 180
TERMINAL = {"COMPLETED", "ERROR", "CANCELED", "DELETED"}
api = HfApi(token=os.environ["HF_TOKEN"])
USER = api.whoami()["name"]
RESULTS = f"{USER}/tp-parse-runs"
MAX_FILE = 50_000_000      # bigger outputs (model files) stay in the results repo; GitHub refuses >100 MB and big pushes time out
REPO = os.environ.get("GITHUB_REPOSITORY", "KealJones/tp-parse")


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def minutes(t):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smh]?)", str(t))
    v, u = float(m[1]), m[2] or "s"
    return v / 60 if u == "s" else v if u == "m" else v * 60


def status(job, lines):
    out = ROOT / job["out"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "HF_STATUS.md").write_text("\n".join([f"# Hugging Face job: {job['slug']}", ""] + lines) + "\n")


def start():
    api.create_repo(RESULTS, repo_type="dataset", private=True, exist_ok=True)
    for f in sorted(Q.glob("*.json")) if Q.exists() else []:
        job = json.loads(f.read_text())
        flavor, timeout = job.get("flavor", "a10g-small"), job.get("timeout", "60m")
        assert minutes(timeout) <= MAX_TIMEOUT_MIN, f"timeout {timeout} is over the {MAX_TIMEOUT_MIN} min cap"
        spec = {**job, "sha": os.environ["GITHUB_SHA"], "repo": REPO, "results_repo": RESULTS}
        runner = f"https://raw.githubusercontent.com/{REPO}/{spec['sha']}/hf/runner.py"
        cmd = ["bash", "-c", f"python -c \"import urllib.request as u; u.urlretrieve('{runner}', 'runner.py')\" && python runner.py"]
        try:
            info = api.run_job(image=job.get("image", IMAGE), command=cmd, flavor=flavor, timeout=timeout,
                               env={"SPEC": json.dumps(spec)}, secrets={"HF_TOKEN": os.environ["HF_TOKEN"]})
            job.update(job_id=info.id, url=info.url, started=now(), sha=spec["sha"])
            PENDING.mkdir(exist_ok=True)
            (PENDING / f.name).write_text(json.dumps(job, indent=1))
            cap = minutes(timeout) / 60 * PRICE.get(flavor, 0)
            status(job, [f"Status: **running** on `{flavor}` (started {job['started']}, time limit {timeout}, "
                         f"so at most about ${cap:.2f})", f"Job page: {info.url}"])
            print(f"[{job['slug']}] started {info.id} on {flavor}")
        except Exception as e:
            job.update(result="launch failed", error=str(e)[-1500:], finished=now())
            DONE.mkdir(exist_ok=True)
            (DONE / f.name).write_text(json.dumps(job, indent=1))
            status(job, ["Status: **launch failed**", "", "```", str(e)[-1500:], "```"])
            print(f"[{job['slug']}] launch failed: {e}")
        f.unlink()


def collect():
    from huggingface_hub import snapshot_download
    for f in sorted(PENDING.glob("*.json")) if PENDING.exists() else []:
        job = json.loads(f.read_text())
        info = api.inspect_job(job_id=job["job_id"])
        stage = info.status.stage
        print(f"[{job['slug']}] {stage}")
        if stage not in TERMINAL:
            status(job, [f"Status: **{stage.lower()}** (started {job['started']}, last check {now()})", f"Job page: {job['url']}"])
            continue
        dest = ROOT / job["out"]
        dest.mkdir(parents=True, exist_ok=True)
        got, js = [], {}
        with tempfile.TemporaryDirectory() as d:
            try:
                snapshot_download(RESULTS, repo_type="dataset", local_dir=d, allow_patterns=[f"{job['slug']}/{job['job_id']}/*"])
                src = Path(d) / job["slug"] / job["job_id"]
                for p in sorted(src.rglob("*")) if src.exists() else []:
                    if p.is_file() and p.stat().st_size > MAX_FILE:     # git can't take it: leave it in the results repo
                        got.append(f"{p.relative_to(src)} (not copied: {p.stat().st_size / 1e6:.0f} MB, it stays in {RESULTS})")
                    elif p.is_file():
                        (dest / p.relative_to(src)).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(p, dest / p.relative_to(src)); got.append(str(p.relative_to(src)))
                js = json.loads((src / "job_status.json").read_text()) if (src / "job_status.json").exists() else {}
            except Exception as e:
                print("download failed:", e)
        if not got:                           # crashed before the runner could upload: keep the job's own log tail
            try:
                lines = [str(x) for x in api.fetch_job_logs(job_id=job["job_id"])]
                (dest / "JOB_LOG.txt").write_text("\n".join(lines[-400:]) + "\n"); got.append("JOB_LOG.txt (from job logs)")
            except Exception as e:
                print("logs failed:", e)
        mins = js.get("elapsed_s", 0) / 60
        cost = mins / 60 * PRICE.get(job.get("flavor", "a10g-small"), 0)
        result = "complete" if stage == "COMPLETED" and js.get("exit_code") == 0 else f"{stage.lower()}" + (f" (exit {js.get('exit_code')})" if js else "")
        job.update(result=result, finished=now(), minutes=round(mins, 1), est_cost=round(cost, 2))
        status(job, [f"Status: **{result}** after {mins:.1f} min of work on `{job.get('flavor')}`, about ${cost:.2f} "
                     "(plus a minute or two of startup)", f"Job page: {job['url']}", "",
                     "Files copied here:", *([f"- {g}" for g in got] or ["- none"]),
                     *(["", f"Hugging Face says: {info.status.message}"] if info.status.message else [])])
        DONE.mkdir(exist_ok=True)
        (DONE / f.name).write_text(json.dumps(job, indent=1))
        f.unlink()


if __name__ == "__main__":
    {"start": start, "collect": collect}[sys.argv[1]]()
