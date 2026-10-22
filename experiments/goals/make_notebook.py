"""Turn goals.py into goals.ipynb (cells split at '# %%' markers)."""
import json, pathlib
src = pathlib.Path(__file__).with_name("goals.py").read_text()
cells = []
for chunk in src.split("# %%")[1:]:
    md = chunk.startswith(" [markdown]")
    body = chunk.split("\n", 1)[1].strip("\n")
    if md:
        lines = [l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines()]
        cells.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(lines)})
    else:
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": body})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
pathlib.Path(__file__).with_name("goals.ipynb").write_text(json.dumps(nb, indent=1))
print(len(cells), "cells")
