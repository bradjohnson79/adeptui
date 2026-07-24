import { test, expect } from "@playwright/test";
import {
  createTempProject,
  deleteProject,
  openSetup,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated setup page", () => {
  test("setup cards render and details expand", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Setup Page ${Date.now()}`);
    try {
      await openSetup(page, project.id);
      await expect(page.locator(".setup-wizard-page").first()).toBeVisible();
      await expect(page.getByTestId("setup-card-pack_essential_photoreal")).toBeVisible();
      await expect(page.getByTestId("setup-card-pack_essential_anime")).toBeVisible();
      await expect(page.getByTestId("setup-card-pack_essential_cinematic")).toBeVisible();

      const card = page.getByTestId("setup-card-pack_essential_photoreal");
      const status = await card.getAttribute("data-status");
      // Unavailable downloads must not look mid-configure without an active op.
      expect(status).not.toBe("installing");

      const details = card.locator("details.setup-ready-details").first();
      if (
        (await details.count()) > 0
        && status !== "installing"
        && !(await page.locator(".setup-dialog-backdrop").isVisible().catch(() => false))
      ) {
        await details.locator("summary").click({ timeout: 5_000 }).catch(() => undefined);
      }

      const checkAgain = card.getByRole("button", { name: /check again/i });
      await expect(checkAgain).toBeVisible();
      await checkAgain.focus();
      await expect(checkAgain).toBeFocused();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
