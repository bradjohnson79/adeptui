import { useTranslation } from "react-i18next";
import { useLanguagePrefs } from "./LanguageProvider";
import type { PromptLanguagePolicy } from "./languagePrefs";
import { mergeProjectLanguage } from "./projectLanguage";
import { api } from "../api";
import type { Project } from "../types";

const POLICIES: PromptLanguagePolicy[] = [
  "auto",
  "user_language",
  "english",
  "project_canonical",
  "bilingual",
  "no_translation",
];

const POLICY_KEYS: Record<PromptLanguagePolicy, string> = {
  auto: "policyAuto",
  user_language: "policyUserLanguage",
  english: "policyEnglish",
  project_canonical: "policyProjectCanonical",
  bilingual: "policyBilingual",
  no_translation: "policyNoTranslation",
};

export function LanguageSettings({
  project,
  onProjectChange,
}: {
  project?: Project;
  onProjectChange?: () => void;
} = {}) {
  const { t } = useTranslation(["settings", "common", "accessibility"]);
  const { prefs, setPrefs, locales } = useLanguagePrefs();

  const persistProject = (patch: {
    conversationLocale?: string;
    projectPrimaryLocale?: string;
    promptLanguagePolicy?: PromptLanguagePolicy;
    exportLocale?: string;
  }) => {
    setPrefs(patch);
    if (!project) return;
    const next = mergeProjectLanguage(project.settings_json, {
      conversationLocale: patch.conversationLocale ?? prefs.conversationLocale,
      projectPrimaryLocale: patch.projectPrimaryLocale ?? prefs.projectPrimaryLocale,
      promptLanguagePolicy: patch.promptLanguagePolicy ?? prefs.promptLanguagePolicy,
      exportLocale: patch.exportLocale ?? prefs.exportLocale,
    });
    void api.updateProject(project.id, { settings_json: next }).then(() => onProjectChange?.());
  };

  return (
    <section className="language-settings" aria-label={t("accessibility:languageSelector")}>
      <h2>{t("settings:title")}</h2>
      <p className="muted">{t("settings:languageHelp")}</p>

      <label>
        <span>{t("settings:interfaceLanguage")}</span>
        <select
          data-testid="m30f-interface-locale"
          value={prefs.interfaceLocale}
          onChange={(e) =>
            setPrefs({
              interfaceLocale: e.target.value,
            })
          }
          aria-label={t("accessibility:languageSelector")}
        >
          {locales.map((l) => (
            <option key={l.locale} value={l.locale}>
              {l.nativeName}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:conversationLanguage")}</span>
        <select
          data-testid="m30f-conversation-locale"
          value={prefs.conversationLocale}
          onChange={(e) => persistProject({ conversationLocale: e.target.value })}
        >
          {locales.map((l) => (
            <option key={l.locale} value={l.locale}>
              {l.nativeName}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:projectLanguage")}</span>
        <select
          data-testid="m30f-project-locale"
          value={prefs.projectPrimaryLocale}
          onChange={(e) => persistProject({ projectPrimaryLocale: e.target.value })}
        >
          {locales.map((l) => (
            <option key={l.locale} value={l.locale}>
              {l.nativeName}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:promptLanguagePolicy")}</span>
        <select
          data-testid="m30f-prompt-policy"
          value={prefs.promptLanguagePolicy}
          onChange={(e) => persistProject({ promptLanguagePolicy: e.target.value as PromptLanguagePolicy })}
        >
          {POLICIES.map((p) => (
            <option key={p} value={p}>
              {t(`settings:${POLICY_KEYS[p]}`)}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:exportLanguage")}</span>
        <select
          data-testid="m30f-export-locale"
          value={prefs.exportLocale}
          onChange={(e) => persistProject({ exportLocale: e.target.value })}
        >
          {locales.map((l) => (
            <option key={l.locale} value={l.locale}>
              {l.nativeName}
            </option>
          ))}
        </select>
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={prefs.followOsLocale}
          onChange={(e) => setPrefs({ followOsLocale: e.target.checked })}
        />
        <span>{t("settings:followOs")}</span>
      </label>

      <p className="muted">{t("settings:rtlNote")}</p>
      <p className="muted">{t("settings:portugueseNote")}</p>
      <p className="muted" data-testid="linguistic-review-disclosure">
        {t("settings:draftQualityNote")}
      </p>
    </section>
  );
}
