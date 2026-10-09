import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

test.describe("Revision D Essentials Pack", () => {
  test("API reports pack without blocking generation", async ({ request }) => {
    await waitForAppReady(request);
    const res = await request.get(`${API}/api/setup/lifecycle/essentials`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    expect(body.id).toBe("adept_ui_essentials");
    expect(body.generationBlockedByPack).toBeFalsy();
    expect(body.essentialTotal).toBe(4);
    const ids = (body.components || []).map((row: { id: string }) => row.id);
    expect(ids).not.toContain("videochat3_4b");
    expect(ids).toContain("sam21_hiera_tiny");
    expect(ids).not.toContain("timelens");
  });

  test("Setup Wizard shows Essentials Pack", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, "Revision D Essentials Review");
    try {
      await page.goto(`/project/${project.id}?workspace=setup`, { waitUntil: "domcontentloaded", timeout: 60_000 });
      await expect(page.locator("[data-testid=setup-essentials-pack]").first()).toBeVisible({ timeout: 90_000 });
      await expect(page.locator("[data-testid=setup-essentials-capabilities]")).toContainText(/Intelligent Selection/i);
      await page.locator("[data-testid=setup-essentials-details]").click();
      await expect(page.locator("[data-testid=setup-essentials-details-list]")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
