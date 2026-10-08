import { GUIDE_REFUSAL } from "../src/guide/messages";

const windowMs = 10 * 60 * 1000;
const maxRequests = 8;
const hits = new Map<string, number[]>();

export function resetRateLimit(): void {
  hits.clear();
}

export function allowRequest(key: string, now = Date.now()): boolean {
  const recent = (hits.get(key) ?? []).filter((stamp) => now - stamp < windowMs);
  if (recent.length >= maxRequests) {
    hits.set(key, recent);
    return false;
  }
  recent.push(now);
  hits.set(key, recent);
  return true;
}

export function blockedIntent(text: string): boolean {
  const value = text.toLowerCase();
  if (/\b(api[_ -]?key|secret key|openai key|system prompt|\.env)\b/.test(value)) return true;
  if (/\bsk-[a-z0-9]{8,}/.test(value)) return true;
  if (/ignore (all |the )?(previous|prior|above) instructions/.test(value)) return true;
  if (/reveal (your |the )?(system )?prompt/.test(value)) return true;
  if (/\b(cat|type|print|show)\b.{0,40}\b(\.env|passwd|credentials)\b/.test(value)) return true;
  return false;
}

export function refusalText(): string {
  return GUIDE_REFUSAL;
}

export function cleanPage(input: unknown): { url: string; title: string; category: string; slug: string } | null {
  if (!input || typeof input !== "object") return null;
  const page = input as Record<string, unknown>;
  const url = typeof page.url === "string" ? page.url.trim() : "";
  const title = typeof page.title === "string" ? page.title.trim().slice(0, 160) : "";
  const category = typeof page.category === "string" ? page.category.trim().slice(0, 80) : "";
  const slug = typeof page.slug === "string" ? page.slug.trim().slice(0, 80) : "";
  if (!url.startsWith("/") || url.startsWith("//") || url.includes("://") || url.length > 200) return null;
  return { url, title, category, slug };
}

export function cleanHistory(input: unknown): { role: "user" | "assistant"; content: string }[] {
  if (!Array.isArray(input)) return [];
  return input
    .slice(-6)
    .flatMap((item) => {
      if (!item || typeof item !== "object") return [];
      const turn = item as Record<string, unknown>;
      const role = turn.role === "assistant" ? "assistant" : turn.role === "user" ? "user" : null;
      const content = typeof turn.content === "string" ? turn.content.trim().slice(0, 800) : "";
      if (!role || !content) return [];
      return [{ role, content }];
    });
}

export function cleanMessage(input: unknown): string | null {
  if (typeof input !== "string") return null;
  const message = input.trim();
  if (!message || message.length > 1200) return null;
  return message;
}
