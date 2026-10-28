"""Runs inside a Hugging Face Job. Fetches the job's files from GitHub at the pushed commit, runs the command,
and always uploads the outputs, the log and the exit status to the private results repo (even on a crash). While the
command runs it also uploads what's in the output folder every few minutes (SPEC "upload_every", seconds; default 120)
and on SIGTERM, so a job that hits its time limit still leaves its partial results."""
import json, os, shutil, signal, subprocess, sys, threading, time, urllib.request

SPEC = json.loads(os.environ["SPEC"])
t0 = time.time()
work = os.path.abspath("work")
os.makedirs(work, exist_ok=True)
log = open(os.path.join(work, "JOB_LOG.txt"), "w")


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    log.write(line + "\n"); log.flush()


code = -1
_up_lock = threading.Lock()


def upload(final=False):
    """Copy the output folder, the log and the status to a fresh folder and upload it (same path every time)."""
    with _up_lock:
        from huggingface_hub import HfApi
        api = HfApi(token=os.environ["HF_TOKEN"])
        up = os.path.abspath("upload")
        shutil.rmtree(up, ignore_errors=True)
        os.makedirs(up, exist_ok=True)
        out = os.path.join(work, SPEC.get("outdir", "out"))
        if os.path.isdir(out):
            shutil.copytree(out, up, dirs_exist_ok=True)
        log.flush()
        shutil.copy(os.path.join(work, "JOB_LOG.txt"), up)
        json.dump({"exit_code": code if final else None, "partial": not final, "elapsed_s": round(time.time() - t0),
                   "job_id": os.environ.get("JOB_ID"), "accelerator": os.environ.get("ACCELERATOR")},
                  open(os.path.join(up, "job_status.json"), "w"))
        api.upload_folder(folder_path=up, repo_id=SPEC["results_repo"], repo_type="dataset",
                          path_in_repo=f"{SPEC['slug']}/{os.environ.get('JOB_ID', 'local')}",
                          commit_message=f"{SPEC['slug']} results" + ("" if final else " (partial)"))


def every():
    while True:
        time.sleep(SPEC.get("upload_every", 120))
        try:
            upload()
            print("uploaded partial results", flush=True)
        except Exception as e:
            print("partial upload failed:", repr(e), flush=True)


def on_term(signum, frame):
    say(f"got signal {signum} after {(time.time() - t0) / 60:.1f} min: uploading what there is")
    try:
        upload()
    finally:
        os._exit(1)


signal.signal(signal.SIGTERM, on_term)
threading.Thread(target=every, daemon=True).start()
try:
    say(f"job {os.environ.get('JOB_ID')} on {os.environ.get('ACCELERATOR')}: {SPEC['slug']} at {SPEC['sha'][:7]}")
    if SPEC.get("pip"):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", *SPEC["pip"]], check=True)
    for path in SPEC["files"]:
        url = f"https://raw.githubusercontent.com/{SPEC['repo']}/{SPEC['sha']}/{path}"
        urllib.request.urlretrieve(url, os.path.join(work, os.path.basename(path)))
        say("fetched", path)
    p = subprocess.Popen(SPEC["cmd"], cwd=work, shell=isinstance(SPEC["cmd"], str),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1)
    for line in p.stdout:
        say(line.rstrip("\n"))
    code = p.wait()
except Exception as e:
    say("runner error:", repr(e))
finally:
    elapsed = time.time() - t0
    say(f"exit code {code} after {elapsed/60:.1f} min")
    upload(final=True)
    print("uploaded results", flush=True)
    sys.exit(0 if code == 0 else 1)
