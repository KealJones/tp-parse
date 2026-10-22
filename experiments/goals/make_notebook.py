"""Turn goals.py / goals_rl.py into notebooks (cells split at '# %%' markers). goals_rl also embeds chat.py."""
import json, pathlib
here = pathlib.Path(__file__).parent
for name in ("goals", "goals_rl"):
    src = (here / f"{name}.py").read_text()
    cells = []
    for chunk in src.split("# %%")[1:]:
        md = chunk.startswith(" [markdown]")
        body = chunk.split("\n", 1)[1].strip("\n")
        if md:
            lines = [l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines()]
            cells.append({"cell_type": "markdown", "metadata": {}, "source": "\n".join(lines)})
        else:
            cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": body})
    if name == "goals_rl":
        chat = (here / "chat.py").read_text()
        assert "'''" not in chat
        idx = next(i for i, c in enumerate(cells) if c["source"].startswith("try:\n    CHAT_PY"))
        cells[idx] = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": "# chat.py, written into the export\nCHAT_PY = r'''" + chat + "'''"}
    nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
          "language_info": {"name": "python"}, "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}
    (here / f"{name}.ipynb").write_text(json.dumps(nb, indent=1))
    print(name, len(cells), "cells")
