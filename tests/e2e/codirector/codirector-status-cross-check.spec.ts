import { expect, test, type Page } from "@playwright/test";
import { API, createTempProject } from "../helpers/app";

async function waitForBetaReady(page: Page) {
  await expect
    .poll(async () => {
      try {
        const response = await page.request.get(`${API}/api/health`);
        return response.ok();
      } catch {
        return false;
      }
    }, { timeout: 60_000 })
    .toBeTruthy();
}

async function openCoDirector(page: Page, projectId: string) {
  await page.goto(`/co-director?projectId=${projectId}`);
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

test.describe("@critical @isolated codirector status cross-check", () => {
  test("menu order, status panel, history, and redacted details are visible", async ({
    page,
    request,
  }) => {
    await waitForBetaReady(page);
    const project = await createTempProject(request, `Status Gauge ${Date.now()}`);

    try {
      const seeded = await request.post(`${API}/api/codirector/status/check`, {
        data: { projectId: project.id },
        timeout: 90_000,
      });
      expect(seeded.ok()).toBeTruthy();

      await openCoDirector(page, project.id);

      await expect(page.getByTestId("codirector-status-chip")).toBeVisible();

      await page.getByTestId("codirector-overflow-button").click();
      const navButtons = page.locator(".codirector-overflow-nav button");
      await expect(navButtons).toHaveText([
        "Options",
        "Model",
        "PI Benchmarks",
        "Knowledge",
        "Access",
        "Audit",
        "Status",
        "Close",
      ]);

      await page.getByTestId("codirector-overflow-panel").getByRole("button", { name: "Status" }).click();
      await expect(page.getByTestId("codirector-status-panel")).toBeVisible();
      await expect(page.getByText("Production Assurance")).toBeVisible();
      await expect(page.getByRole("button", { name: "Run Cross-Check" })).toBeVisible();
      await expect(page.getByText("Recent Checks")).toBeVisible();

      const panelText = await page.getByTestId("codirector-status-panel").textContent();
      expect(panelText || "").not.toContain("http://127.0.0.1");
      expect(panelText || "").not.toMatch(/Bearer\s+/);

      await page.reload();
      await openCoDirector(page, project.id);
      await page.getByTestId("codirector-overflow-button").click();
      await page.getByTestId("codirector-overflow-panel").getByRole("button", { name: "Status" }).click();
      await expect(page.getByTestId("codirector-status-panel")).toBeVisible();
      await expect(page.getByText("Recent Checks")).toBeVisible();
    } finally {
      await request.delete(`${API}/api/projects/${project.id}`, { timeout: 90_000 }).catch(() => undefined);
    }
  });
});
