import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Co-Director header", () => {
  it("does not render a hamburger navigation button", () => {
    const src = readFileSync(new URL("./CoDirectorHeader.tsx", import.meta.url), "utf8");
    expect(src).not.toContain("codirector-menu-button");
    expect(src).not.toContain("Open Co-Director menu");
    expect(src).not.toContain("onOpenNav");
    expect(src).toContain("codirector-overflow-button");
  });
});
