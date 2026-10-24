"""Follow-up 2: fix what follow-up 1 got wrong, and find out where the forgetting comes from.

Follow-up 1 (Qwen3-0.6B, LoRA + slots) read Keal at 40% but lost a lot of English and its readings looped.
Three things were wrong with it:
  - the reading targets had no end-of-answer token, so the model never learned to stop (the loops)
  - the message test scored each option's wording on its own, so it partly measured which option sounds most
    fluent; here the model also sees all four options at once, as A/B/C/D, and we keep its confidence
  - nothing protected English: rank-16 LoRA on every linear layer, trained to zero loss on narrow data

Each arm is one job (run them in parallel):
  lora          follow-up 1 without the slots, plus the end-of-answer fix: where does the forgetting come from?
  gentle        rank-8 LoRA on attention only, 25% replay of the model's own answers to everyday requests,
                lower learning rate, early stopping on held-out loss
  gentle-slots  gentle plus the self-taught slots

Every patched model is scored with the patch on and switched off. Off should give back the untouched model
exactly, so the harness can turn the patch on only for the tasks it was trained for.

  python followup2.py --arm gentle [--pilot] [--model NAME]     writes out/ (results.json, readings.json, RESULTS.md)
"""
import copy, json, math, os, random, re, statistics as st, sys, time

import torch
import torch.nn as nn
import torch.nn.functional as F

import ft                                   # world, checker, slots, LoRA, scoring
import followup as f1                       # Keal-style roughing up and the reading data; also switches on bf16

PILOT = "--pilot" in sys.argv
ARM = ft.arg("--arm", "gentle")
MODEL = ft.arg("--model", "Qwen/Qwen3-0.6B")
ARMS = {
    "lora":         dict(rank=16, where="all",  slots=False, replay=0.0,  lr=2e-4, early=False),
    "gentle":       dict(rank=8,  where="attn", slots=False, replay=0.25, lr=1e-4, early=True),
    "gentle-slots": dict(rank=8,  where="attn", slots=True,  replay=0.25, lr=1e-4, early=True),
}
CFG = ARMS[ARM]
STEPS, MICRO = (20, 4) if PILOT else (1500, 8)  # the same budget as follow-up 1
N_PLAN = 2 if PILOT else 24
N_REPLAY = 32 if PILOT else 1200
OUT = "out"
os.makedirs(OUT, exist_ok=True)
ATTN = {"q_proj", "k_proj", "v_proj", "o_proj"}

# ---------------------------------------------------------------- a patch that can be switched off

_lora_forward, _slots_forward = ft.LoRALinear.forward, ft.Slots.forward
ft.LoRALinear.forward = lambda self, x: self.base(x) if getattr(self, "off", False) else _lora_forward(self, x)
ft.Slots.forward = lambda self, h: h if getattr(self, "off", False) else _slots_forward(self, h)


def patch(model, on):
    for m in model.modules():
        if isinstance(m, (ft.LoRALinear, ft.Slots)):
            m.off = not on


def attach_lora(model, r, where):
    targets = [(parent, cname, child) for layer in model.get_decoder().layers for parent in layer.modules()
               for cname, child in parent.named_children()
               if isinstance(child, nn.Linear) and (where == "all" or cname in ATTN)]
    for parent, cname, child in targets:
        setattr(parent, cname, ft.LoRALinear(child, r, alpha=2 * r))
    for p in model.parameters():
        p.requires_grad_(False)
    lora = [p for m in model.modules() if isinstance(m, ft.LoRALinear) for p in (m.A, m.B)]
    for p in lora:
        p.requires_grad_(True)
    print(f"LoRA rank {r} on {len(targets)} linear layers ({where}): {sum(p.numel() for p in lora)/1e6:.1f}M params", flush=True)
    return lora


# ---------------------------------------------------------------- training data

def with_eos(item):
    ids, mask = item
    return ids + [ft.TOK.eos_token_id], mask + [True]


@torch.no_grad()
def make_replay(model, n, max_new=96, bs=32):
    """The untouched model's own answers to everyday requests: training on them keeps it close to itself."""
    from datasets import load_dataset
    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    reqs = [x["instruction"].strip() for x in dolly if not x["context"] and 15 <= len(x["instruction"]) <= 220]
    random.Random(7).shuffle(reqs)
    tok, eos, pad = ft.TOK, ft.TOK.eos_token_id, ft.TOK.pad_token_id
    texts = [tok.apply_chat_template([{"role": "user", "content": q}], tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False) for q in reqs[:n]]
    out, side = [], tok.padding_side
    tok.padding_side = "left"
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True, add_special_tokens=False).to(ft.DEV)
        with ft.amp():
            g = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=pad)
        for j, t in enumerate(texts[i:i + bs]):
            ans = g[j, enc["input_ids"].shape[1]:].tolist()
            ans = ans[:ans.index(eos) + 1] if eos in ans else [a for a in ans if a != pad]
            p_ids = tok(t, add_special_tokens=False)["input_ids"]
            out.append((p_ids + ans, [False] * len(p_ids) + [True] * len(ans)))
    tok.padding_side = side
    print(f"replay: {len(out)} answers from the untouched model", flush=True)
    return out


# ---------------------------------------------------------------- training

@torch.no_grad()
def val_loss(model, val):
    tot = []
    for i in range(0, len(val), 8):
        x, am, y, pick, _ = ft.collate(val[i:i + 8])
        tot.append(F.cross_entropy(ft.hidden_and_logits(model, x, am, pick), y[pick]).item())
    return st.mean(tot)


def train(model, data, mix, lora, slot_params, val, steps, micro, lam=0.3):
    groups = [{"params": lora, "lr": CFG["lr"]}] + ([{"params": slot_params, "lr": 1e-3}] if slot_params else [])
    opt = torch.optim.AdamW(groups, weight_decay=0.0, betas=(0.9, 0.95))
    base = [g["lr"] for g in opt.param_groups]
    trainable = lora + slot_params
    names, weights = zip(*[(k, w) for k, w in mix.items() if w > 0])
    print(f"training {sum(p.numel() for p in trainable)/1e6:.1f}M params, {steps} steps × {micro}, mix {dict(mix)}", flush=True)
    r, logs, t0 = random.Random(1), [], time.time()
    every = max(1, steps // 10)
    best, best_state, bad, history = math.inf, None, 0, []
    model.train(); ft.slots_mode(model, False)
    for step in range(steps):
        f = min(1, (step + 1) / 50) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g, b in zip(opt.param_groups, base):
            g["lr"] = b * f
        items = [r.choice(data[r.choices(names, weights)[0]]) for _ in range(micro)]
        x, am, y, pick, nxt = ft.collate(items)
        loss = F.cross_entropy(ft.hidden_and_logits(model, x, am, pick), y[pick])
        sl = ft.slot_loss(model, nxt) if slot_params and nxt else torch.zeros((), device=x.device)
        total = loss + lam * sl
        if not torch.isfinite(total):
            raise RuntimeError(f"non-finite loss at step {step}")
        total.backward()
        nn.utils.clip_grad_norm_(trainable, 1.0)
        opt.step(); opt.zero_grad(set_to_none=True)
        logs.append((loss.item(), sl.item()))
        if (step + 1) % every == 0:
            model.eval()
            v = val_loss(model, val)
            model.train()
            a = logs[-every:]
            history.append({"step": step + 1, "train": st.mean(x[0] for x in a), "val": v})
            print(f"    step {step+1}/{steps}  loss {history[-1]['train']:.3f}  val {v:.3f}  next-sentence "
                  f"{st.mean(x[1] for x in a):.3f}  ({time.time()-t0:.0f}s)", flush=True)
            if v < best - 1e-3:
                best, bad = v, 0
                best_state = [p.detach().clone() for p in trainable]
            else:
                bad += 1
                if CFG["early"] and bad >= 2:
                    print(f"    early stop at step {step+1}: held-out loss stopped improving", flush=True)
                    break
    if CFG["early"] and best_state is not None:
        with torch.no_grad():
            for p, b in zip(trainable, best_state):
                p.copy_(b)
    model.eval()
    return logs, history


# ---------------------------------------------------------------- tests

@torch.no_grad()
def mc_test(model, msgs, sure=0.5):
    """All four options shown as A/B/C/D, chat-formatted; each order rotation once, so letter bias cancels.
    Confidence is the averaged probability of the chosen option."""
    tok = ft.TOK
    letters = [tok(L, add_special_tokens=False)["input_ids"] for L in "ABCD"]
    assert all(len(l) == 1 for l in letters), letters
    letters = [l[0] for l in letters]
    ft.slots_mode(model, False)
    rows = []
    for m in msgs:
        opts = [m["meant"]] + m["wrong"]
        order = list(range(4)); random.Random(m["id"]).shuffle(order)
        prob = [0.0] * 4
        for rot in range(4):
            o = order[rot:] + order[:rot]
            ctx = f"Context: {m['context']}\n\n" if m["context"] else ""
            body = (f'{ctx}Someone sent this message: "{m["message"]}"\n\nWhat did they mean?\n'
                    + "\n".join(f"{L}. {opts[i]}" for L, i in zip("ABCD", o)) + "\n\nAnswer with just the letter.")
            text = tok.apply_chat_template([{"role": "user", "content": body}], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
            x = torch.tensor([tok(text, add_special_tokens=False)["input_ids"]], device=ft.DEV)
            with ft.amp():
                lg = model(input_ids=x).logits[0, -1].float()
            p = torch.softmax(lg[letters], -1).tolist()
            for k, i in enumerate(o):
                prob[i] += p[k] / 4
        pick = max(range(4), key=lambda i: prob[i])
        rows.append({"id": m["id"], "kind": m["kind"], "ok": pick == 0, "conf": prob[pick]})

    def summary(rs):
        s = [x for x in rs if x["conf"] >= sure]
        u = [x for x in rs if x["conf"] < sure]
        return {"acc": st.mean(x["ok"] for x in rs), "n": len(rs), "sure_share": len(s) / len(rs),
                "acc_sure": st.mean(x["ok"] for x in s) if s else None,
                "acc_unsure": st.mean(x["ok"] for x in u) if u else None, "mean_conf": st.mean(x["conf"] for x in rs)}
    return {"all": summary(rows), **{k: summary([x for x in rows if x["kind"] == k]) for k in ("typed", "voice")}}, rows


def loops(text):
    w = text.split()
    grams = [" ".join(w[i:i + 3]) for i in range(len(w) - 2)]
    return any(grams.count(g) >= 3 for g in set(grams))


@torch.no_grad()
def readings(model, msgs, max_new=60):
    out = []
    ft.slots_mode(model, False)
    stop = {ft.TOK.eos_token_id, ft.TOK.pad_token_id}
    for m in msgs:
        prompt = (m["context"] + "\n" if m["context"] else "") + f'Message: "{m["message"]}"\nWhat the person wants:'
        ids = ft.TOK(prompt, add_special_tokens=False)["input_ids"]
        x, stopped = torch.tensor([ids], device=ft.DEV), False
        for _ in range(max_new):
            with ft.amp():
                t = int(model(input_ids=x).logits[0, -1].argmax())
            if t in stop:
                stopped = True
                break
            x = torch.cat([x, torch.tensor([[t]], device=ft.DEV)], 1)
        text = ft.TOK.decode(x[0, len(ids):].tolist()).strip()
        out.append({"id": m["id"], "kind": m["kind"], "message": m["message"][:160], "meant": m["meant"],
                    "reading": text, "stopped": stopped, "loops": loops(text)})
    return out


def scores(model, msgs):
    return {"old_test": ft.message_test(model, msgs), "mc": mc_test(model, msgs)[0], "english": ft.english_test(model)}


# ---------------------------------------------------------------- run

def main():
    t0 = time.time()
    torch.manual_seed(0); random.seed(0)
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    print(f"arm {ARM} {CFG} | GPU: {gpu} | bf16: {f1.BF16}", flush=True)
    model = ft.load(MODEL); model.eval()
    msgs = json.load(open("messages.json"))
    if PILOT:
        msgs = msgs[:4] + msgs[-4:]
    ft.load_english(10 if PILOT else 300, 4 if PILOT else 40)
    res = {"model": MODEL, "arm": ARM, "cfg": CFG, "pilot": PILOT, "gpu": gpu}
    res["before"] = scores(model, msgs)
    print("before:", res["before"], flush=True)

    rng = random.Random(0)
    plan = [d for d in ft.make_examples(200 if PILOT else 6000, 0) if len(d[0]) <= 600]
    read_pairs = f1.load_reading_data(150 if PILOT else 8000, 100 if PILOT else 4000)
    read = [with_eos(ft.tokenize_segments([(p, False), (t, True)])) for p, t in read_pairs]
    read = [d for d in read if len(d[0]) <= 400]
    replay = [d for d in make_replay(model, N_REPLAY) if len(d[0]) <= 400] if CFG["replay"] else []
    rng.shuffle(plan); rng.shuffle(read); rng.shuffle(replay)
    nv = 8 if PILOT else 100
    val = plan[:nv] + read[:2 * nv]
    data = {"plan": plan[nv:], "read": read[2 * nv:], "replay": replay}
    mix = {"plan": 0.4 * (1 - CFG["replay"]), "read": 0.6 * (1 - CFG["replay"]), "replay": CFG["replay"]}
    res["train_examples"] = {k: len(v) for k, v in data.items()} | {"val": len(val)}

    slot_params = []
    if CFG["slots"]:
        ft.attach_slots(model)
        slot_params = list(model.slots.parameters())
    lora = attach_lora(model, CFG["rank"], CFG["where"])     # freezes everything else, slots included
    for p in slot_params:
        p.requires_grad_(True)
    logs, res["val_history"] = train(model, data, mix, lora, slot_params, val, STEPS, MICRO)
    res["steps_run"] = len(logs)
    res["final_loss"] = st.mean(v[0] for v in logs[-max(1, len(logs) // 10):])
    res["train_s"] = round(time.time() - t0)

    patch(model, False)
    res["patch_off"] = scores(model, msgs)
    print("patch off:", res["patch_off"], flush=True)
    patch(model, True)
    res["patch_on"] = scores(model, msgs)
    print("patch on:", res["patch_on"], flush=True)
    res["mc_rows"] = mc_test(model, msgs)[1]
    res["plans"], res["plan_sample"] = ft.evaluate_plans(model, N_PLAN, few_shot=False)
    rd = readings(model, msgs)
    res["readings"] = {"stopped": st.mean(x["stopped"] for x in rd), "loops": st.mean(x["loops"] for x in rd)}
    res["total_s"] = round(time.time() - t0)
    json.dump(res, open(f"{OUT}/results.json", "w"), indent=1)
    json.dump(rd, open(f"{OUT}/readings.json", "w"), indent=1, ensure_ascii=False)
    write_report(res, rd)


def write_report(res, rd):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    ppl = lambda d: f"{d['wiki_ppl']:.1f}" if "wiki_ppl" in d else "–"
    c = res["cfg"]
    L = [f"# Follow-up 2, arm `{res['arm']}`", "",
         f"{res['model']} on {res['gpu']}, {res['total_s']/60:.0f} min total. LoRA rank {c['rank']} on {c['where']} linear layers, "
         f"slots {'on' if c['slots'] else 'off'}, replay {c['replay']*100:.0f}%, learning rate {c['lr']}, early stopping "
         f"{'on' if c['early'] else 'off'}. Ran {res['steps_run']} of {STEPS} steps. Training examples: {res['train_examples']}. "
         "None of Keal's messages were in training.", "",
         "## Keal's real messages, four options (chance 25%)", "",
         "New test: all four shown as A/B/C/D, so it's a real choice. \"Sure\" means it gave its pick at least 50%.", "",
         "| | old test (all) | A/B/C/D typed | A/B/C/D voice | A/B/C/D all | share sure | right when sure | right when unsure |",
         "|---|---|---|---|---|---|---|---|"]
    for name, k in (("before (untouched)", "before"), ("patch off", "patch_off"), ("patch on", "patch_on")):
        s = res[k]
        L.append(f"| {name} | {pct(s['old_test']['all'])} | {pct(s['mc']['typed']['acc'])} | {pct(s['mc']['voice']['acc'])} | "
                 f"{pct(s['mc']['all']['acc'])} | {pct(s['mc']['all']['sure_share'])} | {pct(s['mc']['all']['acc_sure'])} | "
                 f"{pct(s['mc']['all']['acc_unsure'])} |")
    L += ["", "## English kept", "", "| | ARC-Easy | WikiText-2 perplexity |", "|---|---|---|"]
    for name, k in (("before (untouched)", "before"), ("patch off", "patch_off"), ("patch on", "patch_on")):
        L.append(f"| {name} | {pct(res[k]['english'].get('arc_easy'))} | {ppl(res[k]['english'])} |")
    P = res["plans"]
    L += ["", "## Planning, patch on", "",
          "| clean short | clean long | messy short | messy long | filler short | filler long |", "|---|---|---|---|---|---|",
          "| " + " | ".join(pct(P[f"{k}/{s}"]["success"]) for k in ("clean", "messy", "filler") for s in ("short", "long")) + " |",
          "", "## Training", ""]
    L += [f"- step {h['step']}: train {h['train']:.3f}, held-out {h['val']:.3f}" for h in res["val_history"]]
    L += ["", f"## Its own reading of each message (stopped on its own {pct(res['readings']['stopped'])}, "
          f"repeats itself {pct(res['readings']['loops'])})", ""]
    for x in rd:
        L += [f"- **[{x['kind']}]** {x['message']}{'…' if len(x['message']) == 160 else ''}",
              f"  - meant: {x['meant']}", f"  - read: {x['reading']}"]
    open(f"{OUT}/RESULTS.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
