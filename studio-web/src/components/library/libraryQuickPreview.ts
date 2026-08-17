/** Shared Quick Preview helpers. Preview is read-only and never mutates Library or Timeline. */

export type QuickPreviewKind = "image" | "video" | "audio";

export function isQuickPreviewKind(kind: string | null | undefined): kind is QuickPreviewKind {
  return kind === "image" || kind === "video" || kind === "audio";
}

export function eventFromActionControl(target: EventTarget | null): boolean {
  if (!target || typeof Element === "undefined" || !(target instanceof Element)) return false;
  return Boolean(target.closest("button, a, input, select, textarea, label, .asset-item__actions"));
}
