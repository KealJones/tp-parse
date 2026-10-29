"""Tiny Gemma 4, stage 1b: Minitron-style importance, measured directly.

  1. Layer sensitivity: bits per byte with each (non-protected) layer removed on its own. Stage 1 used angular
     distance as a proxy and it picked exactly the layers that hurt most (25–33, the KV-shared ones).
  2. Hidden-channel importance: mean |activation| of every hidden-size norm output, summed over layers.
  3. FFN channel importance: mean |activation| x |down_proj column| (as stage 1).
  4. Physically cut candidates (surgery.cut, incl. hidden-size cuts) and measure them before healing,
     with chat samples.

Squiggle text is scored on Gemma's replies only, from whole held-out episodes (stage 1 scored prompts too,
and the heal probe trained on near-identical prompts).

    python analyze.py OUT_DIR      needs kept_ids.json, tokenizer_pruned.json, teacher_results.jsonl.gz
"""
import gzip, json, math, os, random, sys, time
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage1  # noqa: E402
from surgery import cut  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
DEV, DTYPE = stage1.DEV, stage1.DTYPE
T0 = time.time()
R = {"layer_sensitivity": {}, "candidates": {}, "notes": []}


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


def save():
    json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1)


def episodes(path, held=20):
    eps = [json.loads(l) for l in gzip.open(path, "rt")]
    random.Random(0).shuffle(eps)
    def outputs(es):
        return [str(c.get("output") or "") for e in es for c in e.get("calls") or [] if len(str(c.get("output") or "")) > 80]
    return outputs(eps[:held]), eps[held:]


@torch.no_grad()
def bpb_model(model, head_w, encode, docs, cap):
    nats = byts = 0
    for d in docs:
        ids = encode(d)
        if len(ids) < 2:
            continue
        x = torch.tensor([ids], device=DEV)
        h = model(input_ids=x).last_hidden_state[0, :-1]
        lg = torch.tanh((h.float() @ head_w.float().T) / cap) * cap
        nats += F.cross_entropy(lg, x[0, 1:], reduction="sum").item()
        byts += len(d.encode("utf-8"))
    return round(nats / math.log(2) / max(1, byts), 4)


@torch.no_grad()
def samples(model, head_w, encode_raw, decode, chat, stop, n=48):
    out = []
    for p in stage1.PROMPTS + ["What is 17 times 23? Think step by step, then answer."]:
        ids = encode_raw(chat(p)); gen = []
        for _ in range(n):
            h = model(input_ids=torch.tensor([ids + gen], device=DEV)).last_hidden_state[0, -1]
            j = int((h.float() @ head_w.float().T).argmax())
            gen.append(j)
            if j in stop:
                break
        out.append({"prompt": p, "reply": decode(gen)})
    return out


def main():
    from transformers import AutoTokenizer
    from tokenizers import Tokenizer
    tok = AutoTokenizer.from_pretrained(stage1.MODEL)
    kept = json.load(open("kept_ids.json"))
    tj = json.load(open("tokenizer_pruned.json"))
    ptok = Tokenizer.from_str(json.dumps(tj))
    bos_s = ptok.token_to_id(tok.bos_token)
    enc_s = lambda s: [bos_s] + ptok.encode(s, add_special_tokens=False).ids        # student ids
    enc_raw_s = lambda s: ptok.encode(s, add_special_tokens=False).ids
    dec_s = lambda ids: ptok.decode(ids, skip_special_tokens=True)
    chat = lambda p: tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True)
    stop_s = {ptok.token_to_id(t) for t in ("<eos>", "<end_of_turn>", "<turn|>") if ptok.token_to_id(t) is not None}

    held_out, _ = episodes(stage1.AGENT_FILE)
    WS, CS = int(os.environ.get("WEB_SKIP", 50000)), int(os.environ.get("CODE_SKIP", 7000))
    web = stage1.stream("HuggingFaceFW/fineweb-edu", "sample-10BT", "text", 360, skip=WS)
    code = stage1.stream("codeparrot/codeparrot-clean-valid", None, "content", 50, skip=CS)
    cut3 = lambda d: d[:3000]
    evals = {"web": [cut3(d) for d in web[:200]], "code": [cut3(d) for d in code[:40]], "agent_replies": [cut3(d) for d in held_out[:80]]}
    small = {"web": evals["web"][:60], "agent_replies": evals["agent_replies"][:40]}
    cal = [cut3(d) for d in web[200:330]]
    R["data"] = {k: len(v) for k, v in evals.items()} | {"calibration": len(cal)}
    log("data", R["data"])

    m, T, head = stage1.load_gemma()
    cap = getattr(T.config, "final_logit_softcapping", None)
    kept_t = torch.tensor(kept, device=DEV)
    t_head = head.weight[kept_t]                         # teacher rows in student order
    t_in = lambda ids: kept_t[torch.tensor(ids, device=DEV)].tolist()
    enc_t = lambda s: t_in(enc_s(s))                     # teacher ids for the same text

    # Teacher with the pruned vocab: the reference (restricted softmax == a model without those rows).
    @torch.no_grad()
    def bpb_teacher(docs):
        nats = byts = 0
        for d in docs:
            ids_s = enc_s(d)
            x = torch.tensor([t_in(ids_s)], device=DEV)
            h = T(input_ids=x).last_hidden_state[0, :-1]
            lg = torch.tanh((h.float() @ t_head.float().T) / cap) * cap
            nats += F.cross_entropy(lg, torch.tensor(ids_s[1:], device=DEV), reduction="sum").item()
            byts += len(d.encode("utf-8"))
        return round(nats / math.log(2) / max(1, byts), 4)

    S = stage1.Surgery(T)
    R["teacher"] = {k: bpb_teacher(v) for k, v in evals.items()}
    R["teacher_small"] = {k: bpb_teacher(v) for k, v in small.items()}
    log("teacher", R["teacher"], R["teacher_small"])
    save()

    # 1. Layer sensitivity, directly.
    prot = S.protected()
    for i in range(T.config.num_hidden_layers):
        if i in prot:
            continue
        S.set({i})
        R["layer_sensitivity"][i] = {k: round(bpb_teacher(v) - R["teacher_small"][k], 4) for k, v in small.items()}
        log("drop layer", i, R["layer_sensitivity"][i])
    S.set()
    save()
    sens = {i: v["web"] + v["agent_replies"] for i, v in R["layer_sensitivity"].items()}
    order = sorted(sens, key=lambda i: sens[i])
    R["layer_order"] = order
    log("least harmful to drop", [(i, round(sens[i], 3)) for i in order[:12]])

    # 2./3. Hidden and FFN channel importance.
    H = T.config.hidden_size
    hid = torch.zeros(H, device=DEV)
    hooks = []
    for l in T.layers:
        for n in ("input_layernorm", "pre_feedforward_layernorm"):
            def acc(mod, a, o):
                hid.add_(o.float().abs().reshape(-1, o.shape[-1]).mean(0))   # must return None (a value would replace the output)
            hooks.append(getattr(l, n).register_forward_hook(acc))
    with torch.no_grad():
        for d in cal:
            T(input_ids=torch.tensor([enc_t(d)], device=DEV))
    for h in hooks:
        h.remove()
    ffn = stage1.channel_scores(T, enc_t, cal)
    R["hidden_importance_top_share"] = round(float(hid.sort(descending=True).values[:1024].sum() / hid.sum()), 4)
    log("hidden importance: top 1024 of", H, "carry", R["hidden_importance_top_share"])

    # 4. Physically cut candidates.
    L = T.config.num_hidden_layers
    def keep_minus(n):
        return [i for i in range(L) if i not in set(order[:n])]
    cands = json.loads(os.environ.get("CANDIDATES", json.dumps([
        {"name": "ffn0.5", "ffn": 0.5},
        {"name": "h1280_ffn0.5", "hidden": 1280, "ffn": 0.5},
        {"name": "h1024_ffn0.5", "hidden": 1024, "ffn": 0.5},
        {"name": "h1024_ffn0.42_drop4", "hidden": 1024, "ffn": 0.42, "drop": 4},
        {"name": "h1024_ffn0.35_drop6", "hidden": 1024, "ffn": 0.35, "drop": 6},
        {"name": "h768_ffn0.42", "hidden": 768, "ffn": 0.42},
    ])))
    for c in cands:
        keep_layers = keep_minus(c.get("drop", 0))
        hk = hid.topk(c["hidden"]).indices.sort().values.tolist() if c.get("hidden") else None
        st = cut(T, keep_layers, c.get("ffn", 1.0), ffn, kept, hk).to(DEV).eval()
        n_body = sum(p.numel() for n, p in st.named_parameters() if not n.startswith(("embed_tokens", "embed_tokens_per_layer")))
        n_all = sum(p.numel() for p in st.parameters())
        r = {"layers": len(keep_layers), "dropped": sorted(set(range(L)) - set(keep_layers)), "hidden": c.get("hidden", H), "ffn": c.get("ffn", 1.0),
             "params_body": n_body, "params_total": n_all}
        sh = st.embed_tokens.weight
        for k, docs in evals.items():
            r[k] = bpb_model(st, sh, enc_s, docs, cap)
        r["samples"] = samples(st, sh, enc_raw_s, dec_s, chat, stop_s)
        R["candidates"][c["name"]] = r
        log(c["name"], {k: v for k, v in r.items() if k not in ("samples", "dropped")})
        save()
        del st
        if DEV == "cuda":
            torch.cuda.empty_cache()
    write_md()
    log("done")


def write_md():
    lines = ["# Tiny Gemma 4, stage 1b: direct importance (no healing)", "",
             f"Teacher (E2B-it, 80K vocab): {R.get('teacher')}", "",
             "## Layer sensitivity (bpb increase when only that layer is removed; small eval set)", "",
             "| layer | web | Gemma replies |", "|---|---|---|"]
    for i, v in sorted(R["layer_sensitivity"].items(), key=lambda x: x[1]["web"] + x[1]["agent_replies"]):
        lines.append(f"| {i} | {v['web']} | {v['agent_replies']} |")
    lines += ["", f"Hidden: top 1024 of 1536 channels carry {R.get('hidden_importance_top_share')} of the activation mass.", "",
              "## Cut candidates (physically cut, before healing)", "",
              "| candidate | layers | hidden | ffn | body | total | web | code | Gemma replies |", "|---|---|---|---|---|---|---|---|---|"]
    for n, r in R["candidates"].items():
        lines.append(f"| {n} | {r['layers']} | {r['hidden']} | {r['ffn']} | {r['params_body'] / 1e6:.0f}M | {r['params_total'] / 1e6:.0f}M | {r.get('web')} | {r.get('code')} | {r.get('agent_replies')} |")
    lines += ["", "## Samples", ""]
    for n, r in R["candidates"].items():
        lines.append(f"### {n}")
        for s in r["samples"]:
            lines.append(f"- **{s['prompt']}** → {s['reply'][:240]!r}")
        lines.append("")
    open(os.path.join(OUT, "RESULTS.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    code = 0
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    finally:
        save()
        try:
            write_md()
        except Exception as e:
            print("write_md failed", e)
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
