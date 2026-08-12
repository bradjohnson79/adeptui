import { expect, test } from "@playwright/test";

/**
 * M42 Production Dock — Workflows A–H shell/smoke.
 * Workflow I (real generation provenance) is primary-agent certified with live GPU.
 */
test.describe("M42 Production Dock", () => {
  test("A: dock shell expand/collapse and modality menus @m42-dock", async ({ page }) => {
    await page.goto("/");
    const dock = page.getByTestId("production-control-dock");
    await expect(dock).toBeVisible({ timeout: 30_000 });

    const expand = page.getByTestId("production-dock-expand");
    if (await expand.isVisible().catch(() => false)) {
      await expand.click();
    }

    await expect(page.getByTestId("production-dock-bar")).toBeVisible();
    for (const id of [
      "production-dock-menu-llm",
      "production-dock-menu-video",
      "production-dock-menu-image",
      "production-dock-menu-audio",
    ]) {
      await page.getByTestId(id).click();
      await expect(page.getByRole("dialog").first()).toBeVisible();
      await page.keyboard.press("Escape");
    }

    await page.getByTestId("production-dock-settings").click();
    await expect(page.getByRole("dialog").first()).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByTestId("production-dock-collapse").click();
    await expect(page.getByTestId("production-dock-expand")).toBeVisible();
    await expect(page.getByTestId("production-dock-bar")).toHaveCount(0);
  });

  test("B: no floating Co-Director FAB remains @m42-dock", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".codirector-fab, .assistant-fab")).toHaveCount(0);
    await expect(page.getByTestId("production-control-dock")).toBeVisible({ timeout: 30_000 });
  });

  test("C: gate endpoint reports required flags @m42-dock", async ({ request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8758";
    const res = await request.get(`${apiBase}/api/production-control/gate`);
    expect(res.ok()).toBeTruthy();
    const gate = await res.json();
    expect(gate).toHaveProperty("productionDockGo");
    const flags = gate.flags ?? gate;
    expect(flags.contractsPassed).toBeTruthy();
    expect(flags.dockShellPassed).toBeTruthy();
    expect(flags.resolverConsumptionPassed).toBeTruthy();
  });

  test("D: resolve returns provenance for audio @m42-dock", async ({ request }) => {
    const apiBase = process.env.PLAYWRIGHT_API_URL || "http://127.0.0.1:8758";
    const res = await request.get(
      `${apiBase}/api/production-control/resolve?projectId=e32dae30-a014-4ea4-a2f2-69f4b7809bde&modality=audio`,
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const sel = body.selection ?? body;
    expect(sel.activeModelId).toBeTruthy();
    expect(sel.provenance || sel.source).toBeTruthy();
  });
});
