import { apiUrl } from "../../runtime/apiBase";

const CANONICAL_PATH = /^\/api\/projects\/[^/]+\/assets\/[^/]+\/file$/;

/** Browser URL for a Character Creator asset. Accepts only the project-scoped media route. */
export function characterMediaUrl(assetUrl?: string | null): string {
  const raw = String(assetUrl || "").trim();
  if (!raw) return "";
  if (raw.startsWith("http://") || raw.startsWith("https://")) {
    try {
      const parsed = new URL(raw);
      return CANONICAL_PATH.test(parsed.pathname) ? raw : "";
    } catch {
      return "";
    }
  }
  const path = raw.split("?")[0] || "";
  if (!CANONICAL_PATH.test(path)) return "";
  return apiUrl(raw);
}

export function isCanonicalAssetFileUrl(assetUrl?: string | null): boolean {
  return Boolean(characterMediaUrl(assetUrl));
}
