import DOMPurify from "dompurify";

const ALLOWED_TAGS = [
  "p", "br", "strong", "b", "em", "i", "u", "s", "del",
  "h1", "h2", "h3", "h4", "h5", "h6",
  "ul", "ol", "li",
  "blockquote", "hr",
  "span", "div",
  "pre", "code",
];

const ALLOWED_ATTR = ["style", "align", "data-indent", "class"];

const FORBID_TAGS = ["script", "iframe", "object", "embed", "form", "input", "style", "link", "meta"];

const FORBID_ATTR = [
  "onerror", "onload", "onclick", "onmouseover", "onfocus", "onblur", "onchange", "onsubmit",
];

const ALLOWED_URI_REGEXP: RegExp = /^(?!(?:javascript|data|vbscript):)/i;

const SANITIZE_CONFIG = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  ALLOW_DATA_ATTR: false,
  FORBID_TAGS,
  FORBID_ATTR,
  ALLOWED_URI_REGEXP,
} as const;

export const SANITIZE_POLICY = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  FORBID_TAGS,
  FORBID_ATTR,
  ALLOWED_URI_REGEXP,
  ALLOW_DATA_ATTR: false,
} as const;

export function sanitizeHtml(html: string): string {
  if (!html) return "";
  return DOMPurify.sanitize(html, SANITIZE_CONFIG) as string;
}
