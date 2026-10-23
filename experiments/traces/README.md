# Human finding-out traces

Recordings of Keal solving problems while narrating: the notice → find out → try → check loop from the "Finding Out" paper, done by a person.

| trace | kind of problem | the main lesson |
|---|---|---|
| `boustrophedon/` | code, with an unknown word | the judgment took minutes; the cost was recalling syntax |
| `coeliac-dinner/` | everyday planning with a safety side | orient before solving: what actually goes wrong for this person (cross-contact) |
| `moms-birthday/` | working out what a person needs | results carry their assumptions: work done under "say Phoenix" went stale when Ohio arrived |

`episodes.jsonl` (built by `build_episodes.py`) turns them into training episodes. **Mistakes are kept**, and every uncaught one gets the step that catches and fixes it, marked `"added": true`. A clean trace would teach the model it never errs; an uncaught mistake would teach the mistake; mistake + catch + fix teaches recovery.
