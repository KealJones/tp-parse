# tp-relay

A tiny Cloudflare Worker that fetches a web page and hands it back with CORS headers, so a harness running in the browser can read pages that don't allow cross-site requests.

    fetch(`${RELAY_URL}/?url=${encodeURIComponent(page)}`, { headers: { "x-relay-key": RELAY_KEY } })

Requests without the right `x-relay-key` get a 403, so it can't be used as an open proxy. Set `ALLOWED_ORIGIN` in `wrangler.toml` to your page's origin to lock it down further.

Deployed by `.github/workflows/relay-deploy.yml` on every change here. It needs these in the GitHub environment `CLOUDFLARE`:
- `CLOUDFLARE_API_TOKEN`: a Cloudflare API token from the "Edit Cloudflare Workers" template
- `RELAY_KEY`: any long random string; the harness sends it with every request
- `CLOUDFLARE_ACCOUNT_ID` (optional): only needed if the token can see more than one account

Each deploy writes `DEPLOY_STATUS.md` with the URL and a live check.
