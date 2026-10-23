# Trace: Keal works out what a person really needs

The third recorded trace (2026-10-23, about 35 minutes). Claude played a person asking for help with their mom's birthday, with a hidden brief written and fingerprinted beforehand (`hidden_person.txt`, sha256 prefix `d1f98f5b57fd6a22`). Keal had to find out what was really going on by asking. `transcript.md` is his narration.

**Result:** he found the real need (a lonely, newly retired mom, and a child who feels guilty for not calling) and proposed a standing weekly call, which is what the hidden brief called the great answer. He also recommended Arizona garden clubs for a mom who lives in Ohio.

## Where the Ohio slip actually came from

*(Corrected after an independent review. An earlier version of this section said the Arizona clubs were found under a Phoenix placeholder before Ohio was known. The timestamps say otherwise.)*

1. **12:50** He searched gardening season and got a Phoenix result (the search was localised to him).
2. **13:00** He caught it ("that's assuming they're in Phoenix, right?") and asked where the mom lives.
3. **18:20** The answer came back as Ohio, and he wrote "lives in ohio" under Mom in his notes.
4. **23:45**, five minutes *after* that: "Arizona, I'm gonna just say Phoenix" led him to search for Arizona garden clubs. He mixed up whose location mattered. The person asking lives in Arizona; the mom lives in Ohio.
5. **33:05** The reply used the Arizona club.

So there are two different failures:
- **A true stale placeholder:** the Phoenix gardening-season result (step 1) was never revisited once Ohio was known. Dependency tracking catches this: the result depends on `mom_location`, and that changed.
- **The club mix-up isn't staleness.** The idea was created after the fact was known, built on the wrong person's location. Dependency tracking would not catch it, because nothing changed after the idea was made. What catches it is a **final check of the answer against the notes**: every place named in the answer has to match the location of the person it's for.

Both are needed: links between facts and ideas for things that change, and a final check for things that were wrong from the start.

## The rest of the loop

| time | step | what happened |
|---|---|---|
| 0:00 | opening questions | hobbies, things she wanted but didn't buy, budget, timeline (he almost skipped timeline, then asked) |
| 2:40 | listen to wording | "likes... like a lot... or she used to": the tense change is the thread to pull |
| 4:10 | ask with care | asked *why* she slowed down, explained why he was asking, and gave permission not to answer |
| 6:05 | keep a working picture | started notes: interests, budget, timeline, "six days, so shipping matters" |
| 7:55 | wish for memory | "if I had a tool, I'd look up if we'd talked about budget before, and anything about his mom"; "I probably should have done that before I even asked" |
| 9:40 | read between the lines | "she says she's fine, that's probably a lie" |
| 13:00–22:00 | research the person, not the gift | retirement adjustment, the signs, how to support someone, and that it's not the child's job to fix |
| 20:10 | reweigh the plan | "these gift ideas are feeling stupid now... would a reminder of what she can't do make her feel worse?" |
| 22:00 | reason about norms | as a stranger he wouldn't raise depression from two sentences; as an assistant, with evidence, it may be acceptable, but phrased gently |
| 29:25 | tie it to the person | "I don't call her as much as I should" became the scheduled-call suggestion, so it doesn't rely on remembering |

## Where the hour went

The questions and the insight took about 10 minutes in total. Most of the rest was research and browsing: retirement mental health (about 10 minutes), gift and club pages (about 10), and writing the reply (about 5). As in the other traces, the judgment was quick and the expensive part was everything around it.

## What it suggests for training data

- **Results carry their assumptions.** A placeholder is fine while waiting, but everything built on it is marked and re-checked when the real answer arrives.
- **Keep track of whose fact it is.** Two people, two locations: the answer must use the one it's for.
- **Final check against the notes**, item by item: location, budget, timeline.
- **Listen to wording** (tense changes, "she says she's fine"); that's where the real questions come from.
- **Check memory before asking** what you might already know about the person.

## The notes themselves (`notes.md`)

Keal used one notes file as his memory, so every edit was effectively a tool call. How it's organised:
- **By entity:** Mom and Son each get their facts (lives in Ohio, knees, retired). This is the knowledge graph idea in miniature.
- **Claims with their evidence underneath:** "potentially depressed", with the signs (lost interest, retired, "claims she's fine") as children. The claim is hedged, and its support is visible.
- **Sources attached to claims** (the helpguide and ruok links).
- **By topic** for the task itself: budget, timeline, gift ideas.

**Why Ohio still slipped:** the fact (`Mom → lives in Ohio`) and the idea (`Gift Ideas → azgardenclubs.com`) sat in different sections with nothing connecting them. The Phoenix assumption was hidden inside a URL. In a graph, that idea would have an edge to the fact it depends on (the mom's location), and the edit "lives in Ohio" would have flagged it. The notes had the facts; what they lacked were links.
