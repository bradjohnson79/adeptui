import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/api";

/**
 * M2.7 Production Executive closed-loop (mocked providers).
 * Requires STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1=1 on the API under test.
 */
test.describe("Co-Director M2.7 Production Executive @critical @isolated", () => {
  test("dashboard + closed loop respects approval gate when flag on", async ({ page, request }) => {
    const project = await createTempProject(request, "Production Executive E2E");

    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const healthJson = await health.json();
    const execOn = Boolean(healthJson?.operator?.productionExecutiveEnabled);

    await page.goto(`/project/${project.id}`);
    await expect(page.getByTestId("status-production-executive")).toBeVisible();
    await expect(page.getByTestId("status-production-executive")).toContainText(execOn ? "On" : "Off");

    if (!execOn) {
      await page.getByRole("button", { name: /Co-Director/i }).click();
      await expect(page.getByTestId("codirector-production-executive")).toHaveCount(0);
      return;
    }

    // Drive closed loop via API (mocked handlers), then assert UI + approval gate.
    const loop = await request.post("/api/codirector/jobs/closed-loop", {
      data: {
        projectId: project.id,
        sceneId: "scene-e2e-1",
        provider: "mock",
        idempotencyKey: "e2e-m27",
      },
    });
    expect(loop.ok()).toBeTruthy();
    const loopBody = await loop.json();
    const awaitJob = (loopBody.jobs as { id: string; type: string }[]).find(
      (j) => j.type === "await_approval",
    );
    expect(awaitJob).toBeTruthy();

    const drain = await request.post("/api/codirector/jobs/worker/drain", {
      data: { maxSteps: 40 },
    });
    expect(drain.ok()).toBeTruthy();

    const awaitInspect = await request.get(`/api/codirector/jobs/${awaitJob!.id}`);
    expect(awaitInspect.ok()).toBeTruthy();
    const awaitJson = await awaitInspect.json();
    expect(awaitJson.job.status).toBe("NeedsReview");

    const approve = await request.post(`/api/codirector/jobs/${awaitJob!.id}/mark-approval`, {
      data: { proposalId: "prop-scene-e2e-1", approved: true, actor: "e2e" },
    });
    expect(approve.ok()).toBeTruthy();
    expect((await approve.json()).autoApproved).toBeFalsy();

    await request.post("/api/codirector/jobs/worker/drain", { data: { maxSteps: 40 } });

    await page.getByRole("button", { name: /Co-Director/i }).click();
    await page.getByTestId("toggle-production-executive").click();
    await expect(page.getByTestId("production-executive-dashboard")).toBeVisible({ timeout: 15000 });
    await page.getByTestId("executive-tab-history").click();
    await expect(page.getByTestId("executive-jobs-history")).toBeVisible();
    await page.getByTestId("executive-tab-statistics").click();
    await expect(page.getByTestId("executive-statistics")).toBeVisible();
  });
});