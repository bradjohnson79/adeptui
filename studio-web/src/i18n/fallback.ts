import { DEFAULT_LOCALE, resolveSupportedLocale } from "./registry";

/**
 * UI locale resolution (does not change project canonical language):
 * explicit user preference → saved local preference → OS/browser → English
 */
export function resolveInterfaceLocale(input: {
  explicit?: string | null;
  saved?: string | null;
  osOrBrowser?: string | null;
}): string {
  return (
    resolveSupportedLocale(input.explicit) ||
    resolveSupportedLocale(input.saved) ||
    resolveSupportedLocale(input.osOrBrowser) ||
    DEFAULT_LOCALE
  );
}

export function browserLocaleCandidate(): string | null {
  if (typeof navigator === "undefined") return null;
  const list = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const c of list) {
    const hit = resolveSupportedLocale(c);
    if (hit) return hit;
  }
  return null;
}
