import assert from "node:assert/strict";
import test from "node:test";
import {
  LAYOUT_PRESET_RATIOS,
  primarySizeForPreset,
  type CoDirectorLayoutPreset,
} from "./layoutPresets.ts";

test("layout preset ratios are chat 70 / balanced 50 / project 30", () => {
  assert.equal(LAYOUT_PRESET_RATIOS["chat-focus"], 0.7);
  assert.equal(LAYOUT_PRESET_RATIOS.balanced, 0.5);
  assert.equal(LAYOUT_PRESET_RATIOS["project-focus"], 0.3);
});

test("primarySizeForPreset respects min width and ratio", () => {
  const presets: CoDirectorLayoutPreset[] = ["chat-focus", "balanced", "project-focus"];
  for (const preset of presets) {
    const size = primarySizeForPreset(1000, preset);
    assert.ok(size >= 280);
    assert.equal(size, Math.round(1000 * LAYOUT_PRESET_RATIOS[preset]));
  }
});
