"""Loads a GGUF in wllama 3.8.1 (the exact runtime Squiggle's phones use) in headless Chromium and runs one Squiggle
prompt through createChatCompletion with the app's settings (n_ctx 4096, CPU, streamed, temperature 0.7, top_k 64,
top_p 0.95, penalty_repeat 1.15). Prints the reply and whether it parses (thinking + tool call).

  python wllama_check.py model.gguf [--prompt prompt.json]
Needs: pip install playwright && playwright install chromium (headless shell is enough).
"""
import argparse, functools, http.server, json, sys, threading, time
from pathlib import Path

PAGE = """<!doctype html><meta charset="utf-8"><script type="module">
const V = '3.8.1';
const { Wllama } = await import(`https://cdn.jsdelivr.net/npm/@wllama/wllama@${V}/esm/index.min.js`);
const w = new Wllama({ default: `https://cdn.jsdelivr.net/npm/@wllama/wllama@${V}/esm/wasm/wllama.wasm` }, { suppressNativeLog: true });
const t0 = performance.now();
try {
  await w.loadModelFromUrl(location.origin + '/model.gguf', { n_ctx: 4096, n_gpu_layers: 0 });
  const loaded = performance.now() - t0;
  const messages = await (await fetch('/prompt.json')).json();
  const stream = await w.createChatCompletion({ messages, stream: true, max_tokens: 300, temperature: 0.7, top_k: 64, top_p: 0.95, penalty_repeat: 1.15 });
  let out = '', n = 0; const t1 = performance.now();
  let reasoning = '', keys = new Set();
  for await (const c of stream) { const d = c?.choices?.[0]?.delta || {}; Object.keys(d).forEach(k => keys.add(k)); const p = d.content; if (p) { out += p; n++; } if (d.reasoning_content) reasoning += d.reasoning_content; }
  window.__result = { ok: true, loadMs: loaded, genMs: performance.now() - t1, chunks: n, text: out, reasoning, deltaKeys: [...keys] };  // the app reads delta.content only
} catch (e) { window.__result = { ok: false, error: String(e && e.stack || e) }; }
</script>"""

DEFAULT_PROMPT = [
    {"role": "system", "content": "You are Squiggle, an assistant that figures things out. Think first. If you\ndon't know something, don't guess: find it or look it up. For anything with\nmore than one step, make a plan, then do one step at a time.\nCall a tool with a ```tool_call block containing {\"name\", \"arguments\"}; tools\nyou have: plan, done, need, find, and any tool you have looked up with find.\nArguments: plan(goal, steps), done(result), need(what), find(query).\nToday is Tue Oct 27 2026."},
    {"role": "user", "content": "When was the last time anyone was on the moon?"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gguf")
    ap.add_argument("--prompt")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()
    root = Path(a.gguf).resolve().parent
    files = {"/": PAGE.encode(), "/prompt.json": json.dumps(json.load(open(a.prompt)) if a.prompt else DEFAULT_PROMPT).encode()}

    class H(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in files:
                body = files[self.path]
                self.send_response(200)
                self.send_header("Content-Type", "text/html" if self.path == "/" else "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.split("?")[0] == "/model.gguf":
                self.path = "/" + Path(a.gguf).name
            return super().do_GET()

        def log_message(self, *x):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), functools.partial(H, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.on("console", lambda m: print("console:", m.text[:200]) if m.type == "error" else None)
        page.goto(f"http://127.0.0.1:{a.port}/")
        t0 = time.time()
        r = None
        while time.time() - t0 < a.timeout:
            r = page.evaluate("window.__result || null")
            if r:
                break
            time.sleep(2)
        b.close()
    srv.shutdown()
    if not r:
        print(json.dumps({"ok": False, "error": "timed out"}))
        sys.exit(1)
    if r.get("ok"):
        t = r["text"]
        r["has_think"] = t.lstrip().startswith("<think>") and "</think>" in t
        r["has_call"] = "```tool_call" in t
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
