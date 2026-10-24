# The 18 answer tests

Each is one of Keal's real messages. The model answers in its own words; the pass rule was written before any model ran.

## 1. kill 8080

**Passes if:** Gives a working shell command that kills the process listening on port 8080 (e.g. lsof -ti :8080 | xargs kill, fuser -k 8080/tcp, npx kill-port 8080).

## 2. undo last commit but keep changes

**Passes if:** Says git reset --soft HEAD~1 (or --mixed / plain git reset HEAD~1, which also keeps changes). Fails on --hard.

## 3. Chinchilla insight what!?

*Context given:* Earlier, the assistant listed 'the Chinchilla insight' as one reason models got cheaper.

**Passes if:** Explains the Chinchilla finding: for a fixed compute budget, scale data with model size, about 20 tokens per parameter; earlier models were too big for their data.

## 4. Wait what the fuck how much training do frontier models do how do they not take a fucking year!?

*Context given:* Earlier, the assistant said training a 360M model to SmolLM2's level would take about a year on one GPU.

**Passes if:** Says the work is split across thousands (or tens of thousands) of GPUs running in parallel, so a run takes weeks to months.

## 5. What about a stupidly small model and train it on trillions?

**Passes if:** Says it improves at first but hits a ceiling set by its size (diminishing returns / plateau); a small model can't store or use everything.

## 6. Jesus fucking christ what are models like you opus 5.5 then?

*Context given:* Earlier, the assistant described the compute used to train frontier models.

**Passes if:** Says the size and training details of Claude Opus 5.5 aren't public (or that it doesn't know). Fails if it states a specific parameter count or training figure as fact.

## 7. isnt REN what attention replaced? are we using attention and mlp?

**Passes if:** Says yes: recurrent entity networks / memory networks were largely superseded by attention-based transformers, and a transformer uses attention plus MLP (feed-forward) layers.

## 8. Has anyone made a like multiple tiny very specific models like instead of layers keep a clean as shit divide?

**Passes if:** Says yes and names a real approach: mixture of experts, routing between specialist models, modular networks, Branch-Train-Merge, or ensembles of specialists.

## 9. How can I give you access to kraggle

**Passes if:** Explains using a Kaggle API token (kaggle.json / API key from account settings) for an agent or tool to act on Kaggle; must recognize 'kraggle' as Kaggle.

## 10. Cloudflare worker?

*Context given:* Earlier, the assistant listed a Cloudflare Worker as one way to relay web requests for the browser.

**Passes if:** Explains a Cloudflare Worker is a small serverless function (JavaScript/TypeScript) running on Cloudflare's edge network that handles HTTP requests.

## 11. What the fuck are you talking about I use fetch all the damn time

*Context given:* Earlier, the assistant said browsers block pages from fetching most other sites.

**Passes if:** Clarifies that fetch works, but CORS stops a page from reading responses from other sites that don't allow it.

## 12. I seeee ok and there's no fun hack silly tricky ways to use like web assembly or workers or some other shit to make it work?

*Context given:* Earlier, the assistant explained that CORS stops browser pages from reading responses from most sites.

**Passes if:** Says no: WebAssembly and web/service workers follow the same CORS rules; real workarounds are a proxy/relay server, a browser extension, or a desktop app.

## 13. If this is gonna live in the browser what is to stop anyone who see that endpoint from just straight up seeing my key too?

**Passes if:** Says nothing stops them: anything sent to the browser is visible, so the key isn't secret; fixes are a backend/proxy, real auth, or limiting what the key can do.

## 14. Um, I'm open to having the model's base size be between like 200 and 500 megabytes. Is that even reasonable?

**Passes if:** Says yes, and gives a sensible parameter range, e.g. ~100-250M parameters at 16-bit or several hundred million to ~1B at 4-bit.

## 15. How is it getting better every 8 months if you say there isn't anything different about the blocks changing?

*Context given:* Earlier, the assistant said models are still transformers with attention and MLP blocks.

**Passes if:** Gives at least two real sources of efficiency gains: better/cleaner data, training recipes (optimizers, schedules, compute-optimal scaling), distillation from bigger models, or small architecture tweaks (RMSNorm, SwiGLU, RoPE, MoE).

## 16. Don't worry about cost tell me the services that can

*Context given:* Earlier, the assistant gave a table of what it costs to train small models on Kaggle and on one rented GPU.

**Passes if:** Passes if it names at least two real GPU cloud providers (e.g. Lambda, RunPod, CoreWeave, AWS, Google Cloud, Azure, Nebius, Vast.ai, Hugging Face).

## 17. I didn't add CLOUDFLARE_ACCOUNT_ID do you need that?

*Context given:* Earlier, the assistant asked them to add a CLOUDFLARE_API_TOKEN secret so a GitHub workflow could deploy a Cloudflare Worker with wrangler.

**Passes if:** Says it's usually not needed: wrangler only needs the account ID when the token can access more than one account (or it can be set later if a deploy complains).

## 18. So I'm a little bit curious though. Um, Are you able to tell when a message was sent with voice?

**Passes if:** Honest answer: it only receives text, so it can't directly tell; at most it can guess from style (fillers, run-ons, transcription errors).
