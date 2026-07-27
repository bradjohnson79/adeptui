import { getLocale, type LocaleDirection } from "./registry";

export function directionForLocale(locale: string): LocaleDirection {
  return getLocale(locale)?.direction ?? "ltr";
}

export function applyDocumentDirection(locale: string): void {
  if (typeof document === "undefined") return;
  const dir = directionForLocale(locale);
  document.documentElement.lang = locale;
  document.documentElement.dir = dir;
  document.documentElement.dataset.locale = locale;
  document.body.classList.toggle("rtl", dir === "rtl");
  document.body.classList.toggle("ltr", dir === "ltr");
}

export function isRtlLocale(locale: string): boolean {
  return directionForLocale(locale) === "rtl";
}
