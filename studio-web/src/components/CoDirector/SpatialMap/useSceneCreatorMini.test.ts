import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { LOCAL_GENERATION_ATTENTION } from "../../../runtime/localGenerationAttention";
import {
  MINI_GATE_GPT_NOT_READY,
  MINI_GATE_NO_OUTPUT,
  MINI_GATE_QWEN_UNAVAILABLE,
  MINI_GATE_SAVE,
  MINI_GATE_ZIMAGE_NOT_READY,
  sceneCreatorMiniEligibility,
  sceneCreatorMiniHasWork,
  type SceneCreatorMiniEligibilityInput,
} from "./useSceneCreatorMini";

const READY: Omit<SceneCreatorMiniEligibilityInput, "isDirty" | "includeCameras" | "cameraCount" | "includeWorldViews"> = {
  enabled: true,
  mapId: "map-1",
  busy: false,
  generator: "qwen2512",
  qwenReady: true,
  gptReady: true,
  zimageReady: true,
  localBlocked: false,
};

function gate(partial: Partial<SceneCreatorMiniEligibilityInput> = {}) {
  return sceneCreatorMiniEligibility({
    ...READY,
    isDirty: false,
    includeCameras: true,
    cameraCount: 2,
    includeWorldViews: false,
    ...partial,
  });
}

describe("Scene Creator Mini generate eligibility", () => {
  it("SAVED MAP → Generate enabled", () => {
    const next = gate({ isDirty: false });
    expect(next.canGenerate).toBe(true);
    expect(next.gateMessage).toBe("");
  });

  it("DIRTY MAP → Generate disabled + save reason", () => {
    const next = gate({ isDirty: true });
    expect(next.canGenerate).toBe(false);
    expect(next.gateMessage).toBe(MINI_GATE_SAVE);
    expect(next.gateMessage).toBe("Save Spatial Map to generate stills.");
  });

  it("SAVE TRANSITION → dirty → save success → enabled immediately", () => {
    const dirty = gate({ isDirty: true });
    expect(dirty.canGenerate).toBe(false);
    expect(dirty.gateMessage).toBe(MINI_GATE_SAVE);
    const saved = gate({ isDirty: false });
    expect(saved.canGenerate).toBe(true);
    expect(saved.gateMessage).toBe("");
  });

  it("FAILED PRIOR VARIATION → Generate still enabled if otherwise valid", () => {
    const keys = Object.keys(gate());
    expect(keys).not.toContain("take");
    expect(keys).not.toContain("result");
    expect(keys).not.toContain("job");
    expect(keys).not.toContain("variation");
    const next = gate({ isDirty: false });
    expect(next.canGenerate).toBe(true);
  });

  it("NO OUTPUT → disabled", () => {
    const none = gate({ includeCameras: false, cameraCount: 0, includeWorldViews: false });
    expect(none.hasWork).toBe(false);
    expect(none.canGenerate).toBe(false);
    expect(none.gateMessage).toBe(MINI_GATE_NO_OUTPUT);
    expect(none.gateMessage).toBe("Select Camera shots or Room views to generate.");

    const camerasOnButEmpty = gate({ includeCameras: true, cameraCount: 0, includeWorldViews: false });
    expect(camerasOnButEmpty.hasWork).toBe(false);
    expect(camerasOnButEmpty.canGenerate).toBe(false);
    expect(camerasOnButEmpty.gateMessage).toBe(MINI_GATE_NO_OUTPUT);
  });

  it("ONE OUTPUT cameras-only is eligible", () => {
    const next = gate({ includeCameras: true, cameraCount: 1, includeWorldViews: false });
    expect(sceneCreatorMiniHasWork(true, 1, false)).toBe(true);
    expect(next.hasWork).toBe(true);
    expect(next.canGenerate).toBe(true);
  });

  it("ONE OUTPUT room-views-only is eligible", () => {
    const next = gate({ includeCameras: false, cameraCount: 0, includeWorldViews: true });
    expect(sceneCreatorMiniHasWork(false, 0, true)).toBe(true);
    expect(next.hasWork).toBe(true);
    expect(next.canGenerate).toBe(true);
  });

  it("ACTIVE JOB → disabled; job finishes → recomputes", () => {
    const active = gate({ localBlocked: true });
    expect(active.canGenerate).toBe(false);
    expect(active.gateMessage).toBe(LOCAL_GENERATION_ATTENTION);
    const finished = gate({ localBlocked: false });
    expect(finished.canGenerate).toBe(true);
    expect(finished.gateMessage).toBe("");

    const requestActive = gate({ busy: true });
    expect(requestActive.canGenerate).toBe(false);
    const requestFinished = gate({ busy: false });
    expect(requestFinished.canGenerate).toBe(true);
    expect(requestFinished.gateMessage).toBe("");
  });

  it("no map is first after enabled and uses the save reason", () => {
    const next = gate({ mapId: "", isDirty: false, qwenReady: false, localBlocked: true });
    expect(next.canGenerate).toBe(false);
    expect(next.gateMessage).toBe(MINI_GATE_SAVE);
  });

  it("isDirty stays first after no-map and hides Qwen/job/outputs", () => {
    const next = gate({
      isDirty: true,
      includeCameras: false,
      includeWorldViews: false,
      qwenReady: false,
      localBlocked: true,
    });
    expect(next.canGenerate).toBe(false);
    expect(next.gateMessage).toBe(MINI_GATE_SAVE);
    expect(next.gateMessage).not.toBe(MINI_GATE_QWEN_UNAVAILABLE);
    expect(next.gateMessage).not.toBe(MINI_GATE_NO_OUTPUT);
    expect(next.gateMessage).not.toBe(LOCAL_GENERATION_ATTENTION);
  });

  it("no outputs beats Qwen/runtime and active job", () => {
    const next = gate({
      isDirty: false,
      includeCameras: false,
      includeWorldViews: false,
      qwenReady: false,
      localBlocked: true,
    });
    expect(next.canGenerate).toBe(false);
    expect(next.gateMessage).toBe(MINI_GATE_NO_OUTPUT);
  });

  it("Qwen/runtime uses Chief copy and beats active job", () => {
    const next = gate({ isDirty: false, qwenReady: false, localBlocked: true });
    expect(next.canGenerate).toBe(false);
    expect(next.gateMessage).toBe(MINI_GATE_QWEN_UNAVAILABLE);
    expect(next.gateMessage).toBe("Local Qwen is currently unavailable.");
  });

  it("keeps GPT and Z-Image readiness copy", () => {
    expect(gate({ generator: "gpt-image-2", gptReady: false }).gateMessage).toBe(MINI_GATE_GPT_NOT_READY);
    expect(gate({ generator: "zimage", zimageReady: false }).gateMessage).toBe(MINI_GATE_ZIMAGE_NOT_READY);
  });
});

describe("Scene Creator Mini save wiring (canonical, not Mini-only)", () => {
  const mini = readFileSync(new URL("./SceneCreatorMini.tsx", import.meta.url), "utf8");
  const hook = readFileSync(new URL("./useSceneCreatorMini.ts", import.meta.url), "utf8");
  const panel = readFileSync(new URL("./SpatialMapPanel.tsx", import.meta.url), "utf8");

  it("keeps Generate disabled while dirty and does not force disabled false", () => {
    expect(hook).toContain("!input.isDirty");
    expect(mini).toContain("disabled={!mini.canGenerate}");
    expect(mini).not.toMatch(/data-testid="scene-creator-mini-generate"[\s\S]{0,80}disabled=\{false\}/);
  });

  it("surfaces canonical Save next to the gate via handleSave / useSpatialMapSave", () => {
    expect(mini).toContain("onSaveSpatialMap");
    expect(mini).toContain('data-testid="scene-creator-mini-save-map"');
    expect(mini).toContain("Save Spatial Map");
    expect(mini).toContain("onClick={() => void onSaveSpatialMap()}");
    expect(panel).toContain("onSaveSpatialMap={() => void saveState.handleSave()}");
    expect(panel).toContain("isDirty={saveState.isDirty}");
    expect(hook).not.toContain("spatialMapApi.saveMap");
    expect(hook).not.toContain("/maps/");
    expect(mini).not.toContain("spatialMapApi.saveMap");
    expect(mini).not.toContain("/maps/");
  });

  it("does not fold variation/job/take into canGenerate", () => {
    const block = hook.slice(hook.indexOf("const canGenerate ="), hook.indexOf("let gateMessage"));
    expect(block).toContain("!input.isDirty");
    expect(block).not.toMatch(/\btake\b/);
    expect(block).not.toMatch(/\bvariation\b/);
    expect(block).not.toMatch(/\bjob\b/);
    expect(block).not.toMatch(/\bresult\b/);
  });

  it("keeps Regen/Retry on the distinct busy || isDirty || localBlocked predicate", () => {
    expect(mini).toContain("disabled={mini.busy || isDirty || mini.localBlocked}");
  });
});
