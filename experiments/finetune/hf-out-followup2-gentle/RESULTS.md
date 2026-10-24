# Follow-up 2, arm `gentle`

Qwen/Qwen3-0.6B on NVIDIA A10G, 22 min total. LoRA rank 8 on attn linear layers, slots off, replay 25%, learning rate 0.0001, early stopping on. Ran 1200 of 1500 steps. Training examples: {'plan': 5900, 'read': 11800, 'replay': 1200, 'val': 300}. None of Keal's messages were in training.

## Keal's real messages, four options (chance 25%)

New test: all four shown as A/B/C/D, so it's a real choice. "Sure" means it gave its pick at least 50%.

| | old test (all) | A/B/C/D typed | A/B/C/D voice | A/B/C/D all | share sure | right when sure | right when unsure |
|---|---|---|---|---|---|---|---|
| before (untouched) | 27% | 71% | 100% | 84% | 91% | 88% | 50% |
| patch off | 27% | 71% | 100% | 84% | 91% | 88% | 50% |
| patch on | 44% | 62% | 95% | 78% | 96% | 81% | 0% |

## English kept

| | ARC-Easy | WikiText-2 perplexity |
|---|---|---|
| before (untouched) | 57% | 36.3 |
| patch off | 57% | 36.3 |
| patch on | 58% | 61.2 |

## Planning, patch on

| clean short | clean long | messy short | messy long | filler short | filler long |
|---|---|---|---|---|---|
| 79% | 79% | 67% | 75% | 42% | 33% |

## Training

- step 150: train 0.511, held-out 0.155
- step 300: train 0.155, held-out 0.114
- step 450: train 0.134, held-out 0.096
- step 600: train 0.121, held-out 0.084
- step 750: train 0.118, held-out 0.083
- step 900: train 0.110, held-out 0.076
- step 1050: train 0.106, held-out 0.076
- step 1200: train 0.089, held-out 0.077

## Its own reading of each message (stopped on its own 73%, repeats itself 0%)

- **[typed]** Wait what the fuck how much training do frontier models do how do they not take a fucking year!?
  - meant: How much compute frontier models use and how they finish training in months instead of years
  - read: How much training do frontier models do? How do they not take a fucking year?
- **[typed]** Chinchilla insight what!?
  - meant: An explanation of what the Chinchilla finding was and why it mattered
  - read: Chinchilla insight what?
- **[typed]** What about a stupidly small model and train it on trillions?
  - meant: Whether a tiny model trained on a huge amount of text keeps getting better
  - read: What about a stupidly small model and train it on trillions?
- **[typed]** Has anyone made a like multiple tiny very specific models like instead of layers keep a clean as shit divide?
  - meant: Whether anyone has built systems of many small specialist models with clean boundaries between them
  - read: Has anyone made a like multiple tiny very specific models instead of layers keep a clean as shit divide?
- **[typed]** How can I give you access to kraggle
  - meant: The steps to let the assistant start and read Kaggle runs on their behalf
  - read: How can I give you access to kraggle?
- **[typed]** Under the environmental KAGGLE if that matters
  - meant: To mention the secrets are stored inside a GitHub environment named KAGGLE, which may need a config change
  - read: Under the environmental KAGGLE, if that matters
- **[typed]** What the fuck are you talking about I use fetch all the damn time
  - meant: To push back on the claim that browsers can't fetch, since they use fetch all the time
  - read: What the fuck are you talking about?
- **[typed]** I seeee ok and there's no fun hack silly tricky ways to use like web assembly or workers or some other shit to make it work?
  - meant: Whether a trick like WebAssembly or workers can get around the browser's cross-site limits
  - read: I see ok and there's no fun hack silly tricky ways to use like web assembly or workers or some other shit to make it work?
- **[typed]** Cloudflare worker?
  - meant: An explanation of what a Cloudflare Worker is and how it would act as the relay
  - read: Cloudflare worker is one way to relay web requests for the browser.
- **[typed]** If this is gonna live in the browser what is to stop anyone who see that endpoint from just straight up seeing my key too?
  - meant: Whether a key used by a public browser page can be hidden from people who inspect it
  - read: If this is gonna live in the browser, what is to stop anyone who see that endpoint from just straight up seeing my key?
- **[typed]** I want public GitHub pages is why I said simple
  - meant: To explain they want it open because the page will be public on GitHub Pages
  - read: I want public GitHub pages is why I said simple
- **[typed]** Why do you need that?
  - meant: Why the assistant needs a Cloudflare token when the Cloudflare connector is already linked
  - read: Why do you need that?
- **[typed]** It's an account api key…
  - meant: To explain the secret they added is an account-level API key rather than a token
  - read: It's an account api key, so the deploy failed because Cloudflare rejected the token's format.
- **[typed]** I didn't add CLOUDFLARE_ACCOUNT_ID do you need that?
  - meant: Whether the deploy also needs the account ID secret, which they skipped
  - read: I didn't add CLOUDFLARE_ACCOUNT_ID, do you need that?
- **[typed]** could you have tested this locally and seen that it was a catastrophic failure?
  - meant: Whether the failure could have been caught by testing on the assistant's own machine first
  - read: could you have tested this locally and seen that it was a catastrophic failure?
- **[typed]** i meant like smaller scale test
  - meant: To clarify they meant a scaled-down version of the experiment, not the full run
  - read: i mean smaller scale test, but i can't test locally because it has no PyTorch and only two CPU cores.
- **[typed]** isnt REN what attention replaced? are we using attention and mlp?
  - meant: Whether entity networks were replaced by attention, and whether their model uses attention plus MLPs
  - read: Is REN what attention replaced? are we using attention and mlp?
- **[typed]** do we need a teacher?
  - meant: Whether the slots could work without a simulator telling them the true state
  - read: do we need a teacher?
- **[typed]** i have a gemini api key we could use to have gemini teach... if that would help?
  - meant: Whether using Gemini as the teacher during training would help
  - read: I have a gemini api key we could use to have gemini teach...
- **[typed]** the skins is running already we can run another while that one is going though
  - meant: To start the registers experiment now, in parallel, instead of waiting
  - read: the skins is running already we can run another while that one is going though.
- **[typed]** should you maybe rip out the lesson block or whatever? since it failed and see if the slots work better without lessons
  - meant: To drop the failed lesson block and test the slots on their own
  - read: Should you rip out the lesson block or whatever? since it failed and see if the slots work better without lessons?
- **[typed]** Don't worry about cost tell me the services that can
  - meant: A list of services that can actually run big training jobs, regardless of price
  - read: Don't worry about cost, tell me the services that can?
- **[typed]** Jesus fucking christ what are models like you opus 5.5 then?
  - meant: How big the assistant's own model is and how much it took to train
  - read: What are models like you opus 5.5?
- **[typed]** How is it getting better every 8 months if you say there isn't anything different about the blocks changing?
  - meant: How efficiency keeps improving if the transformer blocks supposedly haven't changed
  - read: How is it getting better every 8 months if you say there isn't anything different about the blocks changing?
- **[voice]** Uh, I'm curious if there are models that are already trained for this type of task. That are already really small. Um, and do a good job. Like maybe I think we'…
  - meant: To find existing small models and datasets on Hugging Face for cleaning up rambling speech
  - read: Is there a model that is already trained for this type of task? That are already really small. and do a good job. Maybe you could take a look at Hugging Face. Also, consider their data sets. Maybe there's some stuff there.
- **[voice]** So, uh, I'm curious how this um, this real test thing, if uh, how if it can do those other things and maybe registers does bring it up even more, uh, how would …
  - meant: How adding registers might change the results of the real-data experiment
  - read: How would registers potential right, any effect?
- **[voice]** I'm, I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. Like we have the goals thing, we have the the stories thin…
  - meant: Whether anything tests solving new kinds of problems it wasn't shown, by taking steps to figure them out
  - read: I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. Like we have the goals thing, we have the stories thing. But problem solving that's not provided to you. So you need to take steps to solve and to figure something out.
- **[voice]** I guess I want to discuss kind of like like for sure I'll get out of this uh, voice chat right after this and you can write down that sketch or whatever but lik…
  - meant: To brainstorm what small models are good at, and how a harness built for that exact model should work
  - read: I guess I want to discuss for sure I'll get out of this voice chat right after this and you can write down that sketch or whatever but I also just I do think maybe we could brainstorm or think through more realistically what makes a transformer model itself, what is it really good and capable at a
- **[voice]** Yeah, if you look at pretty much every previous project, and I'm pretty sure if you look at other chats that I've had with you, um, I always talk about it as li…
  - meant: To describe long-term memory as a store that learns their shorthand and keeps recent work close at hand
  - read: If you look at every previous project, and I'm pretty sure if you look at other chats that I've had with you, I always talk about it as there's a graph database behind it all. The harness would be responsible for pulling up relevant information that's needed and if the harness needs to
- **[voice]** So actually, uh, I want to counter what you said. About not deleting memory. Um, the whole point of this project is for it to be uh, a relatively small size uh,…
  - meant: To argue that unused knowledge it can fetch again should be deleted rather than kept forever
  - read: I want to counter what you said. About not deleting memory. The whole point of this project is for it to be a relatively small size, but also very capable. And I don't want it to start retaining a ton amount of data that it's not fucking using and it's never going to
- **[voice]** I'm kind of curious if you think that there is a uh, symbolic or like uh, deterministic NLP type way to take things that like um, that the way I talk and like, …
  - meant: Whether rule-based language processing could clean up their messy messages before a small model sees them
  - read: Is there a symbolic or deterministic NLP way to take things that the way I talk and just take any real example of any prompts that I've given you and then making them clean so that they are good to give to a small model?
- **[voice]** So I'm a little bit curious though. Um, Are you able to tell when a message was sent with voice?
  - meant: Whether the assistant can tell which of their messages were spoken rather than typed
  - read: Are you able to tell when a message was sent with voice?
- **[voice]** I've noticed, at least with ChatGPT, in their voice mode, it isn't the same Claude, or like it's not the same ChatGPT. Like, it's not the same model that I'm ta…
  - meant: Whether the voice assistant is the same model as the text one, or a different model passing messages along
  - read: At least with ChatGPT, in their voice mode, it isn't the same Claude, or it's not the same ChatGPT. When I'm talking to it, I'm curious if over here on in Anthropic's Claude AI, if the model that I'm talking to right now
- **[voice]** from training a model because uh, training a model is going to be really fucking expensive, and I don't think I ever realized how fucking expensive it is, even …
  - meant: To switch from training from scratch to fine-tuning an existing small model like SmolLM or Qwen
  - read: From training a model because training a model is going to be really fucking expensive, and I don't think I ever realized how fucking expensive it is, even for something that's not even a 1B, which I don't. I feel like I've tested 1B models, and I
- **[voice]** Um, yeah, I had actually, hold on. Sorry. So, um, one, one caveat. That I was just thinking about. I don't care how long it takes to do whatever it needs to do.…
  - meant: For the system to say what it doesn't know and show its progress while it figures it out
  - read: I had actually, hold on. Sorry. One, one caveat. I don't care how long it takes to do whatever it needs to do. Especially if it's like showing you, when you do something with Claude and it's like doing a bunch of like research and looking up web pages and
- **[voice]** also, something that I really, really, really, really, really don't want is for um, when you ask the user, it should not be something so stupid and straightforw…
  - meant: When the system asks them something, it should accept any kind of answer, like a ramble or a link
  - read: When you ask the user, it should not be something so stupid and straightforward as I don't understand what X is. Can you tell me in this specific structure? No, a user is never going to follow that structure. It's going to give you weird vagueness and the ums and
- **[voice]** I do not I don't know if this is something maybe there's already a, an existing small model out there. You can feel free to like check Hugging Face or just sear…
  - meant: Whether anyone has built an AI that comes up with genuinely new ideas, not just remixes
  - read: I don't know if this is something maybe there's already a existing small model out there. You can feel free to check Hugging Face or just search the web or whatever, but is there anybody who has tried to create a creative AI that it doesn't just piece together old pieces or whatever,
- **[voice]** And I know I do I do that referencing thing. That's why I keep saying like, oh, we need the harness to be able to pull shit from files from this and that and fr…
  - meant: To explain the harness must handle their messy, back-referencing way of talking, because that's how they talk
  - read: I know I do that referencing thing. That's why I keep saying like, we need the harness to be able to pull shit from files from this and that and from references from ages ago and have messy English parsing and all that stuff. I know that I'm not a good example of how you
- **[voice]** But the point is, like, I think that all this, everything I've been trying to figure out or trying to accomplish with all of these projects across the board is …
  - meant: To describe their goal: a system that finds out what it doesn't know through sources, search or smarter AIs
  - read: I think that all this everything I've been trying to figure out or trying to accomplish with all of these projects across the board is getting some type of base system in place. That can quote unquote figure shit out or figure it out. I want this system, whatever it is, if it doesn
- **[voice]** Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this like sm…
  - meant: How their small model would cope with their real messages, like a bare link, without a harness
  - read: Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this small model, how would that actually translate in a real if we didn't have the harness, we didn't have all this crap,
- **[voice]** Um, I'm open to having the model's base size be between like 200 and 500 megabytes. Is that even reasonable?
  - meant: Whether a model file of 200 to 500 megabytes is a realistic target
  - read: I'm open to having the model's base size be between 200 and 500 megabytes. Is that even reasonable?
- **[voice]** Um, I do want to add it. And I really like the thing that you were talking about from Margaret Bowden. Like those three ideas are Those are genuinely like what …
  - meant: To add creativity to the paper using Boden's three kinds, which match how they work
  - read: Add creativity to the paper.
- **[voice]** So I'm not trying, I'm not trying to like get us to go back to Napkin because Napkin was just like it was a very different project than the one we're working on…
  - meant: To clarify that Napkin was a separate no-LLM project, not something to go back to
  - read: I'm not trying to get us to go back to Napkin because Napkin was just a very different project than the one we're working on. With, but Napkin, I was trying to not have an LLM at all. I didn't want an LLM. It looked up the
- **[voice]** And then the only other thing is like, I know that we tend to do these in one notebook, uh, do you think that we could run all of them as separate notebooks so …
  - meant: To split the experiments into separate notebooks that run at the same time
  - read: And then the only other thing is like, I know that we tend to do these in one notebook, do you think that we could run all of them as separate notebooks so that they run in parallel instead of one after the other?
- **[voice]** Yeah, con I want you to instead of this time, actually, sorry, can we try to write up a paper for this? That is completely devoid of any type of like implementa…
  - meant: A write-up of the core idea as a paper, with no implementation details
  - read: I want you to instead of this time, can we try to write up a paper for this? That is completely devoid of any type of implementation details, and just really gets to the heart of what we're trying to achieve.
