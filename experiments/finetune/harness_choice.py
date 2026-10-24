"""Untouched Qwen3-0.6B plans with a harness: the harness keeps the facts and lists the legal next moves; the
model only picks one, as a lettered multiple-choice answer. No training at all.

The harness only uses what the model was told or found by searching (never the hidden world). Each step it
offers: search for the goal item or the key when their place is unknown, go to any other place, open or unlock
the door here when that's possible, take anything known to be here, choose an item (for "wants a sweet thing"
goals), and finish once the goal item is held. The world checker runs the chosen move.

  python harness_choice.py [--pilot]      writes out/RESULTS.md and out/results.json
"""
import json, os, random, statistics as st, sys, time
import torch
import ft

PILOT = "--pilot" in sys.argv
MODEL = os.environ.get("MODEL", "Qwen/Qwen3-0.6B")
N = 3 if PILOT else 50
OUT = "out"
os.makedirs(OUT, exist_ok=True)
if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
    ft.amp = lambda: torch.autocast(device_type="cuda", dtype=torch.bfloat16)
LETTERS = "ABCDEFGHIJKL"


def options(ep, know):
    """Legal next moves from what is known: list of (step tuple in home words)."""
    a, here, held = ep["agent"], know["here"], know["held"]
    if ep["prop"] and know["chosen"] is None:
        return [("choose", a, i, ep["prop"]) for i in know["prop_items"]]
    target = know["chosen"] or ep["target"]
    if target in held:
        return [("check", a, target)]
    opts = []
    need_key = any(d == "locked" for d in know["doors"].values())
    for item in (target, "key") if need_key else (target,):
        if item not in know["loc"] and item not in held:
            opts.append(("search", item))
    for p in ft.PLACE_N:
        if p != here:
            opts.append(("go", a, p))
    door = know["doors"].get(here, "open")
    if ft.HAS_DOOR[here] and door == "closed":
        opts.append(("open", a, here))
    if ft.HAS_DOOR[here] and door == "locked" and "key" in held:
        opts.append(("unlock", a, here))
    if door == "open" or not ft.HAS_DOOR[here]:
        for item, p in know["loc"].items():
            if p == here and item not in held:
                opts.append(("take", a, item))
    return opts


def sentence(step):
    """The plan sentence for a step (search without its answer)."""
    return ft.step_text(("search", step[1], "?") if step[0] == "search" else step)[0][0]


def run(ep, skin, kind, seed, picker):
    """Plan by repeatedly asking picker(prompt_parts, option_sentences) for an index. Returns (ok, why, steps, searched_needed)."""
    sim = ft.Sim(ep, skin)
    told = {f[1]: f[2] for f in ep["facts"] if f[0] == "loc"}
    know = {"here": ep["start"], "held": set(), "loc": dict(told), "chosen": None if ep["prop"] else ep["target"],
            "doors": {f[1]: f[2] for f in ep["facts"] if f[0] == "door"},
            "prop_items": [f[1] for f in ep["facts"] if f[0] == "prop"]}
    problem = " ".join(ft.problem_words(ep, skin, kind, seed))[: -len(" plan :")]
    history, r = [], random.Random(seed)
    limit = len(ep["plan"]) + 6
    for _ in range(limit):
        opts = options(ep, know)
        r.shuffle(opts)
        texts = [ft.to_skin(sentence(o), skin) for o in opts]
        k = picker(problem, history, texts) if len(opts) > 1 else 0
        step = opts[k]
        inj = sim.step(ft.to_skin(sentence(step), skin).split())
        if sim.status is not None:
            return False, sim.why, len(history)
        history.append(texts[k] + (" " + inj if inj else ""))
        kind_ = step[0]
        if kind_ == "search":
            know["loc"][step[1]] = ep["loc"][step[1]]
        elif kind_ == "choose":
            know["chosen"] = step[2]
        elif kind_ == "go":
            know["here"] = step[2]
        elif kind_ in ("open", "unlock"):
            know["doors"][step[2]] = "open"
        elif kind_ == "take":
            know["held"].add(step[2])
        elif kind_ == "check":
            sim.step(ft.to_skin("done .", skin).split())
            return sim.status == "ok", sim.why, len(history)
    return False, "too many steps", len(history)


def model_picker(model):
    tok = ft.TOK
    ids = [tok(L, add_special_tokens=False)["input_ids"] for L in LETTERS]
    assert all(len(i) == 1 for i in ids), ids
    ids = [i[0] for i in ids]

    @torch.no_grad()
    def pick(problem, history, texts):
        body = (f"Facts: {problem}\n\n"
                + ("Done so far:\n" + "\n".join(f"- {h}" for h in history) + "\n\n" if history else "")
                + "What should happen next to reach the goal? If a needed place is unknown, search first.\n"
                + "\n".join(f"{L}. {t}" for L, t in zip(LETTERS, texts)) + "\n\nAnswer with just the letter.")
        text = tok.apply_chat_template([{"role": "user", "content": body}], tokenize=False,
                                       add_generation_prompt=True, enable_thinking=False)
        x = torch.tensor([tok(text, add_special_tokens=False)["input_ids"]], device=ft.DEV)
        with ft.amp():
            lg = model(input_ids=x).logits[0, -1].float()
        return int(lg[ids[:len(texts)]].argmax())
    return pick


def evaluate(picker, label):
    tests, res, t0 = ft.plan_tests(N), {}, time.time()
    for kind in ("clean", "messy", "filler"):
        for split, eps in tests.items():
            outs = [run(ep, ft.PLAN_SKINS[i % 4], kind, i, picker) for i, ep in enumerate(eps)]
            why = {}
            for ok, w, _ in outs:
                if not ok:
                    why[w] = why.get(w, 0) + 1
            res[f"{kind}/{split}"] = {"success": st.mean(o[0] for o in outs), "fails": why}
            print(f"  {label} {kind}/{split}: {res[f'{kind}/{split}']['success']*100:.0f}%  ({time.time()-t0:.0f}s)", flush=True)
    return res


def main():
    t0 = time.time()
    out = {"model": MODEL, "n": N}
    rnd = random.Random(0)
    out["random"] = evaluate(lambda p, h, t: rnd.randrange(len(t)), "random")
    model = ft.load(MODEL); model.eval()
    out["qwen"] = evaluate(model_picker(model), "qwen")
    out["total_s"] = round(time.time() - t0)
    json.dump(out, open(f"{OUT}/results.json", "w"), indent=1)
    pct = lambda v: f"{v*100:.0f}%"
    cols = [f"{k}/{s}" for k in ("clean", "messy", "filler") for s in ("short", "long")]
    L = [f"# Untouched {MODEL} + planning harness", "",
         f"No training. The harness lists the legal next moves; the model picks one by letter. {N} problems per cell.", "",
         "| picker | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for k in ("random", "qwen"):
        L.append(f"| {k} | " + " | ".join(pct(out[k][c]["success"]) for c in cols) + " |")
    L += ["", "Failures:"] + [f"- {k}: " + ", ".join(f"{w} {n}" for w, n in sorted(
        {w: sum(out[k][c]["fails"].get(w, 0) for c in cols) for c in cols for w in out[k][c]["fails"]}.items(), key=lambda x: -x[1]))
        for k in ("random", "qwen")]
    open(f"{OUT}/RESULTS.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
