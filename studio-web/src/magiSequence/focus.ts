import type { MagiFocusRegion } from "./types";

export const MAGI_FOCUS_ATTR = "data-magi-focus-region";

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (target.isContentEditable) return true;
  if (target.closest("[contenteditable='true']")) return true;
  if (target.closest("input, textarea, select, [role='textbox']")) return true;
  return false;
}

export function isModalOpen(): boolean {
  return Boolean(
    document.querySelector(
      "[role='dialog'][aria-modal='true'], .magi-modal.is-open, [data-magi-modal='open']",
    ),
  );
}

/** Resolve effective region, preferring live DOM typing/modal checks over stale state. */
export function resolveEffectiveFocusRegion(declared: MagiFocusRegion): MagiFocusRegion {
  if (isModalOpen()) return "modal";
  if (isTypingTarget(document.activeElement)) return "text_input";
  return declared;
}

export function canDeleteTimelineSelection(region: MagiFocusRegion): boolean {
  return resolveEffectiveFocusRegion(region) === "timeline";
}

export function canControlPlayback(region: MagiFocusRegion): boolean {
  const effective = resolveEffectiveFocusRegion(region);
  return effective === "timeline" || effective === "viewer";
}

export function canFrameStep(region: MagiFocusRegion): boolean {
  return canControlPlayback(region);
}

export function canUseMagiClipboard(region: MagiFocusRegion, hasTimelineSelection: boolean): boolean {
  return resolveEffectiveFocusRegion(region) === "timeline" && hasTimelineSelection;
}

export function canUseMagiUndo(region: MagiFocusRegion): boolean {
  const effective = resolveEffectiveFocusRegion(region);
  return effective === "timeline" || effective === "viewer" || effective === "media_bin";
}
