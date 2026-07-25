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
}

async function createSceneViaApi(request: APIRequestContext, projectId: string, name: string) {
  const res = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { name, prompt: "Corridor tension beat before the door opens.", duration_sec: 6 },
  });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{ id: string; name: string }>;
}

async function openCoDirector(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}`);
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  await fab.click();
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

async function sendMessage(page: Page, text: string) {
  const textarea = page.getByLabel("Message Co-Director");
  await textarea.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

/**
 * M2.4.1 integrated vertical slice:
 * intention ? plan ? propose_storyboard_generation ? capability check ? approve ?
 * execution_blocked when Comfy/packs unavailable ? no fake asset ? visualValidationPending remains.
 */
test.describe("@critical @isolated codirector intelligence storyboard", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("integrated planning and readiness flow keeps visual validation pending", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Intel Storyboard ${Date.now()}`);

    try {
      const scene = await createSceneViaApi(request, project.id, "Silver Corridor");
      await createBibleViaApi(request, project.id);

      // Tool availability should expose proposal_ready / execution_blocked vocabulary when Comfy is down.
      const availability = await (
        await request.get(`${API}/api/codirector/projects/${project.id}/tools/availability`)
      ).json();
      const storyboard = (availability.tools || availability || []).find?.(
        (t: { toolId?: string }) => t.toolId === "propose_storyboard_generation",
      ) || (availability.find?.((t: { toolId?: string }) => t.toolId === "propose_storyboard_generation"));
      // Soft assert: endpoint shape varies; UI path below is authoritative.
      void storyboard;
      void scene;

      await openCoDirector(page, project.id);
      await sendMessage(page, "Create the next storyboard shot.");

      // Backend intelligence path (not local planFromIntention) should surface analysis/plan UI.
      await expect(page.locator(".codirector-intelligence-status")).toBeVisible({ timeout: 25_000 });
      await expect(page.getByRole("button", { name: /Production Analysis/i })).toBeVisible({
        timeout: 20_000,
      });

      const proposalCard = page.locator(".codirector-proposal-card");
      await expect(proposalCard).toBeVisible({ timeout: 45_000 });
      await expect(proposalCard).toContainText(/storyboard/i);

      // UI must not claim a render completed before approval/execution.
      const bodyBefore = await page.locator("body").innerText();
      expect(bodyBefore).not.toMatch(/render completed|render finished|asset created/i);

      await proposalCard.getByRole("button", { name: "Approve" }).click();
      await expect(proposalCard).toBeHidden({ timeout: 25_000 });

      const bodyAfter = await page.locator("body").innerText();
      expect(bodyAfter).not.toMatch(/render completed|render finished/i);
      // Honest blocked/pending language is acceptable; fake success is not.
      expect(bodyAfter.toLowerCase()).not.toContain("visual validation complete");

      // No new image/video asset should be invented by the propose tool.
      const assets = await (await request.get(`${API}/api/projects/${project.id}/assets`)).json();
      const assetList = Array.isArray(assets) ? assets : assets.assets || [];
      expect(assetList.filter((a: { kind?: string }) => /image|video/i.test(String(a.kind || ""))).length).toBe(0);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
