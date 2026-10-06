/** Canonical project Story — shared by Story Express and Script Writer Story. */

export const STORY_CANONICAL_CHANGED = "adept-story-canonical-changed";

export type CanonicalStoryEntry = {
  id: string;
  projectId: string;
  title: string;
  entryType: string;
  logline: string;
  shortSummary: string;
  longSummary: string;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
};

export type StoryCanonicalChangedDetail = {
  projectId: string;
  entryId: string;
  title: string;
  longSummary: string;
  source: "scriptwriter" | "express";
};

export function emitStoryCanonicalChanged(detail: StoryCanonicalChangedDetail): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(STORY_CANONICAL_CHANGED, { detail }));
}

export function subscribeStoryCanonicalChanged(
  handler: (detail: StoryCanonicalChangedDetail) => void,
): () => void {
  if (typeof window === "undefined") return () => undefined;
  const listener = (event: Event) => {
    const custom = event as CustomEvent<StoryCanonicalChangedDetail>;
    if (custom.detail) handler(custom.detail);
  };
  window.addEventListener(STORY_CANONICAL_CHANGED, listener);
  return () => window.removeEventListener(STORY_CANONICAL_CHANGED, listener);
}

export function looksLikeHtml(value: string): boolean {
  return /<\/?[a-z][\s\S]*>/i.test((value || "").trim());
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** TipTap needs HTML. Plain-text Express fields become paragraphs. */
export function toEditorHtml(value: string): string {
  const raw = (value || "").trim();
  if (!raw) return "<p></p>";
  if (looksLikeHtml(raw)) return raw;
  return raw
    .split(/\n{2,}/)
    .map((block) => `<p>${escapeHtml(block).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

export function isBlankStoryHtml(html: string): boolean {
  return !html.replace(/<[^>]+>/g, " ").replace(/&nbsp;/gi, " ").trim();
}

export function defaultStoryTitle(projectName: string): string {
  const name = (projectName || "").trim() || "Untitled";
  return `${name} — Story`;
}

export function pickPrimaryStoryEntry(entries: CanonicalStoryEntry[]): CanonicalStoryEntry | null {
  if (!entries.length) return null;
  const stories = entries.filter((e) => e.entryType === "project_story");
  const pool = stories.length ? stories : entries;
  const withBody = pool.filter(
    (e) => Boolean((e.longSummary || "").replace(/<[^>]+>/g, "").trim() || e.logline || e.shortSummary),
  );
  const ranked = (withBody.length ? withBody : pool).slice().sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
  return ranked[0] || null;
}
