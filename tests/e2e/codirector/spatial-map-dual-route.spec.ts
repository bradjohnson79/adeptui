/**
 * Spatial Map Standard start surface remains on the spatial workspace.
 * Co-Director Spatial Map is Express-only.
 */
import { expect, test, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";

test.setTimeout(6 * 60 * 1000);

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
      await page.waitForTimeout(400);
    } else {
      break;
    }
  }
}

test.describe("Spatial Map dual-route environment creation", () => {
  test("Co-Director Express form and Standard workspace entry stay split", async ({ page, request }) => {
    await expect.poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 }).toBeTruthy();
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await dismissOnboarding(page);
    const tab = page.getByTestId("codirector-content-tab-spatial_map");
    await expect(tab).toBeVisible({ timeout: 30_000 });
    await tab.click({ force: true });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("spatial-map-mode-toggle")).toHaveCount(0);
    await expect(page.getByText("Improve Spatial Understanding")).toHaveCount(0);

    const form = page.getByTestId("spatial-map-express-form");
    if (await form.isVisible().catch(() => false)) {
      await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
      await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);
      await expect(page.getByTestId("spatial-map-generate")).toBeVisible();
      await expect(
        page.getByTestId("spatial-map-atlas-engine").or(page.getByTestId("spatial-map-gpt-required")),
      ).toBeVisible();
    } else {
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible();
    }
  });
});
