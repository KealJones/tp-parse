"""Runs inside a Hugging Face Job. Fetches the job's files from GitHub at the pushed commit, runs the command,
and always uploads the outputs, the log and the exit status to the private results repo (even on a crash)."""
import json, os, shutil, subprocess, sys, time, urllib.request

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
    log.close()
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    up = os.path.abspath("upload")
    os.makedirs(up, exist_ok=True)
    out = os.path.join(work, SPEC.get("outdir", "out"))
    if os.path.isdir(out):
        shutil.copytree(out, up, dirs_exist_ok=True)
    shutil.copy(os.path.join(work, "JOB_LOG.txt"), up)
    json.dump({"exit_code": code, "elapsed_s": round(elapsed), "job_id": os.environ.get("JOB_ID"),
               "accelerator": os.environ.get("ACCELERATOR")}, open(os.path.join(up, "job_status.json"), "w"))
    api.upload_folder(folder_path=up, repo_id=SPEC["results_repo"], repo_type="dataset",
                      path_in_repo=f"{SPEC['slug']}/{os.environ.get('JOB_ID', 'local')}", commit_message=f"{SPEC['slug']} results")
    print("uploaded results", flush=True)
    sys.exit(0 if code == 0 else 1)
