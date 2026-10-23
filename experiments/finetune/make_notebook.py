"""Builds one Kaggle notebook per base model. Each writes ft.py + messages.json, runs a pilot of every code path,
then the full run (GPU 0: untouched then ft; GPU 1: ft-slots then lora-slots), then the report."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
B64 = {f: base64.b64encode((here / f).read_bytes()).decode() for f in ("ft.py", "messages.json")}
MODELS = {"qwen3-0-6b": "Qwen/Qwen3-0.6B", "smollm2-360m": "HuggingFaceTB/SmolLM2-360M-Instruct"}

SETUP = '''import base64, os, subprocess, sys
for f, b in {files}.items():
    open(f, "wb").write(base64.b64decode(b))
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import transformers
v = tuple(int(x) for x in transformers.__version__.split(".")[:2])
print("transformers", transformers.__version__)
if v < (4, 51):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers>=4.51", "datasets"], check=True)
    print("upgraded transformers; restart not needed since workers are fresh processes")'''

RUN = r'''import glob, json, time, torch
MODEL = "{model}"
NGPU = max(1, torch.cuda.device_count())
print("GPUs:", [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
PLAN = {{0: ["untouched", "ft"], 1: ["ft-slots", "lora-slots"]}} if NGPU > 1 else {{0: ["untouched", "ft", "ft-slots", "lora-slots"]}}


def run(tag):
    procs = []
    for g, versions in PLAN.items():
        log = open(f"{{tag}}_gpu{{g}}.txt", "w")
        cmd = " && ".join(f"{{sys.executable}} -u ft.py worker --model {{MODEL}} --version {{v}} --gpu {{g}} --tag {{tag}}" for v in versions)
        procs.append((g, subprocess.Popen(cmd, shell=True, stdout=log, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(60 if tag == "pilot" else 300)
        for g, _ in procs:
            lines = [l for l in open(f"{{tag}}_gpu{{g}}.txt").read().splitlines() if l.strip()]
            print(f"[{{(time.time()-t0)/60:5.1f}} min gpu{{g}}] " + (lines[-1][:200] if lines else "starting"), flush=True)
    ok = all(p.returncode == 0 for _, p in procs)
    for g, p in procs:
        if p.returncode != 0:
            print(f"--- gpu{{g}} failed (exit {{p.returncode}}) ---\n" + open(f"{{tag}}_gpu{{g}}.txt").read()[-5000:])
    return ok'''

PILOT = '''ok = run("pilot")
done = sorted(glob.glob("pilot_*.json"))
lines = ["## Pilot (20 training steps, 2 problems per cell: every code path once)", ""]
for f in done:
    r = json.load(open(f))
    lines.append(f"- {r['version']}: ran in {r['total_s']}s, clean short {r['plans']['clean/short']['success']*100:.0f}%")
GO = ok and len(done) == 4
lines += ["", "Pilot passed; full run started." if GO else "**Pilot failed; full run skipped. See pilot_gpu*.txt.**"]
open("PILOT.md", "w").write("\\n".join(lines) + "\\n")
print("\\n".join(lines))'''

FULL = '''if GO:
    run("full")
else:
    print("skipped")'''

REPORT = '''r = subprocess.run([sys.executable, "ft.py", "report", "--model", MODEL], capture_output=True, text=True)
print(r.stdout[-20000:], r.stderr[-3000:])'''

for slug, model in MODELS.items():
    head = (f"# Fine-tune test: {model}\n\nFour versions of the same pretrained model: untouched (few-shot), full fine-tune, "
            "full fine-tune + state slots, LoRA + state slots. Scored on planning in the world (clean, messy, filler), honest gaps, "
            "English kept, Keal's real messages, and again after squashing to 4 bits. A pilot runs every code path first. "
            f"Results: `FT_RESULTS_{model.split('/')[-1].lower()}.md`.")
    cells = [{"cell_type": "markdown", "metadata": {}, "source": head}]
    for src in (SETUP.format(files=json.dumps(B64)), RUN.format(model=model), PILOT, FULL, REPORT):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
          "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
    (here / f"ft_{slug}.ipynb").write_text(json.dumps(nb, indent=1))
    print(f"ft_{slug}.ipynb")
