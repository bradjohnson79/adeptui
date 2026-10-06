/**
 * Workspace Library organization + density. Reuses named Korri project.
 * Never POST /api/projects.
 */
import { expect, test } from "@playwright/test";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";

test.describe("Library organization + density", () => {
  test("project library walk stays coherent", async ({ page }) => {
    await page.setViewportSize({ width: 1600, height: 960 });
    await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=library`, { waitUntil: "domcontentloaded" });

    await expect(page.getByRole("heading", { name: /^Libraries$/ })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /^Folders$/ })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("library-section-assets")).toBeVisible();
    await expect(page.getByTestId("library-type-nav")).toBeVisible();
    await expect(page.getByTestId("library-filters")).toBeVisible();
    await expect(page.getByTestId("library-scope-project")).toBeVisible();

    const search = page.getByTestId("library-search");
    await expect(search).toBeVisible();
    await search.fill("korri");
    await page.waitForTimeout(400);

    await page.getByTestId("library-filter-video").click();
    await expect(page.getByTestId("library-filter-video")).toHaveClass(/primary/);

    await page.getByTestId("library-filter-audio").click();
    await expect(page.getByTestId("library-filter-audio")).toHaveClass(/primary/);

    await page.getByRole("button", { name: /^Qwen$/ }).click();
    await expect(page.getByRole("button", { name: /^Qwen$/ })).toHaveClass(/primary/);

    await page.getByRole("button", { name: /^All$/ }).first().click();
    await page.getByRole("button", { name: /^All$/ }).nth(1).click();
    await search.fill("");

    const cards = page.getByTestId("library-asset-card");
    const empty = page.getByTestId("library-empty-compact");
    if ((await cards.count()) === 0) {
      await expect(empty).toBeVisible();
    } else {
      await cards.first().click();
      await expect(page.getByRole("heading", { name: /^Asset Graph$/ })).toBeVisible();
      const details = page.locator(".library-details");
      if (await details.count()) {
        await details.locator("summary").click();
        await expect(page.getByTestId("library-provenance").or(page.locator(".library-details"))).toBeVisible();
      }
    }

    const collections = page.getByTestId("library-collections");
    await expect(collections).toBeVisible();
    const collectionRow = collections.locator(".library-collection-row").first();
    if (await collectionRow.count()) {
      const pack = collections.locator("summary");
      if (!(await collectionRow.isVisible().catch(() => false))) {
        await pack.click();
      }
      if (await collectionRow.isVisible().catch(() => false)) {
        await collectionRow.click();
      }
    }

    await page.getByRole("button", { name: /^All assets$/ }).click();
    await expect(page.getByTestId("library-section-assets")).toBeVisible();

    await page.getByTestId("library-scope-global").click();
    await expect(page.getByTestId("library-scope-global")).toHaveClass(/primary/);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: /^Libraries$/ })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("heading", { name: /^Folders$/ })).toBeVisible();
    await expect(page.getByTestId("library-type-nav")).toBeVisible();
    await expect(page.getByTestId("library-filters")).toBeVisible();

    const cols = await page.locator(".library-layout").evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(cols.split(" ").filter(Boolean).length).toBeGreaterThanOrEqual(2);
  });
});
