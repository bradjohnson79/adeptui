import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

test.describe("Brand Studio retired from Adept UI v1.1 @DETERMINISTIC", () => {
  test("stale Brand Studio route does not remount and catalog/run stay retired", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `Brand Studio Retired ${Date.now()}`);
    try {
      const catalog = await (await request.get(`${API}/api/generation-tools/catalog`)).json();
      const ids = (catalog.tools as { id: string }[]).map((tool) => tool.id);
      expect(ids).not.toContain("brand.studio");

      const retired = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "brand.studio", prompt: "must not generate" },
      });
      expect(retired.status()).toBe(410);

      await page.goto("/");
      await expect(page.getByTestId("explore-adept-ui")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("explore-workspace-brandstudio")).toHaveCount(0);

      await page.getByRole("button", { name: /^Production$/ }).click();
      await expect(page.getByTestId("production-item-brandstudio")).toHaveCount(0);
      await page.keyboard.press("Escape");

      await page.goto(`/project/${project.id}?workspace=brandstudio`);
      await expect(page).not.toHaveURL(/workspace=brandstudio/, { timeout: 45_000 });
      await expect(page).toHaveURL(new RegExp(`/project/${project.id}`));
      await expect(page.getByTestId("brand-studio")).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "Workspaces" })).toBeVisible({ timeout: 45_000 });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
