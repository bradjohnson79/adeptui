/**
 * Owner E2E: primary Regenerates Environment Reference Sheet (not silent restitch).
 * Named Jacob project only. Full paid ers.generate is in-scope.
 */
import { expect, test, type Page } from "@playwright/test";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const MAP_ID = "477b450c-734d-49ae-a40a-51402e0a832f";

test.setTimeout(40 * 60 * 1000);

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

async function openObservatoryMap(page: Page) {
  await page.goto(`${UI}/co-director?projectId=${encodeURIComponent(PROJECT_ID)}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await dismissOnboarding(page);
  const showContent = page.getByRole("button", { name: "Show project content" });
  if (await showContent.isVisible().catch(() => false)) {
    await showContent.click({ force: true }).catch(() => undefined);
  }
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 45_000 });
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    if (await page.getByTestId("spatial-map-panel").isVisible().catch(() => false)) break;
    await page.waitForTimeout(700);
  }
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
  const select = page.locator("#spatial-map-select");
  if ((await select.count()) > 0) {
    await select.selectOption(MAP_ID);
    await expect(select).toHaveValue(MAP_ID, { timeout: 15_000 });
  }
}

test.describe("Spatial Map ERS regenerate button", () => {
  test.describe.configure({ retries: 0 });

  test("primary Regenerates Environment Reference Sheet starts a full generate", async ({ page }) => {
    await openObservatoryMap(page);
    const monitor = page.getByTestId("ers-generation-monitor");
    await expect(monitor).toBeVisible({ timeout: 45_000 });

    const generate = page.getByTestId("ers-generate");
    await expect(generate).toBeVisible({ timeout: 20_000 });
    await expect(generate).toBeEnabled();
    const beforeSrc =
      (await page.locator("img.spatial-map__ers-live-img").getAttribute("src").catch(() => "")) || "";

    const execPost = page.waitForRequest(
      (req) =>
        req.method() === "POST" &&
        /\/api\/codirector\/projects\/[^/]+\/executions\/?$/.test(req.url()) &&
        String(req.postData() || "").includes("ers.generate"),
      { timeout: 45_000 },
    );
    await generate.scrollIntoViewIfNeeded();
    await generate.click();
    const posted = await execPost;
    const body = posted.postDataJSON() as { capability?: string; context?: Record<string, unknown> };
    expect(body.capability).toBe("ers.generate");
    expect(body.context?.forceFull || body.context?.force_full).toBeTruthy();
    expect(body.context?.retry_component || "").toBe("");
    expect(body.context?.retryComponent || "").toBe("");
    expect(body.context?.ers_pipeline || body.context?.ersPipeline).toBe("full_sheet");

    await expect(generate).toHaveText(/Generating/i, { timeout: 15_000 });
    await expect(monitor).toHaveAttribute("data-phase", /queued|generating/, { timeout: 20_000 });
    await expect(page.getByTestId("ers-generation-progress")).toBeVisible({ timeout: 20_000 });
    const stages = page.getByTestId("ers-generation-stages");
    if (await stages.isVisible().catch(() => false)) {
      const text = (await stages.innerText()) || "";
      expect(text).not.toMatch(/1\.\s*Master|Generating North|Generating East/);
      expect(text).toMatch(/Preparing Environment Reference Sheet|Generating full ERS|Resolving characters/);
    }

    await expect(monitor).toHaveAttribute("data-phase", "complete", { timeout: 38 * 60 * 1000 });
    const img = page.locator("img.spatial-map__ers-live-img");
    await expect(img).toBeVisible();
    const afterSrc = (await img.getAttribute("src")) || "";
    expect(afterSrc).toBeTruthy();
    if (beforeSrc) expect(afterSrc).not.toBe(beforeSrc);

    await page.reload();
    await openObservatoryMap(page);
    await expect(page.getByTestId("ers-generation-monitor")).toHaveAttribute("data-phase", "complete", {
      timeout: 45_000,
    });
    const reloaded = page.locator("img.spatial-map__ers-live-img");
    await expect(reloaded).toBeVisible({ timeout: 20_000 });
    const reloadedSrc = (await reloaded.getAttribute("src")) || "";
    expect(reloadedSrc).toBe(afterSrc);
  });
});
