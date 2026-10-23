# tp-relay

A tiny Cloudflare Worker that fetches a web page and hands it back with CORS headers, so a harness running in the browser can read pages that don't allow cross-site requests.

    fetch(`${RELAY_URL}/?url=${encodeURIComponent(page)}`)

It is open for now. To lock it later, add a `RELAY_KEY` secret to the Worker (`npx wrangler secret put RELAY_KEY` in this folder, or in the Cloudflare dashboard); from then on every request needs a matching `x-relay-key` header. For real login, put Cloudflare Access in front of it.

Deployed by `.github/workflows/relay-deploy.yml` on every change here. It needs these in the GitHub environment `CLOUDFLARE`:
- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token from the "Edit Cloudflare Workers" template
- `CLOUDFLARE_ACCOUNT_ID` (optional): only needed if the token can see more than one account

Each deploy writes `DEPLOY_STATUS.md` with the URL and a live check.
