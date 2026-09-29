import { describe, expect, it } from "vitest";
import { applyPromptFragment, composeCameraFragment } from "./applyPromptFragment";
import { LIGHTING_PRESETS } from "./lightingPresets";
import { LENS_PRESETS } from "./lensPresets";
import { SCENE_PRESETS } from "./scenePresets";
import { SHOT_PRESETS } from "./shotPresets";

const beats = "0–5 sec\nCamera approaches the distant point of light.";

describe("prompt guide fragments", () => {
  it("gives every preset a sentence", () => {
    for (const preset of [...SCENE_PRESETS, ...LENS_PRESETS, ...SHOT_PRESETS, ...LIGHTING_PRESETS]) {
      expect(preset.promptFragment.trim().endsWith(".")).toBe(true);
      expect(preset.label.length).toBeGreaterThan(0);
    }
  });

  it("places a scene fragment above the filmmaker's beats", () => {
    const scene = SCENE_PRESETS.find((item) => item.id === "realistic-anime");
    const next = applyPromptFragment(beats, "scene", scene!.promptFragment, {});
    expect(next.prompt.startsWith(scene!.promptFragment)).toBe(true);
    expect(next.prompt.endsWith(beats)).toBe(true);
  });

  it("replaces only the previous scene helper", () => {
    const anime = SCENE_PRESETS.find((item) => item.id === "realistic-anime")!;
    const noir = SCENE_PRESETS.find((item) => item.id === "film-noir")!;
    const first = applyPromptFragment(beats, "scene", anime.promptFragment, {});
    const second = applyPromptFragment(first.prompt, "scene", noir.promptFragment, first.memory);
    expect(second.prompt.includes(anime.promptFragment)).toBe(false);
    expect(second.prompt.includes(noir.promptFragment)).toBe(true);
    expect(second.prompt.endsWith(beats)).toBe(true);
  });

  it("keeps filmmaker edits when the helper text no longer matches", () => {
    const anime = SCENE_PRESETS.find((item) => item.id === "realistic-anime")!;
    const noir = SCENE_PRESETS.find((item) => item.id === "film-noir")!;
    const first = applyPromptFragment(beats, "scene", anime.promptFragment, {});
    const edited = first.prompt.replace("Realistic anime", "My rewritten anime");
    const second = applyPromptFragment(edited, "scene", noir.promptFragment, first.memory);
    expect(second.prompt.includes("My rewritten anime")).toBe(true);
    expect(second.prompt.includes(beats)).toBe(true);
  });

  it("composes one camera sentence from lens and shot", () => {
    const lens = LENS_PRESETS.find((item) => item.id === "85mm")!;
    const shot = SHOT_PRESETS.find((item) => item.id === "mcu")!;
    const text = composeCameraFragment(lens, shot);
    expect(text.includes("85mm")).toBe(true);
    expect(text.includes("Medium Close-Up")).toBe(true);
    expect(text.split(".").filter(Boolean)).toHaveLength(1);
  });
});
