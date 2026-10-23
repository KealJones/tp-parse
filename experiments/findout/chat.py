#!/usr/bin/env python3
"""Play with the finding-out model in Ollama.

    ollama create findout -f Modelfile
    python3 chat.py              # a fresh invented world; ask about its towns, creatures, items and people
    python3 chat.py --show       # also print the world, so you can check its answers

The script is the harness: it runs the model's searches against the world, does its arithmetic, answers its
questions (it asks you), and flags searches that rested on a replaced assumption.
"""
import json, os, random, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from world import SYSTEM, ACTION_RE, Harness, attrs_of, make_world  # noqa: E402

URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
MODEL = os.environ.get("FINDOUT_MODEL", "findout")
STOPS = ["</search>", "</calc>", "</ask>", "</fact>", "</assume>", "</answer>", "</think>", "</check>"]


def step(messages, partial):
    body = {"model": MODEL, "stream": False, "messages": messages + ([{"role": "assistant", "content": partial}] if partial else []),
            "options": {"temperature": 0, "num_predict": 96, "stop": STOPS}}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        out = json.loads(r.read())
    text = out["message"]["content"]
    # Ollama drops the stop string; put the closing tag back
    for s in STOPS:
        opener = "<" + s[2:-1]
        if opener in text and s not in text:
            return text + s
    return text


class Person:
    def __init__(self):
        self.interrupt = None

    def get(self, k, default=None):
        if k == "town":
            return input("  the model asks you (type a reply): ").strip()
        return default


def main():
    W = make_world(random.Random())
    if "--show" in sys.argv:
        print(json.dumps(W, indent=1))
    names = [n for kind in W.values() for n in kind]
    print("Invented world. Some names you can ask about:", ", ".join(names[:10]), "...\n")
    while True:
        q = input("you: ").strip()
        if not q:
            break
        H = Harness(W, Person())
        H.act = _ask_aware(H)
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]
        text = ""
        for _ in range(14):
            piece = step(messages, text)
            if not piece:
                break
            text += piece
            m = list(ACTION_RE.finditer(piece))
            if not m:
                break
            tag, at, body = m[-1].group(1), attrs_of(m[-1].group(2)), m[-1].group(3).strip()
            print(f"  [{tag}] {body}" if tag != "answer" else "")
            if tag == "answer":
                print("model:", body, "\n")
                break
            obs = H.act(tag, at, body)
            if obs:
                print("   ", obs)
            text += "\n" + obs + "\n" if obs else "\n"


def _ask_aware(H):
    orig = Harness.act

    def act(tag, attrs, body):
        if tag == "ask":
            H.log.append((tag, attrs, body))
            return "<reply>" + input(f"  model asks: {body}\n  you: ").strip() + "</reply>"
        return orig(H, tag, attrs, body)
    return act


if __name__ == "__main__":
    main()
