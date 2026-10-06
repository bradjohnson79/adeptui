import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Express Standard CTA honesty", () => {
  it("Wiki character actions name Character Creator, not an Express destination", () => {
    const wiki = readFileSync(new URL("./ProjectWikiPanel.tsx", import.meta.url), "utf8");
    expect(wiki).toContain("Open in Character Creator");
    expect(wiki).not.toContain(">Open Character<");
    const foundation = readFileSync(new URL("./CoDirectorProjectContent.tsx", import.meta.url), "utf8");
    expect(foundation).toContain("Opens the full Character Creator");
  });
});
