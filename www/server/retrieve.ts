import type { GuidePage, ScoredChunk, StoredChunk } from "./types";
import { contentTokens, cosine, embedText, expandQuery, tokenize } from "./vectors";

type Posting = { length: number; freq: Map<string, number> };

function postings(chunks: StoredChunk[]): { docs: Posting[]; df: Map<string, number>; avg: number } {
  const docs: Posting[] = [];
  const df = new Map<string, number>();
  let total = 0;
  for (const chunk of chunks) {
    const tokens = contentTokens(`${chunk.title} ${chunk.heading} ${chunk.tags.join(" ")} ${chunk.text}`);
    const freq = new Map<string, number>();
    for (const token of tokens) freq.set(token, (freq.get(token) ?? 0) + 1);
    total += tokens.length;
    docs.push({ length: tokens.length || 1, freq });
    for (const token of freq.keys()) df.set(token, (df.get(token) ?? 0) + 1);
  }
  return { docs, df, avg: total / Math.max(chunks.length, 1) };
}

function bm25(query: string[], docs: Posting[], df: Map<string, number>, avg: number, count: number): number[] {
  const k1 = 1.2;
  const b = 0.75;
  return docs.map((doc) => {
    let score = 0;
    for (const token of query) {
      const freq = doc.freq.get(token) ?? 0;
      if (!freq) continue;
      const documents = df.get(token) ?? 0;
      const idf = Math.log(1 + (count - documents + 0.5) / (documents + 0.5));
      const denom = freq + k1 * (1 - b + (b * doc.length) / avg);
      score += idf * ((freq * (k1 + 1)) / denom);
    }
    return score;
  });
}

function identifierTokens(query: string): string[] {
  return tokenize(query).filter((token) => token.includes("_") && /[a-z]/.test(token) && /\d|[a-z]{3,}_/.test(token));
}

function deictic(query: string): boolean {
  return /\b(this|here|this article|this page)\b/i.test(query);
}

export function retrieve(question: string, chunks: StoredChunk[], page?: GuidePage | null, limit = 4): ScoredChunk[] {
  const codes = identifierTokens(question);
  const pool = codes.length
    ? chunks.filter((chunk) => {
        const haystack = `${chunk.title} ${chunk.heading} ${chunk.tags.join(" ")} ${chunk.text}`.toLowerCase();
        return codes.every((code) => haystack.includes(code));
      })
    : chunks;
  if (codes.length && pool.length === 0) return [];
  const expanded = expandQuery(question);
  const queryTokens = contentTokens(expanded);
  const { docs, df, avg } = postings(pool);
  const lexicalScores = bm25(queryTokens, docs, df, avg, pool.length);
  const queryVector = embedText(expanded);
  const maxLexical = Math.max(...lexicalScores, 0);
  const pointing = deictic(question);
  const scored = pool.map((chunk, index) => {
    const lexical = maxLexical > 0 ? (lexicalScores[index] ?? 0) / maxLexical : 0;
    const semantic = Math.max(0, cosine(queryVector, chunk.vector));
    let score = codes.length ? lexical : lexical * 0.8 + semantic * 0.2;
    const label = new Set(contentTokens(`${chunk.title} ${chunk.heading} ${chunk.tags.join(" ")}`));
    let overlap = 0;
    for (const token of queryTokens) if (label.has(token)) overlap += 1;
    score += Math.min(overlap, 4) * 0.12;
    if (page?.slug && chunk.slug === page.slug) score *= pointing ? 1 : 1.45;
    if (page?.url && chunk.url === page.url) score *= 1.15;
    return { chunk, score, lexical, semantic };
  });
  const ranked = scored.filter((item) => item.score >= 0.18).sort((a, b) => b.score - a.score);
  if (pointing && page?.slug) {
    const current = scored
      .filter((item) => item.chunk.slug === page.slug)
      .sort((a, b) => b.score - a.score)[0];
    if (current) {
      const rest = ranked.filter((item) => item.chunk.id !== current.chunk.id);
      return [current, ...rest].slice(0, limit);
    }
  }
  return ranked.slice(0, limit);
}

export function sourceKey(item: ScoredChunk): string {
  return `${item.chunk.url}#${item.chunk.heading}`;
}

export function citationSources(hits: ScoredChunk[]): ScoredChunk[] {
  const seen = new Set<string>();
  const sources: ScoredChunk[] = [];
  for (const hit of hits) {
    if (seen.has(hit.chunk.url)) continue;
    seen.add(hit.chunk.url);
    sources.push(hit);
    if (sources.length === 3) break;
  }
  return sources;
}

export function queryTokensForTest(question: string): string[] {
  return tokenize(expandQuery(question));
}
