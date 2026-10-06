import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const src = readFileSync(new URL("./Home.tsx", import.meta.url), "utf8");

describe("Home compact library", () => {
  it("bounds library results and resets scroll when search, filter, or view change", () => {
    expect(src).toContain("useHomeLibraryBounds");
    expect(src).toContain("home-library-results");
    expect(src).toContain("gs-library__results");
    expect(src).toContain("data-visible-rows");
    expect(src).toContain("libraryBounds.height");
    expect(src).toContain("scrollTo({ top: 0 })");
    expect(src).toContain("statusFilter");
  });
});
