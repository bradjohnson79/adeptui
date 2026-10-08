import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { faq } from "./content";
import {
  escapeHtml,
  futureSections,
  resolveSiteUrl,
  robotsTxt,
  sitemapXml,
  softwareJsonLd,
} from "./seo";

describe("public site URL", () => {
  it("accepts only a public https origin", () => {
    expect(resolveSiteUrl("https://adept.example")).toBe("https://adept.example");
    expect(resolveSiteUrl("https://adept.example/path")).toBe("https://adept.example");
    expect(resolveSiteUrl("")).toBeNull();
    expect(resolveSiteUrl("http://adept.example")).toBeNull();
    expect(resolveSiteUrl("https://localhost")).toBeNull();
    expect(resolveSiteUrl("https://127.0.0.1")).toBeNull();
  });
});

describe("crawl files", () => {
  it("allows crawling and never blocks the site", () => {
    const robots = robotsTxt("https://adept.example");
    expect(robots).toContain("Allow: /");
    expect(robots).not.toContain("Disallow: /");
    expect(robots).toContain("Sitemap: https://adept.example/sitemap.xml");
    expect(robotsTxt(null)).not.toContain("Sitemap:");
  });

  it("writes one absolute homepage in the sitemap", () => {
    const xml = sitemapXml("https://adept.example");
    expect(xml).toContain("http://www.sitemaps.org/schemas/sitemap/0.9");
    expect(xml).toContain("<loc>https://adept.example/</loc>");
    expect(xml).not.toContain("localhost");
  });
});

describe("structured data", () => {
  it("describes the software without invented commercial fields", () => {
    const raw = softwareJsonLd({
      origin: "https://adept.example",
      name: "Adept UI",
      description: "A unified AI filmmaking environment.",
      imagePath: "/brand/adept-ui-social.webp",
    });
    const data = JSON.parse(raw) as { "@graph": Record<string, unknown>[] };
    const app = data["@graph"].find((node) => node["@type"] === "SoftwareApplication");
    expect(app).toMatchObject({
      name: "Adept UI",
      applicationCategory: "MultimediaApplication",
      operatingSystem: "Windows, macOS, Linux",
      url: "https://adept.example/",
    });
    expect(raw).not.toContain("aggregateRating");
    expect(raw).not.toContain("reviewCount");
    expect(raw).not.toContain("offers");
    expect(app?.creativeWorkStatus).toBe("Beta");
    expect(raw).not.toContain("softwareVersion");
    expect(raw).not.toContain("production-ready");
    expect(raw).not.toContain("\"stable\"");
    expect(raw).not.toContain("downloadUrl");
    expect(raw).not.toContain("license");
    expect(raw).toContain("https://github.com/bradjohnson79/adeptui");
    expect(raw).not.toContain("huggingface.co");
    expect(data["@graph"].some((node) => node["@type"] === "Organization")).toBe(false);
  });

  it("omits canonical URLs when no public origin is configured", () => {
    const raw = softwareJsonLd({
      origin: null,
      name: "Adept UI",
      description: "A unified AI filmmaking environment.",
      imagePath: "/brand/adept-ui-social.webp",
    });
    expect(raw).not.toContain("localhost");
    expect(raw).not.toContain('"url"');
  });
});

describe("index document", () => {
  it("does not use a keywords meta tag", () => {
    const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
    expect(html).not.toMatch(/name=["']keywords["']/i);
    expect(html).toContain("google-site-verification");
    expect(html).not.toContain("TOKEN");
  });
});

describe("copy safety helpers", () => {
  it("escapes noscript text and keeps future sections unpublished", () => {
    expect(escapeHtml(`A & B <C>`)).toBe("A &amp; B &lt;C&gt;");
    expect(futureSections).toEqual(["/guides/", "/blog/", "/resources/"]);
    expect(faq.items.some((item) => item.q === "Is Adept UI open source?")).toBe(true);
  });
});
