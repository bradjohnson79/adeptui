import { useEffect, useMemo, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import i18n, { changeInterfaceLanguage, initI18n } from "./config";
import {
  loadLanguagePreferences,
  saveLanguagePreferences,
  type LanguagePreferences,
} from "./languagePrefs";
import { activeLocales } from "./registry";

export type LanguageContextValue = {
  prefs: LanguagePreferences;
  setPrefs: (patch: Partial<LanguagePreferences>) => void;
  locales: ReturnType<typeof activeLocales>;
  ready: boolean;
};

import { createContext, useContext } from "react";

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function useLanguagePrefs(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguagePrefs requires LanguageProvider");
  return ctx;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [prefs, setPrefsState] = useState<LanguagePreferences>(() => loadLanguagePreferences());

  useEffect(() => {
    let cancelled = false;
    initI18n().then(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<LanguageContextValue>(
    () => ({
      prefs,
      locales: activeLocales(),
      ready,
      setPrefs: (patch) => {
        setPrefsState((prev) => {
          const next = { ...prev, ...patch };
          saveLanguagePreferences(next);
          if (patch.interfaceLocale && patch.interfaceLocale !== prev.interfaceLocale) {
            void changeInterfaceLanguage(patch.interfaceLocale);
          }
          return next;
        });
      },
    }),
    [prefs, ready]
  );

  if (!ready) {
    return (
      <div className="i18n-boot" role="status" aria-live="polite">
        Loading…
      </div>
    );
  }

  return (
    <I18nextProvider i18n={i18n}>
      <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
    </I18nextProvider>
  );
}
