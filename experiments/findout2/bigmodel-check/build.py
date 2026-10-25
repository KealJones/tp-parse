import zlib, pickle, json, world2 as w
PICK = {"bc": (w.h_bridge_compare, [1, 2, 3, 0, 6, 7]),
        "ad": (w.h_ask_diff, [0, 1, 3, 4, 5, 8]),
        "am": (w.h_argmax4, [0, 1, 4, 10])}
eps = {}
for tag, (fn, idx) in PICK.items():
    ts = w.make_set(zlib.crc32(fn.__name__.encode()) % 1000 + 300, 24, [fn])
    for i in idx:
        t = ts[i]
        eps[f"{tag}{i}"] = {k: t[k] for k in ("type", "style", "request", "world", "person", "needs", "short", "given")} | {"idx": i}
open("eps.bin", "wb").write(zlib.compress(pickle.dumps(eps)))
print(json.dumps({k: v["request"] for k, v in eps.items()}, indent=1))
