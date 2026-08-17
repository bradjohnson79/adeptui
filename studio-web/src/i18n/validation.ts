import { BETA_CRITICAL_NAMESPACES, NAMESPACES, SUPPORTED_LOCALES } from "./registry";

const SUSPICIOUS = /<\s*script|javascript:|onerror\s*=|onload\s*=/i;
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;

export interface PackValidationIssue {
  locale: string;
  namespace: string;
  key: string;
  code: string;
  message: string;
}

export interface PackParityReport {
  locale: string;
  namespace: string;
  missing: string[];
  extra: string[];
  empty: string[];
}

export function flattenMessages(input: unknown, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  if (!input || typeof input !== "object" || Array.isArray(input)) return out;
  for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, flattenMessages(value, path));
    } else {
      out[path] = value == null ? "" : String(value);
    }
  }
  return out;
}

export function compareLocalePack(
  en: Record<string, string>,
  other: Record<string, string>,
  locale: string,
  namespace: string
): PackParityReport {
  const missing: string[] = [];
  const empty: string[] = [];
  for (const key of Object.keys(en)) {
    if (!(key in other)) {
      missing.push(key);
      continue;
    }
    if (!String(other[key] ?? "").trim()) empty.push(key);
  }
  const extra = Object.keys(other).filter((key) => {
    if (key in en) return false;
    const base = key.replace(PLURAL_SUFFIX, "");
    return !(base in en) && !Object.keys(en).some((k) => k.replace(PLURAL_SUFFIX, "") === base);
  });
  return { locale, namespace, missing, extra, empty };
}

export function validateMessageTemplates(
  en: Record<string, string>,
  other: Record<string, string>,
  locale: string,
  namespace: string
): PackValidationIssue[] {
  const issues: PackValidationIssue[] = [];
  for (const [key, enVal] of Object.entries(en)) {
    if (!(key in other) || !String(other[key] ?? "").trim()) {
      if (BETA_CRITICAL_NAMESPACES.includes(namespace)) {
        issues.push({
          locale,
          namespace,
          key,
          code: "MISSING_CRITICAL_KEY",
          message: `Missing critical key ${namespace}.${key}`,
        });
      }
      continue;
    }
    const val = String(other[key]);
    if (SUSPICIOUS.test(val)) {
      issues.push({
        locale,
        namespace,
        key,
        code: "SUSPICIOUS_CONTENT",
        message: `Suspicious content in ${namespace}.${key}`,
      });
    }
    const enVars = [...enVal.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort();
    const otVars = [...val.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort();
    if (enVars.join(",") !== otVars.join(",")) {
      issues.push({
        locale,
        namespace,
        key,
        code: "INTERPOLATION_MISMATCH",
        message: `Interpolation vars mismatch for ${namespace}.${key}`,
      });
    }
  }
  return issues;
}

export function expectedNamespaces(): readonly string[] {
  return NAMESPACES;
}

export function expectedLocales(): readonly string[] {
  return SUPPORTED_LOCALES;
}
