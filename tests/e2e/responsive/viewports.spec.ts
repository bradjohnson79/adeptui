import { test, expect } from "@playwright/test";
import { createTempProject, deleteProject, openSetup, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
  { width: 1024, height: 768 },
];

test.describe("@critical @isolated responsive", () => {
  for (const vp of VIEWPORTS) {
    test(`setup readable at ${vp.width}x${vp.height}`, async ({ page, request }) => {
      const observer = new AuditObserver(page, test.info());
      observer.attach();
      await waitForAppReady(request);
      const project = await createTempProject(request, `Resp ${vp.width} ${Date.now()}`);
      try {
        await page.setViewportSize(vp);
        await openSetup(page, project.id);
        const card = page.getByTestId("setup-card-pack_essential_photoreal");
        await expect(card).toBeVisible();
        const box = await card.boundingBox();
        expect(box).toBeTruthy();
        expect(box!.width).toBeGreaterThan(200);
        await observer.snapshot(`setup_${vp.width}x${vp.height}`);
        observer.assertHealthyBrowser();
      } finally {
        await deleteProject(request, project.id);
        observer.flush();
      }
    });
  }
});
