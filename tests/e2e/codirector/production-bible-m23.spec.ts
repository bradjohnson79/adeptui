import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

async function createBibleViaApi(request: APIRequestContext, projectId: string) {
  const preview = await (
    await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/preview`, { data: {} })
  ).json();
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/confirm`, {
    data: { entities: preview.entities, facts: preview.facts, summary: preview.summary },
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function openBibleWorkspace(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=bible`);
  await expect(page.getByRole("heading", { name: "Production Bible" })).toBeVisible({ timeout: 30_000 });
}

/**
 * M2.3 vertical slice: create character → approve → lock → blocked edit → export
 */
test.describe("@isolated codirector m2.3 production bible vertical slice", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("production-ready character lifecycle via API and UI export", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `M23 Slice ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);

      const charRes = await request.post(`${API}/api/codirector/projects/${project.id}/bible/characters`, {
        data: {
          entityKey: "elena",
          displayName: "Elena Voss",
          data: {
            description: "Lead investigator",
            personality: "Determined",
            motivation: "Truth",
            appearanceSummary: "Trench coat, scar",
            readiness: "production_ready",
          },
        },
      });
      expect(charRes.ok()).toBeTruthy();
      const character = await charRes.json();
      const stableId = character.stableId as string;

      await request.post(`${API}/api/codirector/projects/${project.id}/bible/characters/${stableId}/approve`);
      await request.post(`${API}/api/codirector/projects/${project.id}/bible/characters/${stableId}/lock`);

      const blocked = await request.patch(`${API}/api/codirector/projects/${project.id}/bible/characters/${stableId}`, {
        data: { description: "Should fail" },
        contentRevision: character.contentRevision,
      });
      expect(blocked.status()).toBe(409);
      expect((await blocked.json()).detail.code).toBe("LOCKED_ENTITY_REQUIRES_APPROVAL");

      const ctx = await request.get(
        `${API}/api/codirector/projects/${project.id}/bible/context/character/${stableId}`,
      );
      expect(ctx.ok()).toBeTruthy();
      expect((await ctx.json()).found).toBe(true);

      const exported = await request.get(`${API}/api/codirector/projects/${project.id}/bible/export`);
      expect(exported.ok()).toBeTruthy();
      expect((await exported.json()).schemaVersion).toBe("m2.3");

      // Every lifecycle step above is a versioned Bible change (create, approve, lock), so the
      // number is not a constant. Read it back from the API and require the workspace to be
      // showing that same version — a stale or wrong version in the UI still fails.
      const bible = await (await request.get(`${API}/api/codirector/projects/${project.id}/bible`)).json();
      const currentVersion = Number(bible.currentVersion.versionNumber);
      expect(currentVersion).toBeGreaterThan(1);

      await openBibleWorkspace(page, project.id);
      await expect(page.getByText(new RegExp(`Version ${currentVersion} of`))).toBeVisible({
        timeout: 15_000,
      });
      await page.getByRole("button", { name: "Characters" }).click();
      await expect(page.getByText("Elena Voss")).toBeVisible();
      await page.getByRole("button", { name: "Export JSON" }).click();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
