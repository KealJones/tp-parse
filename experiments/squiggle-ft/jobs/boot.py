"""Sets up a Hugging Face Job for squiggle-ft, then runs a script in it.

hf/runner.py fetches this one file into work/ and runs the job's cmd there. This script:
  1. prints the GPU (nvidia-smi)
  2. unpacks experiments/squiggle-ft from tp-parse at the job's commit into ./sqft
  3. unpacks KealJones/squiggle at the pinned commit into ./squiggle (SQUIGGLE_DIR) — the app code episodes run on
  4. installs node 22 and the experiment's npm packages (isomorphic-git, linkedom)
  5. runs `bash sqft/jobs/<script>` with outputs going to ./out (which the runner uploads)

  python boot.py smoke.sh
"""
import json, os, subprocess, sys, tarfile, time, urllib.request

SQUIGGLE_COMMIT = "f54bbf7c6be51681cc44e221a763ee2ec3a97890"   # KealJones/squiggle main 2026-10-28: small models get a quarter-window history and no injected facts/other chats (5c8f3f7), calculate knows pi and e (f54bbf7), Squiggle Small = SQ; teach-v2 ran on f09cac0, teach-v1 on e9c27ca
t0 = time.time()
os.environ['SQFT_T0'] = str(int(t0))   # job start, so scripts can budget the job's time limit


def get(url, dest):
    for i in range(5):
        try:
            urllib.request.urlretrieve(url, dest)
            return
        except Exception as e:
            print("retry", url, e, flush=True)
            time.sleep(5 + 5 * i)
    raise RuntimeError(f"could not download {url}")


def untar(tgz, dest, inner=None):
    os.makedirs(dest, exist_ok=True)
    with tarfile.open(tgz) as t:
        members = [m for m in t.getmembers() if m.name != "pax_global_header"]
        root = members[0].name.split("/")[0]
        pre = f"{root}/{inner}/" if inner else f"{root}/"
        for m in members:
            if m.name.startswith(pre) and len(m.name) > len(pre):
                m.name = m.name[len(pre):]
                t.extract(m, dest)


spec = json.loads(os.environ.get("SPEC", "{}"))
sha = spec.get("sha", "main")
subprocess.run("nvidia-smi || true", shell=True)
# vLLM's torch.compile/triton and the llama.cpp build need a C compiler; the pytorch runtime image has none.
subprocess.run("(command -v gcc && command -v cmake) || (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gcc g++ make cmake >/dev/null) || echo 'apt-get failed'", shell=True)
get(f"https://codeload.github.com/KealJones/tp-parse/tar.gz/{sha}", "tp.tgz")
untar("tp.tgz", "sqft", "experiments/squiggle-ft")
get(f"https://codeload.github.com/KealJones/squiggle/tar.gz/{SQUIGGLE_COMMIT}", "sq.tgz")
untar("sq.tgz", "squiggle")
vers = json.load(urllib.request.urlopen("https://nodejs.org/dist/index.json"))
v = next(x["version"] for x in vers if x["version"].startswith("v22."))
get(f"https://nodejs.org/dist/{v}/node-{v}-linux-x64.tar.gz", "node.tgz")
untar("node.tgz", "node")
env = dict(os.environ, PATH=os.path.abspath("node/bin") + ":" + os.environ["PATH"], SQUIGGLE_DIR=os.path.abspath("squiggle"),
           NODE_NO_WARNINGS="1", PYTHONUNBUFFERED="1", TOKENIZERS_PARALLELISM="false", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
subprocess.run(["npm", "ci", "--silent", "--no-audit", "--no-fund"], cwd="sqft", env=env, check=True)
print(f"boot: node {v}, squiggle {SQUIGGLE_COMMIT}, tp-parse {sha[:7]}, setup took {time.time() - t0:.0f} s", flush=True)
os.makedirs("out", exist_ok=True)
code = subprocess.run(["bash", os.path.join("jobs", sys.argv[1]), os.path.abspath("out")], cwd="sqft", env=env).returncode
sys.exit(code)
