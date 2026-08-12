import { expect, test } from "@playwright/test";

/**
 * M41 4.1B — Certified Workflow Library honesty (no live Comfy generation).
 */
test.describe("M41 4.1B Certified Workflow Library", () => {
  test("certified-registry API lists production pipeline + deferred honesty", async ({
    request,
  }) => {
    const res = await request.get("/api/video-runtime/certified-registry");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const keys = new Set((body.entries || []).map((e: { workflowKey: string }) => e.workflowKey));
    for (const k of [
      "ltx.simple_i2v",
      "wan.three_frame",
      "director.batch_timeline",
      "video.extend",
      "video.upscale",
    ]) {
      expect(keys.has(k)).toBeTruthy();
    }
    const upscale = (body.entries || []).find(
      (e: { workflowKey: string }) => e.workflowKey === "video.upscale",
    );
    expect(upscale?.status).toBe("Deferred");
    expect(upscale?.productionReady).toBeFalsy();
    for (const e of body.entries || []) {
      if (e.status !== "Certified") {
        expect(e.productionReady).toBeFalsy();
      }
    }
  });

  test("resolver selects wan.three_frame when middle frame present", async ({ request }) => {
    const res = await request.post("/api/video-runtime/resolve", {
      data: {
        intent: "scene_render",
        engine: "wan",
        presentInputs: {
          start_asset_id: "s1",
          middle_asset_id: "m1",
          end_asset_id: "e1",
        },
      },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.leaf_workflow_key || body.leafWorkflowKey).toBe("wan.three_frame");
  });

  test("gate exposes 4.1B/4.1B-L certified counts and set inclusion", async ({
    request,
  }) => {
    const res = await request.get("/api/video-runtime/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(["M41-4.1B", "M41-4.1B-L"]).toContain(body.phase);
    expect(typeof body.certifiedWorkflowCount).toBe("number");
    expect(Array.isArray(body.requiredLocalProductionWorkflowKeys)).toBeTruthy();
  });

  test("diagnostics page shows Certified Workflow Library", async ({ page }) => {
    await page.goto("/diagnostics/video-runtime");
    await expect(page.getByTestId("video-runtime-diagnostics")).toBeVisible();
    await expect(page.getByTestId("certified-workflow-registry")).toBeVisible({
      timeout: 15000,
    });
  });
});
