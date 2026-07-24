const SECRET = /(api[_ -]?key|token|password|secret|authorization)\s*[:=]\s*\S+/gi;
const HOME = /([A-Z]:\\Users\\[^\\/]+|\/Users\/[^/]+|\/home\/[^/]+)/gi;

export function redact(text: string): string {
  return String(text || "")
    .replace(SECRET, "$1=[redacted]")
    .replace(HOME, "[user-home]");
}

export function redactDeep<T>(value: T): T {
  if (typeof value === "string") return redact(value) as T;
  if (Array.isArray(value)) return value.map((item) => redactDeep(item)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(value as Record<string, unknown>)) {
      out[key] = /token|secret|password|authorization/i.test(key)
        ? "[redacted]"
        : redactDeep(nested);
    }
    return out as T;
  }
  return value;
}
