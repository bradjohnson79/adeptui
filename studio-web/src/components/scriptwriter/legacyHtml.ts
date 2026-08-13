import type { ScriptElement } from "./types";

const INDENT_PX = 40;

function escapeHtml(text: string): string {
  return (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function elementsToHtml(elements: ScriptElement[]): string {
  if (!elements || elements.length === 0) return "<p></p>";
  return elements
    .map((el) => {
      const text = escapeHtml(el.text || "");
      switch (el.type) {
        case "scene_heading":
          return `<h1>${text}</h1>`;
        case "character":
          return `<p style="margin-left: ${INDENT_PX * 6}px; text-transform: uppercase;">${text}</p>`;
        case "parenthetical":
          return `<p style="margin-left: ${INDENT_PX * 7}px; font-style: italic;">${text}</p>`;
        case "dialogue":
          return `<p style="margin-left: ${INDENT_PX * 6}px; margin-right: ${INDENT_PX * 6}px;">${text}</p>`;
        case "transition":
          return `<p style="text-align: right; text-transform: uppercase;">${text}</p>`;
        case "shot":
          return `<p style="text-transform: uppercase; font-weight: 600;">${text}</p>`;
        default:
          return `<p>${text}</p>`;
      }
    })
    .join("");
}

export function isBlankHtml(html: string | null | undefined): boolean {
  if (!html) return true;
  const stripped = html.replace(/<[^>]*>/g, "").trim();
  return stripped.length === 0;
}
