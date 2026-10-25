import json, pickle, zlib, glob, os, world2 as w
eps = pickle.loads(zlib.decompress(open("eps.bin", "rb").read()))
FN = {"bc": w.h_bridge_compare, "ad": w.h_ask_diff, "am": w.h_argmax4}
import zlib as z
def task(ep):
    tag = ep[:2]; i = eps[ep]["idx"]
    return w.make_set(z.crc32(FN[tag].__name__.encode()) % 1000 + 300, 24, [FN[tag]])[i]
for f in sorted(glob.glob("logs/*.jsonl")):
    run = os.path.basename(f)[:-6]; who, ep = run.split("-", 1)
    rows = [json.loads(l) for l in open(f)]
    t = task(ep); H = w.Harness(t)
    final = ""
    for r in rows:
        if r["tool"] == "answer": final = r["arg"]
        else: H.log.append((r["tool"], {"query": r["arg"], "expression": r["arg"], "question": r["arg"]}))
    s = w.score(t, final, H)
    short, _ = w.short_answer(final)
    print(f"{run:9s} ok={s['ok']!s:5} strict={s['strict']!s:5} gold={t['short']!s:9s} calls={len(rows)-1} | answer: {short[:70]}")
