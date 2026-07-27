import { DEFAULT_LOCALE, isSupportedLocale } from "./registry";
import { browserLocaleCandidate, resolveInterfaceLocale } from "./fallback";

const KEY = "adept_ui_language_prefs_v1";

export type PromptLanguagePolicy =
  | "auto"
  | "user_language"
  | "english"
  | "project_canonical"
  | "bilingual"
  | "no_translation";

export interface LanguagePreferences {
  interfaceLocale: string;
  conversationLocale: string;
  projectPrimaryLocale: string;
  promptLanguagePolicy: PromptLanguagePolicy;
  exportLocale: string;
  followOsLocale: boolean;
}

export const DEFAULT_LANGUAGE_PREFERENCES: LanguagePreferences = {
  interfaceLocale: DEFAULT_LOCALE,
  conversationLocale: DEFAULT_LOCALE,
  projectPrimaryLocale: DEFAULT_LOCALE,
  promptLanguagePolicy: "auto",
  exportLocale: DEFAULT_LOCALE,
  followOsLocale: false,
};

function sanitizeLocale(value: unknown, fallback: string): string {
  return typeof value === "string" && isSupportedLocale(value) ? value : fallback;
}

export function loadLanguagePreferences(): LanguagePreferences {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) {
      const resolved = resolveInterfaceLocale({
        saved: null,
        osOrBrowser: browserLocaleCandidate(),
      });
      return { ...DEFAULT_LANGUAGE_PREFERENCES, interfaceLocale: resolved, conversationLocale: resolved };
    }
    const data = JSON.parse(raw) as Partial<LanguagePreferences>;
    const base = { ...DEFAULT_LANGUAGE_PREFERENCES, ...data };
    base.interfaceLocale = sanitizeLocale(base.interfaceLocale, DEFAULT_LOCALE);
    base.conversationLocale = sanitizeLocale(base.conversationLocale, base.interfaceLocale);
    base.projectPrimaryLocale = sanitizeLocale(base.projectPrimaryLocale, DEFAULT_LOCALE);
    base.exportLocale = sanitizeLocale(base.exportLocale, base.interfaceLocale);
    if (base.followOsLocale) {
      base.interfaceLocale = resolveInterfaceLocale({
        explicit: null,
        saved: base.interfaceLocale,
        osOrBrowser: browserLocaleCandidate(),
      });
    }
    return base;
  } catch {
    return { ...DEFAULT_LANGUAGE_PREFERENCES };
  }
}

export function saveLanguagePreferences(prefs: LanguagePreferences): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota */
  }
}

export function updateLanguagePreferences(
  patch: Partial<LanguagePreferences>
): LanguagePreferences {
  const next = { ...loadLanguagePreferences(), ...patch };
  saveLanguagePreferences(next);
  return next;
}
