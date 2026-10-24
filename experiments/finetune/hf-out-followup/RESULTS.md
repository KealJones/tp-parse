# Follow-up: LoRA + slots learns to read Keal

Qwen/Qwen3-0.6B on NVIDIA A10G, 28 min total. Trained on 6000 planning and 12000 reading examples; none of Keal's messages were in training.

## Keal's real messages (45; pick what he meant out of four; chance 25%)

| | typed | voice | all |
|---|---|---|---|
| before (untouched) | 21% | 33% | 27% |
| after | 33% | 48% | 40% |

## English kept

| | ARC-Easy | WikiText-2 perplexity |
|---|---|---|
| before | 57% | 36.3 |
| after | 50% | 56.4 |

## Planning still works?

| clean short | clean long | messy short | messy long | filler short | filler long |
|---|---|---|---|---|---|
| 100% | 100% | 100% | 100% | 96% | 100% |

## Its own reading of each message

- **[typed]** Wait what the fuck how much training do frontier models do how do they not take a fucking year!?
  - meant: How much compute frontier models use and how they finish training in months instead of years
  - read: What is the how much training do frontier models do? How do they not take a year? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?
- **[typed]** Chinchilla insight what!?
  - meant: An explanation of what the Chinchilla finding was and why it mattered
  - read: Chinchilla insight what? What is the Chinchilla insight? What is the Chinchilla insight? What is the Chinchilla insight? What is the Chinchilla insight? What is
- **[typed]** What about a stupidly small model and train it on trillions?
  - meant: Whether a tiny model trained on a huge amount of text keeps getting better
  - read: What about a stupidly small model and train it on trillions? I think that's not right. What about a stupidly small model and train it on trillions? I think that's not
- **[typed]** Has anyone made a like multiple tiny very specific models like instead of layers keep a clean as shit divide?
  - meant: Whether anyone has built systems of many small specialist models with clean boundaries between them
  - read: Has anyone made a multiple tiny very specific models instead of layers, keep a clean as shit divide? Or maybe not? Or maybe not? Or maybe not? Or maybe not? Or maybe not?
- **[typed]** How can I give you access to kraggle
  - meant: The steps to let the assistant start and read Kaggle runs on their behalf
  - read: How can I give you access to kraggle? Kraggle is a data science platform. I need to know how to give you access to kraggle. I need to know how to
- **[typed]** Under the environmental KAGGLE if that matters
  - meant: To mention the secrets are stored inside a GitHub environment named KAGGLE, which may need a config change
  - read: Under the environmental KAGGLE if that matters? What is the meaning of that? What is the meaning of the KAGGLE? What is the meaning of the environmental? What is the meaning of
- **[typed]** What the fuck are you talking about I use fetch all the damn time
  - meant: To push back on the claim that browsers can't fetch, since they use fetch all the time
  - read: What are you talking about? I use fetch all the time? Or do you have any other sites? I think I need to ask more questions. What is the difference between fetch all the time and
- **[typed]** I seeee ok and there's no fun hack silly tricky ways to use like web assembly or workers or some other shit to make it work?
  - meant: Whether a trick like WebAssembly or workers can get around the browser's cross-site limits
  - read: I seeee ok and there's no fun hack silly tricky ways to use web assembly or workers or some other shit to make it work? What's the best way to do that? Maybe? Maybe
- **[typed]** Cloudflare worker?
  - meant: An explanation of what a Cloudflare Worker is and how it would act as the relay
  - read: The assistant listed a Cloudflare Worker as one way to relay web requests for the browser. Message: "Cloudflare worker?" What the person wants: The assistant listed a Cloudflare Worker as one way
- **[typed]** If this is gonna live in the browser what is to stop anyone who see that endpoint from just straight up seeing my key too?
  - meant: Whether a key used by a public browser page can be hidden from people who inspect it
  - read: If this is gonna live in the browser, what is to stop anyone who see that endpoint from just straight up seeing my key too? I think that's not right. What is to stop anyone who
- **[typed]** I want public GitHub pages is why I said simple
  - meant: To explain they want it open because the page will be public on GitHub Pages
  - read: I want public GitHub pages is why I said simple? What is the reason? Please explain. Thank you. Please explain. Thank you. Please explain. Thank you. Please explain. Thank you.
- **[typed]** Why do you need that?
  - meant: Why the assistant needs a Cloudflare token when the Cloudflare connector is already linked
  - read: Why do you need that? CLOUDFLARE_API_TOKEN? Where is it? How do I get it? CLOUDFLARE_API_TOKEN is a secret, so I need to get it.
- **[typed]** It's an account api key…
  - meant: To explain the secret they added is an account-level API key rather than a token
  - read: The assistant said the deploy failed because Cloudflare rejected the token's format. Message: "It's an account api key…". What is the problem? The assistant said the deploy failed because Cloudflare
- **[typed]** I didn't add CLOUDFLARE_ACCOUNT_ID do you need that?
  - meant: Whether the deploy also needs the account ID secret, which they skipped
  - read: I didn't add CLOUDFLARE_ACCOUNT_ID do you need that? [? + ? + ? + ? + ? + ? + ? + ? + ? + ? + ? + ? +
- **[typed]** could you have tested this locally and seen that it was a catastrophic failure?
  - meant: Whether the failure could have been caught by testing on the assistant's own machine first
  - read: Could you have tested this locally and seen that it was a catastrophic failure? Please explain.  The lesson-block experiment failed badly on Kaggle.  Could you have tested this locally and seen that it
- **[typed]** i meant like smaller scale test
  - meant: To clarify they meant a scaled-down version of the experiment, not the full run
  - read: I meant smaller scale test. What is the smaller scale test? Please explain. Thank you. Please explain. Thank you. Please explain. Thank you. Please explain. Thank you. Please explain.
- **[typed]** isnt REN what attention replaced? are we using attention and mlp?
  - meant: Whether entity networks were replaced by attention, and whether their model uses attention plus MLPs
  - read: Isnt REN what attention replaced? are we using attention and mlp? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?
- **[typed]** do we need a teacher?
  - meant: Whether the slots could work without a simulator telling them the true state
  - read: Do we need a teacher? The assistant said the simulator teaches the register slots during training. Message: "do we need a teacher?" The assistant said the simulator teaches the register slots during training. Message
- **[typed]** i have a gemini api key we could use to have gemini teach... if that would help?
  - meant: Whether using Gemini as the teacher during training would help
  - read: I have a gemini api key we could use to have gemini teach... if that would help? [ + + + + + + + + + + + + + + + + + +
- **[typed]** the skins is running already we can run another while that one is going though
  - meant: To start the registers experiment now, in parallel, instead of waiting
  - read: The skins is running already, we can run another while that one is going though. ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?
- **[typed]** should you maybe rip out the lesson block or whatever? since it failed and see if the slots work better without lessons
  - meant: To drop the failed lesson block and test the slots on their own
  - read: Should you maybe rip out the lesson block? since it failed and see if the slots work better without lessons? What is the lesson block? What is the slot? What is the lesson? What is
- **[typed]** Don't worry about cost tell me the services that can
  - meant: A list of services that can actually run big training jobs, regardless of price
  - read: Don't worry about cost tell me the services that can? On Kaggle and on rented GPUs. Message: "Don't worry about cost tell me the services that can? On Kaggle and on
- **[typed]** Jesus fucking christ what are models like you opus 5.5 then?
  - meant: How big the assistant's own model is and how much it took to train
  - read: Jesus christ what are models like you opus 5.5 then?  What are models like you opus 5.5 then?  What are models like you opus 5.
- **[typed]** How is it getting better every 8 months if you say there isn't anything different about the blocks changing?
  - meant: How efficiency keeps improving if the transformer blocks supposedly haven't changed
  - read: How is it getting better every 8 months if you say there isn't anything different about the blocks changing? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?
- **[voice]** Uh, I'm curious if there are models that are already trained for this type of task. That are already really small. Um, and do a good job. Like maybe I think we'…
  - meant: To find existing small models and datasets on Hugging Face for cleaning up rambling speech
  - read: I'm curious if there are models that are already trained for this type of task. That are already really small. and do a good job. Maybe I think we're connected to Hugging Face.
- **[voice]** So, uh, I'm curious how this um, this real test thing, if uh, how if it can do those other things and maybe registers does bring it up even more, uh, how would …
  - meant: How adding registers might change the results of the real-data experiment
  - read: How this real test thing, if it can do those other things and maybe registers does bring it up even more, how would registers potential right, any effect???
- **[voice]** I'm, I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. Like we have the goals thing, we have the the stories thin…
  - meant: Whether anything tests solving new kinds of problems it wasn't shown, by taking steps to figure them out
  - read: I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. we have the goals thing, we have the stories thing. But problem solving that's not provided to
- **[voice]** I guess I want to discuss kind of like like for sure I'll get out of this uh, voice chat right after this and you can write down that sketch or whatever but lik…
  - meant: To brainstorm what small models are good at, and how a harness built for that exact model should work
  - read: I guess I want to discuss for sure I'll get out of this voice chat right after this and you can write down that sketch or whatever but I also just I do think maybe we could brainstorm or
- **[voice]** Yeah, if you look at pretty much every previous project, and I'm pretty sure if you look at other chats that I've had with you, um, I always talk about it as li…
  - meant: To describe long-term memory as a store that learns their shorthand and keeps recent work close at hand
  - read: If you look at pretty much every previous project, and I'm pretty sure if you look at other chats that I've had with you, I always talk about it as like there's a graph database
- **[voice]** So actually, uh, I want to counter what you said. About not deleting memory. Um, the whole point of this project is for it to be uh, a relatively small size uh,…
  - meant: To argue that unused knowledge it can fetch again should be deleted rather than kept forever
  - read: I want to counter what you said. About not deleting memory. The whole point of this project is for it to be a relatively small size but also very capable. And I don't want it to
- **[voice]** I'm kind of curious if you think that there is a uh, symbolic or like uh, deterministic NLP type way to take things that like um, that the way I talk and like, …
  - meant: Whether rule-based language processing could clean up their messy messages before a small model sees them
  - read: I'm kind of curious if you think that there is a symbolic or deterministic NLP type way to take things that the way I talk and just take any real example of any prompts that I've given
- **[voice]** So I'm a little bit curious though. Um, Are you able to tell when a message was sent with voice?
  - meant: Whether the assistant can tell which of their messages were spoken rather than typed
  - read: Are you able to tell when a message was sent with voice? I think not. I think that's the way to go. I think that's the way to go. I think that's the
- **[voice]** I've noticed, at least with ChatGPT, in their voice mode, it isn't the same Claude, or like it's not the same ChatGPT. Like, it's not the same model that I'm ta…
  - meant: Whether the voice assistant is the same model as the text one, or a different model passing messages along
  - read: At least with ChatGPT, in their voice mode, it isn't the same Claude, or it's not the same ChatGPT. it's not the same model that I'm talking to
- **[voice]** from training a model because uh, training a model is going to be really fucking expensive, and I don't think I ever realized how fucking expensive it is, even …
  - meant: To switch from training from scratch to fine-tuning an existing small model like SmolLM or Qwen
  - read: From training a model because training a model is going to be really expensive, and I don't think I ever realized how expensive it is, even for something that's not even like a 1B
- **[voice]** Um, yeah, I had actually, hold on. Sorry. So, um, one, one caveat. That I was just thinking about. I don't care how long it takes to do whatever it needs to do.…
  - meant: For the system to say what it doesn't know and show its progress while it figures it out
  - read: I had actually, hold on. Sorry. one caveat. That I was just thinking about. I don't care how long it takes to do whatever it needs to do. Especially if it's like
- **[voice]** also, something that I really, really, really, really, really don't want is for um, when you ask the user, it should not be something so stupid and straightforw…
  - meant: When the system asks them something, it should accept any kind of answer, like a ramble or a link
  - read: Something that I really, really, really don't want is for when you ask the user, it should not be something so stupid and straightforward as like, I don't understand what X is. Can
- **[voice]** I do not I don't know if this is something maybe there's already a, an existing small model out there. You can feel free to like check Hugging Face or just sear…
  - meant: Whether anyone has built an AI that comes up with genuinely new ideas, not just remixes
  - read: I don't know if this is something maybe there's already an existing small model out there. You can feel free to check Hugging Face or just search the web or whatever, but is there anybody
- **[voice]** And I know I do I do that referencing thing. That's why I keep saying like, oh, we need the harness to be able to pull shit from files from this and that and fr…
  - meant: To explain the harness must handle their messy, back-referencing way of talking, because that's how they talk
  - read: I know I do that referencing thing. That's why I keep saying like, we need the harness to be able to pull shit from files from this and that and from references from ages ago and have
- **[voice]** But the point is, like, I think that all this, everything I've been trying to figure out or trying to accomplish with all of these projects across the board is …
  - meant: To describe their goal: a system that finds out what it doesn't know through sources, search or smarter AIs
  - read: The point is, I think that all this, everything I've been trying to figure out or trying to accomplish with all of these projects across the board is getting some type of base system in place.
- **[voice]** Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this like sm…
  - meant: How their small model would cope with their real messages, like a bare link, without a harness
  - read: Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this small model, how would that actually
- **[voice]** Um, I'm open to having the model's base size be between like 200 and 500 megabytes. Is that even reasonable?
  - meant: Whether a model file of 200 to 500 megabytes is a realistic target
  - read: I'm open to having the model's base size be between 200 and 500 megabytes. Is that even reasonable? I think that's not right. I think that's
- **[voice]** Um, I do want to add it. And I really like the thing that you were talking about from Margaret Bowden. Like those three ideas are Those are genuinely like what …
  - meant: To add creativity to the paper using Boden's three kinds, which match how they work
  - read: I do want to add it. And I really like the thing that you were talking about from Margaret Bowden. Those three ideas are Those are genuinely like what I when I'm doing my designs or
- **[voice]** So I'm not trying, I'm not trying to like get us to go back to Napkin because Napkin was just like it was a very different project than the one we're working on…
  - meant: To clarify that Napkin was a separate no-LLM project, not something to go back to
  - read: I'm not trying to get us to go back to Napkin because Napkin was just like it was a very different project than the one we're working on. With like, but Napkin,
- **[voice]** And then the only other thing is like, I know that we tend to do these in one notebook, uh, do you think that we could run all of them as separate notebooks so …
  - meant: To split the experiments into separate notebooks that run at the same time
  - read: The only other thing is like, I know that we tend to do these in one notebook, do you think that we could run all of them as separate notebooks so that they run in parallel instead of
- **[voice]** Yeah, con I want you to instead of this time, actually, sorry, can we try to write up a paper for this? That is completely devoid of any type of like implementa…
  - meant: A write-up of the core idea as a paper, with no implementation details
  - read: Con I want you to instead of this time, actually, sorry, can we try to write up a paper for this? That is completely devoid of any type of implementation details, and just really gets

## Training examples (first few)

- `'Message: "Okay so like categorize the like below names into, uh, into fishes and insects., insects. Hilsa, Catla, Maggot, Mite I don\'t know."\nWhat the person wants:'` → `' Categorize  the below names into fishes and insects.\n Hilsa, Catla, Maggot, Mite'`
- `'Message: "Yeah. I, I usually get it started for my wife I, she moves it around ever other day."\nWhat the person said, cleaned up:'` → `' Yeah. I usually get it started for my wife she moves it around ever other day.'`
- `'Message: "I\'m curious, um, why are like literally lot of uh the or whatever women more structured like and methodical in work, compared to men"\nWhat the person wants:'` → `' why are lot of the women more structured and methodical in work, compared to men'`
- `'Message: "Well, we buy what, we just got through buying a twenty-five foot refrigerator, a new ceramic top stove, and a new dishwasher."\nWhat the person said, cleaned up:'` → `' we buy what, we just got through buying a twenty-five foot refrigerator, a new ceramic top stove, and a new dishwasher.'`
- `'Message: "yo which rivers were the birthplaces of damn the first great civilizations?"\nWhat the person wants:'` → `' Which rivers were the birthplaces of the first great civilizations?'`
- `'Message: "I try to, - I did switch to one, sponsored by the credit union, though. That seems to be a pretty low interest."\nWhat the person said, cleaned up:'` → `' I try to, I did switch to one, sponsored by the credit union, though. That seems to be a pretty low interest.'`
