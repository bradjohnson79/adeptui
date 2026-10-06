/** Creator-facing spoken languages. Codes match studio-api/app/film_timeline/spoken_language.py. */

export const SPOKEN_LANGUAGES: Array<{ code: string; label: string }> = [
  { code: "en", label: "English" },
  { code: "fr", label: "French" },
  { code: "es", label: "Spanish" },
  { code: "de", label: "German" },
  { code: "it", label: "Italian" },
  { code: "pt", label: "Portuguese" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "zh", label: "Mandarin Chinese" },
  { code: "yue", label: "Cantonese" },
  { code: "hi", label: "Hindi" },
  { code: "ar", label: "Arabic" },
  { code: "ru", label: "Russian" },
  { code: "custom", label: "Other / Custom" },
];

export function spokenLanguageLabel(code: string, custom = ""): string {
  if (code === "custom") return custom.trim() || "English";
  return SPOKEN_LANGUAGES.find((item) => item.code === code)?.label || "English";
}
