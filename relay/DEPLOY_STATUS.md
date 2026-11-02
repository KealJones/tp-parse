# Relay deploy

Locked: requests need an `x-relay-key` header.

- without a key: HTTP 403 (should be 403)
- with the key, fetch https://example.com: HTTP 403, page fetched: no
- checked: 2026-11-02T02:21:48Z
