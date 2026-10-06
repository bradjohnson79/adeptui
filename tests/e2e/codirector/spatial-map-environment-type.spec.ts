/**
 * Express has no Local/API or Interior/Exterior Environment Type chrome.
 * Named cert project only.
 */
import { expect, test, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const ENV_DESC =
  "Long silver metallic corridor with an elevator door at the end of the corridor.";

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

test("Express never exposes Local/API or Environment Type", async ({ page, request }) => {
  await expect.poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 }).toBeTruthy();
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  await page.getByTestId("codirector-content-tab-spatial_map").click({ force: true });
  const form = page.getByTestId("spatial-map-express-form");
  if (!(await form.isVisible({ timeout: 20_000 }).catch(() => false))) {
    test.info().annotations.push({
      type: "note",
      description: "Existing Spatial Map present; empty-form skipped.",
    });
    await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);
    return;
  }

  const executions: Array<Record<string, unknown>> = [];
  page.on("request", (req) => {
    if (req.method() === "POST" && /\/executions\/?$/.test(req.url())) {
      try {
        executions.push(req.postDataJSON() as Record<string, unknown>);
      } catch {
        /* ignore */
      }
    }
  });

  await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
  await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);
  await expect(page.getByText("Interior", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Exterior", { exact: true })).toHaveCount(0);
  await expect(
    page.getByTestId("spatial-map-atlas-engine").or(page.getByTestId("spatial-map-gpt-required")),
  ).toBeVisible();

  await page.getByTestId("scene-description-input").fill(ENV_DESC);
  if (await page.getByTestId("spatial-map-generate").isEnabled()) {
    const before = executions.length;
    await page.getByTestId("spatial-map-generate").click();
    await expect.poll(() => executions.length, { timeout: 15_000 }).toBeGreaterThan(before);
    const ctx = ((executions[executions.length - 1] || {}).context || {}) as Record<string, unknown>;
    expect(String(ctx.generationMethod || ctx.generation_method)).toBe("api");
    expect(ctx.environmentType).toBeUndefined();
    expect(ctx.environment_type).toBeUndefined();
    expect(JSON.stringify(ctx)).not.toContain('"exterior"');
    expect(JSON.stringify(ctx)).not.toContain('"interior"');
  }
});
