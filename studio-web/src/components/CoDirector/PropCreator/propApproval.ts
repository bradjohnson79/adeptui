import type { PropAngleSlot, PropCandidate, PropEntity } from "./types";

export const OPTIONAL_PROP_VIEWS = ["front", "back", "left", "right", "top", "bottom", "hero"] as const;
export const REQUIRED_PROP_VIEWS = ["front", "back", "left", "right", "top", "bottom"] as const;
export const CANONICAL_PRS_ORDER = ["primary", ...OPTIONAL_PROP_VIEWS] as const;

export const ADDITIONAL_VIEWS_TITLE = "Additional Views (optional)";
export const ADDITIONAL_VIEWS_HINT = "Optional — add for stronger multi-angle consistency.";

export const SHEET_COMPOSE_HINT_READY =
  "Compose from approved Primary, then any approved additional views. Missing views are skipped.";
export const SHEET_COMPOSE_HINT_BLOCKED =
  "Approve Primary to create a Prop Reference Sheet. Additional views are optional.";

const FAILED = new Set(["failed", "error", "cancelled", "missing"]);

function aid(value?: string | null): string {
  return String(value || "").trim();
}

export function candidateHasValidAsset(candidate?: PropCandidate | null): boolean {
  if (!candidate || !aid(candidate.asset_id)) return false;
  return !FAILED.has(String(candidate.status || "").trim().toLowerCase());
}

export function validPrimaryCandidate(prop: PropEntity | null | undefined): PropCandidate | null {
  if (!prop) return null;
  const found = [...(prop.candidates || [])].reverse().find(candidateHasValidAsset);
  return found || null;
}

export function validPrimaryCandidateAssetId(prop: PropEntity | null | undefined): string {
  return aid(validPrimaryCandidate(prop)?.asset_id);
}

export function approvedPrimaryAssetId(prop: PropEntity | null | undefined): string {
  if (!prop) return "";
  if ((prop.mode || "standard") === "advanced") {
    return aid(prop.primary_approved_asset_id) || aid(prop.approved_asset_id);
  }
  return aid(prop.approved_asset_id);
}

export function canApprovePrimary(prop: PropEntity | null | undefined): boolean {
  const candidateId = validPrimaryCandidateAssetId(prop);
  if (!candidateId) return false;
  return candidateId !== approvedPrimaryAssetId(prop);
}

/** Image shown in the Primary box. A pending replacement beats a stale approved pointer. */
export function visiblePrimaryPreviewAssetId(prop: PropEntity | null | undefined): string {
  const pending = validPrimaryCandidateAssetId(prop);
  const approved = approvedPrimaryAssetId(prop);
  if (pending && pending !== approved) return pending;
  return pending || approved;
}

export function primaryPreviewIsPendingReplacement(prop: PropEntity | null | undefined): boolean {
  const pending = validPrimaryCandidateAssetId(prop);
  const approved = approvedPrimaryAssetId(prop);
  return Boolean(pending && approved && pending !== approved);
}

export function canApproveView(slot: PropAngleSlot | null | undefined, pending = false): boolean {
  if (pending || !slot) return false;
  if (slot.approved) return false;
  return Boolean(aid(slot.asset_id));
}

export function propIdentityReady(prop: PropEntity | null | undefined): boolean {
  return Boolean(approvedPrimaryAssetId(prop));
}

export function missingOptionalViews(prop: PropEntity | null | undefined): string[] {
  const angles = prop?.angles || {};
  return OPTIONAL_PROP_VIEWS.filter((key) => {
    const slot = angles[key] as PropAngleSlot | undefined;
    return !(slot?.approved && aid(slot.asset_id));
  });
}

export function missingRequiredViews(prop: PropEntity | null | undefined): string[] {
  const angles = prop?.angles || {};
  return REQUIRED_PROP_VIEWS.filter((key) => {
    const slot = angles[key] as PropAngleSlot | undefined;
    return !(slot?.approved && aid(slot.asset_id));
  });
}

export function approvedComposeViews(prop: PropEntity | null | undefined): string[] {
  if (!propIdentityReady(prop)) return [];
  const views: string[] = ["primary"];
  const angles = prop?.angles || {};
  for (const key of OPTIONAL_PROP_VIEWS) {
    const slot = angles[key] as PropAngleSlot | undefined;
    if (slot?.approved && aid(slot.asset_id)) views.push(key);
  }
  return views;
}

export function canComposeAdvancedSheet(prop: PropEntity | null | undefined): boolean {
  return propIdentityReady(prop);
}
