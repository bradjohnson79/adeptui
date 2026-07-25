import { marked } from "marked";
import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "p",
  "br",
  "strong",
  "em",
  "b",
  "i",
  "ul",
  "ol",
  "li",
  "code",
  "pre",
  "a",
  "h1",
  "h2",
  "h3",
  "h4",
  "blockquote",
  "hr",
];

const ALLOWED_ATTR = ["href", "title", "rel", "target", "class"];

marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * Convert assistant markdown to a sanitized HTML subset for bubble rendering.
 * Safe for streaming: incomplete markdown degrades without throwing.
 */
export function renderAssistantMarkdown(content: string): string {
  if (!content) return "";
  try {
    const raw = marked.parse(content, { async: false }) as string;
    const clean = DOMPurify.sanitize(raw, {
      ALLOWED_TAGS,
      ALLOWED_ATTR,
      ALLOW_DATA_ATTR: false,
      FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input"],
      FORBID_ATTR: ["style", "onerror", "onload", "onclick"],
    });
    // Force safe link attributes after sanitize.
    return clean.replace(/<a\b([^>]*)>/gi, (_match, attrs: string) => {
      const hrefMatch = attrs.match(/\bhref\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))/i);
      const href = (hrefMatch?.[2] || hrefMatch?.[3] || hrefMatch?.[4] || "").trim();
      if (!/^https?:\/\//i.test(href)) {
        return "<a>";
      }
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">`;
    });
  } catch {
    // Streaming partials or exotic markdown should never blank the bubble.
    const escaped = content
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<p>${escaped}</p>`;
  }
}
