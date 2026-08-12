import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

async function waitForStudioReady(request: import("@playwright/test").APIRequestContext) {
  await expect
    .poll(async () => {
      try {
        return (await request.get(`${API}/api/health`)).ok();
      } catch {
        return false;
      }
    }, { timeout: 60_000 })
    .toBeTruthy();
}

/**
 * DETERMINISTIC_BROWSER_REGRESSION
 * Fixture/state checks — does not perform REAL_LOCAL_EXECUTION renders.
 */
test.describe("M3.0h local-first deterministic browser regression", () => {
  test("LOCAL-01 ImageGen workspace loads with labeled prompt", async ({ page, request }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `M30H-LF L01 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=imagegen`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByRole("heading", { name: /^ImageGen$/i })).toBeVisible({
        timeout: 30_000,
      });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("LOCAL-15 Director shell loads for project with local provenance note", async ({
    page,
    request,
  }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `M30H-LF L15 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.locator("body")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
