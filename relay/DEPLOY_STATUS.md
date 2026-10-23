# Relay deploy

Deploy failed (exit 1). Last lines of the wrangler output:

```

 ⛅️ wrangler 4.152.0
────────────────────

Cloudflare collects anonymous telemetry about your usage of Wrangler. Learn more at https://github.com/cloudflare/workers-sdk/tree/main/packages/wrangler/telemetry.md

[31m✘ [41;31m[[41;97mERROR[41;31m][0m [1mA request to the Cloudflare API (/accounts) failed.[0m

  Invalid request headers [code: 6003]
  
  - Invalid format for Authorization header [code: 6111]

  
  If you think this is a bug, please open an issue at: [4mhttps://github.com/cloudflare/workers-sdk/issues/new/choose[0m


🪵  Logs were written to "/home/runner/.config/.wrangler/logs/wrangler-2026-10-23_02-09-51_040.log"
```

Token shape (no value shown): length 32 raw / 32 cleaned; whitespace removed: no; only hex: yes
