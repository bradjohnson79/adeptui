import { expect, test } from "@playwright/test";

/**
 * Wave 6P product-surface honesty + gate contracts.
 * Live Comfy media success remains certified under artifacts/m41/41bl.
 */

test.describe("M41 W6P product beta", () => {
  test("wave6p gate endpoint exposes exact inclusion fields", async ({ request }) => {
    const res = await request.get("/api/video-runtime/wave6p-gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.phase).toBe("M41-W6P");
    for (const key of [
      "prerequisiteEngineGo",
      "consumerContractPassed",
      "toolRegistryPassed",
      "productionIntentPassed",
      "plannerPassed",
      "wave6pGo",
      "missingRequirements",
    ]) {
      expect(body).toHaveProperty(key);
    }
  });

  test("video-runtime gate embeds wave6p block", async ({ request }) => {
    const res = await request.get("/api/video-runtime/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.wave6ProductionActivationUnlocked).toBeTruthy();
    expect(body.wave6p).toBeTruthy();
    expect(body.wave6p.phase).toBe("M41-W6P");
  });

  test("resolve scene_render remains certified for product consumers", async ({ request }) => {
    const res = await request.post("/api/video-runtime/resolve", {
      data: {
        intent: "scene_render",
        engine: "ltx",
        presentInputs: { start_asset_id: "fixture-start" },
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(String(body.status).toLowerCase()).toBe("certified");
    expect(body.workflowKey || body.workflow_key).toBeTruthy();
  });
});
