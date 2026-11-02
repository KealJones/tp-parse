// tp-relay: fetches a web page server-side and returns it with CORS headers, so a browser-based harness can read it.
// Locked by default: every request needs an x-relay-key header matching the RELAY_KEY secret. With no RELAY_KEY set,
// it refuses everything rather than running as an open proxy. Set ALLOWED_ORIGIN to lock it to one page.
interface Env {
  RELAY_KEY?: string;
  ALLOWED_ORIGIN: string;
}

const MAX_BYTES = 5 * 1024 * 1024; // refuse to relay anything larger than 5 MB

// Only public web addresses: no localhost, private ranges, link-local or odd ports.
function allowedTarget(raw: string | null): URL | null {
  if (!raw) return null;
  let u: URL;
  try { u = new URL(raw); } catch { return null; }
  if (u.protocol !== "https:" && u.protocol !== "http:") return null;
  if (u.username || u.password) return null;
  if (u.port && u.port !== "80" && u.port !== "443") return null;
  const h = u.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (h === "localhost" || h.endsWith(".localhost") || h.endsWith(".local") || h.endsWith(".internal")) return null;
  if (/^(0|10|127)\./.test(h) || /^169\.254\./.test(h) || /^192\.168\./.test(h) || /^172\.(1[6-9]|2\d|3[01])\./.test(h)) return null;
  if (/^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(h)) return null;
  if (h.includes(":") && (h === "::1" || h.startsWith("fc") || h.startsWith("fd") || h.startsWith("fe80"))) return null;
  return u;
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
    const target = allowedTarget(new URL(req.url).searchParams.get("url"));
    if (!target) return new Response("pass ?url= with a public http(s) address", { status: 400, headers: cors });
    try {
      const r = await fetch(target.toString(), { headers: { "User-Agent": "Mozilla/5.0 (compatible; tp-relay)" }, redirect: "follow" });
      const final = allowedTarget(r.url);
      if (!final) return new Response("redirected to a non-public address", { status: 400, headers: cors });
      const len = Number(r.headers.get("Content-Length") ?? 0);
      if (len > MAX_BYTES) return new Response("page too large", { status: 413, headers: cors });
      const body = await r.arrayBuffer();
      if (body.byteLength > MAX_BYTES) return new Response("page too large", { status: 413, headers: cors });
      return new Response(body, {
        status: r.status,
        headers: { ...cors, "Content-Type": r.headers.get("Content-Type") ?? "text/plain", "X-Final-Url": r.url },
      });
    } catch (e) {
      return new Response(`fetch failed: ${e}`, { status: 502, headers: cors });
    }
  },
};
