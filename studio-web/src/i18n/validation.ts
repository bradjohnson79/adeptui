import { BETA_CRITICAL_NAMESPACES, NAMESPACES, SUPPORTED_LOCALES } from "./registry";

const SUSPICIOUS = /<\s*script|javascript:|onerror\s*=|onload\s*=/i;

export interface PackValidationIssue {
  locale: string;
  namespace: string;
  key: string;
  code: string;
  message: string;
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
