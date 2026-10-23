"""Build registers_v2.ipynb: writes rv2.py, runs a pilot on both GPUs, gates on it, runs the full set, reports."""
import base64, json, pathlib

here = pathlib.Path(__file__).parent
code = base64.b64encode((here / "rv2.py").read_bytes()).decode()

HEADER = """# Registers v2

State slots carried alongside a 3.6M-parameter planner, in the skins world. Four models, five seeds each:

- `base`: plain GPT
- `taught-ends`: 8 slots that update at sentence ends; 4 taught by the simulator (where, holding, door here, goal item), fading out late in training
- `taught-every`: the same, but any word can update the slots
- `self-every`: every-word slots with no simulator at all; they're trained to predict the next sentence's words

Tests: seen skins, short and long problems, plus a **messy** version of every problem with all periods removed from the facts.

The notebook runs a short pilot first (base vs taught-every, both GPUs) and stops if the registers model is clearly broken. Then the full run splits across the GPUs. Results: `REGISTERS_V2_RESULTS.md`."""

WRITE = f"""import base64
open("rv2.py", "wb").write(base64.b64decode("{code}"))
print("wrote rv2.py")"""

RUNNER = r'''import subprocess, sys, json, glob, time, os, torch
NGPU = max(1, torch.cuda.device_count())
print("GPUs:", NGPU, [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())])
COST = {"base": 1.0, "taught-ends": 1.6, "taught-every": 1.6, "self-every": 1.7}


def assign(jobs):
    """Greedy split by rough cost so both GPUs finish at about the same time."""
    load, out = [0.0] * NGPU, {g: [] for g in range(NGPU)}
    for j in sorted(jobs, key=lambda j: -COST[j.split(":")[0]]):
        g = load.index(min(load))
        out[g].append(j); load[g] += COST[j.split(":")[0]]
    return out


def run_workers(plan, steps, ntest, tag):
    procs = []
    for g, jobs in plan.items():
        if jobs:
            f = open(f"{tag}_gpu{g}.txt", "w")
            procs.append((g, subprocess.Popen([sys.executable, "-u", "rv2.py", "worker", "--gpu", str(g), "--jobs", ",".join(jobs),
                                               "--steps", str(steps), "--ntest", str(ntest), "--tag", tag],
                                              stdout=f, stderr=subprocess.STDOUT)))
    t0 = time.time()
    while any(p.poll() is None for _, p in procs):
        time.sleep(120)
        for g, _ in procs:
            lines = [l for l in open(f"{tag}_gpu{g}.txt").read().splitlines() if l.strip()]
            print(f"[{(time.time()-t0)/60:5.1f} min gpu{g}] " + (lines[-1] if lines else "starting"), flush=True)
    ok = True
    for g, p in procs:
        print(f"[gpu{g}] exit code {p.returncode}")
        if p.returncode != 0:
            ok = False
            print(open(f"{tag}_gpu{g}.txt").read()[-4000:])
    return ok'''

PILOT = r'''pilot_jobs = ["base:0", "taught-every:0"]
ok = run_workers(assign(pilot_jobs) if NGPU > 1 else {0: pilot_jobs}, steps=1500, ntest=15, tag="pilot")
rows = {r["cond"]: r for f in glob.glob("pilot_results_gpu*.jsonl") for r in map(json.loads, open(f))}
reason = None
if not ok or len(rows) < 2:
    reason = "a pilot worker crashed (see pilot_gpu*.txt in the output)"
elif rows["taught-every"]["final_lm"] > rows["base"]["final_lm"] * 1.15:
    reason = f"the registers model's training loss is far behind base ({rows['taught-every']['final_lm']:.3f} vs {rows['base']['final_lm']:.3f})"
GO = reason is None
lines = ["## Pilot (1,500 steps, seed 0)", ""]
for c, r in rows.items():
    lines.append(f"- {c}: loss {r['final_lm']:.3f}, seen " + ", ".join(f"{k} {v['success']*100:.0f}%" for k, v in r["seen"].items())
                 + f", {r['train_s']}s training")
lines += ["", "Pilot passed; full run started." if GO else f"**Pilot failed: {reason}. Full run skipped.**"]
open("PILOT.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))'''

FULL = r'''if GO:
    jobs = [f"{c}:{s}" for s in range(5) for c in ["base", "taught-ends", "taught-every", "self-every"]]
    plan = assign(jobs)
    print({g: len(j) for g, j in plan.items()})
    run_workers(plan, steps=8000, ntest=50, tag="full")
else:
    print("skipped:", reason)'''

REPORT = r'''r = subprocess.run([sys.executable, "rv2.py", "report"], capture_output=True, text=True)
print(r.stdout[-20000:], r.stderr[-3000:])'''

cells = [{"cell_type": "markdown", "metadata": {}, "source": HEADER}]
for src in (WRITE, RUNNER, PILOT, FULL, REPORT):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "registers_v2.ipynb").write_text(json.dumps(nb, indent=1))
print("registers_v2.ipynb", len(cells), "cells")
