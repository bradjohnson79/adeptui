import { getLocale, DEFAULT_LOCALE } from "./registry";

function numberLocaleTag(locale: string): string {
  return getLocale(locale)?.numberLocale ?? locale ?? DEFAULT_LOCALE;
}

function dateLocaleTag(locale: string): string {
  return getLocale(locale)?.dateLocale ?? locale ?? DEFAULT_LOCALE;
}

export function formatNumber(value: number, locale: string, options?: Intl.NumberFormatOptions): string {
  return new Intl.NumberFormat(numberLocaleTag(locale), options).format(value);
}

export function formatPercent(value: number, locale: string): string {
  return new Intl.NumberFormat(numberLocaleTag(locale), {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatFileSize(bytes: number, locale: string): string {
  if (!Number.isFinite(bytes) || bytes < 0) return formatNumber(0, locale);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${formatNumber(n, locale, { maximumFractionDigits: i === 0 ? 0 : 1 })} ${units[i]}`;
}

export function formatDateTime(isoOrDate: string | Date, locale: string): string {
  const d = typeof isoOrDate === "string" ? new Date(isoOrDate) : isoOrDate;
  if (Number.isNaN(d.getTime())) return String(isoOrDate);
  return new Intl.DateTimeFormat(dateLocaleTag(locale), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

export function formatRelativeTime(from: Date, to: Date, locale: string): string {
  const diffSec = Math.round((from.getTime() - to.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(dateLocaleTag(locale), { numeric: "auto" });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, "second");
  const min = Math.round(diffSec / 60);
  if (Math.abs(min) < 60) return rtf.format(min, "minute");
  const hr = Math.round(diffSec / 3600);
  if (Math.abs(hr) < 48) return rtf.format(hr, "hour");
  const day = Math.round(diffSec / 86400);
  return rtf.format(day, "day");
}

export function formatList(items: string[], locale: string): string {
  try {
    return new Intl.ListFormat(numberLocaleTag(locale), { style: "long", type: "conjunction" }).format(items);
  } catch {
    return items.join(", ");
  }
}
