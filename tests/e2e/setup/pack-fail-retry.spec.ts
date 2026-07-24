import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";
import {
  API,
  browseForcedFolder,
  clearPackOverrides,
  confirmCheckpoint,
  createTempProject,
  deleteProject,
  ensurePackSource,
  makeTempDir,
  openSetup,
  setFixtureScenario,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const PACK = "pack_essential_cinematic";

test.describe("@critical @isolated pack fail retry", () => {
  test("failed download keeps API alive and retry succeeds", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    observer.allow(/\/assets\/.*\.zip/);
    observer.allow(/simulated download failure/);
    observer.allow(/download_http_error|Download failed|HTTP 500/i);
    await waitForAppReady(request);
    await clearPackOverrides(request);
    await request.post(`${API}/api/e2e/recover-operations`);
    await request.post(`${API}/api/e2e/clear-component-location`, {
      data: { component_id: PACK },
    });
    await setFixtureScenario(request, { mode: "valid" });
    await ensurePackSource(request, PACK);

    const project = await createTempProject(request, `Pack Fail ${Date.now()}`);
    const destFail = makeTempDir("adept-fail-dest-");
    const destRetry = makeTempDir("adept-retry-dest-");
    try {
      await setFixtureScenario(request, { mode: "fail_download" });
      await openSetup(page, project.id);
      const card = page.getByTestId(`setup-card-${PACK}`);
      const installBtn = card.getByRole("button", { name: /Download and Install/i });
      await expect(installBtn).toBeEnabled({ timeout: 30_000 });

      const opResponsePromise = page.waitForResponse(
        (res) =>
          res.url().includes(`/setup/components/${PACK}/recommended-action`) &&
          res.request().method() === "POST" &&
          res.ok(),
        { timeout: 30_000 },
      );
      await installBtn.click();
      const opResponse = await opResponsePromise;
      const started = await opResponse.json();
      const operationId = String(started.operation_id || "");
      expect(operationId).toBeTruthy();

      await browseForcedFolder(page, destFail);
      await confirmCheckpoint(page);

      await expect
        .poll(async () => {
          const snap = await (
            await request.get(`${API}/api/setup/operations/${operationId}`)
          ).json();
          return snap.status;
        }, { timeout: 90_000 })
        .toBe("failed");

      const failedOp = await (
        await request.get(`${API}/api/setup/operations/${operationId}`)
      ).json();
      expect(String(failedOp.error || failedOp.stage || "")).toMatch(
        /500|download|fail/i,
      );
      expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();

      // Recover and retry through the same UI path with a fresh empty destination.
      await setFixtureScenario(request, { mode: "valid" });
      await request.post(`${API}/api/e2e/recover-operations`);
      await request.post(`${API}/api/e2e/clear-component-location`, {
        data: { component_id: PACK },
      });
      await ensurePackSource(request, PACK);

      await page.goto(`/project/${project.id}?workspace=setup&r=${Date.now()}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.locator(".setup-wizard-page").first()).toBeVisible({ timeout: 45_000 });
      await expect(page.locator(".setup-component-grid").first()).toBeVisible({ timeout: 30_000 });

      const retryCard = page.getByTestId(`setup-card-${PACK}`);
      await retryCard.scrollIntoViewIfNeeded();
      await expect(retryCard).not.toHaveAttribute("data-status", "ready", { timeout: 15_000 });

      const retryBtn = retryCard.getByRole("button", { name: /Download and Install/i });
      await expect(retryBtn).toBeEnabled({ timeout: 30_000 });
      await retryBtn.click();
      await browseForcedFolder(page, destRetry);
      await confirmCheckpoint(page);

      await expect
        .poll(async () => {
          const status = await request.get(`${API}/api/setup/status`);
          const body = await status.json();
          return body.components.find((c: { id: string }) => c.id === PACK)?.status;
        }, { timeout: 120_000 })
        .toBe("ready");

      expect(fs.existsSync(path.join(destRetry, "pack.json"))).toBeTruthy();
      expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();
      await openSetup(page, project.id);
      await expect(page.getByTestId(`setup-card-${PACK}`)).toHaveAttribute("data-status", "ready");
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
      for (const dir of [destFail, destRetry]) {
        try {
          fs.rmSync(dir, { recursive: true, force: true });
        } catch {
          /* ignore */
        }
      }
    }
  });
});
