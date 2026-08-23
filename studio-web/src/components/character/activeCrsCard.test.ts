import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { resolveActiveCrsCard } from "./activeCrsCard";

describe("resolveActiveCrsCard", () => {
  it("keeps the approved sheet when the pack draft has no image", () => {
    const resolved = resolveActiveCrsCard({
      approvedAssetId: "b6ab-approved",
      crsRevision: 3,
      draft: {
        status: "failed",
        provenance: "LOCAL — Qwen Image 2512 — Reference Conditioned",
        label: "Hero",
      },
      characterName: "Korri",
    });
    expect(resolved.status).toBe("approved");
    expect(resolved.hero?.sheetAssetId || resolved.hero?.assetId).toBe("b6ab-approved");
    expect(resolved.revision).toBe(3);
  });

  it("shows a new draft only when it has a different viewable image", () => {
    const resolved = resolveActiveCrsCard({
      approvedAssetId: "b6ab-approved",
      crsRevision: 3,
      draft: { assetId: "new-draft", status: "done", label: "Candidate 1" },
    });
    expect(resolved.status).toBe("draft");
    expect(resolved.hero?.assetId).toBe("new-draft");
    expect(resolved.showBoth).toBe(true);
    expect(resolved.canon?.assetId).toBe("b6ab-approved");
    expect(resolved.draft?.assetId).toBe("new-draft");
  });

  it("does not treat the approved image as a draft when the pack repeats it", () => {
    const resolved = resolveActiveCrsCard({
      approvedAssetId: "b6ab-approved",
      draft: { sheetAssetId: "b6ab-approved", status: "done" },
    });
    expect(resolved.status).toBe("approved");
  });

  it("shows a generating draft when nothing is approved yet", () => {
    const resolved = resolveActiveCrsCard({
      draft: { status: "generating", label: "Hero" },
    });
    expect(resolved.status).toBe("draft");
    expect(resolved.hero?.status).toBe("generating");
  });

  it("does not call a generating sheet missing when the image is not ready yet", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const card = readFileSync(join(here, "CharacterActiveCrsCard.tsx"), "utf8");
    expect(card).toContain("character-active-crs-thumb-generating");
    expect(card).toContain("Generating Character Reference Sheet");
    expect(card).toContain("isLiveGenerating(hero)");
    expect(card.indexOf("isLiveGenerating(hero)")).toBeLessThan(
      card.indexOf("The Character Reference Sheet image is missing."),
    );
  });

  it("treats a finished Front-only V2 image as a viewable draft", () => {
    const resolved = resolveActiveCrsCard({
      draft: {
        assetId: "front-tile-only",
        status: "done",
        viewJobs: [{ role: "hero_identity", status: "done", assetId: "front-tile-only" }],
      },
    });
    expect(resolved.status).toBe("draft");
    expect(resolved.hero?.assetId).toBe("front-tile-only");
  });

  it("shows a generating draft (Reject-able) over the approved sheet, but preserves the approved canon", () => {
    // P9 fix: a generating draft with no asset must NOT be hidden behind the
    // approved sheet. It takes the draft hero slot so Reject/cancel is
    // reachable; the approved look is preserved via canon + showBoth.
    const resolved = resolveActiveCrsCard({
      approvedAssetId: "b6ab-approved",
      crsRevision: 3,
      draft: { status: "generating", label: "Hero" },
    });
    expect(resolved.status).toBe("draft");
    expect(resolved.hero?.status).toBe("generating");
    expect(resolved.canon?.sheetAssetId || resolved.canon?.assetId).toBe("b6ab-approved");
    expect(resolved.showBoth).toBe(true);
    expect(resolved.revision).toBe(3);
  });

  it("still keeps the approved sheet when the draft is failed (not generating)", () => {
    // A failed draft must not hide the approved look — only a
    // live-generating draft takes the hero slot.
    const resolved = resolveActiveCrsCard({
      approvedAssetId: "b6ab-approved",
      crsRevision: 3,
      draft: { status: "failed", label: "Hero" },
    });
    expect(resolved.status).toBe("approved");
    expect(resolved.hero?.sheetAssetId || resolved.hero?.assetId).toBe("b6ab-approved");
  });

});


describe("Approve / Reject confirm (shared card, no candidate grid)", () => {
  it("exposes Reject only for draft status on the shared card", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const card = readFileSync(join(here, "CharacterActiveCrsCard.tsx"), "utf8");
    expect(card).toContain("character-active-crs-reject");
    expect(card).toContain("onReject");
    expect(card).toMatch(/status !== "approved" && onReject/);
    expect(card).not.toContain("CharacterCandidateGrid");
  });

  it("CharacterCore always confirms Approve and Reject with Adept Dialog", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const core = readFileSync(join(here, "CharacterCore.tsx"), "utf8");
    expect(core).toContain('from "../ui/Dialog"');
    expect(core).toContain("character-approve-crs-dialog");
    expect(core).toContain("character-reject-crs-dialog");
    expect(core).toContain("requestApprove");
    const approveFn = core.slice(core.indexOf("const handleApprove"), core.indexOf("const requestApprove"));
    expect(approveFn).not.toContain("window.confirm");
    expect(core).not.toContain("CharacterCandidateGrid");
  });

  it("Reject dialog stays open during async and blocks dismiss while busy", () => {
    // P9 dismiss-path audit: Confirm/Cancel/Escape/backdrop/double-click must
    // all be blocked while the reject request is in flight, and the dialog
    // must not auto-close on primary (caller closes in finally).
    const here = dirname(fileURLToPath(import.meta.url));
    const core = readFileSync(join(here, "CharacterCore.tsx"), "utf8");
    // Anchor on the reject dialog's unique open prop (it appears before the
    // other props in the JSX), then slice to its closing </Dialog>.
    const start = core.indexOf("open={!!rejectTarget}");
    const end = core.indexOf("</Dialog>", start) + "</Dialog>".length;
    const rejectDialog = core.slice(start, end);
    expect(rejectDialog).toContain("closeOnPrimary={false}");
    expect(rejectDialog).toContain("primaryDisabled={crsActionBusy}");
    expect(rejectDialog).toContain("primaryLoading={crsActionBusy}");
    // onClose (Cancel/Escape/backdrop) must be guarded by !crsActionBusy.
    expect(rejectDialog).toMatch(/onClose[\s\S]*if \(!crsActionBusy\) setRejectTarget\(null\)/);
    // handleReject must clear rejectTarget in finally so network failure /
    // already-gone still dismiss the spinner.
    const handleReject = core.slice(core.indexOf("const handleReject"), core.indexOf("const handleUseAsIdentity"));
    expect(handleReject).toContain("setRejectTarget(null)");
    expect(handleReject).toContain("finally");
  });

  it("handleReject allows reject-during-gen via jobId (no longer refuses a generating draft)", () => {
    // P10: Reject during generation must cancel the in-flight job, not refuse.
    // The handler now uses the jobId as candidateKey when there is no assetId,
    // and only refuses when there is neither an asset nor a job to reject.
    const here = dirname(fileURLToPath(import.meta.url));
    const core = readFileSync(join(here, "CharacterCore.tsx"), "utf8");
    const handleReject = core.slice(core.indexOf("const handleReject"), core.indexOf("const handleUseAsIdentity"));
    expect(handleReject).toContain("Reject-during-gen");
    expect(handleReject).toContain("candidateKey");
    // It must NOT short-circuit on a missing assetId alone.
    expect(handleReject).not.toContain("That look is still generating");
    // It passes candidateId (jobId) to the backend so the job is cancelled.
    expect(handleReject).toContain("candidateId: candidateKey");
  });
});
