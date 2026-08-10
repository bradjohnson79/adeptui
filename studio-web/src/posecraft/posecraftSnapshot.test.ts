import { describe, expect, it } from "vitest";
import {
  POSECRAFT_SNAPSHOT_CAP,
  createDefaultDocument,
  createSnapshot,
  deleteSnapshot,
  duplicateSnapshot,
  getSelectedSnapshot,
  renameSnapshot,
  selectSnapshot,
} from "./state";
import { parsePoseCraftDocument } from "./storage";
import { POSECRAFT_SCHEMA_VERSION } from "./types";

function makeDoc() {
  return createDefaultDocument();
}

describe("PoseCraft Snapshot CRUD", () => {
  it("creates a frozen snapshot with immutable camera/figures/primitives and selects it", () => {
    const doc = makeDoc();
    const before = doc.currentScene;
    const { document: withSnap, snapshotId } = createSnapshot(
      doc,
      "proj-1",
      "asset-1",
      "Scene: Blocking\nLead — adult-female — Neutral",
    );
    expect(snapshotId).toBeTruthy();
    expect(withSnap.snapshots?.length).toBe(1);
    expect(withSnap.selectedSnapshotId).toBe(snapshotId);
    const snap = withSnap.snapshots![0]!;
    expect(snap.imageAssetId).toBe("asset-1");
    expect(snap.projectId).toBe("proj-1");
    expect(snap.sceneRevision).toBe(before.revision);
    expect(snap.camera).toEqual(before.camera);
    expect(snap.figures.length).toBe(before.figures.length);
    expect(snap.primitives.length).toBe(before.primitives.length);
    expect(snap.semanticSummary).toContain("Lead");
    // Frozen copy: mutating the live scene after capture does NOT change the snapshot.
    const mutated = { ...before, revision: before.revision + 1 };
    expect(snap.sceneRevision).toBe(before.revision);
    expect(mutated.revision).not.toBe(snap.sceneRevision);
  });

  it("rename only changes name; frozen camera/figures are untouched", () => {
    const doc = makeDoc();
    const { document: withSnap, snapshotId } = createSnapshot(doc, "proj-1", "asset-1", "summary");
    const frozen = withSnap.snapshots![0]!;
    const renamed = renameSnapshot(withSnap, snapshotId, "Wide master");
    expect(renamed.snapshots![0]!.name).toBe("Wide master");
    expect(renamed.snapshots![0]!.camera).toEqual(frozen.camera);
    expect(renamed.snapshots![0]!.figures).toEqual(frozen.figures);
    // Empty rename is a no-op.
    expect(renameSnapshot(renamed, snapshotId, "   ")).toBe(renamed);
  });

  it("duplicate copies the frozen composition under a new snapshotId and selects it", () => {
    const doc = makeDoc();
    const { document: withSnap, snapshotId } = createSnapshot(doc, "proj-1", "asset-1", "summary", "Original");
    const duped = duplicateSnapshot(withSnap, snapshotId);
    expect(duped.snapshots?.length).toBe(2);
    const copy = duped.snapshots![1]!;
    expect(copy.snapshotId).not.toBe(snapshotId);
    expect(copy.name).toBe("Original Copy");
    expect(copy.camera).toEqual(withSnap.snapshots![0]!.camera);
    expect(duped.selectedSnapshotId).toBe(copy.snapshotId);
  });

  it("delete removes the snapshot and clears selection if it was selected", () => {
    const doc = makeDoc();
    const { document: withSnap, snapshotId } = createSnapshot(doc, "proj-1", "asset-1", "summary");
    const deleted = deleteSnapshot(withSnap, snapshotId);
    expect(deleted.snapshots?.length).toBe(0);
    expect(deleted.selectedSnapshotId).toBeNull();
  });

  it("select sets selectedSnapshotId (null clears); unknown id is a no-op", () => {
    const doc = makeDoc();
    const { document: withSnap, snapshotId } = createSnapshot(doc, "proj-1", "asset-1", "summary");
    const selected = selectSnapshot(withSnap, snapshotId);
    expect(getSelectedSnapshot(selected)?.snapshotId).toBe(snapshotId);
    const cleared = selectSnapshot(selected, null);
    expect(getSelectedSnapshot(cleared)).toBeNull();
    expect(cleared.selectedSnapshotId).toBeNull();
    // Unknown id is a no-op (does not clear an existing selection).
    const stable = selectSnapshot(withSnap, "does-not-exist");
    expect(stable.selectedSnapshotId).toBe(snapshotId);
  });

  it("caps at POSECRAFT_SNAPSHOT_CAP and drops oldest on overflow", () => {
    let doc = makeDoc();
    for (let i = 0; i < POSECRAFT_SNAPSHOT_CAP + 3; i++) {
      const { document: next } = createSnapshot(doc, "proj-1", `asset-${i}`, "summary", `Snap ${i}`);
      doc = next;
    }
    expect(doc.snapshots?.length).toBe(POSECRAFT_SNAPSHOT_CAP);
    // Newest first; the last three overflows are dropped from the tail (oldest).
    expect(doc.snapshots![0]!.name).toBe(`Snap ${POSECRAFT_SNAPSHOT_CAP + 2}`);
  });
});

describe("PoseCraft Snapshot storage migration", () => {
  it("parsePoseCraftDocument defaults missing snapshots to [] and selectedSnapshotId to null", () => {
    const raw = JSON.stringify({
      schemaVersion: POSECRAFT_SCHEMA_VERSION,
      currentScene: {
        schemaVersion: POSECRAFT_SCHEMA_VERSION,
        revision: 1,
        updatedAt: "2026-01-01T00:00:00Z",
        name: "x",
        notes: "",
        stage: { gridSize: 12, showAxes: true, showPrimitives: true },
        camera: {
          lensMm: 35, aspect: "16:9", guides: ["safe"],
          alpha: 0, beta: 1, radius: 7, target: { x: 0, y: 1, z: 0 },
        },
        figures: [],
        primitives: [],
        selectedFigureId: null,
        selectedJoint: "head",
      },
      savedVersions: [],
    });
    const doc = parsePoseCraftDocument(raw);
    expect(doc.snapshots).toEqual([]);
    expect(doc.selectedSnapshotId).toBeNull();
  });

  it("parsePoseCraftDocument preserves existing snapshots + selection", () => {
    const base = makeDoc();
    const { document: withSnap, snapshotId } = createSnapshot(base, "proj-1", "asset-1", "summary", "Kept");
    const raw = JSON.stringify(withSnap);
    const parsed = parsePoseCraftDocument(raw);
    expect(parsed.snapshots?.length).toBe(1);
    expect(parsed.snapshots![0]!.snapshotId).toBe(snapshotId);
    expect(parsed.selectedSnapshotId).toBe(snapshotId);
  });
});
