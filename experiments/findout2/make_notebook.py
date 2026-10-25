"""Build teacher.ipynb (full) and teacher_quick.ipynb (40 tasks, a smoke test) from teacher.py + world2.py, for the Kaggle bridge."""
import json, pathlib
here = pathlib.Path(__file__).parent
src = (here / "teacher.py").read_text()
world = (here / "world2.py").read_text().split("# %%\nif __name__ == \"__main__\":")[0]
line = "# (world2.py is inlined here by make_notebook.py)\nfrom world2 import *  # noqa: E402,F401  -- replaced in the notebook\n"
assert line in src
src = src.replace(line, world + "\n")


def cells(text):
    out = []
    for chunk in text.split("# %%")[1:]:
        md = chunk.startswith(" [markdown]")
        body = chunk.split("\n", 1)[1].strip("\n") if "\n" in chunk else ""
        if not body:
            continue
        if md:
            out.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines())})
        else:
            out.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": body})
    return out


for name, quick in (("teacher", False), ("teacher_quick", True)):
    s = src.replace('QUICK = "--quick" in sys.argv', 'QUICK = True or "--quick" in sys.argv') if quick else src
    nb = {"cells": cells(s), "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
          "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
    (here / f"{name}.ipynb").write_text(json.dumps(nb, indent=1))
    code = "\n".join(c["source"] for c in nb["cells"] if c["cell_type"] == "code")
    compile(code, name, "exec")
    print(name, len(nb["cells"]), "cells, compiles")
