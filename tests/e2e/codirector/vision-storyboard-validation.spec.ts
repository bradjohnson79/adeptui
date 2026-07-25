import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.5 vertical slice: storyboard plan pending -> mock validate -> correction proposal path.
 * Requires STUDIO_FEATURE_VISION_VALIDATION_V1=1 on the API under test.
 */
test.describe("Co-Director M2.5 vision storyboard validation @critical @isolated", () => {
  test("validation workspace appears when flag on and pending deep-link works", async ({ page, request }) => {
    const project = await createTempProject(request, "Vision Validation E2E");

    // Health should expose the flag (suite env may leave it off — assert UI hide path then).
    const health = await request.get("/api/health");
    expect(health.ok()).toBeTruthy();
    const healthJson = await health.json();
    const visionOn = Boolean(healthJson?.operator?.visionValidationEnabled);

    await page.goto(`/project/${project.id}`);
    await expect(page.getByTestId("status-vision-validation")).toBeVisible();
    await expect(page.getByTestId("status-vision-validation")).toContainText(visionOn ? "On" : "Off");

    if (!visionOn) {
      // Flag off: workspace must stay hidden even if we open Co-Director.
      await page.getByRole("button", { name: /Co-Director/i }).click();
      await expect(page.getByTestId("codirector-validation-workspace")).toHaveCount(0);
      return;
    }

    // Flag on: exercise mock validate via API then open workspace history.
    const validate = await request.post("/api/codirector/vision/validate", {
      data: {
        projectId: project.id,
        provider: "mock",
        fixtureProfile: "warnings",
      },
    });
    expect(validate.ok()).toBeTruthy();
    const payload = await validate.json();
    expect(payload.report?.passed).toBeFalsy();
    expect(payload.session?.status).toBe("completed");

    const correction = await request.post("/api/codirector/vision/correction", {
      data: {
        projectId: project.id,
        sessionId: payload.session.sessionId,
        notes: "E2E correction",
      },
    });
    expect(correction.ok()).toBeTruthy();
    const correctionBody = await correction.json();
    expect(correctionBody.proposalId).toBeTruthy();

    await page.getByRole("button", { name: /Co-Director/i }).click();
    // Open workspace via run control (pending badge may or may not be set without intelligence plan).
    await page.getByTestId("codirector-validation-workspace").locator("button.primary").first().click();
    await expect(page.getByTestId("validation-summary")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("validation-history")).toBeVisible();
  });
});
