"""Follow-up: can LoRA + state slots learn to read Keal, without ever seeing his messages?

Qwen3-0.6B, frozen, with rank-16 LoRA patches and the self-taught every-word slots (the `lora-slots` setup from
the fine-tune test). Trained on a mix of:
  - the planning task with the harness in the loop (so the skill stays)
  - everyday requests (Dolly-15k instructions) roughed up the way Keal types and talks → the clean request
  - real conversational speech with fillers, repeats and restarts (disfluency-sft) → the clean text
Scored on all 45 of Keal's real messages (never in training): pick what he meant out of four, typed vs voice,
before and after training, plus planning and English kept. It also writes its own reading of every message.

  python followup.py [--pilot]          runs everything; writes out/ (results.json, readings.json, RESULTS.md)
"""
import json, math, os, random, re, statistics as st, sys, time

import torch
import torch.nn as nn
import torch.nn.functional as F

import ft                                   # the fine-tune test: world, checker, slots, LoRA, scoring

PILOT = "--pilot" in sys.argv
MODEL = "Qwen/Qwen3-0.6B"
STEPS, MICRO = (20, 4) if PILOT else (1500, 8)
N_PLAN = 2 if PILOT else 24
OUT = "out"
os.makedirs(OUT, exist_ok=True)

BF16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
if BF16:                                    # A10G / L4 / A100: bf16 is safer than fp16 and needs no loss scaling
    ft.amp = lambda: torch.autocast(device_type="cuda", dtype=torch.bfloat16)
    ft.AMP_ON = False                       # turns off the fp16 GradScaler; autocast above still runs in bf16


# ---------------------------------------------------------------- roughing up clean requests, Keal-style

VOICE_FILL = ["um", "uh", "like", "so", "you know", "I mean", "kind of", "basically", "like literally", "or whatever"]
VOICE_TAIL = [" You know what I mean?", " or whatever.", " if that makes sense.", " I don't know.", " Does that make sense?"]
VOICE_HEAD = ["So, uh, ", "Um, ", "Yeah, so ", "Okay so like ", "I'm curious, um, ", "So I was thinking, "]
TYPED_HEAD = ["", "", "ok ", "wait ", "hmm ", "yo "]
TYPED_TAIL = ["", "", "?", " lol", "??", " idk", "!?"]
SWEAR = ["fucking ", "damn ", ""]


def typo(w, r):
    if len(w) > 3 and r.random() < 0.5:
        i = r.randrange(1, len(w) - 1)
        return w[:i] + w[i + 1] + w[i] + w[i + 2:]
    return w


def voice_style(text, r):
    words = text.rstrip(".?!").split()
    out = []
    for i, w in enumerate(words):
        if r.random() < 0.12:
            out += r.choice(VOICE_FILL).split()
        if r.random() < 0.06 and i < len(words) - 1:         # restart: "I, I want" / "can you, can we"
            out += [w + ","]
        if r.random() < 0.04:
            out += [w + ",", "uh,"]
        out.append(w)
    body = " ".join(out)
    s = r.choice(VOICE_HEAD) + body[0].lower() + body[1:]
    if r.random() < 0.5:
        s += r.choice(VOICE_TAIL)
    return s


def typed_style(text, r):
    s = text.rstrip(".?!")
    if r.random() < 0.7:
        s = s[0].lower() + s[1:]
    s = re.sub(r"[,;:]", "", s) if r.random() < 0.6 else s
    words = [typo(w, r) if r.random() < 0.05 else w for w in s.split()]
    if r.random() < 0.25 and len(words) > 3:
        i = r.randrange(1, len(words) - 1)
        words.insert(i, r.choice(SWEAR).strip() or "like")
    return (r.choice(TYPED_HEAD) + " ".join(words) + r.choice(TYPED_TAIL)).strip()


DISFL_MARKS = [(r"\{[FDE] ([^}]*)\}", r"\1"), (r"<[a-z_]+>", ""), (r"\[|\]|\+", ""), (r"\s--\s", " "), (r"\s+", " ")]


def unmark(t):
    for a, b in DISFL_MARKS:
        t = re.sub(a, b, t)
    return t.strip()


def load_reading_data(n_req, n_speech, seed=0):
    from datasets import load_dataset
    r = random.Random(seed)
    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    reqs = [x["instruction"].strip() for x in dolly if not x["context"] and 15 <= len(x["instruction"]) <= 220]
    r.shuffle(reqs)
    out = []
    for q in reqs[:n_req]:
        messy = voice_style(q, r) if r.random() < 0.5 else typed_style(q, r)
        out.append((f'Message: "{messy}"\nWhat the person wants:', " " + q))
    sp = load_dataset("darrowoflykos/disfluency-sft", split="train")
    pairs = [(unmark(x["target_text"]), x["clean_text"].strip()) for x in sp if x["control"]["level"] in ("moderate", "heavy")]
    pairs = [(a, b) for a, b in pairs if a != b and 20 <= len(b) <= 300]
    r.shuffle(pairs)
    for a, b in pairs[:n_speech]:
        out.append((f'Message: "{a}"\nWhat the person said, cleaned up:', " " + b))
    keal = {m["message"].strip() for m in json.load(open("messages.json"))}
    assert not any(k in p for k in keal for p, _ in out), "a test message leaked into training"
    r.shuffle(out)
    return out


# ---------------------------------------------------------------- training on the mix

def train_mixed(model, plan_data, read_data, steps, micro, lam=0.3):
    slot_params = list(model.slots.parameters())
    for p in slot_params:
        p.requires_grad_(True)
    lora = [p for m in model.modules() if isinstance(m, ft.LoRALinear) for p in (m.A, m.B)]
    opt = torch.optim.AdamW([{"params": lora, "lr": 2e-4}, {"params": slot_params, "lr": 1e-3}], weight_decay=0.0, betas=(0.9, 0.95))
    base = [g["lr"] for g in opt.param_groups]
    print(f"training {sum(p.numel() for p in lora)/1e6:.1f}M LoRA + {sum(p.numel() for p in slot_params)/1e6:.2f}M slot params, "
          f"{steps} steps × {micro}", flush=True)
    r, logs, t0 = random.Random(1), [], time.time()
    model.train(); ft.slots_mode(model, False)
    for step in range(steps):
        f = min(1, (step + 1) / 50) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g, b in zip(opt.param_groups, base):
            g["lr"] = b * f
        items = [r.choice(plan_data) if r.random() < 0.4 else r.choice(read_data) for _ in range(micro)]
        x, am, y, pick, nxt = ft.collate(items)
        loss = F.cross_entropy(ft.hidden_and_logits(model, x, am, pick), y[pick])
        sl = ft.slot_loss(model, nxt) if nxt else torch.zeros((), device=x.device)
        total = loss + lam * sl
        if not torch.isfinite(total):
            raise RuntimeError(f"non-finite loss at step {step}")
        total.backward()
        nn.utils.clip_grad_norm_(lora + slot_params, 1.0)
        opt.step(); opt.zero_grad(set_to_none=True)
        logs.append((loss.item(), sl.item()))
        if (step + 1) % max(1, steps // 15) == 0:
            a = logs[-max(1, steps // 15):]
            print(f"    step {step+1}/{steps}  loss {st.mean(v[0] for v in a):.3f}  next-sentence {st.mean(v[1] for v in a):.3f}"
                  f"  ({time.time()-t0:.0f}s)", flush=True)
    model.eval()
    return logs


@torch.no_grad()
def readings(model, msgs, max_new=40):
    """The model's own one-line reading of each message (greedy)."""
    out = []
    ft.slots_mode(model, False)
    for m in msgs:
        prompt = (m["context"] + "\n" if m["context"] else "") + f'Message: "{m["message"]}"\nWhat the person wants:'
        ids = ft.TOK(prompt, add_special_tokens=False)["input_ids"]
        x = torch.tensor([ids], device=ft.DEV)
        for _ in range(max_new):
            with ft.amp():
                t = int(model(input_ids=x).logits[0, -1].argmax())
            if t in (ft.TOK.eos_token_id, ft.TOK.pad_token_id):
                break
            x = torch.cat([x, torch.tensor([[t]], device=ft.DEV)], 1)
            if "\n" in ft.TOK.decode([t]):
                break
        out.append({"id": m["id"], "kind": m["kind"], "message": m["message"][:160], "meant": m["meant"],
                    "reading": ft.TOK.decode(x[0, len(ids):].tolist()).strip()})
    return out


def main():
    t0 = time.time()
    torch.manual_seed(0); random.seed(0)
    print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none", "| bf16:", BF16, flush=True)
    model = ft.load(MODEL); model.eval()
    msgs = json.load(open("messages.json"))
    if PILOT:
        msgs = msgs[:4] + msgs[-4:]
    ft.load_english(10 if PILOT else 300, 4 if PILOT else 40)
    res = {"model": MODEL, "pilot": PILOT, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    res["before"] = {"messages": ft.message_test(model, msgs), "english": ft.english_test(model)}
    print("before:", res["before"], flush=True)
    ft.attach_slots(model)
    ft.attach_lora(model)
    plan_data = ft.make_examples(200 if PILOT else 6000, 0)
    plan_data = [d for d in plan_data if len(d[0]) <= 600]
    read_pairs = load_reading_data(150 if PILOT else 8000, 100 if PILOT else 4000)
    read_data = [ft.tokenize_segments([(p, False), (t, True)]) for p, t in read_pairs]
    read_data = [d for d in read_data if len(d[0]) <= 400]
    res["train_examples"] = {"planning": len(plan_data), "reading": len(read_data)}
    res["read_samples"] = [{"prompt": p, "target": t} for p, t in read_pairs[:6]]
    logs = train_mixed(model, plan_data, read_data, STEPS, MICRO)
    res["final_loss"] = st.mean(v[0] for v in logs[-max(1, len(logs) // 10):])
    res["train_s"] = round(time.time() - t0)
    res["after"] = {"messages": ft.message_test(model, msgs), "english": ft.english_test(model)}
    print("after:", res["after"], flush=True)
    res["plans"], res["plan_sample"] = ft.evaluate_plans(model, N_PLAN, few_shot=False)
    rd = readings(model, msgs)
    res["total_s"] = round(time.time() - t0)
    json.dump(res, open(f"{OUT}/results.json", "w"), indent=1)
    json.dump(rd, open(f"{OUT}/readings.json", "w"), indent=1, ensure_ascii=False)
    write_report(res, rd)


def write_report(res, rd):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    b, a = res["before"], res["after"]
    L = ["# Follow-up: LoRA + slots learns to read Keal", "",
         f"{res['model']} on {res['gpu']}, {res['total_s']/60:.0f} min total. Trained on {res['train_examples']['planning']} planning "
         f"and {res['train_examples']['reading']} reading examples; none of Keal's messages were in training.", "",
         f"## Keal's real messages ({a['messages']['n']}; pick what he meant out of four; chance 25%)", "",
         "| | typed | voice | all |", "|---|---|---|---|",
         f"| before (untouched) | {pct(b['messages']['typed'])} | {pct(b['messages']['voice'])} | {pct(b['messages']['all'])} |",
         f"| after | {pct(a['messages']['typed'])} | {pct(a['messages']['voice'])} | {pct(a['messages']['all'])} |", "",
         "## English kept", "", "| | ARC-Easy | WikiText-2 perplexity |", "|---|---|---|"]
    for k, d in (("before", b["english"]), ("after", a["english"])):
        L.append(f"| {k} | {pct(d.get('arc_easy'))} | {d['wiki_ppl']:.1f} |" if "wiki_ppl" in d else f"| {k} | {pct(d.get('arc_easy'))} | – |")
    P = res["plans"]
    L += ["", "## Planning still works?", "",
          "| clean short | clean long | messy short | messy long | filler short | filler long |", "|---|---|---|---|---|---|",
          "| " + " | ".join(pct(P[f"{k}/{s}"]["success"]) for k in ("clean", "messy", "filler") for s in ("short", "long")) + " |",
          "", "## Its own reading of each message", ""]
    for x in rd:
        L += [f"- **[{x['kind']}]** {x['message']}{'…' if len(x['message']) == 160 else ''}",
              f"  - meant: {x['meant']}", f"  - read: {x['reading']}"]
    L += ["", "## Training examples (first few)", ""] + [f"- `{s['prompt']!r}` → `{s['target']!r}`" for s in res["read_samples"]]
    open(f"{OUT}/RESULTS.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
