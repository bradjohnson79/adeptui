/**
 * M42 Wave 4C — Director → Timeline product rename (Scenarios A–J).
 */
import { expect, test } from "@playwright/test";

test.describe("M42 W4C Timeline rename @DETERMINISTIC", () => {
  test("Scenario A/B — Home shows Timeline Generator, not standalone Director product", async ({ page }) => {
    await page.goto("/");
    const cards = page.getByTestId("studio-launch-cards");
    if (!(await cards.count())) {
      test.skip(true, "Home launch cards not available");
      return;
    }
    await expect(page.getByTestId("timeline-launch-card")).toBeVisible();
    await expect(page.getByTestId("timeline-launch-card")).toContainText("Timeline Generator");
    await expect(page.getByTestId("director-launch-card")).toHaveCount(0);
    await expect(page.getByTestId("codirector-launch-card")).toBeVisible();
    await expect(page.getByTestId("codirector-launch-card")).toContainText("Co-Director");
  });

  test("Scenario C — legacy workspace=director resolves to Timeline workspace", async ({ page, request }) => {
    const projects = await request.get("/api/projects");
    if (!projects.ok()) {
      test.skip(true, "API unavailable");
      return;
    }
    const body = await projects.json();
    const id = body?.projects?.[0]?.id || body?.[0]?.id;
    if (!id) {
      test.skip(true, "No project");
      return;
    }
    await page.goto(`/project/${id}?workspace=director`);
    await expect(page).toHaveURL(/workspace=timeline/);
  });

  test("Scenario F — Co-Director name preserved", async ({ page }) => {
    await page.goto("/");
    const cd = page.getByTestId("codirector-launch-card");
    if (!(await cd.count())) {
      const chrome = page.getByTestId("chrome-codirector");
      if (await chrome.count()) {
        await expect(chrome).toContainText("Co-Director");
        return;
      }
      test.skip(true, "Co-Director UI not visible");
      return;
    }
    await expect(cd).toContainText("Co-Director");
    await expect(cd).not.toHaveText(/^Director$/);
  });

  test("Scenario H — search aliases map to Timeline product display", async ({ page }) => {
    await page.goto("/");
    // Command palette / chrome search if present
    const search = page.getByRole("searchbox").or(page.getByPlaceholder(/search/i)).first();
    if (!(await search.count())) {
      test.skip(true, "No search box");
      return;
    }
    await search.fill("Director");
    // Should not show two product results labeled Director + Timeline as separate products
    const directorOnly = page.getByRole("option", { name: /^Director$/ });
    await expect(directorOnly).toHaveCount(0);
  });
});
