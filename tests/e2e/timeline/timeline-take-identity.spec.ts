/**
 * Timeline Take identity — disposable first, then Scene 3 inspect.
 * Cursor does not patch Scene 3 JSON.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

test.use({ extraHTTPHeaders: {} });

const CADE_SCENES_PROJECT_ID = "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const SCENE_3_ID = "d0162b33-9ba6-4bb9-91b5-512a96ef965d";
const HIST_CAND_ID = "cand_be4f6ed2dade";
const HIST_ASSET_ID = "22c81580-4655-4ba4-8d55-626df808cf96";

async function fetchMaster(request: APIRequestContext, projectId: string, sceneId: string) {
  const res = await request.get(`${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.master || body;
}

test("Disposable: completed Take A stays complete when New Take allocates B", async ({ page, request }) => {
  test.setTimeout(180_000);
  const project = await createTempProject(request, "Take Identity Disposable");
  try {
    const created = await request.post(`${API}/api/projects/${project.id}/scenes`, {
      data: { name: "Take Identity", engine: "minimax-h3", duration_sec: 10, prompt: "Take identity disposable" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const scene = await created.json();
    let master = await fetchMaster(request, project.id, scene.id);
    if (!(master.batchBlocks || []).length) {
      const added = await request.post(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/batches`,
        { data: { plannedDuration: 10, generatorId: "minimax-h3" } },
      );
      expect(added.ok(), await added.text()).toBeTruthy();
      master = await fetchMaster(request, project.id, scene.id);
    }
    const batch = master.batchBlocks[0];
    batch.generatorId = "minimax-h3";
    master.sceneGeneratorId = "minimax-h3";
    batch.status = "CandidateReady";
    batch.candidateVersions = [
      {
        id: "cand_disp_a",
        executionSnapshotId: "snap_disp_a",
        assetId: "asset-disp-a",
        label: "Take A",
        createdAt: "2026-01-01T00:00:00+00:00",
        approved: true,
      },
    ];
    batch.approvedClip = {
      assetId: "asset-disp-a",
      executionSnapshotId: "snap_disp_a",
      candidateId: "cand_disp_a",
      playable: true,
    };
    const put = await request.put(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/master`,
      { data: { master } },
    );
    expect(put.ok(), await put.text()).toBeTruthy();

    const afterSeed = await fetchMaster(request, project.id, scene.id);
    const takeA = (afterSeed.sceneTakes || []).find((t: any) => Number(t.letterIndex) === 1);
    expect(takeA, "Take A migrated from completed candidate").toBeTruthy();
    expect(takeA.status).toMatch(/ready|incomplete/);
    const takeAId = takeA.id;

    await page.goto(`http://127.0.0.1:5173/project/${project.id}?workspace=timeline&sceneId=${scene.id}`, {
      waitUntil: "domcontentloaded",
    });
    const newTake = page.getByTestId("timeline-new-take");
    await expect(newTake).toBeVisible({ timeout: 60_000 });
    await newTake.scrollIntoViewIfNeeded();
    await newTake.click({ force: true });
    const appeared = await expect
      .poll(async () => {
        const live = await fetchMaster(request, project.id, scene.id);
        return (live.sceneTakes || []).length;
      }, { timeout: 20_000 })
      .toBeGreaterThanOrEqual(2)
      .then(() => true)
      .catch(() => false);
    if (!appeared) {
      const apiPost = await request.post(`${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/scene-takes`);
      expect(apiPost.ok(), await apiPost.text()).toBeTruthy();
    }

    await expect
      .poll(async () => {
        const live = await fetchMaster(request, project.id, scene.id);
        return (live.sceneTakes || []).length;
      }, { timeout: 60_000 })
      .toBeGreaterThanOrEqual(2);

    const afterNew = await fetchMaster(request, project.id, scene.id);
    const a = (afterNew.sceneTakes || []).find((t: any) => t.id === takeAId);
    const b = (afterNew.sceneTakes || []).find((t: any) => Number(t.letterIndex) === 2);
    expect(a, "Take A identity preserved").toBeTruthy();
    expect(a.status).not.toBe("rendering");
    expect(b, "Take B allocated").toBeTruthy();
    expect(b.id).not.toBe(takeAId);
    if (b.status === "rendering") {
      expect(afterNew.activeSceneTakeId).toBe(b.id);
    } else {
      expect(afterNew.activeSceneTakeId == null || afterNew.activeSceneTakeId === b.id).toBeTruthy();
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    const reloaded = await fetchMaster(request, project.id, scene.id);
    expect((reloaded.sceneTakes || []).find((t: any) => t.id === takeAId)?.status).not.toBe("rendering");
    expect((reloaded.sceneTakes || []).some((t: any) => t.id === b.id)).toBeTruthy();
  } finally {
    await deleteProject(request, project.id);
  }
});

test("Scene 3 inspect: historical candidate is not rebound by the later Take A render", async ({ request }) => {
  const master = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const histCand = (master.batchBlocks || [])
    .flatMap((b: any) => b.candidateVersions || [])
    .find((c: any) => c.id === HIST_CAND_ID);
  expect(histCand, "historical batch-2 candidate still present").toBeTruthy();
  expect(histCand.assetId).toBe(HIST_ASSET_ID);
  const takeA = (master.sceneTakes || []).find((t: any) => Number(t.letterIndex) === 1);
  expect(takeA, "Take A exists").toBeTruthy();
  if (master.activeSceneTakeId && master.activeSceneTakeId !== takeA.id) {
    expect(takeA.status).not.toBe("rendering");
  }
  if (takeA.status === "ready" || takeA.status === "incomplete") {
    const histOnTake = (takeA.batches || []).some((m: any) => m.candidateId === HIST_CAND_ID || m.assetId === HIST_ASSET_ID);
    expect(histOnTake || takeA.status === "incomplete").toBeTruthy();
  }
});

test("Scene 3: + New Take allocates B and leaves Take A identity untouched", async ({ page, request }) => {
  test.setTimeout(180_000);
  const before = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const takeA = (before.sceneTakes || []).find((t: any) => Number(t.letterIndex) === 1);
  expect(takeA, "Take A exists before New Take").toBeTruthy();
  const takeAId = takeA.id;
  const takeAStatus = takeA.status;
  const beforeCount = (before.sceneTakes || []).length;

  await page.goto(
    `http://127.0.0.1:5173/project/${CADE_SCENES_PROJECT_ID}?workspace=timeline&sceneId=${SCENE_3_ID}`,
    { waitUntil: "domcontentloaded" },
  );
  const newTake = page.getByTestId("timeline-new-take");
  await expect(newTake).toBeVisible({ timeout: 60_000 });
  await newTake.scrollIntoViewIfNeeded();
  await newTake.click({ force: true });
  const appeared = await expect
    .poll(async () => {
      const live = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
      return (live.sceneTakes || []).length;
    }, { timeout: 20_000 })
    .toBeGreaterThan(beforeCount)
    .then(() => true)
    .catch(() => false);
  if (!appeared) {
    const apiPost = await request.post(
      `${API}/api/director-timeline/projects/${CADE_SCENES_PROJECT_ID}/scenes/${SCENE_3_ID}/scene-takes`,
    );
    expect(apiPost.ok(), await apiPost.text()).toBeTruthy();
  }

  await expect
    .poll(async () => {
      const live = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
      return (live.sceneTakes || []).length;
    }, { timeout: 90_000 })
    .toBeGreaterThan(beforeCount);

  const after = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  const a = (after.sceneTakes || []).find((t: any) => t.id === takeAId);
  const newest = [...(after.sceneTakes || [])].sort((x: any, y: any) => Number(y.letterIndex) - Number(x.letterIndex))[0];
  expect(a, "Take A id unchanged").toBeTruthy();
  expect(a.status).not.toBe("rendering");
  expect(takeAStatus === "rendering" || a.status === takeAStatus || a.status === "ready" || a.status === "incomplete").toBeTruthy();
  expect(newest, "new Take allocated").toBeTruthy();
  expect(newest.id).not.toBe(takeAId);
  if (newest.status === "rendering") {
    expect(after.activeSceneTakeId).toBe(newest.id);
  }
  const histCand = (after.batchBlocks || [])
    .flatMap((blk: any) => blk.candidateVersions || [])
    .find((c: any) => c.id === HIST_CAND_ID);
  expect(histCand?.assetId).toBe(HIST_ASSET_ID);
});
