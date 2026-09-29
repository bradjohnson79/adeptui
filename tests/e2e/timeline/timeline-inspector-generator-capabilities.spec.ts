/**
 * Batch Inspector: generator-specific quality under Generator,
 * live native audio, restored Continuity / Advanced.
 * Reuses Korri Anadriya. Creates a disposable scene.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const UI = process.env.ADEPT_UI_ORIGIN || "http://127.0.0.1:5173";
const SCENE_NAME = "Inspector Capability Cert";

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function openRightInspector(page: Page) {
  const rightToggle = page.getByTestId("timeline-drawer-right-toggle");
  await expect(rightToggle).toBeVisible();
  if ((await rightToggle.getAttribute("aria-expanded")) !== "true") {
    await rightToggle.click();
  }
  await expect(rightToggle).toHaveAttribute("aria-expanded", "true");
  const tab = page.getByTestId("timeline-tab-inspector");
  if (await tab.isVisible().catch(() => false)) await tab.click();
  await expect(page.getByTestId("timeline-inspector")).toBeVisible({ timeout: 20_000 });
}

async function cleanupTempScenes(request: APIRequestContext) {
  const project = await getJson(request, `/api/projects/${PROJECT_ID}`);
  for (const scene of project.scenes || []) {
    if (String(scene.name || "").startsWith(SCENE_NAME)) {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}`);
    }
  }
}

test.describe("Timeline Inspector generator capabilities", () => {
  test.setTimeout(180_000);
  test.skip(process.env.ADEPT_ALLOW_KORRI_MUTATION !== "1", "Requires ADEPT_ALLOW_KORRI_MUTATION=1");

  test("quality follows selected generator; native audio is live; Advanced is LoRA", async ({
    page,
    request,
  }) => {
    await expect
      .poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 })
      .toBeTruthy();
    await cleanupTempScenes(request);

    const created = await request.post(`${API}/api/projects/${PROJECT_ID}/scenes`, {
      data: { name: SCENE_NAME, engine: "minimax-h3", duration_sec: 5, prompt: "Capability cert" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const scene = await created.json();
    const sceneId = scene.id as string;

    try {
      let master = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
      let batch = (master.master || master).batchBlocks?.[0];
      if (!batch?.id) {
        const added = await request.post(
          `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches`,
          { data: { plannedDuration: 5, generatorId: "minimax-h3" } },
        );
        expect(added.ok(), await added.text()).toBeTruthy();
        master = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`);
        batch = (master.master || master).batchBlocks?.[0];
      }
      const batchId = batch.id as string;
      await request.patch(
        `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches/${batchId}`,
        { data: { generatorId: "minimax-h3", h3Resolution: { mode: "manual", megapixels: 2 } } },
      );

      const gens = await getJson(request, `/api/director-timeline/generators`);
      const h3Row = (gens.generators || []).find((row: { id?: string }) => String(row.id || "").startsWith("minimax-h3"));
      const ltxRow = (gens.generators || []).find((row: { id?: string }) => String(row.id || "").includes("ltx-2.5"));
      const h3Adapter = (gens.timelineAdapters || []).find((row: { id?: string }) => String(row.id || "").includes("minimax-h3"));
      expect(h3Adapter?.qualityControl || h3Row?.qualityControl).toBe("h3_megapixels");
      expect(Boolean(h3Adapter?.audio_generation || h3Row?.supportsAudio)).toBeTruthy();

      await page.goto(`${UI}/project/${PROJECT_ID}?workspace=timeline&sceneId=${sceneId}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await page.getByTestId(`timeline-batch-${batchId}`).click();
      const generation = page.getByTestId("timeline-batch-generation");
      await expect(generation).toBeVisible({ timeout: 20_000 });

      await generation.getByTestId("timeline-batch-generator").selectOption({ value: "minimax-h3" }).catch(async () => {
        const options = await generation.getByTestId("timeline-batch-generator").locator("option").allTextContents();
        const match = options.find((label) => /minimax|h3/i.test(label));
        if (match) await generation.getByTestId("timeline-batch-generator").selectOption({ label: match });
      });
      await expect(generation.getByTestId("timeline-batch-resolution")).toBeVisible({ timeout: 15_000 });
      await expect(generation.getByTestId("timeline-batch-quality")).toHaveCount(0);
      await expect(generation.getByTestId("timeline-native-audio-status")).toBeVisible();
      const h3Audio = (await generation.getByTestId("timeline-native-audio-status").innerText()).trim();
      expect(h3Audio).not.toMatch(/None \(generator has no native audio\)/i);
      if (h3Row?.executable !== false && h3Adapter?.audio_generation !== false) {
        expect(h3Audio).toMatch(/SUPPORTED|Checking/i);
      }

      if (ltxRow?.id) {
        await generation.getByTestId("timeline-batch-generator").selectOption(String(ltxRow.id));
        await expect(generation.getByTestId("timeline-batch-quality")).toBeVisible({ timeout: 15_000 });
        await expect(generation.getByTestId("timeline-batch-resolution")).toHaveCount(0);
        const ltxAudio = (await generation.getByTestId("timeline-native-audio-status").innerText()).trim();
        expect(ltxAudio).not.toMatch(/None \(generator has no native audio\)/i);
        await generation.getByTestId("timeline-batch-generator").selectOption("minimax-h3");
        await expect(generation.getByTestId("timeline-batch-resolution")).toBeVisible({ timeout: 15_000 });
        await expect(generation.getByTestId("timeline-batch-quality")).toHaveCount(0);
      }

      const continuity = page.getByTestId("timeline-batch-continuity");
      await expect(continuity).toBeVisible();
      if (!(await continuity.getByTestId("timeline-cd-continuity-enabled").isVisible().catch(() => false))) {
        await continuity.locator("summary").click();
      }
      await expect(continuity.getByTestId("timeline-cd-continuity-enabled")).toBeVisible();
      await expect(continuity.getByTestId("timeline-cd-review-cadence")).toBeVisible();

      const advanced = page.getByTestId("timeline-batch-advanced");
      await expect(advanced).toBeVisible();
      if (!(await advanced.locator("text=LoRA").first().isVisible().catch(() => false))) {
        await advanced.locator("summary").click();
      }
      await expect(advanced.getByTestId("timeline-batch-resolution")).toHaveCount(0);
      await expect(advanced.getByTestId("timeline-batch-quality")).toHaveCount(0);
      await expect(advanced.getByTestId("timeline-native-audio")).toHaveCount(0);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
      await openRightInspector(page);
      await page.getByTestId(`timeline-batch-${batchId}`).click();
      await expect(page.getByTestId("timeline-batch-generation").getByTestId("timeline-batch-resolution")).toBeVisible({
        timeout: 20_000,
      });
      const after = await getJson(
        request,
        `/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`,
      );
      const saved = ((after.master || after).batchBlocks || []).find((row: { id?: string }) => row.id === batchId);
      expect(saved?.h3Resolution?.megapixels === 2 || saved?.h3Resolution?.mode === "manual").toBeTruthy();
    } finally {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}`);
    }
  });
});
