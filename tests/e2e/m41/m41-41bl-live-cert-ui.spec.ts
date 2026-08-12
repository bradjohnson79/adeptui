import { expect, test } from "@playwright/test";

/**
 * M41 4.1B-L — UI honesty for Certified Library + production gate sets.
 */
test.describe("M41 4.1B-L Live Cert UI honesty", () => {
  test("gate exposes release-stable required sets and inclusion fields", async ({
    request,
  }) => {
    const res = await request.get("/api/video-runtime/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.phase).toBe("M41-4.1B-L");
    expect(Array.isArray(body.requiredLocalProductionWorkflowKeys)).toBeTruthy();
    expect(body.requiredLocalProductionWorkflowKeys).toContain("ltx.simple_i2v");
    expect(body.requiredLocalProductionWorkflowKeys).toContain("wan.three_frame");
    expect(body.requiredLocalProductionWorkflowKeys).toContain("lipsync.latentsync");
    expect(Array.isArray(body.requiredCloudProductionWorkflowKeys)).toBeTruthy();
    expect(Array.isArray(body.enabledCloudProductionWorkflowKeys)).toBeTruthy();
    expect(typeof body.localGateSatisfied).toBe("boolean");
    expect(typeof body.cloudGateSatisfied).toBe("boolean");
    expect(typeof body.wave6ConsumerContractPassed).toBe("boolean");
    // Credentials must not shrink the release-defined required cloud set
    expect(body.requiredCloudProductionWorkflowKeys.length).toBeGreaterThan(0);
  });

  test("Production Ready only when Certified; Deferred upscale not ready", async ({
    request,
  }) => {
    const res = await request.get("/api/video-runtime/certified-registry");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    for (const e of body.entries || []) {
      if (e.status !== "Certified") {
        expect(e.productionReady).toBeFalsy();
      }
      if (e.status === "Certified") {
        expect(e.productionReady).toBeTruthy();
        expect(e.certificationRecordId || e.certificationRecord).toBeTruthy();
      }
    }
    const upscale = (body.entries || []).find(
      (e: { workflowKey: string }) => e.workflowKey === "video.upscale",
    );
    expect(upscale?.status).toBe("Deferred");
    expect(upscale?.productionReady).toBeFalsy();

    for (const cloudKey of ["fal.seedance", "fal.kling", "fal.veo", "fal.runway"]) {
      const cloud = (body.entries || []).find(
        (e: { workflowKey: string }) => e.workflowKey === cloudKey,
      );
      if (cloud && cloud.status !== "Certified") {
        expect(cloud.productionReady).toBeFalsy();
      }
    }
  });

  test("WAN three-frame limitations describe dual-segment stitching", async ({
    request,
  }) => {
    const res = await request.get("/api/video-runtime/certified-registry/wan.three_frame");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const text = JSON.stringify(body.limitations || []).toLowerCase();
    expect(text).toContain("first-to-middle");
    expect(text).toContain("middle-to-last");
    expect(text).toContain("stitch");
  });

  test("diagnostics shows Certified Workflow Library", async ({ page }) => {
    await page.goto("/diagnostics/video-runtime");
    await expect(page.getByTestId("video-runtime-diagnostics")).toBeVisible();
    await expect(page.getByTestId("certified-workflow-registry")).toBeVisible({
      timeout: 15000,
    });
  });
});
