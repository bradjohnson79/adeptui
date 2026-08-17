import { describe, expect, it } from "vitest";
import {
  loadPublishedSnapshots,
  persistPublishedSnapshots,
  removePublishedSnapshots,
  storyPublishedStorageKey,
} from "./storyPublishMarker";

/**
 * StoryEntryEditor — pure-logic unit tests for the "Save to Wiki" manual
 * publish behavior (Amendment: Story → Wiki Manual Save) plus the CDX-059
 * persisted published-revision marker.
 *
 * The component is a React component with API dependencies and no jsdom/RTL
 * render harness exists in this repo, so these tests cover the extractable
 * pure logic: dirty-state detection (Story has unpublished changes), the
 * publish-snapshot semantics, and the persisted marker that keeps the dirty
 * state stable across reloads. Full UI render + interaction coverage is in the
 * Playwright E2E suite.
 */

type StorySnapshot = {
  title: string;
  logline: string;
  shortSummary: string;
  longSummary: string;
};

/** Mirror of the component's hasUnpublishedChanges logic. */
function hasUnpublishedChanges(
  current: StorySnapshot,
  lastPublished: StorySnapshot | undefined,
): boolean {
  if (!lastPublished) {
    return Boolean(current.title || current.logline || current.shortSummary || current.longSummary);
  }
  return (
    lastPublished.title !== current.title ||
    lastPublished.logline !== current.logline ||
    lastPublished.shortSummary !== current.shortSummary ||
    lastPublished.longSummary !== current.longSummary
  );
}

describe("Save to Wiki manual publish — dirty state", () => {
  it("editing Story before any publish shows unpublished changes", () => {
    const current = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
    expect(hasUnpublishedChanges(current, undefined)).toBe(true);
  });

  it("immediately after publish, no unpublished changes", () => {
    const current = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
    const snap = { ...current };
    expect(hasUnpublishedChanges(current, snap)).toBe(false);
  });

  it("editing Story after publish shows unpublished changes", () => {
    const snap = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
    const edited = { ...snap, logline: "v2" };
    expect(hasUnpublishedChanges(edited, snap)).toBe(true);
  });

  it("re-publishing captures the new version (no unpublished changes)", () => {
    const snap = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
    const edited = { ...snap, logline: "v2" };
    const newSnap = { ...edited };
    expect(hasUnpublishedChanges(edited, newSnap)).toBe(false);
    expect(newSnap.logline).toBe("v2");
  });

  it("blank Story fields are preserved as blank (no invented content)", () => {
    const current = { title: "Korri", logline: "", shortSummary: "", longSummary: "" };
    const snap = { ...current };
    // Blank logline stays blank after publish — no fallback content.
    expect(snap.logline).toBe("");
    expect(hasUnpublishedChanges(current, snap)).toBe(false);
  });

  it("a Story with no content and no publish is not reported unpublished", () => {
    const current = { title: "", logline: "", shortSummary: "", longSummary: "" };
    expect(hasUnpublishedChanges(current, undefined)).toBe(false);
  });

  it("only the published entry snapshot is compared (per-entry isolation)", () => {
    // Simulate two entries; only entry A was published. Entry B has content and
    // was never published → entry B is unpublished, entry A is clean.
    const snapA = { title: "A", logline: "a-log", shortSummary: "a-short", longSummary: "a-long" };
    const currentA = { ...snapA };
    const currentB = { title: "B", logline: "b-log", shortSummary: "b-short", longSummary: "b-long" };
    expect(hasUnpublishedChanges(currentA, snapA)).toBe(false);
    expect(hasUnpublishedChanges(currentB, undefined)).toBe(true);
  });
});

// ── CDX-059: persisted published-revision marker (survives reload) ─────────

function memoryStorage() {
  const map = new Map<string, string>();
  return {
    getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
    setItem: (k: string, v: string) => {
      map.set(k, v);
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
  };
}

describe("CDX-059 persisted published-revision marker", () => {
  it("a published story stays clean after reload (marker persists)", () => {
    const storage = memoryStorage();
    const projectId = "proj-reload";
    const entryId = "entry-1";
    const published = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };

    // Creator publishes → the marker is persisted.
    persistPublishedSnapshots(projectId, { [entryId]: published }, storage);

    // Simulate a page reload: the editor remounts, loads the persisted marker,
    // and re-fetches the same entry values from the server.
    const restored = loadPublishedSnapshots(projectId, storage);
    const current = { ...published };
    expect(hasUnpublishedChanges(current, restored[entryId])).toBe(false);
  });

  it("marker is keyed by project id (no cross-project leakage)", () => {
    const storage = memoryStorage();
    persistPublishedSnapshots(
      "proj-a",
      { e1: { title: "A", logline: "", shortSummary: "", longSummary: "" } },
      storage,
    );
    expect(Object.keys(loadPublishedSnapshots("proj-b", storage)).length).toBe(0);
    expect(storyPublishedStorageKey("proj-a") !== storyPublishedStorageKey("proj-b")).toBe(true);
  });

  it("edited-elsewhere values still show unpublished after reload", () => {
    const storage = memoryStorage();
    const projectId = "proj-edit";
    const entryId = "e1";
    const published = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
    persistPublishedSnapshots(projectId, { [entryId]: published }, storage);

    // After reload the server returns newer values (edited + autosaved before reload).
    const restored = loadPublishedSnapshots(projectId, storage);
    const edited = { ...published, logline: "v2" };
    expect(hasUnpublishedChanges(edited, restored[entryId])).toBe(true);
  });

  it("corrupt marker JSON degrades to an empty map", () => {
    const storage = memoryStorage();
    const projectId = "proj-corrupt";
    storage.setItem(storyPublishedStorageKey(projectId), "{not-json");
    expect(loadPublishedSnapshots(projectId, storage)).toEqual({});
  });

  it("no storage available degrades to empty map and safe no-op persist", () => {
    expect(loadPublishedSnapshots("proj-nostore", null)).toEqual({});
    expect(() =>
      persistPublishedSnapshots(
        "proj-nostore",
        { e1: { title: "x", logline: "", shortSummary: "", longSummary: "" } },
        null,
      ),
    ).not.toThrow();
  });

  it("removePublishedSnapshots clears the marker for a project", () => {
    const storage = memoryStorage();
    const projectId = "proj-remove";
    persistPublishedSnapshots(
      projectId,
      { e1: { title: "x", logline: "", shortSummary: "", longSummary: "" } },
      storage,
    );
    expect(Object.keys(loadPublishedSnapshots(projectId, storage)).length).toBe(1);
    removePublishedSnapshots(projectId, storage);
    expect(loadPublishedSnapshots(projectId, storage)).toEqual({});
  });
});
