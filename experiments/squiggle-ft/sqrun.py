"""Runs episodes through Squiggle's real agent loop (sq/driver.mjs, one node process per episode) and answers its
model calls with a backend: a script, a teacher (vLLM) or a student (transformers).

    runner = Runner(backend, squiggle_dir, work_dir, concurrency=32)
    results = runner.run(episodes)        # episodes: [Episode]; results: [dict] with every model call

An Episode says what the world holds (repos, memory facts, past chats, recipes, home files), the first user message
and how the simulated user answers later (a function: turn result -> next message or None).
"""
import asyncio, json, os, shutil, sys, tempfile, time, traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

HERE = Path(__file__).resolve().parent


@dataclass
class Episode:
    id: str
    family: str
    first: str                                   # the first user message
    world: dict = field(default_factory=dict)    # {repos, facts, sessions, recipes, home}
    gold: dict = field(default_factory=dict)     # what the checker needs (never shown to the model)
    user: Optional[Callable] = None              # (turn: dict, episode) -> next user message (str or (text, session)) or None
    approve: str = "deny"
    max_turns: int = 4
    meta: dict = field(default_factory=dict)


class ScriptBackend:
    """Replies from a list (or a function of the request) per episode: for samples and tests."""
    def __init__(self, scripts):
        self.scripts = scripts                   # episode id -> list[str] | callable(req) -> str

    async def generate(self, reqs):
        out = []
        for r in reqs:
            s = self.scripts[r["episode"]]
            if callable(s):
                out.append(s(r))
            else:
                i = r["index"]
                out.append(s[i] if i < len(s) else "<think>The script ran out.</think>\n(script ended)")
        return out


class Runner:
    def __init__(self, backend, squiggle_dir, work_dir, concurrency=24, offline=False, batch_wait=0.25, log=print, max_calls=40):
        self.max_calls = max_calls   # model calls per episode before it is stopped (like the user pressing Stop)
        self.backend, self.squiggle = backend, str(Path(squiggle_dir).resolve())
        self.work = Path(work_dir)
        self.concurrency, self.offline, self.batch_wait, self.log = concurrency, offline, batch_wait, log
        (self.work / "repo-cache").mkdir(parents=True, exist_ok=True)
        (self.work / "net-cache").mkdir(parents=True, exist_ok=True)
        self.env = dict(os.environ, SQUIGGLE_DIR=self.squiggle, NODE_NO_WARNINGS="1")
        if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
            self.env["NODE_USE_ENV_PROXY"] = "1"

    # ── generation batching ──────────────────────────────────────────────
    async def _batcher(self):
        while True:
            first = await self.q.get()
            batch = [first]
            await asyncio.sleep(self.batch_wait)
            while not self.q.empty():
                batch.append(self.q.get_nowait())
            reqs = [b[0] for b in batch]
            try:
                texts = await self.backend.generate(reqs)
            except Exception as e:
                traceback.print_exc()
                texts = [None] * len(reqs)
                for b in batch:
                    b[1].set_exception(e)
                continue
            for b, t in zip(batch, texts):
                if not b[1].done():
                    b[1].set_result(t)

    async def _ask(self, req):
        if hasattr(self.backend, "generate_one"):          # continuous batching (vLLM's async engine)
            return await self.backend.generate_one(req)
        fut = asyncio.get_running_loop().create_future()
        await self.q.put((req, fut))
        return await fut

    # ── one episode ──────────────────────────────────────────────────────
    async def _episode(self, ep: Episode):
        t0 = time.time()
        root = tempfile.mkdtemp(prefix="sqep-", dir=self.work)
        proc = await asyncio.create_subprocess_exec(
            "node", "--import", str(HERE / "sq" / "register.mjs"), str(HERE / "sq" / "driver.mjs"),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=self.env, cwd=str(HERE), limit=64 * 1024 * 1024)
        err_lines = []

        async def drain():
            async for line in proc.stderr:
                err_lines.append(line.decode("utf-8", "replace").rstrip())
                del err_lines[:-60]
        drainer = asyncio.create_task(drain())

        def send(obj):
            proc.stdin.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())

        spec = {"t": "episode", "first": ep.first, "world": ep.world, "root": root, "approve": ep.approve,
                "repoCache": str(self.work / "repo-cache"), "netCache": str(self.work / "net-cache"), "offline": self.offline}
        send(spec)
        await proc.stdin.drain()
        result = {"id": ep.id, "family": ep.family, "first": ep.first, "gold": ep.gold, "meta": ep.meta, "turns": [], "calls": [], "error": None}
        index = 0
        try:
            async for raw in proc.stdout:
                m = json.loads(raw)
                t = m.get("t")
                if t == "gen":
                    req = {"episode": ep.id, "index": index, "kind": m["kind"], "messages": m["messages"], "max_tokens": m.get("max_tokens", 1024)}
                    index += 1
                    if index > self.max_calls:
                        text = {"error": f"Stopped: more than {self.max_calls} model calls in one episode."}
                        result["capped"] = True
                    else:
                        text = await self._ask(req)
                    meta = err = None
                    if isinstance(text, dict):
                        text, meta, err = text.get("text"), text.get("meta"), text.get("error")
                    send({"t": "out", "id": m["id"], "text": text if text is not None else "", **({"meta": meta} if meta else {}), **({"error": err} if err else {})})
                elif t == "turn":
                    result["turns"].append(m)
                    nxt = None
                    if ep.user and len(result["turns"]) < ep.max_turns:
                        try:
                            nxt = ep.user(m, ep)
                        except Exception as e:
                            result["error"] = f"user simulator: {e!r}"
                    if nxt:
                        text, session = (nxt, None) if isinstance(nxt, str) else nxt
                        send({"t": "user", "text": text, **({"session": session} if session else {})})
                    else:
                        send({"t": "end"})
                elif t == "done":
                    result.update(calls=m["calls"], sessions=m["sessions"], recipes=m["recipes"], facts=m["facts"], net=m["net"])
                elif t == "error":
                    result["error"] = m["error"]
                await proc.stdin.drain()
        except Exception as e:
            result["error"] = f"runner: {e!r}"
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(proc.wait(), 30)
            except asyncio.TimeoutError:
                proc.kill()
            drainer.cancel()
            shutil.rmtree(root, ignore_errors=True)
        if result["error"] or proc.returncode:
            result["error"] = (result["error"] or f"exit {proc.returncode}") + "\n" + "\n".join(err_lines[-20:])
        result["seconds"] = round(time.time() - t0, 1)
        return result

    async def _run(self, episodes, on_result=None, deadline=None):
        self.q = asyncio.Queue()
        batcher = asyncio.create_task(self._batcher())
        sem = asyncio.Semaphore(self.concurrency)
        results = []

        async def one(ep):
            async with sem:
                if deadline and time.time() > deadline:
                    return
                try:
                    r = await asyncio.wait_for(self._episode(ep), 1800)
                except asyncio.TimeoutError:
                    r = {"id": ep.id, "family": ep.family, "first": ep.first, "gold": ep.gold, "meta": ep.meta, "turns": [], "calls": [], "error": "episode timed out"}
                results.append(r)
                if on_result:
                    on_result(r)
        await asyncio.gather(*(one(e) for e in episodes))
        batcher.cancel()
        return results

    def run(self, episodes, on_result=None, deadline=None):
        return asyncio.run(self._run(episodes, on_result, deadline))


# ── Parsing model output with the app's own functions (via node) ─────────────
class AppFormat:
    """engine-wllama.js parseToolCalls / splitThinking / isLooping and agent.js LITE_SYSTEM, called in node, so the
    self-test checks episodes against Squiggle's own code, not a Python copy."""
    def __init__(self, squiggle_dir):
        import subprocess
        env = dict(os.environ, SQUIGGLE_DIR=str(Path(squiggle_dir).resolve()), NODE_NO_WARNINGS="1")
        self.p = subprocess.Popen(["node", "--import", str(HERE / "sq" / "register.mjs"), str(HERE / "sq" / "format.mjs")],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env, cwd=str(HERE))

    def __call__(self, op, **kw):
        self.p.stdin.write(json.dumps({"op": op, **kw}, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        r = json.loads(self.p.stdout.readline())
        if not r.get("ok"):
            raise RuntimeError(r.get("error"))
        return r["value"]

    def close(self):
        self.p.stdin.close()
        self.p.wait()
