"""Kaggle bridge, run by GitHub Actions.

  python kaggle/bridge.py start [queue files...]   push queued notebooks to Kaggle (all of kaggle/queue/ if none given)
  python kaggle/bridge.py collect                  check running jobs; download results of finished ones

A job is a JSON file in kaggle/queue/:
  {"slug": "registers-v2", "notebook": "experiments/registers/registers.ipynb",
   "out": "experiments/registers/kaggle-out", "gpu": true, "internet": false}

start moves it to kaggle/pending/, collect moves it to kaggle/done/ once Kaggle says it finished, and writes
the notebook's output files (small ones) plus KAGGLE_STATUS.md and KAGGLE_LOG.txt into "out".
Needs KAGGLE_USERNAME and KAGGLE_KEY in the environment (GitHub secrets).
"""
import datetime as dt, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
Q, PENDING, DONE = (ROOT / "kaggle" / d for d in ("queue", "pending", "done"))
MAX_FILE = 20 * 1024 * 1024        # output files bigger than this stay on Kaggle (listed in KAGGLE_STATUS.md)
MAX_HOURS = 13                     # Kaggle stops sessions at 12 hours
USER = os.environ.get("KAGGLE_USERNAME", "").strip()


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def kaggle(*args):
    r = subprocess.run(["kaggle", *args], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def write_status(job, lines):
    out = ROOT / job["out"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "KAGGLE_STATUS.md").write_text("\n".join([f"# Kaggle run: {job['slug']}", ""] + lines) + "\n")


def start(files):
    files = [Path(f) for f in files] or sorted(Q.glob("*.json"))
    for f in files:
        f = f if f.is_absolute() else ROOT / f
        if not f.exists() or f.parent != Q:
            continue
        job = json.loads(f.read_text())
        slug = job["slug"]
        assert re.fullmatch(r"[a-z0-9][a-z0-9-]{2,49}", slug), f"bad slug {slug!r}"
        nb = ROOT / job["notebook"]
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(nb, Path(d) / nb.name)
            meta = {"id": f"{USER}/{slug}", "title": slug.replace("-", " "), "code_file": nb.name,
                    "language": "python", "kernel_type": "notebook", "is_private": True,
                    "enable_gpu": bool(job.get("gpu", True)), "enable_tpu": False,
                    "enable_internet": bool(job.get("internet", False)),
                    "dataset_sources": [], "competition_sources": [], "kernel_sources": [], "model_sources": []}
            (Path(d) / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
            code, out = kaggle("kernels", "push", "-p", d)
        print(f"[{slug}] push exit {code}:\n{out}")
        job["push_output"] = out[-2000:]
        m = re.search(r"kaggle\.com/code/([^/\s]+)/([^/\s]+)", out)
        job["ref"] = f"{m[1]}/{m[2]}" if m else f"{USER}/{slug}"     # the real owner name, even if the secret holds an email
        ok = code == 0 and "error" not in out.lower()
        if ok:
            job["started"] = now().isoformat()
            PENDING.mkdir(exist_ok=True)
            (PENDING / f"{slug}.json").write_text(json.dumps(job, indent=1))
            write_status(job, [f"Status: **running** (pushed {job['started']})", "", "```", out, "```"])
        else:
            job["finished"], job["result"] = now().isoformat(), "push failed"
            DONE.mkdir(exist_ok=True)
            (DONE / f"{slug}.json").write_text(json.dumps(job, indent=1))
            write_status(job, ["Status: **push failed**", "", "```", out, "```"])
        f.unlink()


def collect():
    for f in sorted(PENDING.glob("*.json")) if PENDING.exists() else []:
        job = json.loads(f.read_text())
        slug = job["slug"]
        ref = job.get("ref") or f"{USER}/{slug}"
        code, out = kaggle("kernels", "status", ref)
        state = out.lower()
        print(f"[{slug}] status: {out}")
        age = (now() - dt.datetime.fromisoformat(job["started"])).total_seconds() / 3600
        finished = any(w in state for w in ("complete", "error", "cancel")) or age > MAX_HOURS
        if not finished:
            write_status(job, [f"Status: **running** for {age:.1f} h (last check {now().isoformat()})", "", "```", out, "```"])
            continue
        result = "complete" if "complete" in state else "error" if "error" in state else "cancelled" if "cancel" in state else "timed out"
        dest = ROOT / job["out"]
        dest.mkdir(parents=True, exist_ok=True)
        kept, skipped, log_tail = [], [], ""
        with tempfile.TemporaryDirectory() as d:
            c2, o2 = kaggle("kernels", "output", ref, "-p", d)
            print(f"[{slug}] output exit {c2}:\n{o2[-1500:]}")
            for p in sorted(Path(d).rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(d)
                if p.name == f"{slug}.log" or p.suffix == ".log":
                    log_tail = "\n".join(p.read_text(errors="replace").splitlines()[-400:])
                    continue
                if p.stat().st_size > MAX_FILE:
                    skipped.append(f"- {rel} ({p.stat().st_size / 1e6:.0f} MB, download it from Kaggle)")
                    continue
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(p, dest / rel)
                kept.append(f"- {rel}")
        if log_tail:
            (dest / "KAGGLE_LOG.txt").write_text(log_tail + "\n")
        job.update(finished=now().isoformat(), result=result, hours=round(age, 2))
        write_status(job, [f"Status: **{result}** after {age:.1f} h (finished check {job['finished']})",
                           f"Kaggle page: https://www.kaggle.com/code/{ref}", "",
                           "Files copied here:", *(kept or ["- none"]), "",
                           *(["Too big to copy:", *skipped, ""] if skipped else []),
                           "Last status line:", "```", out, "```"])
        DONE.mkdir(exist_ok=True)
        (DONE / f"{slug}.json").write_text(json.dumps(job, indent=1))
        f.unlink()


def setup_auth():
    """The key secret may be a new-style API token or a legacy kaggle.json key: try the token first, then the file."""
    key = os.environ.pop("KAGGLE_KEY", "").strip()
    if not key:
        sys.exit("KAGGLE_KEY is not set")
    os.environ["KAGGLE_API_TOKEN"] = key
    if kaggle("kernels", "list", "--mine", "--page-size", "1")[0] == 0:
        print("auth: API token")
        return
    del os.environ["KAGGLE_API_TOKEN"]
    cfg = Path.home() / ".kaggle"
    cfg.mkdir(exist_ok=True)
    (cfg / "kaggle.json").write_text(json.dumps({"username": USER, "key": key}))
    (cfg / "kaggle.json").chmod(0o600)
    code, out = kaggle("kernels", "list", "--mine", "--page-size", "1")
    print("auth: kaggle.json" if code == 0 else f"auth failed both ways:\n{out[-1500:]}")


if __name__ == "__main__":
    if not USER:
        sys.exit("KAGGLE_USERNAME is not set")
    setup_auth()
    {"start": lambda: start(sys.argv[2:]), "collect": collect}[sys.argv[1]]()
