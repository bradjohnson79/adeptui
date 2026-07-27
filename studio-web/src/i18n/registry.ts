import meta from "./locale-meta.json";

export type LocaleDirection = "ltr" | "rtl";
export type LanguagePackStatus =
  | "DRAFT"
  | "IN_REVIEW"
  | "VERIFIED"
  | "ACTIVE"
  | "DEPRECATED";
export type LinguisticReviewLevel =
  | "KEY_PRESENT"
  | "MACHINE_DRAFT"
  | "LINGUISTICALLY_REVIEWED"
  | "PRODUCTION_APPROVED"
  | "HUMAN_APPROVED";

export interface LocaleDescriptor {
  locale: string;
  displayName: string;
  nativeName: string;
  direction: LocaleDirection;
  fallback: string;
  enabled: boolean;
  status: LanguagePackStatus;
  reviewLevel: LinguisticReviewLevel;
  dateLocale: string;
  numberLocale: string;
  notes?: string;
}

export const NAMESPACES = meta.namespaces as readonly string[];
export const BETA_CRITICAL_NAMESPACES = meta.betaCriticalNamespaces as readonly string[];
export const LOCALE_REGISTRY: readonly LocaleDescriptor[] = meta.locales as LocaleDescriptor[];

export const DEFAULT_LOCALE = "en";
export const SUPPORTED_LOCALES = LOCALE_REGISTRY.map((l) => l.locale);

export function getLocale(locale: string): LocaleDescriptor | undefined {
  return LOCALE_REGISTRY.find((l) => l.locale === locale);
}

export function isSupportedLocale(locale: string): boolean {
  return SUPPORTED_LOCALES.includes(locale);
}

export function activeLocales(): LocaleDescriptor[] {
  return LOCALE_REGISTRY.filter((l) => l.enabled && l.status === "ACTIVE");
}

export function resolveSupportedLocale(candidate: string | null | undefined): string | null {
  if (!candidate) return null;
  const raw = candidate.trim();
  if (!raw) return null;
  if (isSupportedLocale(raw)) return raw;
  const lower = raw.toLowerCase();
  if (lower.startsWith("zh")) {
    if (lower.includes("hant") || lower.includes("tw") || lower.includes("hk")) return null;
    if (isSupportedLocale("zh-Hans")) return "zh-Hans";
  }
  const primary = lower.split("-")[0];
  if (primary === "pt" && isSupportedLocale("pt")) return "pt";
  if (isSupportedLocale(primary)) return primary;
  return null;
}
