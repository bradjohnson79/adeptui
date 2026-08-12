import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

async function waitForStudioReady(request: import("@playwright/test").APIRequestContext) {
  // Production `npm run api` may not expose /api/e2e/status (STUDIO_E2E=1).
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
 * DETERMINISTIC_BROWSER_REGRESSION — LOCAL-16
 * Local Txt2Vid without a start frame must offer local start-frame generation
 * and must never silently route to fal.
 */
test.describe("M3.0h local-first LOCAL-16 no silent fal", () => {
  test("Txt2Vid local/auto opens start-frame dialog before any fal submit", async ({
    page,
    request,
  }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `M30H-LF LOCAL16 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=txt2vid`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("txt2vid-panel")).toBeVisible({ timeout: 30_000 });

      await page.getByLabel(/prompt/i).fill(
        "Exactly one woman in an observation chamber, slow push-in, no music",
      );
      await page.getByTestId("txt2vid-generate").click();

      const dialog = page.getByTestId("paid-fal-fallback-dialog");
      await expect(dialog).toBeVisible();
      await expect(page.getByTestId("generate-local-start-frame")).toBeVisible();
      await expect(page.getByTestId("approve-paid-fal")).toBeVisible();

      // Preferred action: local start frame — cancel must not submit fal.
      await page.getByTestId("cancel-fal-fallback").click();
      await expect(dialog).toBeHidden();
      await expect(page.getByTestId("txt2vid-message")).toContainText(/no fal/i);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Generate local start frame navigates to ImageGen", async ({ page, request }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `M30H-LF IMG ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=txt2vid`);
      await page.waitForLoadState("domcontentloaded");
      await page.getByLabel(/prompt/i).fill("Single character test clip, no music");
      await page.getByTestId("txt2vid-generate").click();
      await page.getByTestId("generate-local-start-frame").click();
      await expect(page.getByRole("heading", { name: /^ImageGen$/i })).toBeVisible({
        timeout: 15_000,
      });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
