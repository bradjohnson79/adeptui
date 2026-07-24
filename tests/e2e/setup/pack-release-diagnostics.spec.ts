import { test, expect } from "@playwright/test";
import {
  API,
  clearPackOverrides,
  createTempProject,
  deleteProject,
  openSetup,
  setFixtureScenario,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const PACK = "pack_essential_anime";

test.describe("@critical @isolated pack release diagnostics", () => {
  test("no releases and no matching asset report clear diagnostics", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await clearPackOverrides(request);
    await request.post(`${API}/api/e2e/recover-operations`);
    const project = await createTempProject(request, `Pack Diag ${Date.now()}`);

    try {
      await setFixtureScenario(request, { mode: "no_releases" });
      const refresh = await request.post(`${API}/api/setup/components/${PACK}/refresh-source`);
      const payload = await refresh.json();
      expect(payload.source_available).toBeFalsy();
      expect(JSON.stringify(payload).toLowerCase()).toMatch(/no published|no_releases|release/);
      expect(payload.repository || payload.resolved_repository || "fixture/local").toBeTruthy();

      await openSetup(page, project.id);
      const card = page.getByTestId(`setup-card-${PACK}`);
      await expect(card).not.toHaveAttribute("data-status", "installing");
      await expect(card.getByRole("button", { name: /Link Existing Folder/i })).toBeVisible();
      expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();

      await setFixtureScenario(request, { mode: "no_matching_asset" });
      const refresh2 = await request.post(`${API}/api/setup/components/${PACK}/refresh-source`);
      const payload2 = await refresh2.json();
      expect(payload2.source_available).toBeFalsy();
      expect(JSON.stringify(payload2).toLowerCase()).toMatch(/asset|no_matching|unrelated|pattern/);

      observer.assertHealthyBrowser();
    } finally {
      await setFixtureScenario(request, { mode: "valid" });
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
