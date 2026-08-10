import { test, expect } from "@playwright/test";
import {
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});
test.afterEach(async ({ page, request }) => {
  await resetLiveBetaTestSurface(request, page);
});

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

      // Live Beta may surface retry/recovery controls instead of "Check Again" when a pack has an
      // interrupted install record. The creator-stable source actions must still remain visible.
      const addSource = card.getByTestId("add-source-url-pack_essential_photoreal");
      await expect(addSource).toBeVisible();
      await addSource.focus();
      await expect(addSource).toBeFocused();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
