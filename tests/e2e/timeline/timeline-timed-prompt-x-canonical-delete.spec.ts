/**
 * Canonical Timed Prompt X: both lanes gone, Inspector scene, undo/redo/reload.
 * Real app, no mocks. Schnick Coffee only. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const MARKER = `e2e-timed-prompt-x-${Date.now()}`;

type PromptSeg = {
  id: string;
  start: number;
  length: number;
  text?: string;
};

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

async function getMaster(request: APIRequestContext, sceneId: string): Promise<SceneMaster> {
  const res = await request.get(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`,
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

function findMasterPrompt(master: SceneMaster, id: string): MasterPrompt | undefined {
  for (const batch of master.batchBlocks || []) {
    const hit = (batch.promptSegments || []).find(
      (seg) => seg.id === id || seg.legacyPromptSegmentId === id || seg.id === `ps_${id}`,
    );
    if (hit) return hit;
  }
  return undefined;
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible({ timeout: 60_000 });
}

async function seedBothLanes(page: Page, sceneId: string, marker: string) {
  return page.evaluate(
    async ({ projectId, sceneId: sid, marker: text }) => {
      const dirRes = await fetch(`/api/projects/${projectId}/scenes/${sid}/director`);
      if (!dirRes.ok) throw new Error(`director GET ${dirRes.status}`);
      const director = await dirRes.json();
      const id = `e2e_tp_${Date.now().toString(36)}`;
      const seg = {
        id,
        start: 3.5,
        length: 1.25,
        text,
        weight: 1,
        reference_binding_ids: [],
      };
      director.prompt_segments = [
        ...(director.prompt_segments || []).filter((row: { id?: string }) => !String(row.id || "").startsWith("e2e_tp_")),
        seg,
      ];
      const put = await fetch(`/api/projects/${projectId}/scenes/${sid}/director`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(director),
      });
      if (!put.ok) throw new Error(`director PUT ${put.status} ${await put.text()}`);
      const masterRes = await fetch(
        `/api/director-timeline/projects/${projectId}/scenes/${sid}/master`,
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
        `/api/director-timeline/projects/${projectId}/scenes/${sid}/batches/${batch.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
          promptSegments: [
            ...(batch.promptSegments || []).filter(
              (row: { id?: string; legacyPromptSegmentId?: string | null; text?: string }) =>
                row.legacyPromptSegmentId !== id &&
                row.id !== ps.id &&
                !String(row.legacyPromptSegmentId || "").startsWith("e2e_tp_") &&
                !String(row.text || "").startsWith("e2e-timed-prompt-x-"),
            ),
            ps,
          ],
        }),
        },
      );
      if (!patch.ok) throw new Error(`batch PATCH ${patch.status} ${await patch.text()}`);
      return { id, start: seg.start, length: seg.length, text, batchId: batch.id, masterSegId: ps.id };
    },
    { projectId: PROJECT_ID, sceneId, marker },
  );
}

async function openInspector(page: Page) {
  const rightOpen = await page.getByTestId("timeline-drawer-right-toggle").getAttribute("aria-expanded");
  if (rightOpen !== "true") {
    const handle = page.getByTestId("timeline-drawer-right-toggle");
    const handleBox = await handle.boundingBox();
    expect(handleBox).toBeTruthy();
    await handle.click({ position: { x: Math.max(2, handleBox!.width / 2), y: 16 } });
  }
  await page.getByTestId("timeline-tab-inspector").click();
}

test.describe("Timed Prompt X canonical delete", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("X removes Timed Prompt from UI, Inspector, both lanes, and compiled payload; undo/redo/reload", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id);
    page.on("dialog", (dialog) => dialog.accept());

    const seeded = await seedBothLanes(page, scene.id, MARKER);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    const clip = () => page.getByTestId(`track-clip-prompt-${seeded.id}`).first();
    await expect(clip()).toBeVisible({ timeout: 60_000 });

    const beforeDirector = await getDirector(request, scene.id);
    const beforeSeg = ((beforeDirector.prompt_segments || []) as PromptSeg[]).find((seg) => seg.id === seeded.id);
    expect(beforeSeg, "seeded prompt_segments row").toBeTruthy();
    const recorded = {
      id: beforeSeg!.id,
      start: beforeSeg!.start,
      length: beforeSeg!.length,
      text: beforeSeg!.text || MARKER,
    };
    const beforeMaster = await getMaster(request, scene.id);
    expect(masterHasPrompt(beforeMaster, recorded.id), "seeded batch.promptSegments").toBeTruthy();
    expect(compileMasterPrompts(beforeMaster)).toContain(MARKER);

    await page.getByTestId(`track-clip-prompt-${recorded.id}`).first().click({ force: true });
    await openInspector(page);
    await expect(page.getByTestId("timeline-timed-prompt-start")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("timeline-inspector")).toContainText(/Prompt Clip|Timed Prompt/i);

    await page
      .getByTestId("timeline-timed-prompt-track")
      .first()
      .locator(`[data-testid="track-clip-prompt-${recorded.id}"]`)
      .first()
      .locator(".track-clip__remove")
      .click({ force: true });

    await expect(page.getByTestId(`track-clip-prompt-${recorded.id}`)).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByTestId("timeline-undo-toast")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("timeline-undo-toast")).toContainText("Removed from Timeline");

    await expect(page.getByTestId("timeline-inspector")).toContainText("Scene Inspector");
    await expect(page.getByTestId("timeline-scene-prompt")).toBeVisible();
    await expect(page.getByTestId("timeline-timed-prompt-start")).toHaveCount(0);

    await expect
      .poll(async () => {
        const tl = await getDirector(request, scene.id);
        return ((tl.prompt_segments || []) as PromptSeg[]).some((seg) => seg.id === recorded.id);
      }, { timeout: 20_000 })
      .toBeFalsy();

    await expect
      .poll(async () => {
        const master = await getMaster(request, scene.id);
        return masterHasPrompt(master, recorded.id);
      }, { timeout: 20_000 })
      .toBeFalsy();

    const afterDeleteMaster = await getMaster(request, scene.id);
    expect(compileMasterPrompts(afterDeleteMaster)).not.toContain(MARKER);

    await page.getByRole("button", { name: "Undo the last Timeline edit" }).click();
    await expect(page.getByTestId(`track-clip-prompt-${recorded.id}`).first()).toBeVisible({ timeout: 20_000 });
    await expect
      .poll(async () => {
        const tl = await getDirector(request, scene.id);
        const seg = ((tl.prompt_segments || []) as PromptSeg[]).find((item) => item.id === recorded.id);
        return seg ? `${seg.id}|${seg.start}|${seg.length}|${seg.text || ""}` : "";
      }, { timeout: 20_000 })
      .toBe(`${recorded.id}|${recorded.start}|${recorded.length}|${recorded.text}`);

    await expect
      .poll(async () => {
        const master = await getMaster(request, scene.id);
        const seg = findMasterPrompt(master, recorded.id);
        return seg ? `${seg.legacyPromptSegmentId || seg.id}|${seg.start}|${seg.length}|${seg.text || ""}` : "";
      }, { timeout: 20_000 })
      .toBe(`${recorded.id}|${recorded.start}|${recorded.length}|${recorded.text}`);
    expect(compileMasterPrompts(await getMaster(request, scene.id))).toContain(MARKER);

    await page.getByRole("button", { name: "Redo the last undone Timeline edit" }).click();
    await expect(page.getByTestId(`track-clip-prompt-${recorded.id}`)).toHaveCount(0, { timeout: 20_000 });
    await expect
      .poll(async () => {
        const tl = await getDirector(request, scene.id);
        return ((tl.prompt_segments || []) as PromptSeg[]).some((seg) => seg.id === recorded.id);
      }, { timeout: 20_000 })
      .toBeFalsy();
    await expect
      .poll(async () => {
        const master = await getMaster(request, scene.id);
        return masterHasPrompt(master, recorded.id);
      }, { timeout: 20_000 })
      .toBeFalsy();
    expect(compileMasterPrompts(await getMaster(request, scene.id))).not.toContain(MARKER);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(`track-clip-prompt-${recorded.id}`)).toHaveCount(0);
    const reloadedDirector = await getDirector(request, scene.id);
    expect(((reloadedDirector.prompt_segments || []) as PromptSeg[]).some((seg) => seg.id === recorded.id)).toBeFalsy();
    const reloadedMaster = await getMaster(request, scene.id);
    expect(masterHasPrompt(reloadedMaster, recorded.id)).toBeFalsy();
    expect(compileMasterPrompts(reloadedMaster)).not.toContain(MARKER);

    const cameraClip = page.locator('[data-testid^="track-clip-camera-"]').first();
    const visualClip = page.locator('[data-testid^="track-clip-image-"]').first();
    const shared = (await cameraClip.count()) ? cameraClip : (await visualClip.count()) ? visualClip : null;
    if (shared) {
      await expect(shared.locator(".track-clip__remove")).toHaveCount(1);
    }
  });
});
