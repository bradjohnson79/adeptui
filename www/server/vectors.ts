const DIM = 256;

export function tokenize(value: string): string[] {
  return value
    .toLowerCase()
    .split(/[^a-z0-9_+.:/_-]+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 1);
}

const stop = new Set([
  "the",
  "and",
  "for",
  "with",
  "that",
  "this",
  "from",
  "your",
  "you",
  "are",
  "was",
  "how",
  "what",
  "why",
  "where",
  "when",
  "does",
  "can",
  "not",
  "into",
  "about",
  "have",
  "has",
  "should",
  "would",
  "could",
  "please",
  "need",
  "just",
  "only",
  "than",
  "then",
  "also",
  "been",
  "were",
  "their",
  "them",
  "they",
  "some",
  "such",
]);

export function contentTokens(value: string): string[] {
  const tokens = tokenize(value).filter((token) => !stop.has(token));
  const folded: string[] = [];
  for (const token of tokens) {
    folded.push(token);
    if (token.length > 4 && token.endsWith("s") && !token.endsWith("ss")) folded.push(token.slice(0, -1));
  }
  return folded;
}

function hashToken(token: string): number {
  let hash = 2166136261;
  for (let index = 0; index < token.length; index += 1) {
    hash ^= token.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** Local vector so retrieval works without a hosted embedding call. */
export function embedText(value: string): number[] {
  const vector = new Array<number>(DIM).fill(0);
  const tokens = contentTokens(value);
  for (const token of tokens) {
    const hash = hashToken(token);
    const bucket = hash % DIM;
    vector[bucket] = (vector[bucket] ?? 0) + ((hash & 1) === 0 ? 1 : -1);
    if (token.length > 4) {
      const stem = hashToken(token.slice(0, 5));
      const stemBucket = stem % DIM;
      vector[stemBucket] = (vector[stemBucket] ?? 0) + 0.35;
    }
  }
  let norm = 0;
  for (const value of vector) norm += value * value;
  norm = Math.sqrt(norm) || 1;
  return vector.map((value) => value / norm);
}

export function cosine(left: number[], right: number[]): number {
  const length = Math.min(left.length, right.length);
  let score = 0;
  for (let index = 0; index < length; index += 1) score += (left[index] ?? 0) * (right[index] ?? 0);
  return score;
}

/**
 * Filmmaker wording mapped onto documentation terms.
 * This expands the query only. It is not a second copy of the docs.
 */
const expansions: Record<string, string[]> = {
  size: ["resolution", "aspect"],
  sizes: ["resolution", "aspect"],
  dimension: ["resolution", "aspect"],
  dimensions: ["resolution", "aspect"],
  gpu: ["local", "video", "memory"],
  vram: ["gpu", "local", "memory"],
  graphics: ["gpu", "local"],
  install: ["installer", "setup", "desktop"],
  installation: ["installer", "setup"],
  download: ["installer", "desktop"],
  linux: ["linux", "desktop", "platform"],
  mac: ["macos", "desktop"],
  windows: ["windows", "desktop"],
  failed: ["failed", "troubleshooting", "generation"],
  stuck: ["stuck", "troubleshooting", "generation"],
  error: ["troubleshooting", "failed"],
  stored: ["storage", "files", "setup"],
  storage: ["stored", "files", "setup"],
  github: ["github", "repository", "source"],
  huggingface: ["hugging", "face"],
  "hugging": ["huggingface", "face"],
};

export function expandQuery(value: string): string {
  const tokens = tokenize(value);
  const extra = tokens.flatMap((token) => expansions[token] ?? []);
  return [...tokens, ...extra].join(" ");
}
