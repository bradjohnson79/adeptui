import { useTranslation } from "react-i18next";
import { useLanguagePrefs } from "./LanguageProvider";
import type { PromptLanguagePolicy } from "./languagePrefs";

const POLICIES: PromptLanguagePolicy[] = [
  "auto",
  "user_language",
  "english",
  "project_canonical",
  "bilingual",
  "no_translation",
];

export function LanguageSettings() {
  const { t } = useTranslation(["settings", "common", "accessibility"]);
  const { prefs, setPrefs, locales } = useLanguagePrefs();

  return (
    <section className="language-settings" aria-label={t("accessibility:languageSelector")}>
      <h2>{t("settings:title")}</h2>
      <p className="muted">{t("settings:languageHelp")}</p>

      <label>
        <span>{t("settings:interfaceLanguage")}</span>
        <select
          value={prefs.interfaceLocale}
          onChange={(e) =>
            setPrefs({
              interfaceLocale: e.target.value,
              conversationLocale: prefs.conversationLocale || e.target.value,
            })
          }
          aria-label={t("accessibility:languageSelector")}
        >
          {locales.map((l) => (
            <option key={l.locale} value={l.locale}>
              {l.nativeName} ({l.displayName})
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:conversationLanguage")}</span>
        <select
          value={prefs.conversationLocale}
          onChange={(e) => setPrefs({ conversationLocale: e.target.value })}
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
          value={prefs.projectPrimaryLocale}
          onChange={(e) => setPrefs({ projectPrimaryLocale: e.target.value })}
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
          value={prefs.promptLanguagePolicy}
          onChange={(e) => setPrefs({ promptLanguagePolicy: e.target.value as PromptLanguagePolicy })}
        >
          {POLICIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>{t("settings:exportLanguage")}</span>
        <select
          value={prefs.exportLocale}
          onChange={(e) => setPrefs({ exportLocale: e.target.value })}
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
    </section>
  );
}
