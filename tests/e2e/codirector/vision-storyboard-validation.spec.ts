import { expect, test, type Page } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * The page has four controls whose accessible name matches /Co-Director/i (header button,
 * two "Ask Co-Director" cover buttons, and the floating action button), so a name-only
 * locator is a strict-mode violation. The FAB is the entry point every other Co-Director
 * spec uses, and it is unique.
 */
async function openCoDirector(page: Page) {
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  await fab.click();
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

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
      await openCoDirector(page);
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

    await openCoDirector(page);

    // The workspace only has a surface once a plan marks visual validation pending — that is
    // the "pending deep-link" this case is named for. A storyboard request is the intent that
    // sets it, so drive it through the composer rather than asserting on an empty container.
    await page.getByLabel("Message Co-Director").fill("Create the next storyboard shot.");
    await page.getByRole("button", { name: "Send message" }).click();

    const workspace = page.getByTestId("codirector-validation-workspace");
    const runValidation = workspace.getByRole("button", { name: /Run mock validation/i });
    await expect(runValidation).toBeVisible({ timeout: 45000 });
    await runValidation.click();

    await expect(page.getByTestId("validation-summary")).toBeVisible({ timeout: 15000 });
    // History is populated by the two sessions created over the API above.
    await expect(page.getByTestId("validation-history")).toBeVisible();
  });
});
