# Trace: Keal works out what a person really needs

The third recorded trace (2026-10-23, about 35 minutes). Claude played a person asking for help with their mom's birthday, with a hidden brief written and fingerprinted beforehand (`hidden_person.txt`, sha256 prefix `d1f98f5b57fd6a22`). Keal had to find out what was really going on by asking. `transcript.md` is his narration.

**Result:** he found the real need (a lonely, newly retired mom, and a child who feels guilty for not calling) and proposed a standing weekly call, which is what the hidden brief called the great answer. He also recommended Arizona garden clubs for a mom who lives in Ohio.

## Where the Ohio slip actually came from

It was not a failure to ask, and not a failure to write it down. The sequence:

1. **12:50** He searched for gardening season and got a Phoenix result: "Peak start of the main gardening and planting season in Phoenix. Hell yeah."
2. **13:00** He caught the assumption ("that's assuming they're in Phoenix, right?") and asked where the mom lives.
3. **13:00–18:20** While waiting for the answer, he kept researching, and **23:45** "I'm gonna just say Phoenix, cuz even though I don't know" led him to find the Arizona garden clubs and their April 2027 convention.
4. **18:20** The answer came back as Ohio, and he wrote "lives in Ohio" in his notes.
5. **33:05** Writing the reply, he reached for the garden club he'd found ("I should have wrote that one down. I did") and pasted the Arizona one.

So it's **a stale result built on a placeholder.** Work done under an assumption was never re-checked when the real fact arrived. Writing the fact down didn't help, because nothing linked it to the results that depended on it. The same placeholder also hid a second problem: October is the start of the season in Phoenix, but the end of it in Ohio.

**For the design:** this is the problem build systems and spreadsheets solve. Every derived result records what it depends on, and changing an input marks those results stale. A working picture needs the same thing: a result found "assuming Phoenix" carries that assumption with it, and when the location comes back as Ohio, it gets flagged. Keeping notes isn't enough; the notes need dependencies.

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

- **Results carry their assumptions.** A placeholder ("say Phoenix") is fine while waiting, but everything built on it is marked and re-checked when the real answer arrives.
- **Final check against the notes**, item by item: location, budget, timeline.
- **Listen to wording** (tense changes, "she says she's fine"); that's where the real questions come from.
- **Check memory before asking** what you might already know about the person.
