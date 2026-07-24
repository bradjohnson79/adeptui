import fs from "node:fs";
import { test, expect } from "@playwright/test";
import {
  API,
  browseForcedFolder,
  confirmCheckpoint,
  createTempProject,
  deleteProject,
  dismissSetupDialogs,
  makeTempDir,
  openSetup,
  waitForAppReady,
  writeLinkFixture,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const PACK = "pack_essential_anime";

test.describe("@critical @isolated pack link existing", () => {
  test("empty rejected; valid accepted; wrong id rejected", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await request.post(`${API}/api/e2e/recover-operations`);
    const project = await createTempProject(request, `Pack Link ${Date.now()}`);
    const empty = makeTempDir("adept-link-empty-");
    const valid = makeTempDir("adept-link-valid-");
    const wrong = makeTempDir("adept-link-wrong-");
    writeLinkFixture(valid, { packId: PACK });
    writeLinkFixture(wrong, { packId: "pack_essential_wrong" });

    try {
      await openSetup(page, project.id);
      const card = page.getByTestId(`setup-card-${PACK}`);

      await card.getByRole("button", { name: /Link Existing Folder/i }).click();
      await browseForcedFolder(page, empty);
      await confirmCheckpoint(page);
      // Scope to the checkpoint dialog — pack cards also mention pack.json in collapsed specs.
      const dialog = page.locator(".setup-dialog[role='dialog']").last();
      await expect(dialog).toBeVisible({ timeout: 30_000 });
      await expect(
        dialog.getByText(/pack\.json|Empty folders|No pack files|missing/i).first(),
      ).toBeVisible({ timeout: 30_000 });
      await dismissSetupDialogs(page);

      await openSetup(page, project.id);
      await page.getByTestId(`setup-card-${PACK}`).getByRole("button", { name: /Link Existing Folder/i }).click();
      await browseForcedFolder(page, valid);
      await confirmCheckpoint(page);
      await expect
        .poll(async () => {
          const status = await request.get(`${API}/api/setup/status`);
          const body = await status.json();
          const comp = body.components.find((c: { id: string }) => c.id === PACK);
          return comp?.status;
        }, { timeout: 60_000 })
        .toBe("ready");

      const before = fs.readFileSync(`${wrong}/pack.json`, "utf8");
      await openSetup(page, project.id);
      await page
        .getByTestId("setup-card-pack_essential_cinematic")
        .getByRole("button", { name: /Link Existing Folder/i })
        .click();
      await browseForcedFolder(page, wrong);
      await confirmCheckpoint(page);
      await expect(page.getByText(/pack id|does not match|wrong|mismatch|invalid/i).first()).toBeVisible({
        timeout: 30_000,
      });
      expect(fs.readFileSync(`${wrong}/pack.json`, "utf8")).toBe(before);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
      for (const dir of [empty, valid, wrong]) {
        try {
          fs.rmSync(dir, { recursive: true, force: true });
        } catch {
          /* ignore */
        }
      }
    }
  });
});
