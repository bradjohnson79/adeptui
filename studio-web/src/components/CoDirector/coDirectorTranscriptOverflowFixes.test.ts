import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Co-Director chat transcript must never grow a horizontal scrollbar.
 * Layout-only contract mirrored from timelineDrawerFixes-style source assertions.
 */
describe("coDirectorTranscriptOverflowFixes", () => {
  const cssPath = resolve(__dirname, "../../styles.css");
  const css = readFileSync(cssPath, "utf8");

  function rulesFor(selector: string): string {
    const idx = css.indexOf(selector);
    expect(idx, `missing selector ${selector}`).toBeGreaterThanOrEqual(0);
    const open = css.indexOf("{", idx);
    const close = css.indexOf("}", open);
    expect(open).toBeGreaterThan(idx);
    expect(close).toBeGreaterThan(open);
    return css.slice(open + 1, close);
  }

  it("transcript scrolls vertically only", () => {
    const block = rulesFor(".codirector-conversation");
    expect(block).toMatch(/overflow-y\s*:\s*auto/);
    expect(block).toMatch(/overflow-x\s*:\s*hidden/);
    expect(block).toMatch(/min-width\s*:\s*0/);
    expect(block).not.toMatch(/overflow\s*:\s*(auto|scroll)\s*;/);
  });

  it("message bubbles wrap long tokens/URLs", () => {
    const bubble = rulesFor(".codirector-msg-bubble");
    expect(bubble).toMatch(/overflow-wrap\s*:\s*anywhere/);
    expect(bubble).toMatch(/word-break\s*:\s*break-word/);
    expect(bubble).toMatch(/max-width\s*:\s*100%/);
    expect(bubble).toMatch(/min-width\s*:\s*0/);
  });

  it("flex message chain allows shrink", () => {
    expect(rulesFor(".codirector-messages")).toMatch(/min-width\s*:\s*0/);
    expect(rulesFor(".codirector-msg")).toMatch(/min-width\s*:\s*0/);
    expect(rulesFor(".codirector-main")).toMatch(/min-width\s*:\s*0/);
  });

  it("code/pre keeps scoped horizontal overflow only", () => {
    const idx = css.lastIndexOf(".codirector-msg-html pre");
    expect(idx).toBeGreaterThanOrEqual(0);
    const open = css.indexOf("{", idx);
    const close = css.indexOf("}", open);
    const pre = css.slice(open + 1, close);
    expect(pre).toMatch(/overflow-x\s*:\s*auto/);
    expect(pre).toMatch(/max-width\s*:\s*100%/);
  });
});
