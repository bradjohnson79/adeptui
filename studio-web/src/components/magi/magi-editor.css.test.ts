import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "magi-editor.css"), "utf8");

describe("MAGI shell CSS contract", () => {
  it("locks MAGI into the Adept shell instead of a second 100dvh stack", () => {
    expect(css).not.toMatch(/height:\s*calc\(100dvh\s*-\s*72px\)/);
    expect(css).toContain(".app-shell-fixed .magi-shell");
    expect(css).toContain(".magi-workspace-stack");
    expect(css).toContain("min-height: 0");
  });

  it("fits MAGI preview media inside the monitor instead of source pixels", () => {
    expect(css).toContain(".magi-preview-fit-host");
    expect(css).toContain(".magi-preview-fit-frame");
    expect(css).toContain("object-fit: contain");
    expect(css).toMatch(/\.magi-viewer-stage[\s\S]*overflow:\s*hidden/);
  });
});
