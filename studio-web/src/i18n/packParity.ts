import { NAMESPACES, SUPPORTED_LOCALES } from "./registry";
import { compareLocalePack, flattenMessages, type PackParityReport } from "./validation";

const modules = import.meta.glob("./locales/*/*.json", { eager: true, import: "default" }) as Record<
  string,
  Record<string, unknown>
>;

export function loadNamespace(locale: string, namespace: string): Record<string, string> {
  const key = `./locales/${locale}/${namespace}.json`;
  return flattenMessages(modules[key] || {});
}

export function collectPackParity(): PackParityReport[] {
  const reports: PackParityReport[] = [];
  for (const ns of NAMESPACES) {
    const en = loadNamespace("en", ns);
    for (const locale of SUPPORTED_LOCALES) {
      if (locale === "en") continue;
      reports.push(compareLocalePack(en, loadNamespace(locale, ns), locale, ns));
    }
  }
  return reports;
}

export function packParityFailures(reports: PackParityReport[] = collectPackParity()): PackParityReport[] {
  return reports.filter((r) => r.missing.length || r.empty.length);
}
