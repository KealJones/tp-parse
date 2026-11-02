# tp-relay

A tiny Cloudflare Worker that fetches a web page and hands it back with CORS headers, so a harness running in the browser can read pages that don't allow cross-site requests.

    fetch(`${RELAY_URL}/?url=${encodeURIComponent(page)}`, { headers: { "x-relay-key": RELAY_KEY } })

It is locked: every request needs an `x-relay-key` header that matches the Worker's `RELAY_KEY` secret, and with no `RELAY_KEY` set it refuses everything. It only fetches public `http`/`https` addresses (no localhost, private ranges or unusual ports, including after redirects) and refuses pages over 5 MB. Set `ALLOWED_ORIGIN` in `wrangler.toml` to lock it to one page. For real login, put Cloudflare Access in front of it.

Deployed by `.github/workflows/relay-deploy.yml` on every change here. It needs these in the GitHub environment `CLOUDFLARE`:
- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token from the "Edit Cloudflare Workers" template
- `CLOUDFLARE_ACCOUNT_ID` (optional): only needed if the token can see more than one account
- `RELAY_KEY`: the shared key. The workflow sets it as the Worker's secret on each deploy and uses it for the live check. Without it the relay stays locked and the check reports 403.

Each deploy writes `DEPLOY_STATUS.md` with a live check.
