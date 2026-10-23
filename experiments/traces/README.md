# Human finding-out traces

Recordings of Keal solving problems while narrating: the notice → find out → try → check loop from the "Finding Out" paper, done by a person.

| trace | kind of problem | the main lesson |
|---|---|---|
| `boustrophedon/` | code, with an unknown word | the judgment took minutes; the cost was recalling syntax |
| `coeliac-dinner/` | everyday planning with a safety side | orient before solving: what actually goes wrong for this person (cross-contact) |
| `moms-birthday/` | working out what a person needs | results carry their assumptions: work done under "say Phoenix" went stale when Ohio arrived |

`episodes.jsonl` (built by `build_episodes.py`, checked by `validate.py`) turns them into training episodes, format v2.1:
- **Typed events instead of loose notes:** `fact`, `assume`, `need`, `todo`/`done`, and `idea` with the keys it rests on, so a harness can tell what went stale when a fact changes.
- **Observations** (`result`, `reply`, `harness`) come from the world and aren't trained on. The harness only lists the working picture; it never states facts about the world.
- **Every event has a provenance tag:** `recorded`, `condensed`, `reconstructed` (code rebuilt from the screen recording; `validate.py --run` re-runs every code step, and each one reproduces the output in the recording) or `added`.
- **Mistakes are kept**, and each uncaught one gets the step that catches and fixes it. A clean trace would teach the model it never errs, and an uncaught mistake would teach the mistake. Mistake, then catch, then fix teaches recovery.
- **Any "can't" or "impossible" is treated as a claim:** it becomes an `assume` and gets one lookup before it can be said (mirrored letters turned out to be possible, approximately).

An independent review (2026-10-23) found no leakage from the hidden brief in the birthday trace. Its other findings (a duplicate episode, unsourced facts, placeholders inside trained steps, misordered steps) are fixed in v2.1.
