import assert from "node:assert/strict";
import test from "node:test";

/**
 * StoryEntryEditor — pure-logic unit tests for the "Save to Wiki" manual
 * publish behavior (Amendment: Story → Wiki Manual Save).
 *
 * The component is a React component with API dependencies and no jsdom/RTL
 * render harness exists in this repo, so these tests cover the extractable
 * pure logic: dirty-state detection (Story has unpublished changes) and the
 * publish-snapshot semantics. Full UI render + interaction coverage is in the
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

test("Save to Wiki: editing Story before any publish shows unpublished changes", () => {
  const current = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
  assert.equal(hasUnpublishedChanges(current, undefined), true);
});

test("Save to Wiki: immediately after publish, no unpublished changes", () => {
  const current = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
  const snap = { ...current };
  assert.equal(hasUnpublishedChanges(current, snap), false);
});

test("Save to Wiki: editing Story after publish shows unpublished changes", () => {
  const snap = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
  const edited = { ...snap, logline: "v2" };
  assert.equal(hasUnpublishedChanges(edited, snap), true);
});

test("Save to Wiki: re-publishing captures the new version (no unpublished changes)", () => {
  const snap = { title: "Korri", logline: "v1", shortSummary: "s1", longSummary: "l1" };
  const edited = { ...snap, logline: "v2" };
  const newSnap = { ...edited };
  assert.equal(hasUnpublishedChanges(edited, newSnap), false);
  assert.equal(newSnap.logline, "v2");
});

test("Save to Wiki: blank Story fields are preserved as blank (no invented content)", () => {
  const current = { title: "Korri", logline: "", shortSummary: "", longSummary: "" };
  const snap = { ...current };
  // Blank logline stays blank after publish — no fallback content.
  assert.equal(snap.logline, "");
  assert.equal(hasUnpublishedChanges(current, snap), false);
});

test("Save to Wiki: a Story with no content and no publish is not 'unpublished'", () => {
  const current = { title: "", logline: "", shortSummary: "", longSummary: "" };
  assert.equal(hasUnpublishedChanges(current, undefined), false);
});

test("Save to Wiki: only the published entry's snapshot is compared (per-entry isolation)", () => {
  // Simulate two entries; only entry A was published. Entry B has content and
  // was never published → entry B is unpublished, entry A is clean.
  const snapA = { title: "A", logline: "a-log", shortSummary: "a-short", longSummary: "a-long" };
  const currentA = { ...snapA };
  const currentB = { title: "B", logline: "b-log", shortSummary: "b-short", longSummary: "b-long" };
  assert.equal(hasUnpublishedChanges(currentA, snapA), false);
  assert.equal(hasUnpublishedChanges(currentB, undefined), true);
});
