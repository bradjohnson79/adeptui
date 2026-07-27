import type { Resource } from "i18next";
import { NAMESPACES, SUPPORTED_LOCALES } from "./registry";

const modules = import.meta.glob("./locales/*/*.json", { eager: true, import: "default" }) as Record<
  string,
  Record<string, string>
>;

export async function loadBundledResources(): Promise<Resource> {
  const resources: Resource = {};
  for (const locale of SUPPORTED_LOCALES) {
    resources[locale] = {};
    for (const ns of NAMESPACES) {
      const key = `./locales/${locale}/${ns}.json`;
      const data = modules[key];
      if (data) {
        (resources[locale] as Record<string, unknown>)[ns] = data;
      }
    }
  }
  return resources;
}

export function listLoadedLocaleFiles(): string[] {
  return Object.keys(modules).sort();
}
