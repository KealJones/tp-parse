#!/usr/bin/env python3
"""Talk to the goals model through Ollama, answering its searches.

Setup:   ollama create goals -f Modelfile
Demo:    python3 chat.py           test problems; this script plays the lookup tool
Yours:   python3 chat.py --you     type your own world; you answer its searches

Only the words in words.txt are known to the model. Write sentences the way it was trained:
lower case, spaces around punctuation, e.g. "the person is at the field . the person wants the bread ."
"""
import json, os, random, re, sys, urllib.request

MODEL = os.environ.get("GOALS_MODEL", "goals")
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/generate"
HERE = os.path.dirname(os.path.abspath(__file__))


def generate(text):
    body = {"model": MODEL, "prompt": text, "raw": True, "stream": False,
            "options": {"temperature": 0, "num_ctx": 256, "num_predict": 120, "stop": ["?", "the goal is done"]}}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["response"]


def tidy(t):
    return " ".join(re.sub(r"([.,:?])", r" \1 ", t).split())


def plan(prompt, answer, max_rounds=8):
    """Run the model; whenever it asks 'search : where is the X ?', call answer(X) and feed the result back."""
    text = tidy(prompt)
    if not text.endswith("plan :"):
        text += " plan :"
    start = len(text)
    for _ in range(max_rounds):
        out = tidy(generate(text))
        text = (text + " " + out).strip()
        m = re.search(r"search : where is the (\w+)$", out)
        if m:
            place = answer(m.group(1))
            text += f" ? result : the {m.group(1)} is at the {place} ."
            continue
        if re.search(r", so$", out):
            text += " the goal is done . done ."
        break
    return [s.strip() for s in re.findall(r"[^.?]+[.?]", text[start:])]


def show(lines):
    for s in lines:
        print(("   ↳ " if s.startswith("result") else " - ") + s)


def demo():
    eps = [json.loads(l) for l in open(os.path.join(HERE, "episodes.jsonl"))]
    random.shuffle(eps)
    for ep in eps:
        print(f"\n[{ep['split']}] {ep['prompt']}\n")
        show(plan(ep["prompt"], lambda item: ep["loc"].get(item, "field")))
        print("\n expected:", ep["gold"])
        if input("\nEnter for another, q to quit: ").strip().lower() == "q":
            break


def yours():
    words = set(open(os.path.join(HERE, "words.txt")).read().split())
    print(__doc__.split("Only")[1].strip(), "\n")
    while True:
        world = input("world + goal (blank to quit): ").strip()
        if not world:
            break
        unknown = sorted({w for w in tidy(world).split() if w not in words})
        if unknown:
            print("  unknown words:", ", ".join(unknown), "(see words.txt)")
            continue
        show(plan(world, lambda item: input(f"  the model asks where the {item} is. place: ").strip().split()[-1]))
        print()


if __name__ == "__main__":
    yours() if "--you" in sys.argv else demo()
