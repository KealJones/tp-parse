// Stand-in for app/src/embed.js: phones run with embeddings off (BM25 only).
export const embedReady = () => false;
export function loadEmbedder() { return Promise.resolve(false); }
export async function embed() { return null; }
