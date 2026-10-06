import { test, expect } from "@playwright/test";
import {
  API,
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

async function resetAgreement(request: import("@playwright/test").APIRequestContext) {
  const e2e = await request.post(`${API}/api/e2e/essential-agreement/reset`, { data: {} });
  if (e2e.ok()) return;
  await request.post(`${API}/api/setup/essential-agreement/decline`);
}

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
  await resetAgreement(request);
});

test.afterEach(async ({ page, request }) => {
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @isolated essential components agreement", () => {
  test("open full notice, agree, persist, reload, bump, decline", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Essential Agreement ${Date.now()}`);
    try {
      await openSetup(page, project.id, { setupMode: "guided" });
      const panel = page.getByTestId("essential-agreement-panel");
      await expect(panel).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("essential-agreement-version")).toContainText("2026.08.1");

      await page.getByTestId("essential-agreement-open-full").click();
      const document = page.getByTestId("essential-agreement-document");
      await expect(document).toBeVisible();
      await expect(document).toContainText("MoGe-2 Geometry Reconstruction");
      await expect(document).toContainText("VGGT-1B Commercial Geometry Reconstruction");
      await expect(document).toContainText("facebook/VGGT-1B-Commercial");

      const agree = page.getByTestId("essential-agreement-agree");
      await expect(agree).toBeEnabled();
      await agree.click();
      await expect(page.getByTestId("essential-agreement-status")).toContainText(/accepted/i, {
        timeout: 15_000,
      });

      const persisted = await request.get(`${API}/api/setup/essential-agreement`);
      expect(persisted.ok()).toBeTruthy();
      const persistedJson = await persisted.json();
      expect(persistedJson.accepted).toBeTruthy();
      expect(persistedJson.eligible).toBeTruthy();
      expect(persistedJson.acceptedVersion).toBe("2026.08.1");

      await page.reload();
      await expect(page.getByTestId("essential-agreement-panel")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("essential-agreement-status")).toContainText(/accepted/i);
      await expect(page.getByTestId("essential-agreement-agree")).toBeDisabled();

      const bump = await request.post(`${API}/api/e2e/essential-agreement/set-version`, {
        data: { version: "2026.08.2-e2e" },
      });
      if (bump.ok()) {
        await page.reload();
        await expect(page.getByTestId("essential-agreement-status")).toContainText(/UPDATED TERMS REQUIRE AGREEMENT/i);
        await page.getByTestId("essential-agreement-open-full").click();
        await expect(page.getByTestId("essential-agreement-agree")).toBeEnabled();
        await page.getByTestId("essential-agreement-agree").click();
        await expect(page.getByTestId("essential-agreement-status")).toContainText(/accepted/i);
      } else {
        const stale = await request.post(`${API}/api/setup/essential-agreement/accept`, {
          data: { version: "2025.01.0", documentAvailableConfirmed: true },
        });
        expect(stale.status()).toBe(409);
      }

      await page.getByTestId("essential-agreement-decline").click();
      await expect(page.getByTestId("essential-agreement-status")).toContainText(/ineligible|Decline|agree/i);
      const afterDecline = await request.get(`${API}/api/setup/essential-agreement`);
      expect((await afterDecline.json()).eligible).toBeFalsy();
      const install = await request.post(`${API}/api/setup/lifecycle/components/moge2_geometry/install`, {
        data: { confirm: true },
      });
      expect(install.status()).toBe(409);

      observer.assertHealthyBrowser();
    } finally {
      await resetAgreement(request);
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
