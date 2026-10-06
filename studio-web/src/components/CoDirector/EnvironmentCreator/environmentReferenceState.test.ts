import { describe, expect, it } from "vitest";
import {
  ERS_NOT_CREATED_MESSAGE,
  environmentDraftStatusLabel,
  environmentReferenceStatusLabel,
  isOwnedEnvironmentDraft,
  isProjectEnvironmentReferenceSheet,
  isErsSnapshotSheet,
  resolveErsEditMasterId,
  ersListDisplayLabel,
} from "./environmentReferenceState";

describe("environment reference state", () => {
  it("keeps a name-only draft out of the reference sheet list", () => {
    const draft = { name: "Coffee House", status: "draft", ers_composite_asset_id: null, projectId: "p1" };
    expect(isProjectEnvironmentReferenceSheet(draft)).toBe(false);
    expect(isOwnedEnvironmentDraft(draft, "p1")).toBe(true);
    expect(environmentDraftStatusLabel({})).toBe("Draft");
  });

  it("keeps a reference image draft out of the reference sheet list", () => {
    const draft = { status: "draft", ers_composite_asset_id: "", projectId: "p1" };
    expect(isProjectEnvironmentReferenceSheet(draft)).toBe(false);
  });

  it("lists an approved official visual and a generated sheet", () => {
    expect(
      isProjectEnvironmentReferenceSheet({ status: "approved", ers_composite_asset_id: "asset-1", projectId: "p1" }),
    ).toBe(true);
    expect(environmentReferenceStatusLabel({ status: "approved" })).toBe("Approved Environment (Original)");
    expect(
      isProjectEnvironmentReferenceSheet({ status: "draft", ers_composite_asset_id: "asset-2", projectId: "p1" }),
    ).toBe(true);
    expect(environmentReferenceStatusLabel({ status: "draft" })).toBe("ERS Ready (Original)");
    expect(isOwnedEnvironmentDraft({ ers_composite_asset_id: "asset-2", projectId: "p1" }, "p1")).toBe(false);
  });

  it("does not treat another project's unfinished sheet as a local draft", () => {
    expect(isOwnedEnvironmentDraft({ projectId: "other", ers_composite_asset_id: null }, "p1")).toBe(false);
  });

  it("uses the conversational failure sentence", () => {
    expect(ERS_NOT_CREATED_MESSAGE).toContain("wasn’t created");
    expect(ERS_NOT_CREATED_MESSAGE).not.toContain("draft");
    expect(environmentDraftStatusLabel({ generating: true })).toBe("Generating ERS");
    expect(environmentDraftStatusLabel({ failed: true })).toBe("Generation Failed");
  });
});


describe("ERS snapshot list helpers", () => {
  it("detects snapshots and routes Edit to the master", () => {
    const snap = {
      recordKind: "snapshot",
      isEditableMaster: false,
      snapshotNumber: 2,
      snapshotOfSheetId: "master-1",
      parentSheetId: "master-1",
      ers_composite_asset_id: "baked-1",
    };
    expect(isErsSnapshotSheet(snap)).toBe(true);
    expect(environmentReferenceStatusLabel(snap)).toBe("Snapshot SS-2");
    expect(resolveErsEditMasterId(snap, "snap-id")).toBe("master-1");
    expect(isErsSnapshotSheet({ status: "approved", ers_composite_asset_id: "a" })).toBe(false);
  });
});


describe("ERS list display labels", () => {
  it("keeps original name exact and labels snapshots as SS-N only", () => {
    expect(
      ersListDisplayLabel({ name: "Schnick Coffee Shop", status: "approved", ers_composite_asset_id: "a" }),
    ).toBe("Schnick Coffee Shop");
    expect(
      ersListDisplayLabel({
        name: "Schnick Coffee Shop SS-2",
        recordKind: "snapshot",
        snapshotNumber: 2,
        snapshotOfSheetId: "m",
        ers_composite_asset_id: "b",
      }),
    ).toBe("Schnick Coffee Shop SS-2");
    expect(
      ersListDisplayLabel({
        name: "Schnick Coffee Shop",
        recordKind: "snapshot",
        snapshotNumber: 3,
        snapshotOfSheetId: "m",
        ers_composite_asset_id: "c",
      }),
    ).toBe("Schnick Coffee Shop SS-3");
  });
});
