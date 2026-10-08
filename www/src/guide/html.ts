import { escapeHtml } from "../docs/parse";

const ALLOWED = new Set(["p", "ul", "ol", "li", "strong", "em", "code", "br"]);

function safeHref(value: string): string | null {
  const href = value.trim();
  if (href.startsWith("/") && !href.startsWith("//") && !href.includes("\\")) return href;
  if (href.startsWith("#") && !href.includes(":")) return href;
  if (href.startsWith("https://") && !href.includes(" ")) return href;
  return null;
}

/** Assistant text becomes display HTML. Only a small tag set survives. */
export function guideHtml(raw: string): string {
  const stripped = raw
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "");
  let html = escapeHtml(stripped);
  html = html.replace(/&lt;(\/?)(p|ul|ol|li|strong|em|code|br)\b(?:(?!&gt;).)*&gt;/gi, (_match, slash: string, tag: string) => {
    const name = tag.toLowerCase();
    if (!ALLOWED.has(name)) return "";
    if (name === "br") return "<br>";
    return `<${slash ? "/" : ""}${name}>`;
  });
  html = html.replace(/&lt;a\b(?:(?!&gt;).)*?href=&quot;(.*?)&quot;(?:(?!&gt;).)*&gt;/gi, (_match, href: string) => {
    const decoded = href.replaceAll("&amp;", "&").replaceAll("&quot;", '"');
    const safe = safeHref(decoded);
    return safe ? `<a href="${escapeHtml(safe)}">` : "";
  });
  html = html.replace(/&lt;\/a&gt;/gi, "</a>");
  return html;
}
