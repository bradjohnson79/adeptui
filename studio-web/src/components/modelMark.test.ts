import assert from "node:assert/strict";
import test from "node:test";
import { modelMark } from "./modelMark.ts";

test("honest model mark: ✓ only when installed AND healthy", () => {
  assert.equal(modelMark(true, true), "✓");
});

test("honest model mark: ○ when not installed (even if default)", () => {
  // The previous logic showed ✓ for the default provider even when uninstalled.
  // This regression test pins the honest behavior: uninstalled → ○, never ✓.
  assert.equal(modelMark(false, false), "○");
  assert.equal(modelMark(false, true), "○");
});

test("honest model mark: ○ when installed but unhealthy", () => {
  assert.equal(modelMark(true, false), "○");
});

test("honest model mark: ○ when unknown", () => {
  assert.equal(modelMark(undefined, undefined), "○");
});
