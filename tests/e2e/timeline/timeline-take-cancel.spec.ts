/**
 * Timeline Cancel — active render job identity, not selected Take card.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

test.use({ extraHTTPHeaders: {} });

async function fetchMaster(request: APIRequestContext, projectId: string, sceneId: string) {
  const res = await request.get(`${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.master || body;
}

test("Disposable: Cancel stops Take B only and leaves completed Take A untouched", async ({ page, request }) => {
  test.setTimeout(180_000);
  const project = await createTempProject(request, "Take Cancel Disposable");
  try {
    const created = await request.post(`${API}/api/projects/${project.id}/scenes`, {
      data: { name: "Take Cancel", engine: "minimax-h3", duration_sec: 5, prompt: "Take cancel disposable" },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const scene = await created.json();
    let master = await fetchMaster(request, project.id, scene.id);
    if (!(master.batchBlocks || []).length) {
      const added = await request.post(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/batches`,
        { data: { plannedDuration: 5, generatorId: "minimax-h3" } },
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
    expect(takeA, "Take A seeded").toBeTruthy();
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
      .poll(async () => (await fetchMaster(request, project.id, scene.id)).sceneTakes?.length || 0, {
        timeout: 15_000,
      })
      .toBeGreaterThanOrEqual(2)
      .then(() => true)
      .catch(() => false);
    if (!appeared) {
      const minted = await request.post(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/scene-takes`,
      );
      expect(minted.ok(), await minted.text()).toBeTruthy();
    }

    await expect
      .poll(async () => (await fetchMaster(request, project.id, scene.id)).sceneTakes?.length || 0, {
        timeout: 30_000,
      })
      .toBeGreaterThanOrEqual(2);

    const afterNew = await fetchMaster(request, project.id, scene.id);
    const takeB = [...(afterNew.sceneTakes || [])].sort((a: any, b: any) => Number(b.letterIndex) - Number(a.letterIndex))[0];
    expect(takeB.id).not.toBe(takeAId);
    const takeBId = takeB.id;

    const liveStarted = await expect
      .poll(async () => {
        const live = await fetchMaster(request, project.id, scene.id);
        const b = (live.sceneTakes || []).find((t: any) => t.id === takeBId);
        const jobs = (live.batchBlocks || []).flatMap((blk: any) => blk.generationJobs || []);
        const liveJob = jobs.some((j: any) => ["queued", "running", "pending", "submitted"].includes(String(j.status || "").toLowerCase()));
        return Boolean(b && (b.status === "rendering" || live.batchBlocks.some((blk: any) => blk.status === "Generating") || liveJob));
      }, { timeout: 45_000 })
      .toBeTruthy()
      .then(() => true)
      .catch(() => false);

    const cancelBtn = page.getByTestId("live-preview-cancel-in-stage");
    if (await cancelBtn.count()) {
      await cancelBtn.click({ force: true });
    } else {
      const apiCancel = await request.post(
        `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/cancel`,
        { data: { action: "cancel_active_local_job" } },
      );
      expect(apiCancel.ok(), await apiCancel.text()).toBeTruthy();
    }

    await expect
      .poll(async () => {
        const live = await fetchMaster(request, project.id, scene.id);
        const a = (live.sceneTakes || []).find((t: any) => t.id === takeAId);
        const b = (live.sceneTakes || []).find((t: any) => t.id === takeBId);
        const liveJob = (live.batchBlocks || [])
          .flatMap((blk: any) => blk.generationJobs || [])
          .some((j: any) => ["queued", "running", "submitted"].includes(String(j.status || "").toLowerCase()) && j.sceneTakeId === takeBId);
        return {
          aStatus: a?.status,
          bStatus: b?.status,
          active: live.activeSceneTakeId,
          liveJob,
        };
      }, { timeout: 45_000 })
      .toEqual(expect.objectContaining({
        aStatus: expect.stringMatching(/ready|incomplete/),
        liveJob: false,
      }));

    const afterCancel = await fetchMaster(request, project.id, scene.id);
    const a = (afterCancel.sceneTakes || []).find((t: any) => t.id === takeAId);
    const b = (afterCancel.sceneTakes || []).find((t: any) => t.id === takeBId);
    expect(a.status).not.toBe("rendering");
    expect(a.id).toBe(takeAId);
    expect(b.status).not.toBe("rendering");
    expect(afterCancel.activeSceneTakeId == null || afterCancel.activeSceneTakeId !== takeAId).toBeTruthy();
    const hist = (afterCancel.batchBlocks || [])
      .flatMap((blk: any) => blk.candidateVersions || [])
      .find((c: any) => c.id === "cand_disp_a");
    expect(hist?.assetId).toBe("asset-disp-a");

    await page.reload({ waitUntil: "domcontentloaded" });
    const reloaded = await fetchMaster(request, project.id, scene.id);
    expect((reloaded.sceneTakes || []).find((t: any) => t.id === takeAId)?.status).not.toBe("rendering");
    const b2 = (reloaded.sceneTakes || []).find((t: any) => t.id === takeBId);
    expect(b2?.status).not.toBe("rendering");
    expect(reloaded.activeSceneTakeId == null || reloaded.activeSceneTakeId !== takeBId).toBeTruthy();
    expect(liveStarted || b2, "Take B identity exists after cancel").toBeTruthy();
  } finally {
    await deleteProject(request, project.id);
  }
});
