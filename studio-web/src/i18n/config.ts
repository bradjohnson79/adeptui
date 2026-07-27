import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { DEFAULT_LOCALE, NAMESPACES, SUPPORTED_LOCALES } from "./registry";
import { loadBundledResources } from "./loader";
import { loadLanguagePreferences } from "./languagePrefs";
import { applyDocumentDirection } from "./direction";

let initialized = false;

export async function initI18n(): Promise<typeof i18n> {
  if (initialized) return i18n;
  const prefs = loadLanguagePreferences();
  const resources = await loadBundledResources();
  await i18n.use(initReactI18next).init({
    resources,
    lng: prefs.interfaceLocale,
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: [...SUPPORTED_LOCALES],
    ns: [...NAMESPACES],
    defaultNS: "common",
    interpolation: { escapeValue: true },
    returnNull: false,
    returnEmptyString: false,
    react: { useSuspense: false },
  });
  applyDocumentDirection(prefs.interfaceLocale);
  i18n.on("languageChanged", (lng) => applyDocumentDirection(lng));
  initialized = true;
  return i18n;
}

export function changeInterfaceLanguage(locale: string): Promise<void> {
  applyDocumentDirection(locale);
  return i18n.changeLanguage(locale).then(() => undefined);
}

export default i18n;
