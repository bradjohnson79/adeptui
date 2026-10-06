import { describe, expect, it } from "vitest";
import {
  ADDITIONAL_VIEWS_HINT,
  ADDITIONAL_VIEWS_TITLE,
  approvedComposeViews,
  canApprovePrimary,
  canApproveView,
  canComposeAdvancedSheet,
  missingOptionalViews,
  missingRequiredViews,
  propIdentityReady,
  validPrimaryCandidateAssetId,
  visiblePrimaryPreviewAssetId,
} from "./propApproval";
import type { PropAngleSlot, PropCandidate, PropEntity } from "./types";

function candidate(partial: Partial<PropCandidate> = {}): PropCandidate {
  return {
    id: "cand-1",
    prop_id: "prop-1",
    index: 0,
    job_id: "",
    asset_id: "asset-primary",
    status: "complete",
    source: "local",
    family: "upload",
    model: "uploaded",
    provenance_label: "Uploaded",
    conditioning: "description_guided",
    take_label: "Uploaded primary 1",
    origin: "uploaded",
    ...partial,
  };
}

function slot(partial: Partial<PropAngleSlot> = {}): PropAngleSlot {
  return {
    key: "front",
    status: "complete",
    asset_id: "asset-front",
    approved: false,
    source: "uploaded",
    ...partial,
  };
}

function prop(partial: Partial<PropEntity> = {}): PropEntity {
  return {
    id: "prop-1",
    project_id: "proj-1",
    tag: "Starfighter",
    display_label: "Cade Starfighter",
    library_asset_id: "",
    notes: "",
    visual_style: "",
    description: "",
    mode: "advanced",
    primary_phase: "review",
    candidates: [candidate()],
    ...partial,
  };
}

describe("Prop approval optionality", () => {
  it("enables Approve Primary after an uploaded candidate exists", () => {
    const entity = prop();
    expect(validPrimaryCandidateAssetId(entity)).toBe("asset-primary");
    expect(canApprovePrimary(entity)).toBe(true);
    expect(propIdentityReady(entity)).toBe(false);
  });

  it("disables Approve Primary when no candidate asset exists", () => {
    const entity = prop({ candidates: [] });
    expect(canApprovePrimary(entity)).toBe(false);
    expect(propIdentityReady(entity)).toBe(false);
  });

  it("re-enables Approve Primary after a replacement upload", () => {
    const entity = prop({
      primary_approved_asset_id: "asset-old",
      approved_asset_id: "asset-old",
      primary_phase: "approved",
      candidates: [candidate({ id: "old", asset_id: "asset-old" }), candidate({ id: "new", asset_id: "asset-new" })],
    });
    expect(canApprovePrimary(entity)).toBe(true);
  });

  it("previews the pending replacement instead of the stale approved Primary", () => {
    const entity = prop({
      primary_approved_asset_id: "asset-old-blue",
      approved_asset_id: "asset-old-blue",
      primary_phase: "approved",
      candidates: [
        candidate({ id: "old", asset_id: "asset-old-blue" }),
        candidate({ id: "new", asset_id: "asset-new-real" }),
      ],
    });
    expect(visiblePrimaryPreviewAssetId(entity)).toBe("asset-new-real");
    expect(visiblePrimaryPreviewAssetId(entity)).not.toBe("asset-old-blue");
  });

  it("previews the approved Primary when no replacement candidate exists", () => {
    const entity = prop({
      primary_approved_asset_id: "asset-primary",
      approved_asset_id: "asset-primary",
      primary_phase: "approved",
      candidates: [candidate({ asset_id: "asset-primary" })],
    });
    expect(visiblePrimaryPreviewAssetId(entity)).toBe("asset-primary");
  });

  it("does not treat empty optional views as identity blockers", () => {
    const entity = prop({
      primary_approved_asset_id: "asset-primary",
      approved_asset_id: "asset-primary",
      primary_phase: "approved",
      angles: {},
    });
    expect(propIdentityReady(entity)).toBe(true);
    expect(missingOptionalViews(entity)).toEqual(["front", "back", "left", "right", "top", "bottom", "hero"]);
  });

  it("approves optional view cards independently of Primary", () => {
    expect(canApproveView(slot())).toBe(true);
    expect(canApproveView(slot({ approved: true }))).toBe(false);
    expect(canApproveView(slot({ asset_id: null }))).toBe(false);
    expect(canApproveView(undefined)).toBe(false);
  });

  it("does not let optional views alone make identity valid", () => {
    const entity = prop({
      candidates: [],
      primary_approved_asset_id: null,
      approved_asset_id: null,
      angles: { front: slot({ approved: true }) },
    });
    expect(propIdentityReady(entity)).toBe(false);
    expect(canApprovePrimary(entity)).toBe(false);
    expect(canComposeAdvancedSheet(entity)).toBe(false);
  });

  it("titles additional views as optional, not required", () => {
    expect(ADDITIONAL_VIEWS_TITLE).toBe("Additional Views (optional)");
    expect(ADDITIONAL_VIEWS_HINT).toBe("Optional — add for stronger multi-angle consistency.");
    expect(ADDITIONAL_VIEWS_TITLE).not.toMatch(/required/i);
    expect(ADDITIONAL_VIEWS_HINT).not.toMatch(/required|approve front|hero is optional/i);
  });

  it("enables the Prop Reference Sheet when only Primary is approved", () => {
    const primaryOnly = prop({
      primary_approved_asset_id: "asset-primary",
      approved_asset_id: "asset-primary",
      primary_phase: "approved",
      angles: {},
    });
    expect(propIdentityReady(primaryOnly)).toBe(true);
    expect(canComposeAdvancedSheet(primaryOnly)).toBe(true);
    expect(approvedComposeViews(primaryOnly)).toEqual(["primary"]);
    expect(missingOptionalViews(primaryOnly)).toEqual(["front", "back", "left", "right", "top", "bottom", "hero"]);
  });

  it("composes the approved subset and skips missing optional views", () => {
    const angles = Object.fromEntries(
      ["front", "back", "left", "right", "top", "bottom"].map((key) => [
        key,
        slot({ key, approved: true, asset_id: `asset-${key}` }),
      ]),
    );
    const ready = prop({
      primary_approved_asset_id: "asset-primary",
      approved_asset_id: "asset-primary",
      primary_phase: "approved",
      angles,
    });
    expect(missingRequiredViews(ready)).toEqual([]);
    expect(canComposeAdvancedSheet(ready)).toBe(true);
    expect(approvedComposeViews(ready)).toEqual(["primary", "front", "back", "left", "right", "top", "bottom"]);
    const missingLeft = prop({
      ...ready,
      angles: { ...angles, left: slot({ key: "left", approved: false, asset_id: "asset-left" }) },
    });
    expect(missingRequiredViews(missingLeft)).toEqual(["left"]);
    expect(canComposeAdvancedSheet(missingLeft)).toBe(true);
    expect(approvedComposeViews(missingLeft)).toEqual(["primary", "front", "back", "right", "top", "bottom"]);
    expect(approvedComposeViews(missingLeft)).not.toContain("left");
    expect(approvedComposeViews(missingLeft)).not.toContain("hero");
  });
});
