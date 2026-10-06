/**
 * Home library hydration truth. Reuses the live project list.
 * Never POST /api/projects.
 */
import { expect, test } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

test.describe("Home library hydration", () => {
  test("does not show first-use empty while projects exist", async ({ page, request }) => {
    test.setTimeout(90_000);
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), await health.text()).toBeTruthy();
    const list = await request.get(`${API}/api/projects`);
    expect(list.ok(), await list.text()).toBeTruthy();
    const projects = (await list.json()) as Array<{ id?: string; archived?: number }>;
    const visible = projects.filter((row) => !row.archived);

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });

    const loading = page.getByTestId("home-projects-loading");
    if (await loading.count()) {
      await expect(loading).toBeHidden({ timeout: 30_000 });
    }

    if (visible.length > 0) {
      await expect(page.getByText("No Projects Yet")).toHaveCount(0);
      await expect(page.getByText("Could not load projects")).toHaveCount(0);
      await expect(page.locator("[data-testid^='project-card-'], [data-testid='project-cover-card']").first()).toBeVisible({
        timeout: 20_000,
      });
    } else {
      await expect(page.getByText(/No Projects Yet|Create your first/i).first()).toBeVisible();
    }
  });
});
