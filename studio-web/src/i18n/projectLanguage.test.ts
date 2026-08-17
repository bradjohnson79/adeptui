import { describe, expect, it } from "vitest";
import { DEFAULT_LANGUAGE_PREFERENCES } from "./languagePrefs";
import {
  languageProjectContext,
  mergeProjectLanguage,
  overlayProjectLanguage,
  parseProjectLanguage,
  promptIntelligenceLanguageModules,
} from "./projectLanguage";

describe("M30F project language source of truth", () => {
  it("keeps interface locale global when overlaying project language", () => {
    const prefs = {
      ...DEFAULT_LANGUAGE_PREFERENCES,
      interfaceLocale: "ja",
      conversationLocale: "en",
    };
    const next = overlayProjectLanguage(
      prefs,
      JSON.stringify({
        language: {
          conversationLocale: "fr",
          projectPrimaryLocale: "es",
          promptLanguagePolicy: "english",
          exportLocale: "pt",
        },
      }),
    );
    expect(next.interfaceLocale).toBe("ja");
    expect(next.conversationLocale).toBe("fr");
    expect(next.projectPrimaryLocale).toBe("es");
    expect(next.promptLanguagePolicy).toBe("english");
    expect(next.exportLocale).toBe("pt");
  });

  it("does not clobber unrelated project settings when merging language", () => {
    const raw = mergeProjectLanguage(
      JSON.stringify({ library: { unfiled: true }, language: { conversationLocale: "en" } }),
      { conversationLocale: "fr", promptLanguagePolicy: "bilingual" },
    );
    const parsed = JSON.parse(raw) as { library: { unfiled: boolean }; language: { conversationLocale: string } };
    expect(parsed.library.unfiled).toBe(true);
    expect(parseProjectLanguage(raw).conversationLocale).toBe("fr");
    expect(parseProjectLanguage(raw).promptLanguagePolicy).toBe("bilingual");
  });

  it("maps bilingual policy to English + Chinese modules and english policy to English only", () => {
    expect(promptIntelligenceLanguageModules("bilingual")).toEqual(["en", "zh"]);
    expect(promptIntelligenceLanguageModules("english")).toEqual(["en"]);
    const ctx = languageProjectContext({
      ...DEFAULT_LANGUAGE_PREFERENCES,
      interfaceLocale: "es",
      conversationLocale: "fr",
      promptLanguagePolicy: "english",
      projectPrimaryLocale: "ja",
    });
    expect(ctx.promptLanguagePolicy).toBe("english");
    expect(ctx.interfaceLocale).toBe("es");
    expect(ctx.conversationLocale).toBe("fr");
  });
});
