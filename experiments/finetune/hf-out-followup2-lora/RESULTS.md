# Follow-up 2, arm `lora`

Qwen/Qwen3-0.6B on NVIDIA A10G, 28 min total. LoRA rank 16 on all linear layers, slots off, replay 0%, learning rate 0.0002, early stopping off. Ran 1500 of 1500 steps. Training examples: {'plan': 5900, 'read': 11800, 'replay': 0, 'val': 300}. None of Keal's messages were in training.

## Keal's real messages, four options (chance 25%)

New test: all four shown as A/B/C/D, so it's a real choice. "Sure" means it gave its pick at least 50%.

| | old test (all) | A/B/C/D typed | A/B/C/D voice | A/B/C/D all | share sure | right when sure | right when unsure |
|---|---|---|---|---|---|---|---|
| before (untouched) | 27% | 71% | 100% | 84% | 91% | 88% | 50% |
| patch off | 27% | 71% | 100% | 84% | 91% | 88% | 50% |
| patch on | 38% | 50% | 67% | 58% | 47% | 81% | 38% |

## English kept

| | ARC-Easy | WikiText-2 perplexity |
|---|---|---|
| before (untouched) | 57% | 36.3 |
| patch off | 57% | 36.3 |
| patch on | 52% | 67.9 |

## Planning, patch on

| clean short | clean long | messy short | messy long | filler short | filler long |
|---|---|---|---|---|---|
| 100% | 100% | 100% | 100% | 100% | 100% |

## Training

- step 150: train 0.271, held-out 0.083
- step 300: train 0.037, held-out 0.075
- step 450: train 0.033, held-out 0.064
- step 600: train 0.034, held-out 0.058
- step 750: train 0.025, held-out 0.053
- step 900: train 0.020, held-out 0.046
- step 1050: train 0.020, held-out 0.045
- step 1200: train 0.016, held-out 0.046
- step 1350: train 0.015, held-out 0.042
- step 1500: train 0.014, held-out 0.041

## Its own reading of each message (stopped on its own 73%, repeats itself 0%)

- **[typed]** Wait what the fuck how much training do frontier models do how do they not take a fucking year!?
  - meant: How much compute frontier models use and how they finish training in months instead of years
  - read: How much training do frontier models do, how do they not take a year?
- **[typed]** Chinchilla insight what!?
  - meant: An explanation of what the Chinchilla finding was and why it mattered
  - read: Chinchilla insight what?
- **[typed]** What about a stupidly small model and train it on trillions?
  - meant: Whether a tiny model trained on a huge amount of text keeps getting better
  - read: What about a stupidly small model and train it on trillions?
- **[typed]** Has anyone made a like multiple tiny very specific models like instead of layers keep a clean as shit divide?
  - meant: Whether anyone has built systems of many small specialist models with clean boundaries between them
  - read: Has anyone made a multiple tiny very specific models instead of layers keep a clean divide?
- **[typed]** How can I give you access to kraggle
  - meant: The steps to let the assistant start and read Kaggle runs on their behalf
  - read: How can I give you access to kraggle?
- **[typed]** Under the environmental KAGGLE if that matters
  - meant: To mention the secrets are stored inside a GitHub environment named KAGGLE, which may need a config change
  - read: Under the environmental KAGGLE, add the secrets to the GitHub repo, and they said they added them.
- **[typed]** What the fuck are you talking about I use fetch all the damn time
  - meant: To push back on the claim that browsers can't fetch, since they use fetch all the time
  - read: What are you talking about? I use fetch all the time.
- **[typed]** I seeee ok and there's no fun hack silly tricky ways to use like web assembly or workers or some other shit to make it work?
  - meant: Whether a trick like WebAssembly or workers can get around the browser's cross-site limits
  - read: I see ok and there's no fun hack, silly, tricky ways to use web assembly or workers or some other shit to make it work?
- **[typed]** Cloudflare worker?
  - meant: An explanation of what a Cloudflare Worker is and how it would act as the relay
  - read: The assistant listed a Cloudflare Worker as one way to relay web requests for the browser.
- **[typed]** If this is gonna live in the browser what is to stop anyone who see that endpoint from just straight up seeing my key too?
  - meant: Whether a key used by a public browser page can be hidden from people who inspect it
  - read: If this is gonna live in the browser, what is to stop anyone who see that endpoint from just straight up seeing my key too?
- **[typed]** I want public GitHub pages is why I said simple
  - meant: To explain they want it open because the page will be public on GitHub Pages
  - read: Public GitHub pages is why I said simple?
- **[typed]** Why do you need that?
  - meant: Why the assistant needs a Cloudflare token when the Cloudflare connector is already linked
  - read: Why do you need that?
- **[typed]** It's an account api key…
  - meant: To explain the secret they added is an account-level API key rather than a token
  - read: It's an account api key
- **[typed]** I didn't add CLOUDFLARE_ACCOUNT_ID do you need that?
  - meant: Whether the deploy also needs the account ID secret, which they skipped
  - read: I didn't add CLOUDFLARE_ACCOUNT_ID do you need that?
- **[typed]** could you have tested this locally and seen that it was a catastrophic failure?
  - meant: Whether the failure could have been caught by testing on the assistant's own machine first
  - read: Could you have tested this locally and seen that it was a catastrophic failure?
- **[typed]** i meant like smaller scale test
  - meant: To clarify they meant a scaled-down version of the experiment, not the full run
  - read: I meant smaller scale test
- **[typed]** isnt REN what attention replaced? are we using attention and mlp?
  - meant: Whether entity networks were replaced by attention, and whether their model uses attention plus MLPs
  - read: Isnt REN what attention replaced? are we using attention and mlp?
- **[typed]** do we need a teacher?
  - meant: Whether the slots could work without a simulator telling them the true state
  - read: Do we need a teacher?
- **[typed]** i have a gemini api key we could use to have gemini teach... if that would help?
  - meant: Whether using Gemini as the teacher during training would help
  - read: I have a gemini api key we could use to have gemini teach... if that would help?
- **[typed]** the skins is running already we can run another while that one is going though
  - meant: To start the registers experiment now, in parallel, instead of waiting
  - read: The skins is running already, we can run another while that one is going though.
- **[typed]** should you maybe rip out the lesson block or whatever? since it failed and see if the slots work better without lessons
  - meant: To drop the failed lesson block and test the slots on their own
  - read: Should you maybe rip out the lesson block? since it failed and see if the slots work better without lessons?
- **[typed]** Don't worry about cost tell me the services that can
  - meant: A list of services that can actually run big training jobs, regardless of price
  - read: Don't worry about cost tell me the services that can be done on Kaggle and on rented GPUs.
- **[typed]** Jesus fucking christ what are models like you opus 5.5 then?
  - meant: How big the assistant's own model is and how much it took to train
  - read: What are models like you opus 5.5 then?
- **[typed]** How is it getting better every 8 months if you say there isn't anything different about the blocks changing?
  - meant: How efficiency keeps improving if the transformer blocks supposedly haven't changed
  - read: How is it getting better every 8 months if you say there isn't anything different about the blocks changing?
- **[voice]** Uh, I'm curious if there are models that are already trained for this type of task. That are already really small. Um, and do a good job. Like maybe I think we'…
  - meant: To find existing small models and datasets on Hugging Face for cleaning up rambling speech
  - read: I'm curious if there are models that are already trained for this type of task. And do a good job. Maybe I think we're connected to Hugging Face. Maybe you could take a look at Hugging Face. Also, consider their data sets. Maybe there's some stuff there.
- **[voice]** So, uh, I'm curious how this um, this real test thing, if uh, how if it can do those other things and maybe registers does bring it up even more, uh, how would …
  - meant: How adding registers might change the results of the real-data experiment
  - read: How if it can do those other things and maybe registers does bring it up even more, how would registers potential right, any effect?
- **[voice]** I'm, I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. Like we have the goals thing, we have the the stories thin…
  - meant: Whether anything tests solving new kinds of problems it wasn't shown, by taking steps to figure them out
  - read: I think I'm mostly wondering if we have done anything to consider how it problem solves. Better. We have the goals thing, we have the stories thing. But problem solving that's not provided to you. So that you need to take steps to solve and to figure something out.
- **[voice]** I guess I want to discuss kind of like like for sure I'll get out of this uh, voice chat right after this and you can write down that sketch or whatever but lik…
  - meant: To brainstorm what small models are good at, and how a harness built for that exact model should work
  - read: I guess I want to discuss for sure I'll get out of this voice chat right after this and you can write down that sketch but I also just I do think maybe we could brainstorm or think through more realistically what makes a transformer or the model itself what is it really good and capable at a really
- **[voice]** Yeah, if you look at pretty much every previous project, and I'm pretty sure if you look at other chats that I've had with you, um, I always talk about it as li…
  - meant: To describe long-term memory as a store that learns their shorthand and keeps recent work close at hand
  - read: If you look at pretty much every previous project, and I'm pretty sure if you look at other chats that I've had with you, I always talk about it as there's a graph database behind it all. And the harness would be responsible for pulling up relevant information that's needed and if the
- **[voice]** So actually, uh, I want to counter what you said. About not deleting memory. Um, the whole point of this project is for it to be uh, a relatively small size uh,…
  - meant: To argue that unused knowledge it can fetch again should be deleted rather than kept forever
  - read: I want to counter what you said. About not deleting memory. The whole point of this project is for it to be a relatively small size but also very capable. And I don't want it to start retaining a ton amount of data that it's not using and it's never going to use again
- **[voice]** I'm kind of curious if you think that there is a uh, symbolic or like uh, deterministic NLP type way to take things that like um, that the way I talk and like, …
  - meant: Whether rule-based language processing could clean up their messy messages before a small model sees them
  - read: If you think that there is a symbolic or deterministic NLP type way to take things that the way I talk and just take any real example of any prompts that I've given you and then making them clean so that they are good to give to a small model.
- **[voice]** So I'm a little bit curious though. Um, Are you able to tell when a message was sent with voice?
  - meant: Whether the assistant can tell which of their messages were spoken rather than typed
  - read: Are you able to tell when a message was sent with voice?
- **[voice]** I've noticed, at least with ChatGPT, in their voice mode, it isn't the same Claude, or like it's not the same ChatGPT. Like, it's not the same model that I'm ta…
  - meant: Whether the voice assistant is the same model as the text one, or a different model passing messages along
  - read: At least with ChatGPT, in their voice mode, it isn't the same Claude, or it's not the same ChatGPT. it's not the same model that I'm talking to. When I'm talking to it, I'm curious if over here on in Anthropic's Claude
- **[voice]** from training a model because uh, training a model is going to be really fucking expensive, and I don't think I ever realized how fucking expensive it is, even …
  - meant: To switch from training from scratch to fine-tuning an existing small model like SmolLM or Qwen
  - read: From training a model because training a model is going to be really fucking expensive, and I don't think I ever realized how fucking expensive it is, even for something that's not even a 1B, which I don't. I feel like I've tested 1B models, and I
- **[voice]** Um, yeah, I had actually, hold on. Sorry. So, um, one, one caveat. That I was just thinking about. I don't care how long it takes to do whatever it needs to do.…
  - meant: For the system to say what it doesn't know and show its progress while it figures it out
  - read: I had actually, hold on. Sorry. One caveat. That I was just thinking about. I don't care how long it takes to do whatever it needs to do. Especially if it's showing when you do something with Claude and it's doing a bunch of research and looking up web pages and
- **[voice]** also, something that I really, really, really, really, really don't want is for um, when you ask the user, it should not be something so stupid and straightforw…
  - meant: When the system asks them something, it should accept any kind of answer, like a ramble or a link
  - read: Something that I really, really, really, don't want is for when you ask the user, it should not be something so stupid and straightforward as I don't understand what X is. Can you tell me in this specific structure? No, a user is never going to follow that structure. It
- **[voice]** I do not I don't know if this is something maybe there's already a, an existing small model out there. You can feel free to like check Hugging Face or just sear…
  - meant: Whether anyone has built an AI that comes up with genuinely new ideas, not just remixes
  - read: I don't know if this is something maybe there's already an existing small model out there. You can feel free to check Hugging Face or just search the web, but is there anybody who has tried to create a creative AI something that it doesn't just piece together old pieces or maybe it's
- **[voice]** And I know I do I do that referencing thing. That's why I keep saying like, oh, we need the harness to be able to pull shit from files from this and that and fr…
  - meant: To explain the harness must handle their messy, back-referencing way of talking, because that's how they talk
  - read: I know I do I do that referencing thing. That's why I keep saying like, we need the harness to be able to pull shit from files from this and that and from references from ages ago and have messy English parsing and all that stuff. I know that I'm not a good example of
- **[voice]** But the point is, like, I think that all this, everything I've been trying to figure out or trying to accomplish with all of these projects across the board is …
  - meant: To describe their goal: a system that finds out what it doesn't know through sources, search or smarter AIs
  - read: I think that all this, everything I've been trying to figure out or trying to accomplish with all of these projects across the board is getting some type of base system in place. That can quote unquote figure shit out or figure it out. I want this system, whatever it is, if it
- **[voice]** Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this like sm…
  - meant: How their small model would cope with their real messages, like a bare link, without a harness
  - read: Just look at our chat, like genuinely analyze my specific messages to you and consider what I'm asking of you and if I were to do the same thing to this small model, how would that actually translate in a real if we didn't have the harness, we didn't have all this crap,
- **[voice]** Um, I'm open to having the model's base size be between like 200 and 500 megabytes. Is that even reasonable?
  - meant: Whether a model file of 200 to 500 megabytes is a realistic target
  - read: I'm open to having the model's base size be between 200 and 500 megabytes. Is that even reasonable?
- **[voice]** Um, I do want to add it. And I really like the thing that you were talking about from Margaret Bowden. Like those three ideas are Those are genuinely like what …
  - meant: To add creativity to the paper using Boden's three kinds, which match how they work
  - read: I do want to add it. And I really like the thing that you were talking about from Margaret Bowden. Those three ideas are genuinely what I do. I don't intentionally do them that way, but like that is how I work. I do a lot of derivatives and parody.
- **[voice]** So I'm not trying, I'm not trying to like get us to go back to Napkin because Napkin was just like it was a very different project than the one we're working on…
  - meant: To clarify that Napkin was a separate no-LLM project, not something to go back to
  - read: I'm not trying to get us to go back to Napkin because Napkin was just a very different project than the one we're working on. With Napkin, I was trying to not have an LLM at all. I didn't want an LLM. And it looked up the senses
- **[voice]** And then the only other thing is like, I know that we tend to do these in one notebook, uh, do you think that we could run all of them as separate notebooks so …
  - meant: To split the experiments into separate notebooks that run at the same time
  - read: And then the only other thing is I know that we tend to do these in one notebook, do you think that we could run all of them as separate notebooks so that they run in parallel instead of one after the other?
- **[voice]** Yeah, con I want you to instead of this time, actually, sorry, can we try to write up a paper for this? That is completely devoid of any type of like implementa…
  - meant: A write-up of the core idea as a paper, with no implementation details
  - read: Con I want you to instead of this time, sorry, can we try to write up a paper for this? That is completely devoid of any type of implementation details, and just really gets to the heart of what we're trying to achieve.
