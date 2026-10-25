"""Build weird.ipynb (full) and weird_quick.ipynb (smoke test) from weird.py."""
import json, pathlib
here = pathlib.Path(__file__).parent
src = (here / "weird.py").read_text()
for name, quick in (("weird", False), ("weird_quick", True)):
    s = src.replace('QUICK = "--quick" in sys.argv', 'QUICK = True') if quick else src
    cells = []
    for chunk in s.split("# %%")[1:]:
        md = chunk.startswith(" [markdown]")
        body = chunk.split("\n", 1)[1].strip("\n")
        if md:
            cells.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines())})
        else:
            cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": body})
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}, "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
    (here / f"{name}.ipynb").write_text(json.dumps(nb, indent=1))
    compile("\n".join(c["source"] for c in cells if c["cell_type"] == "code"), name, "exec")
    print(name, len(cells), "cells, compiles")
