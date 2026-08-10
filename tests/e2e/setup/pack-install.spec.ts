import fs from "node:fs";
import path from "node:path";
import { test, expect } from "@playwright/test";
import {
  API,
  clearActiveInstallJobs,
  clearComponentLocation,
  clearPackOverrides,
  confirmInstallPreflight,
  createTempProject,
  deleteProject,
  ensurePackSource,
  makeTempDir,
  openSetup,
  setInstallPreflightDestination,
  setFixtureScenario,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const PACK = "pack_essential_photoreal";

test.describe("@critical @isolated pack install", () => {
  test("empty folder accepted for download and install; state persists", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await setFixtureScenario(request, { mode: "valid" });
    await clearPackOverrides(request);
    await request.post(`${API}/api/e2e/recover-operations`);
    await clearActiveInstallJobs(request, PACK);
    await clearComponentLocation(request, PACK);
    await ensurePackSource(request, PACK);

    const project = await createTempProject(request, `Pack Install ${Date.now()}`);
    const dest = makeTempDir("adept-install-dest-");
    try {
      await openSetup(page, project.id);
      const card = page.getByTestId(`setup-card-${PACK}`);
      const installBtn = card.getByRole("button", { name: /^(Download and Install|Install|Continue Install)$/i });
      await expect(installBtn).toBeEnabled({ timeout: 30_000 });
      await installBtn.click();

      await setInstallPreflightDestination(page, dest);
      await confirmInstallPreflight(page);

      await expect
        .poll(async () => {
          const status = await request.get(`${API}/api/setup/status`);
          const body = await status.json();
          const comp = body.components.find((c: { id: string }) => c.id === PACK);
          return comp?.status;
        }, { timeout: 120_000 })
        .toBe("ready");

      expect(fs.existsSync(path.join(dest, "pack.json"))).toBeTruthy();

      await page.reload();
      await openSetup(page, project.id);
      const card3 = page.getByTestId(`setup-card-${PACK}`);
      await expect(card3).toHaveAttribute("data-status", "ready");
      expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
      try {
        fs.rmSync(dest, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
    }
  });
});
