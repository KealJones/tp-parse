"""Ask first: teach a small model to find out what someone actually needs before answering.

Qwen3-0.6B, frozen, with a switchable rank-16 LoRA patch on every linear layer (the setup that learned planning
perfectly in follow-up 2). Trained on scenarios.py: vague requests with a hidden brief, a simulated person who only
answers what's asked, and gold trajectories in Keal's pattern (open broad, pull on the odd detail, look up what
you don't know, check against your notes, then answer). A fifth of the training needs no questions at all, so it
learns when not to ask.

Scored, untouched (with two worked examples) vs patched, in the same harness:
  - success: the answer meets the real need with no contradictions (meat in a vegetarian meal, the wrong state,
    over budget, an oven when there isn't one)
  - found the real need, asked at all, asked when it didn't need to, checked before answering
  - families: gift, dinner, code (trained), given (shouldn't ask), trip (never trained on)
  - Keal's three recorded tasks, in the harness and as plain chat, transcripts saved for comparing with what he did
  - English kept (WikiText-2 perplexity), patch on and off

  python askfirst.py [--pilot]          writes out/ (RESULTS.md, results.json, transcripts.json)
"""
import json, math, os, random, re, statistics as st, sys, time

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

from scenarios import *  # noqa: F401,F403

PILOT = "--pilot" in sys.argv
MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "Qwen/Qwen3-0.6B"
DEV = "cuda" if torch.cuda.is_available() else "cpu"
BF16 = DEV == "cuda" and torch.cuda.is_bf16_supported()
N_TRAIN = 64 if PILOT else 6000
EPOCHS = 1 if PILOT else 2
BATCH, MICRO, MAXLEN = 8, 2, 1024
N_TEST = 2 if PILOT else 30
OUT = "out"
os.makedirs(OUT, exist_ok=True)
T0 = time.time()
MIX = {"gift": 0.35, "dinner": 0.25, "code": 0.15, "gift-given": 0.125, "dinner-given": 0.125}


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


def amp():
    return torch.autocast(device_type="cuda", dtype=torch.bfloat16 if BF16 else torch.float16, enabled=DEV == "cuda")


tok = AutoTokenizer.from_pretrained(MODEL)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
END = tok.eos_token


def prompt_text(request, shots=(), system=True):
    msgs = [{"role": "system", "content": SYSTEM}] if system else []
    for q, a in shots:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": request})
    try:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


# ---------------------------------------------------------------- a LoRA patch that can be switched off

class LoRALinear(nn.Module):
    def __init__(self, base, r=16, alpha=32):
        super().__init__()
        self.base, self.scale, self.off = base, alpha / r, False
        self.A = nn.Parameter(torch.randn(r, base.in_features, device=base.weight.device) / math.sqrt(base.in_features))
        self.B = nn.Parameter(torch.zeros(base.out_features, r, device=base.weight.device))

    def forward(self, x):
        y = self.base(x)
        return y if self.off else y + (x @ self.A.T.to(x.dtype)) @ (self.B.T.to(x.dtype) * self.scale)


def attach_lora(model, r=16):
    targets = [(p, n, c) for layer in model.model.layers for p in layer.modules() for n, c in p.named_children() if isinstance(c, nn.Linear)]
    for p, n, c in targets:
        setattr(p, n, LoRALinear(c, r, 2 * r))
    for q in model.parameters():
        q.requires_grad_(False)
    params = [q for m in model.modules() if isinstance(m, LoRALinear) for q in (m.A, m.B)]
    for q in params:
        q.requires_grad_(True)
    log(f"LoRA rank {r} on {len(targets)} linear layers: {sum(q.numel() for q in params)/1e6:.1f}M params")
    return params


def patch(model, on):
    for m in model.modules():
        if isinstance(m, LoRALinear):
            m.off = not on


# ---------------------------------------------------------------- data

def encode(sc):
    p = prompt_text(sc["request"])
    pieces, _, _ = render_gold(sc)
    text, mask = p, [0] * len(p)
    for piece, trained in pieces:
        text += piece; mask += [int(trained)] * len(piece)
    text += END; mask += [1] * len(END)
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=True, max_length=MAXLEN)
    lab = [i if mask[min(e, len(mask)) - 1] else -100 for i, (s, e) in zip(enc["input_ids"], enc["offset_mapping"])]
    return enc["input_ids"], lab


def make(seed, n, fams):
    r = random.Random(seed)
    names, w = zip(*fams.items())
    return [TRAIN_FAMILIES[r.choices(names, w)[0]](r) for _ in range(n)]


def collate(batch):
    L = max(len(i) for i, _ in batch)
    ids = torch.full((len(batch), L), tok.pad_token_id); lab = torch.full((len(batch), L), -100)
    att = torch.zeros((len(batch), L), dtype=torch.long)
    for b, (i, l) in enumerate(batch):
        ids[b, :len(i)] = torch.tensor(i); lab[b, :len(l)] = torch.tensor(l); att[b, :len(i)] = 1
    return ids.to(DEV), lab.to(DEV), att.to(DEV)


def train(model, params, data):
    opt = torch.optim.AdamW(params, lr=2e-4, weight_decay=0.0, betas=(0.9, 0.95))
    total = EPOCHS * math.ceil(len(data) / BATCH)
    step, t = 0, time.time()
    model.train()
    for ep in range(EPOCHS):
        d = data[:]; random.Random(ep).shuffle(d)
        for i in range(0, len(d), BATCH):
            for g in opt.param_groups:
                g["lr"] = 2e-4 * min(1, (step + 1) / 50) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / total)))
            opt.zero_grad(set_to_none=True)
            for j in range(i, min(i + BATCH, len(d)), MICRO):       # micro-batches: a full batch of 8 runs out of memory
                ids, lab, att = collate(d[j:j + MICRO])
                with amp():
                    h = model.model(input_ids=ids, attention_mask=att).last_hidden_state
                    sel = lab[:, 1:] != -100
                    logits = model.lm_head(h[:, :-1][sel])
                loss = F.cross_entropy(logits.float(), lab[:, 1:][sel])
                (loss * len(ids) / len(d[i:i + BATCH])).backward()
                del h, logits
            nn.utils.clip_grad_norm_(params, 1.0); opt.step()
            step += 1
            if step % max(1, total // 15) == 0 or step == total:
                log(f"  step {step}/{total} loss {loss.item():.3f} ({(time.time() - t) / step:.2f} s/step)")
    model.eval()


# ---------------------------------------------------------------- running a model in the harness (batched)

CLOSE = re.compile(r"</(think|ask|search|fact|check|answer)>")


@torch.no_grad()
def rollout(model, scs, shots=(), max_steps=16, new_tokens=260):
    S_ = [dict(sc=sc, H=Harness(sc), text="", ans=None, done=False, prompt=prompt_text(sc["request"], shots)) for sc in scs]
    side = tok.padding_side
    tok.padding_side = "left"
    for _ in range(max_steps):
        live = [s for s in S_ if not s["done"]]
        if not live:
            break
        for i in range(0, len(live), 32):
            chunk = live[i:i + 32]
            enc = tok([s["prompt"] + s["text"] for s in chunk], return_tensors="pt", padding=True, add_special_tokens=False).to(DEV)
            with amp():
                out = model.generate(**enc, max_new_tokens=new_tokens, do_sample=False, pad_token_id=tok.pad_token_id,
                                     stop_strings=STOPS, tokenizer=tok)
            for s, seq in zip(chunk, out[:, enc["input_ids"].shape[1]:]):
                gen = tok.decode(seq, skip_special_tokens=True)
                c = CLOSE.search(gen)
                if not c:                    # no closed tag: an unclosed <answer>, or plain untagged text, counts as the answer
                    s["text"] += gen
                    s["ans"] = gen.split("<answer>", 1)[1].strip() if "<answer>" in gen else (gen.strip() if gen.strip() else None)
                    s["done"] = True
                    continue
                piece = gen[:c.end()]
                s["text"] += piece
                a = list(ACTION_RE.finditer(piece))
                if not a:
                    s["done"] = True
                    continue
                tag, at, body = a[-1].group(1), attrs_of(a[-1].group(2)), a[-1].group(3).strip()
                if tag == "answer":
                    s["ans"], s["done"] = body, True
                    continue
                obs = s["H"].act(tag, at, body)
                s["text"] += "\n" + (obs + "\n" if obs else "")
    tok.padding_side = side
    return S_


def evaluate(model, name, shots=()):
    res, transcripts = {}, {}
    r = random.Random(123)
    tests = {k: [f(r) for _ in range(N_TEST)] for k, f in TEST_FAMILIES.items()}
    tests |= {k: [f(random.Random(5))] for k, f in KEAL.items()}
    for fam, scs in tests.items():
        S_ = rollout(model, scs, shots)
        rows = [score(s["sc"], s["ans"], s["H"]) for s in S_]
        res[fam] = rows
        transcripts[fam] = [{"request": s["sc"]["request"], "text": s["text"], "ok": rw["ok"], "parts": rw["parts"]} for s, rw in zip(S_[:3], rows)]
        log(f"  {name:10} {fam:20} success {st.mean(x['ok'] for x in rows)*100:5.1f}%  asked {st.mean(x['asked'] > 0 for x in rows)*100:5.1f}%")
    return res, transcripts


@torch.no_grad()
def plain_chat(model, request, n=500):
    t = prompt_text(request, system=False)
    enc = tok(t, return_tensors="pt", add_special_tokens=False).to(DEV)
    with amp():
        g = model.generate(**enc, max_new_tokens=n, do_sample=False, pad_token_id=tok.pad_token_id)
    return tok.decode(g[0, enc["input_ids"].shape[1]:], skip_special_tokens=True).strip()


@torch.no_grad()
def wiki_ppl(model, n=4 if PILOT else 40):
    try:
        from datasets import load_dataset
        d = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")
    except Exception as e:
        log("WikiText unavailable:", e)
        return None
    ids = tok("\n".join(t for t in d["text"] if len(t) > 200), add_special_tokens=False)["input_ids"]
    nll = []
    for i in range(n):
        x = torch.tensor([ids[i * 256:(i + 1) * 256]], device=DEV)
        with amp():
            lg = model(input_ids=x).logits.float()
        nll.append(F.cross_entropy(lg[0, :-1], x[0, 1:]).item())
    return math.exp(st.mean(nll))


# ---------------------------------------------------------------- run

def summary(res):
    out = {}
    for fam, rows in res.items():
        out[fam] = dict(n=len(rows), success=st.mean(x["ok"] for x in rows), asked=st.mean(x["asked"] > 0 for x in rows),
                        found_need=st.mean(x["deep"] for x in rows), checked=st.mean(x["checked"] for x in rows),
                        no_answer=st.mean(x["no_answer"] for x in rows), questions=st.mean(x["asked"] for x in rows),
                        parts={k: round(st.mean(x["parts"][k] for x in rows if k in x["parts"]), 2) for k in dict.fromkeys(k for x in rows for k in x["parts"])})
    return out


def main():
    log("GPU:", torch.cuda.get_device_name(0) if DEV == "cuda" else "none", "| bf16:", BF16)
    model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).to(DEV).eval()
    R = {"model": MODEL, "pilot": PILOT}
    train_sc = make(1, N_TRAIN, MIX)
    data = [encode(sc) for sc in train_sc]
    lens = [len(i) for i, _ in data]
    log(f"{len(data)} training episodes, mean {st.mean(lens):.0f} tokens, max {max(lens)}")
    r = random.Random(9)                        # two worked examples for the untouched model: one asks, one doesn't
    shots = []
    for sc in (code(r), dinner(r, given=True)):
        shots.append((sc["request"], "".join(p for p, _ in render_gold(sc)[0])))

    log("untouched, two worked examples")
    res_base, tr_base = evaluate(model, "untouched", shots)
    R["untouched"] = summary(res_base)
    R["ppl_before"] = wiki_ppl(model)
    keal_plain = {k: {"untouched": plain_chat(model, KEAL[k](random.Random(5))["request"])} for k in KEAL}

    params = attach_lora(model)
    train(model, params, data)
    patch(model, True)
    log("patched")
    res_p, tr_p = evaluate(model, "patched")
    R["patched"] = summary(res_p)
    R["ppl_patch_on"] = wiki_ppl(model)
    for k in KEAL:
        keal_plain[k]["patched"] = plain_chat(model, KEAL[k](random.Random(5))["request"])
    patch(model, False)
    R["ppl_patch_off"] = wiki_ppl(model)
    R["minutes"] = round((time.time() - T0) / 60, 1)
    json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
    json.dump({"untouched": tr_base, "patched": tr_p, "keal_plain_chat": keal_plain}, open(f"{OUT}/transcripts.json", "w"), indent=1, ensure_ascii=False)
    report(R, tr_base, tr_p, keal_plain)


def report(R, tr_base, tr_p, keal_plain):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    L = ["# Ask first: results", "", f"{R['model']}, {N_TRAIN} training episodes, {R['minutes']} min. Untouched gets two worked examples; "
         "patched gets none. Same harness, same simulated person.", "",
         "| family | untouched success | patched success | untouched asked | patched asked | untouched found need | patched found need | patched checked |",
         "|---|---|---|---|---|---|---|---|"]
    for fam in R["patched"]:
        b, p = R["untouched"][fam], R["patched"][fam]
        L.append(f"| {fam} (n={p['n']}) | {pct(b['success'])} | {pct(p['success'])} | {pct(b['asked'])} | {pct(p['asked'])} | "
                 f"{pct(b['found_need'])} | {pct(p['found_need'])} | {pct(p['checked'])} |")
    L += ["", "\"given\" has everything in the message, so asking there is a mistake. \"found need\" = the person revealed the hidden reason, "
          "restriction or error.", "", "## What made answers fail (share of episodes passing each part)", ""]
    for fam in R["patched"]:
        L.append(f"- {fam}: untouched {R['untouched'][fam]['parts']} | patched {R['patched'][fam]['parts']}")
    L += ["", "## English kept (WikiText-2 perplexity, lower is better)", "",
          f"untouched {R['ppl_before']}, patch on {R['ppl_patch_on']}, patch off {R['ppl_patch_off']}", "",
          "## Keal's three tasks in the harness", ""]
    for k in KEAL:
        for name, tr in (("untouched", tr_base), ("patched", tr_p)):
            t = tr[k][0]
            L += [f"### {k}, {name} ({'pass' if t['ok'] else 'fail'}: {t['parts']})", "", "```", t["request"], "", t["text"].strip()[-4000:], "```", ""]
    L += ["## Keal's three tasks as plain chat (no tools, no system prompt)", ""]
    for k, v in keal_plain.items():
        for name in ("untouched", "patched"):
            L += [f"### {k}, {name}", "", "```", v[name][:3000], "```", ""]
    L += ["## Sample episodes", ""]
    for fam in ("gift", "dinner", "trip (unseen)", "given"):
        for name, tr in (("untouched", tr_base), ("patched", tr_p)):
            t = tr[fam][0]
            L += [f"### {fam}, {name} ({'pass' if t['ok'] else 'fail'})", "", "```", t["request"], "", t["text"].strip()[-2500:], "```", ""]
    open(f"{OUT}/RESULTS.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:20]), flush=True)


if __name__ == "__main__":
    main()
