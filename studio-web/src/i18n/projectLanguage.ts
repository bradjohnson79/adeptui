import {
  DEFAULT_LANGUAGE_PREFERENCES,
  type LanguagePreferences,
  type PromptLanguagePolicy,
} from "./languagePrefs";
import { DEFAULT_LOCALE, isSupportedLocale } from "./registry";

export const PROJECT_LANGUAGE_KEY = "language";

export type ProjectLanguageState = {
  conversationLocale: string;
  projectPrimaryLocale: string;
  promptLanguagePolicy: PromptLanguagePolicy;
  exportLocale: string;
};

const POLICIES: PromptLanguagePolicy[] = [
  "auto",
  "user_language",
  "english",
  "project_canonical",
  "bilingual",
  "no_translation",
];

function sanitizeLocale(value: unknown, fallback: string): string {
  return typeof value === "string" && isSupportedLocale(value) ? value : fallback;
}

function sanitizePolicy(value: unknown, fallback: PromptLanguagePolicy): PromptLanguagePolicy {
  return typeof value === "string" && POLICIES.includes(value as PromptLanguagePolicy)
    ? (value as PromptLanguagePolicy)
    : fallback;
}

export function parseSettingsObject(raw?: string | null): Record<string, unknown> {
  try {
    const parsed = JSON.parse(raw || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export function hasProjectLanguage(settingsJson?: string | null): boolean {
  const settings = parseSettingsObject(settingsJson);
  return Boolean(settings[PROJECT_LANGUAGE_KEY] && typeof settings[PROJECT_LANGUAGE_KEY] === "object");
}

export function parseProjectLanguage(settingsJson?: string | null): ProjectLanguageState {
  const settings = parseSettingsObject(settingsJson);
  const lang = (settings[PROJECT_LANGUAGE_KEY] || {}) as Record<string, unknown>;
  const fallback = DEFAULT_LANGUAGE_PREFERENCES;
  return {
    conversationLocale: sanitizeLocale(lang.conversationLocale, fallback.conversationLocale),
    projectPrimaryLocale: sanitizeLocale(lang.projectPrimaryLocale, fallback.projectPrimaryLocale),
    promptLanguagePolicy: sanitizePolicy(lang.promptLanguagePolicy, fallback.promptLanguagePolicy),
    exportLocale: sanitizeLocale(lang.exportLocale, fallback.exportLocale),
  };
}

export function mergeProjectLanguage(
  settingsJson: string | undefined | null,
  patch: Partial<ProjectLanguageState>,
): string {
  const settings = parseSettingsObject(settingsJson);
  const current = parseProjectLanguage(settingsJson);
  settings[PROJECT_LANGUAGE_KEY] = { ...current, ...patch };
  return JSON.stringify(settings);
}

export function overlayProjectLanguage(
  prefs: LanguagePreferences,
  settingsJson?: string | null,
): LanguagePreferences {
  const project = parseProjectLanguage(settingsJson);
  return {
    ...prefs,
    conversationLocale: project.conversationLocale || prefs.conversationLocale,
    projectPrimaryLocale: project.projectPrimaryLocale || prefs.projectPrimaryLocale,
    promptLanguagePolicy: project.promptLanguagePolicy || prefs.promptLanguagePolicy,
    exportLocale: project.exportLocale || prefs.exportLocale,
  };
}

export function languageProjectContext(prefs: LanguagePreferences): {
  sourceLanguage: string;
  promptLanguagePolicy: PromptLanguagePolicy;
  projectPrimaryLocale: string;
  conversationLocale: string;
  interfaceLocale: string;
  exportLocale: string;
} {
  const source =
    prefs.promptLanguagePolicy === "project_canonical"
      ? prefs.projectPrimaryLocale
      : prefs.promptLanguagePolicy === "user_language"
        ? prefs.conversationLocale
        : prefs.conversationLocale || prefs.interfaceLocale || DEFAULT_LOCALE;
  return {
    sourceLanguage: source,
    promptLanguagePolicy: prefs.promptLanguagePolicy,
    projectPrimaryLocale: prefs.projectPrimaryLocale,
    conversationLocale: prefs.conversationLocale,
    interfaceLocale: prefs.interfaceLocale,
    exportLocale: prefs.exportLocale,
  };
}

export function promptIntelligenceLanguageModules(policy: PromptLanguagePolicy): string[] {
  if (policy === "bilingual") return ["en", "zh"];
  return ["en"];
}
