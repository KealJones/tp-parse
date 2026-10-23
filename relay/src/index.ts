// tp-relay: fetches a web page server-side and returns it with CORS headers, so a browser-based harness can read it.
// Only answers requests that carry the secret x-relay-key header. Set ALLOWED_ORIGIN to lock it to one page.
interface Env {
  RELAY_KEY: string;
  ALLOWED_ORIGIN: string;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const cors = {
      "Access-Control-Allow-Origin": env.ALLOWED_ORIGIN || "*",
      "Access-Control-Allow-Headers": "x-relay-key",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "GET") return new Response("GET only", { status: 405, headers: cors });
    if (!env.RELAY_KEY || req.headers.get("x-relay-key") !== env.RELAY_KEY) {
      return new Response("forbidden", { status: 403, headers: cors });
    }
    const target = new URL(req.url).searchParams.get("url");
    if (!target || !/^https?:\/\//i.test(target)) return new Response("pass ?url=https://...", { status: 400, headers: cors });
    try {
      const r = await fetch(target, { headers: { "User-Agent": "Mozilla/5.0 (compatible; tp-relay)" }, redirect: "follow" });
      return new Response(r.body, {
        status: r.status,
        headers: { ...cors, "Content-Type": r.headers.get("Content-Type") ?? "text/plain", "X-Final-Url": r.url },
      });
    } catch (e) {
      return new Response(`fetch failed: ${e}`, { status: 502, headers: cors });
    }
  },
};
