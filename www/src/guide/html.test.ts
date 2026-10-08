import { describe, expect, it } from "vitest";
import { guideHtml } from "./html";

describe("guide HTML", () => {
  it("keeps paragraphs, lists, emphasis, and safe links", () => {
    const html = guideHtml(
      '<p>Start here.</p><ul><li><strong>Timeline</strong> holds shots.</li></ul><p>Read <a href="/docs/timeline/what-is-timeline">Timeline</a> and <a href="https://adeptui.org/docs">the site</a>.</p>',
    );
    expect(html).toContain("<p>Start here.</p>");
    expect(html).toContain("<ul><li><strong>Timeline</strong> holds shots.</li></ul>");
    expect(html).toContain('<a href="/docs/timeline/what-is-timeline">Timeline</a>');
    expect(html).toContain('<a href="https://adeptui.org/docs">the site</a>');
  });

  it("drops scripts, handlers, and unsafe links", () => {
    const html = guideHtml(
      '<p onclick="alert(1)">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a><a href="//evil.example">also bad</a>',
    );
    expect(html).not.toContain("<script");
    expect(html).not.toContain("onclick");
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("evil.example");
    expect(html).toContain("<p>Hi</p>");
  });
});
