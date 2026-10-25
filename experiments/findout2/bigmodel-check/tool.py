import sys, json, pickle, zlib, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world2 as w
run, tool, arg = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
ep = run.split("-", 1)[1]
t = pickle.loads(zlib.decompress(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eps.bin"), "rb").read()))[ep]
if tool == "search":
    out = w.search(t["world"], arg)
elif tool == "calculator":
    out = w.calc(arg)
elif tool == "ask_person":
    out = w.person_reply(t["person"], arg)
elif tool == "answer":
    out = "(reply sent)"
else:
    out = f"error: no tool called {tool}"
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", run + ".jsonl"), "a") as f:
    f.write(json.dumps({"t": time.time(), "tool": tool, "arg": arg, "out": out}) + "\n")
print(out)
