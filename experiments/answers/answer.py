"""Each model answers every task in its own words (chat format, greedy). No options, no hints.
  python answer.py [--pilot]     writes out/answers.json and out/AUTO.md (first-pass regex check)"""
import json, os, re, sys, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PILOT = "--pilot" in sys.argv
CONFIGS = [("Qwen/Qwen3-0.6B", False), ("Qwen/Qwen3-0.6B", True), ("Qwen/Qwen3-1.7B", True), ("Qwen/Qwen3-4B", True)]
if PILOT:
    CONFIGS = CONFIGS[:2]
tasks = json.load(open("tasks.json"))[: 3 if PILOT else None]
os.makedirs("out", exist_ok=True)
out, t0 = [], time.time()
for name, think in CONFIGS:
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.bfloat16).to("cuda").eval()
    texts = [tok.apply_chat_template([{"role": "user", "content": (t["ctx"] + "\n\n" if t["ctx"] else "") + t["msg"]}],
                                     tokenize=False, add_generation_prompt=True, enable_thinking=think) for t in tasks]
    for i in range(0, len(texts), 6):
        enc = tok(texts[i:i + 6], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            g = model.generate(**enc, max_new_tokens=(64 if PILOT else 2048 if think else 600), do_sample=False,
                               pad_token_id=tok.pad_token_id)
        for j, t in enumerate(tasks[i:i + 6]):
            full = tok.decode(g[j, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            ans = full.split("</think>")[-1].strip()
            ok = all(re.search(p, ans, re.I | re.S) for p in t["auto"]) and not any(re.search(p, ans, re.I) for p in t["fail_if"])
            out.append({"model": name, "think": think, "id": t["id"], "msg": t["msg"], "answer": ans,
                        "thinking": full.split("</think>")[0] if "</think>" in full else "", "auto_pass": ok,
                        "truncated": think and "</think>" not in full})
    print(f"{name} think={think}: auto {sum(o['auto_pass'] for o in out if o['model'] == name and o['think'] == think)}/{len(tasks)} "
          f"({time.time()-t0:.0f}s)", flush=True)
    del model; torch.cuda.empty_cache()
json.dump(out, open("out/answers.json", "w"), indent=1, ensure_ascii=False)
L = ["# Auto check (regex first pass; Claude grades by hand against each task's rule)", ""]
for name, think in CONFIGS:
    rows = [o for o in out if o["model"] == name and o["think"] == think]
    L.append(f"- {name}, thinking {'on' if think else 'off'}: {sum(r['auto_pass'] for r in rows)}/{len(rows)}"
             f" (cut off mid-thought: {sum(r['truncated'] for r in rows)})")
open("out/AUTO.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
