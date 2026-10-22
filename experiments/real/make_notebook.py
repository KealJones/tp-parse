"""Turn real.py into real.ipynb (cells split at '# %%'), with hubs.json inlined."""
import json, pathlib
here = pathlib.Path(__file__).parent
src = (here / "real.py").read_text()
hubs = (here / "hubs.json").read_text().strip()
line = 'HUBS = json.load(open("hubs.json")) if os.path.exists("hubs.json") else None  # replaced inline in the notebook'
assert line in src
src = src.replace(line, f"HUBS = json.loads({hubs!r})  # Basic English word -> toki pona hub (experiments/basic-english)")
cells = []
for chunk in src.split("# %%")[1:]:
    md = chunk.startswith(" [markdown]")
    body = chunk.split("\n", 1)[1].strip("\n")
    if md:
        cells.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines())})
    else:
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": body})
nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
      "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
(here / "real.ipynb").write_text(json.dumps(nb, indent=1))
print(len(cells), "cells")
