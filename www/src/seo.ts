/**
 * Public-site SEO helpers.
 * A production origin is optional. Localhost is never used as a canonical URL.
 * Search Console verification belongs in index.html as
 * <meta name="google-site-verification" content="TOKEN" />
 * once a real token is issued. Do not invent one.
 *
 * Future sections, unpublished until each has a real page:
 * /guides/  /blog/  /resources/
 * Documentation lives at /docs and is published from www/docs.
 */

import { officialSameAs } from "./externalLinks";

export const futureSections = ["/guides/", "/blog/", "/resources/"] as const;

export const socialImagePath = "/brand/adept-ui-social.webp";

export function resolveSiteUrl(raw: string | undefined | null): string | null {
  const trimmed = raw?.trim();
  if (!trimmed) return null;
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return null;
  }
  if (url.protocol !== "https:") return null;
  const host = url.hostname.toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".local")) return null;
  if (url.username || url.password) return null;
  return url.origin;
}

export function sitemapXml(origin: string, paths: readonly string[] = ["/"]): string {
  const urls = paths
    .map((item) => {
      const loc = item === "/" ? `${origin}/` : `${origin}${item}`;
      return `  <url>\n    <loc>${loc}</loc>\n  </url>`;
    })
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;
}

export function robotsTxt(origin: string | null): string {
  const lines = ["User-agent: *", "Allow: /", ""];
  if (origin) lines.push(`Sitemap: ${origin}/sitemap.xml`, "");
  return lines.join("\n");
}

export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

type FaqItem = { q: string; a: string };

export function noscriptSummary(input: { title: string; description: string; faqs: readonly FaqItem[] }): string {
  const items = input.faqs
    .map((item) => `<h2>${escapeHtml(item.q)}</h2><p>${escapeHtml(item.a)}</p>`)
    .join("");
  return `<noscript><article><h1>${escapeHtml(input.title)}</h1><p>${escapeHtml(input.description)}</p>${items}</article></noscript>`;
}

export function softwareJsonLd(input: { origin: string | null; name: string; description: string; imagePath: string }): string {
  const application: Record<string, unknown> = {
    "@type": "SoftwareApplication",
    name: input.name,
    applicationCategory: "MultimediaApplication",
    operatingSystem: "Windows, macOS, Linux",
    creativeWorkStatus: "Beta",
    description: input.description,
    featureList: [
      "Character creation",
      "Storyboarding",
      "AI image generation",
      "AI video generation",
      "AI voice generation",
      "Timeline assembly",
      "Finishing",
      "Local and API models",
    ],
  };
  const sameAs = officialSameAs();
  if (sameAs.length) application.sameAs = sameAs;
  const graph: Record<string, unknown>[] = [application];
  if (input.origin) {
    application.url = `${input.origin}/`;
    application.image = `${input.origin}${input.imagePath}`;
    graph.push({
      "@type": "WebSite",
      name: input.name,
      url: `${input.origin}/`,
    });
  }
  const payload = {
    "@context": "https://schema.org",
    "@graph": graph,
  };
  return JSON.stringify(payload).replaceAll("<", "\\u003c");
}

export function headTags(input: { origin: string | null; name: string; description: string }): string {
  const tags = [
    `<script type="application/ld+json">${softwareJsonLd({
      origin: input.origin,
      name: input.name,
      description: input.description,
      imagePath: socialImagePath,
    })}</script>`,
  ];
  if (input.origin) {
    tags.unshift(
      `<link rel="canonical" href="${input.origin}/" />`,
      `<meta property="og:url" content="${input.origin}/" />`,
    );
  }
  return tags.join("\n    ");
}
