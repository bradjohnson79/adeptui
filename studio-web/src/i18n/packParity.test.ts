import { describe, expect, it } from "vitest";
import { NAMESPACES, SUPPORTED_LOCALES } from "./registry";
import { collectPackParity, loadNamespace, packParityFailures } from "./packParity";

describe("M30F locale pack parity", () => {
  it("registers twelve locales including RTL Arabic and Urdu", () => {
    expect(SUPPORTED_LOCALES).toEqual([
      "en",
      "fr",
      "es",
      "ja",
      "zh-Hans",
      "hi",
      "ru",
      "pt",
      "ar",
      "bn",
      "id",
      "ur",
    ]);
  });

  it("has an English pack for every namespace", () => {
    for (const ns of NAMESPACES) {
      const en = loadNamespace("en", ns);
      expect(Object.keys(en).length, `empty English namespace ${ns}`).toBeGreaterThan(0);
    }
  });

  it("has the same keys in every non-English locale with no empty values", () => {
    const failures = packParityFailures(collectPackParity());
    const summary = failures
      .map(
        (f) =>
          `${f.locale}/${f.namespace} missing=${f.missing.join(",")} empty=${f.empty.join(",")}`,
      )
      .join("\n");
    expect(failures, summary).toEqual([]);
  });
});
