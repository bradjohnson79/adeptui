import type { CharacterCandidate } from "./types";

export type ActiveCrsStatus = "approved" | "draft" | "none";

export function candidateAssetId(c: CharacterCandidate | null | undefined): string {
  const sheet = String(c?.sheetAssetId || "").trim();
  if (sheet) return sheet;
  const views = c?.viewJobs || [];
  const identityOnly =
    views.length === 1 &&
    ["hero_identity", "front", "front_full"].includes(String(views[0].role || views[0].viewRole || ""));
  if (identityOnly) {
    return String(views[0].assetId || c?.assetId || "").trim();
  }
  if (views.length) return "";
  return String(c?.assetId || "").trim();
}

export function isLiveGenerating(c: CharacterCandidate | null | undefined): boolean {
  const status = String(c?.status || "").trim().toLowerCase();
  if (status === "generating" || status === "queued" || status === "starting" || status === "running") {
    return true;
  }
  const views = c?.viewJobs || [];
  if (views.length && !String(c?.sheetAssetId || "").trim()) {
    return views.some((view) => {
      const viewStatus = String(view.status || "").trim().toLowerCase();
      return viewStatus !== "done" && viewStatus !== "failed" && viewStatus !== "error" && viewStatus !== "cancelled";
    });
  }
  return false;
}

/**
 * Active CRS card selection.
 *
 * A failed or empty visual-sheet candidate must not hide the approved look.
 * Draft only wins when it has a different viewable image (ready to Approve).
 */
function canonHero(args: {
  approvedAssetId: string;
  approvedMatch?: CharacterCandidate | null;
  characterName?: string;
}): CharacterCandidate {
  const match = args.approvedMatch;
  return match
    ? { ...match, assetId: args.approvedAssetId, sheetAssetId: match.sheetAssetId || args.approvedAssetId }
    : {
        assetId: args.approvedAssetId,
        sheetAssetId: args.approvedAssetId,
        label: args.characterName || "Character Reference Sheet",
        status: "done",
        qualityTier: "2K",
      };
}

export function resolveActiveCrsSheets(args: {
  approvedAssetId?: string | null;
  crsRevision?: number | null;
  draft?: CharacterCandidate | null;
  approvedMatch?: CharacterCandidate | null;
  characterName?: string;
}): {
  canon: CharacterCandidate | null;
  draft: CharacterCandidate | null;
  showBoth: boolean;
} {
  const approvedId = String(args.approvedAssetId || "").trim();
  const draft = args.draft || null;
  const draftId = candidateAssetId(draft);
  const distinctDraft = Boolean(draft && draftId && draftId !== approvedId);
  const liveDraft = Boolean(draft && (draftId || isLiveGenerating(draft)));
  // A generating draft with no asset yet (e.g. SenseNova loader still
  // running). This must NOT be hidden behind the approved sheet — the
  // creator needs to see it to Reject/cancel the in-flight job.
  const generatingDraft = Boolean(draft && !draftId && isLiveGenerating(draft));
  const canon = approvedId
    ? canonHero({
        approvedAssetId: approvedId,
        approvedMatch: args.approvedMatch,
        characterName: args.characterName,
      })
    : null;
  // Show the draft if it is a distinct ready draft OR a live-generating
  // draft. The approved canon is preserved via canon + showBoth so the
  // approved look is never lost when a generating draft takes the hero slot.
  const shownDraft = distinctDraft || generatingDraft
    ? draft
    : !approvedId && liveDraft
      ? draft
      : null;
  return {
    canon,
    draft: shownDraft,
    showBoth: Boolean(canon && (distinctDraft || generatingDraft)),
  };
}

export function resolveActiveCrsCard(args: {
  approvedAssetId?: string | null;
  crsRevision?: number | null;
  draft?: CharacterCandidate | null;
  approvedMatch?: CharacterCandidate | null;
  characterName?: string;
}): {
  hero: CharacterCandidate | null;
  status: ActiveCrsStatus;
  revision: number | null;
  canon: CharacterCandidate | null;
  draft: CharacterCandidate | null;
  showBoth: boolean;
} {
  const approvedId = String(args.approvedAssetId || "").trim();
  const draft = args.draft || null;
  const draftId = candidateAssetId(draft);
  const revision = typeof args.crsRevision === "number" && args.crsRevision > 0 ? args.crsRevision : null;
  const sheets = resolveActiveCrsSheets(args);
  const generatingDraft = Boolean(draft && !draftId && isLiveGenerating(draft));

  if (draftId && draftId !== approvedId) {
    return {
      hero: draft,
      status: "draft",
      revision: (draft as { revision?: number })?.revision ?? revision,
      canon: sheets.canon,
      draft: sheets.draft,
      showBoth: sheets.showBoth,
    };
  }

  // A generating draft (no asset yet) alongside an approved sheet: show it as
  // the draft hero so Reject/cancel is reachable. The approved look is
  // preserved via canon + showBoth — it is NOT lost. Previously this returned
  // status "approved", which hid the in-flight job and made Reject a no-op.
  if (approvedId && generatingDraft) {
    return {
      hero: draft,
      status: "draft",
      revision,
      canon: sheets.canon,
      draft,
      showBoth: true,
    };
  }

  if (approvedId) {
    return {
      hero: sheets.canon,
      status: "approved",
      revision,
      canon: sheets.canon,
      draft: sheets.draft,
      showBoth: sheets.showBoth,
    };
  }

  if (draft && (draftId || isLiveGenerating(draft))) {
    return { hero: draft, status: "draft", revision, canon: null, draft, showBoth: false };
  }

  return { hero: null, status: "none", revision, canon: null, draft: null, showBoth: false };
}
