import type { ThemePreference } from "../modelRegistry/contracts";

export type ResolvedTheme = "aurora-night" | "aurora-day";

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: light)").matches) {
      return "aurora-day";
    }
    return "aurora-night";
  }
  return preference === "aurora-day" ? "aurora-day" : "aurora-night";
}

export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference);
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", resolved);
  }
  return resolved;
}

export function watchSystemTheme(onChange: (resolved: ResolvedTheme) => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const media = window.matchMedia("(prefers-color-scheme: light)");
  const handler = () => onChange(media.matches ? "aurora-day" : "aurora-night");
  media.addEventListener("change", handler);
  return () => media.removeEventListener("change", handler);
}
