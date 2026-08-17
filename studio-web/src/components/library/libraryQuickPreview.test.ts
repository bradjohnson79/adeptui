import assert from "node:assert/strict";
import test from "node:test";
import { eventFromActionControl, isQuickPreviewKind } from "./libraryQuickPreview.ts";

test("Quick Preview only opens for image, video, and audio", () => {
  assert.equal(isQuickPreviewKind("image"), true);
  assert.equal(isQuickPreviewKind("video"), true);
  assert.equal(isQuickPreviewKind("audio"), true);
  assert.equal(isQuickPreviewKind("document"), false);
  assert.equal(isQuickPreviewKind("pdf"), false);
});

test("action controls do not open Quick Preview without a DOM element", () => {
  assert.equal(eventFromActionControl(null), false);
  assert.equal(eventFromActionControl({} as EventTarget), false);
});
