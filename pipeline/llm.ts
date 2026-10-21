// Minimal Anthropic Messages API client with retries. No SDK, just fetch.
//
// Needs ANTHROPIC_API_KEY. ANTHROPIC_BASE_URL can point somewhere else
// (the pipeline's tests point it at a local mock server).

export interface LlmRequest {
  system: string;
  user: string;
  model: string;
  maxTokens?: number;
  temperature?: number;
}

export interface LlmResponse {
  text: string;
  stopReason: string;
  inputTokens: number;
  outputTokens: number;
}

const RETRYABLE = new Set([408, 409, 429, 500, 502, 503, 504, 529]);

export async function callClaude(req: LlmRequest, attempts = 6): Promise<LlmResponse> {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error('ANTHROPIC_API_KEY is not set. Get a key at console.anthropic.com and export it before running.');
  const base = process.env.ANTHROPIC_BASE_URL ?? 'https://api.anthropic.com';

  for (let attempt = 1; ; attempt++) {
    let res: Response;
    try {
      res = await fetch(`${base}/v1/messages`, {
        method: 'POST',
        headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({
          model: req.model,
          max_tokens: req.maxTokens ?? 2048,
          temperature: req.temperature ?? 0.3,
          system: req.system,
          messages: [{ role: 'user', content: req.user }],
        }),
      });
    } catch (err) {
      if (attempt >= attempts) throw err;
      await sleep(backoff(attempt));
      continue;
    }

    if (res.ok) {
      const body = (await res.json()) as {
        content: { type: string; text?: string }[];
        stop_reason: string;
        usage: { input_tokens: number; output_tokens: number };
      };
      return {
        text: body.content.filter((b) => b.type === 'text').map((b) => b.text ?? '').join('').trim(),
        stopReason: body.stop_reason,
        inputTokens: body.usage?.input_tokens ?? 0,
        outputTokens: body.usage?.output_tokens ?? 0,
      };
    }

    const detail = await res.text().catch(() => '');
    if (!RETRYABLE.has(res.status) || attempt >= attempts) {
      throw new Error(`API error ${res.status}: ${detail.slice(0, 300)}`);
    }
    const retryAfter = Number(res.headers.get('retry-after'));
    await sleep(Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : backoff(attempt));
  }
}

function backoff(attempt: number): number {
  return Math.min(60_000, 1000 * 2 ** (attempt - 1)) * (0.5 + Math.random() / 2);
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
