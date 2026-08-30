/**
 * Single Timed Prompt track. Schnick Coffee only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

type PromptSeg = {
  id: string;
  start: number;
  length: number;
  text?: string;
  reference_binding_ids?: string[];
};

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function firstScene(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  const scene = Array.isArray(scenes) ? scenes[0] : null;
  expect(scene?.id).toBeTruthy();
  return scene as { id: string };
}

async function getDirector(request: APIRequestContext, sceneId: string) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}/director`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible({ timeout: 60_000 });
}

function promptClips(page: Page) {
  return page.locator('[data-testid^="track-clip-prompt-"]');
}

type MasterPrompt = {
  id: string;
  start?: number;
  length?: number;
  text?: string;
  productionPrompt?: string | null;
  legacyPromptSegmentId?: string | null;
};

type SceneMaster = {
  batchBlocks?: Array<{ id: string; promptSegments?: MasterPrompt[] }>;
};

async function getMaster(request: APIRequestContext, sceneId: string): Promise<SceneMaster> {
  const res = await request.get(
    `${API}/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.master || body) as SceneMaster;
}

function compileMasterPrompts(master: SceneMaster): string {
  const parts: string[] = [];
  for (const batch of master.batchBlocks || []) {
    for (const seg of batch.promptSegments || []) {
      const text = String(seg.productionPrompt || seg.text || "").trim();
      if (text) parts.push(text);
    }
  }
  return parts.join("\n");
}

function masterHasPrompt(master: SceneMaster, id: string): boolean {
  return (master.batchBlocks || []).some((batch) =>
    (batch.promptSegments || []).some(
      (seg) => seg.id === id || seg.legacyPromptSegmentId === id || seg.id === `ps_${id}`,
    ),
  );
}

test.describe("Timeline single Timed Prompt track", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("one Timed Prompt row holds many horizontal clips through add, timing edit, and reload", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const original = await getDirector(request, scene.id);
    const originalIds = new Set((original.prompt_segments || []).map((seg: PromptSeg) => seg.id));

    try {
      await openTimeline(page, scene.id);
      await expect(page.getByTestId("timeline-timed-prompt-track")).toHaveCount(1);
      await expect(page.getByTestId("timeline-v2-label-timed-prompt")).toHaveCount(1);
      await expect(page.getByTestId("timeline-v2-label-timed-prompt")).toHaveText(/TIMED PROMPT/i);
      await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);
      await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);
      await expect(page.getByTestId("timeline-v2-label-timed-instructions")).toHaveCount(0);

      const beforeCount = await promptClips(page).count();
      expect(beforeCount).toBe((original.prompt_segments || []).length);
      const trackCount = await page.getByTestId("timeline-timed-prompt-track").count();
      expect(trackCount).toBe(1);
      expect(trackCount === beforeCount && beforeCount > 1, "track row count must never equal clip count").toBeFalsy();

      const boundExisting = (original.prompt_segments || []).find(
        (seg: PromptSeg) => (seg.reference_binding_ids || []).length > 0,
      ) as PromptSeg | undefined;
      if (boundExisting) {
        await expect(page.getByTestId(`prompt-token-summary-${boundExisting.id}`)).toBeVisible();
      }

      await page.getByTestId("timeline-toolbar-prompt-add").click();
      await expect
        .poll(async () => {
          const tl = await getDirector(request, scene.id);
          return ((tl.prompt_segments || []) as PromptSeg[]).filter((seg) => !originalIds.has(seg.id)).length;
        }, { timeout: 20_000 })
        .toBe(1);
      await expect(page.getByTestId("timeline-toolbar-prompt-add")).toBeEnabled();
      await page.getByTestId("timeline-toolbar-prompt-add").click();

      let added: PromptSeg[] = [];
      await expect
        .poll(async () => {
          const tl = await getDirector(request, scene.id);
          added = ((tl.prompt_segments || []) as PromptSeg[])
            .filter((seg) => !originalIds.has(seg.id))
            .sort((a, b) => a.start - b.start || a.id.localeCompare(b.id));
          return added.length;
        }, { timeout: 20_000 })
        .toBe(2);

      await expect(page.getByTestId("timeline-timed-prompt-track")).toHaveCount(1);
      await expect(promptClips(page)).toHaveCount(beforeCount + 2);

      const [clipA, clipB] = added;
      const boxA = await page.getByTestId(`track-clip-prompt-${clipA.id}`).boundingBox();
      const boxB = await page.getByTestId(`track-clip-prompt-${clipB.id}`).boundingBox();
      expect(boxA).toBeTruthy();
      expect(boxB).toBeTruthy();
      expect(Math.abs(boxA!.y - boxB!.y), "Prompt clips must share one row").toBeLessThanOrEqual(2);
      expect(Math.abs(boxA!.x - boxB!.x), "Prompt clips must sequence horizontally").toBeGreaterThan(8);

      const rowBox = await page.getByTestId("timeline-timed-prompt-track").boundingBox();
      expect(rowBox).toBeTruthy();
      expect(rowBox!.height, "Timed Prompt row must stay compact").toBeLessThanOrEqual(56);
      await mkdir("artifacts/timeline-timed-prompt", { recursive: true });
      await page.screenshot({ path: "artifacts/timeline-timed-prompt/one-track.png", fullPage: false });

      await page.getByTestId(`track-clip-prompt-${clipB.id}`).click();
      const rightOpen = await page.getByTestId("timeline-drawer-right-toggle").getAttribute("aria-expanded");
      if (rightOpen !== "true") {
        const handle = page.getByTestId("timeline-drawer-right-toggle");
        const handleBox = await handle.boundingBox();
        expect(handleBox).toBeTruthy();
        await handle.click({ position: { x: Math.max(2, handleBox!.width / 2), y: 16 } });
      }
      await page.getByTestId("timeline-tab-inspector").click();
      await expect(page.getByTestId("timeline-timed-prompt-start")).toBeVisible({ timeout: 20_000 });
      await page.getByTestId("timeline-timed-prompt-start").fill("3.5");
      await page.getByTestId("timeline-timed-prompt-start").blur();
      await expect
        .poll(async () => {
          const tl = await getDirector(request, scene.id);
          const seg = ((tl.prompt_segments || []) as PromptSeg[]).find((item) => item.id === clipB.id);
          return seg?.start;
        }, { timeout: 20_000 })
        .toBeCloseTo(3.5, 1);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("timeline-timed-prompt-track")).toHaveCount(1);
      await expect(page.getByTestId("timeline-v2-label-timed-prompt")).toHaveCount(1);
      await expect(page.getByTestId(`track-clip-prompt-${clipA.id}`)).toBeVisible();
      await expect(page.getByTestId(`track-clip-prompt-${clipB.id}`)).toBeVisible();
      await expect(promptClips(page)).toHaveCount(beforeCount + 2);
      await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);
      await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);

      const reloaded = await getDirector(request, scene.id);
      const reloadedA = ((reloaded.prompt_segments || []) as PromptSeg[]).find((item) => item.id === clipA.id);
      const reloadedB = ((reloaded.prompt_segments || []) as PromptSeg[]).find((item) => item.id === clipB.id);
      expect(reloadedA?.id).toBe(clipA.id);
      expect(reloadedB?.id).toBe(clipB.id);
      expect(reloadedB?.start).toBeCloseTo(3.5, 1);
      expect(reloadedA?.reference_binding_ids || []).toEqual(clipA.reference_binding_ids || []);
      expect(reloadedB?.reference_binding_ids || []).toEqual(clipB.reference_binding_ids || []);
      if (boundExisting) {
        const stillBound = ((reloaded.prompt_segments || []) as PromptSeg[]).find((item) => item.id === boundExisting.id);
        expect(stillBound?.reference_binding_ids).toEqual(boundExisting.reference_binding_ids);
        await expect(page.getByTestId(`prompt-token-summary-${boundExisting.id}`)).toBeVisible();
      }

      const afterBoxes = await page.evaluate((ids: [string, string]) => {
        const a = document.querySelector(`[data-testid="track-clip-prompt-${ids[0]}"]`)?.getBoundingClientRect();
        const b = document.querySelector(`[data-testid="track-clip-prompt-${ids[1]}"]`)?.getBoundingClientRect();
        return {
          ay: a?.y || 0,
          by: b?.y || 0,
          ax: a?.x || 0,
          bx: b?.x || 0,
        };
      }, [clipA.id, clipB.id] as [string, string]);
      expect(Math.abs(afterBoxes.ay - afterBoxes.by)).toBeLessThanOrEqual(2);
      expect(Math.abs(afterBoxes.ax - afterBoxes.bx)).toBeGreaterThan(8);
    } finally {
      await request.put(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`, {
        data: original,
      });
    }
  });

  test("Timed Prompt X delete is canonical on both lanes", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const marker = `e2e-timed-prompt-x-${Date.now()}`;
    await openTimeline(page, scene.id);

    const seeded = await page.evaluate(
      async ({ projectId, sceneId, text }) => {
        const dirRes = await fetch(`/api/projects/${projectId}/scenes/${sceneId}/director`);
        if (!dirRes.ok) throw new Error(`director GET ${dirRes.status}`);
        const director = await dirRes.json();
        const id = `e2e_tp_${Date.now().toString(36)}`;
        const seg = {
          id,
          start: 0.5,
          length: 1.25,
          text,
          weight: 1,
          reference_binding_ids: [],
        };
        director.prompt_segments = [...(director.prompt_segments || []), seg];
        const put = await fetch(`/api/projects/${projectId}/scenes/${sceneId}/director`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(director),
        });
        if (!put.ok) throw new Error(`director PUT ${put.status} ${await put.text()}`);
        const masterRes = await fetch(
          `/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`,
        );
        if (!masterRes.ok) throw new Error(`master GET ${masterRes.status}`);
        const masterBody = await masterRes.json();
        const master = masterBody.master || masterBody;
        const batch = (master.batchBlocks || [])[0];
        if (!batch?.id) throw new Error("no batch to seed promptSegments");
        const ps = {
          id: `ps_${id}`,
          start: seg.start,
          length: seg.length,
          text,
          role: "primary",
          strength: 1,
          anchorIds: [],
          executionStrategy: "compiled",
          versionId: `psv_${id}`,
          legacyPromptSegmentId: id,
          referenceBindingIds: [],
        };
        const patch = await fetch(
          `/api/director-timeline/projects/${projectId}/scenes/${sceneId}/batches/${batch.id}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ promptSegments: [...(batch.promptSegments || []), ps] }),
          },
        );
        if (!patch.ok) throw new Error(`batch PATCH ${patch.status} ${await patch.text()}`);
        return { id, start: seg.start, length: seg.length, text };
      },
      { projectId: PROJECT_ID, sceneId: scene.id, text: marker },
    );

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(`track-clip-prompt-${seeded.id}`)).toBeVisible({ timeout: 60_000 });
    expect(masterHasPrompt(await getMaster(request, scene.id), seeded.id)).toBeTruthy();

    await page.getByTestId(`track-clip-prompt-${seeded.id}`).click();
    const rightOpen = await page.getByTestId("timeline-drawer-right-toggle").getAttribute("aria-expanded");
    if (rightOpen !== "true") {
      const handle = page.getByTestId("timeline-drawer-right-toggle");
      const handleBox = await handle.boundingBox();
      expect(handleBox).toBeTruthy();
      await handle.click({ position: { x: Math.max(2, handleBox!.width / 2), y: 16 } });
    }
    await page.getByTestId("timeline-tab-inspector").click();
    await expect(page.getByTestId("timeline-timed-prompt-start")).toBeVisible({ timeout: 20_000 });

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId(`track-clip-prompt-${seeded.id}`).locator(".track-clip__remove").click();

    await expect(page.getByTestId(`track-clip-prompt-${seeded.id}`)).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByTestId("timeline-undo-toast")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("timeline-inspector")).toContainText("Scene Inspector");
    await expect(page.getByTestId("timeline-timed-prompt-start")).toHaveCount(0);

    await expect
      .poll(async () => {
        const tl = await getDirector(request, scene.id);
        return ((tl.prompt_segments || []) as PromptSeg[]).some((seg) => seg.id === seeded.id);
      }, { timeout: 20_000 })
      .toBeFalsy();
    await expect
      .poll(async () => masterHasPrompt(await getMaster(request, scene.id), seeded.id), { timeout: 20_000 })
      .toBeFalsy();
    expect(compileMasterPrompts(await getMaster(request, scene.id))).not.toContain(marker);

    await page.getByRole("button", { name: "Undo the last Timeline edit" }).click();
    await expect(page.getByTestId(`track-clip-prompt-${seeded.id}`)).toBeVisible({ timeout: 20_000 });
    await expect
      .poll(async () => {
        const tl = await getDirector(request, scene.id);
        return ((tl.prompt_segments || []) as PromptSeg[]).some((seg) => seg.id === seeded.id);
      }, { timeout: 20_000 })
      .toBeTruthy();
    await expect
      .poll(async () => masterHasPrompt(await getMaster(request, scene.id), seeded.id), { timeout: 20_000 })
      .toBeTruthy();
  });
});
