/**
 * Spoken-language authority — persist via product API/Inspector, then submit.
 * Does not patch Scene 3 JSON. Does not invent English from Cade's name.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

test.use({ extraHTTPHeaders: {} });
test.describe.configure({ retries: 0 });

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

test("Disposable: Spoken Language persist unblocks the authority error", async ({ page, request }) => {
  test.setTimeout(180_000);
  const project = await createTempProject(request, "Spoken Language Disposable");
  try {
    const created = await request.post(`${API}/api/projects/${project.id}/scenes`, {
      data: {
        name: "Spoken Language",
        engine: "minimax-h3",
        duration_sec: 5,
        prompt: 'CADE: "Where is the Adept?"',
      },
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
    batch.speechWindows = [
      {
        start: 0,
        end: 4,
        speechKind: "prompt_dialogue",
        speakers: [{ speakerName: "Cade", text: "Where is the Adept?" }],
      },
    ];
    const put = await request.put(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/master`,
      { data: { master } },
    );
    expect(put.ok(), await put.text()).toBeTruthy();
    expect((await fetchMaster(request, project.id, scene.id)).sceneLanguage || "").toBe("");

    await page.goto(`http://127.0.0.1:5173/project/${project.id}?workspace=timeline&sceneId=${scene.id}`, {
      waitUntil: "domcontentloaded",
    });
    const spoken = page.getByTestId("timeline-spoken-language");
    await expect(spoken).toBeAttached({ timeout: 60_000 });
    await spoken.selectOption("en", { force: true });
    await expect
      .poll(async () => {
        const live = await fetchMaster(request, project.id, scene.id);
        return String(live.sceneLanguage || live.spokenLanguage?.sceneLanguage || "");
      }, { timeout: 20_000 })
      .toBe("en");

    const allowed = await request.post(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/generate`,
      { data: { scope: "full", draftMode: true } },
    );
    const allowedBody = await allowed.json();
    const allowedError =
      allowedBody.error ||
      allowedBody.errors?.[0]?.error ||
      allowedBody.detail?.error ||
      "";
    expect(allowedError, JSON.stringify(allowedBody)).not.toBe("SPOKEN_LANGUAGE_AUTHORITY_MISSING");
    await request.post(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/cancel`,
      { data: { action: "cancel_active_local_job" } },
    );
  } finally {
    await deleteProject(request, project.id);
  }
});

test("Scene 3: Spoken Language persists and historical Take A stays intact", async ({ page, request }) => {
  test.setTimeout(120_000);
  const master = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  expect(String(master.sceneLanguage || master.spokenLanguage?.sceneLanguage || "")).toBe("en");
  const takeA = (master.sceneTakes || []).find((t: any) => Number(t.letterIndex) === 1);
  expect(takeA?.id).toBe("stk_c4e4aa5c383b");
  expect(takeA?.status).not.toBe("rendering");
  const hist = (master.batchBlocks || [])
    .flatMap((b: any) => b.candidateVersions || [])
    .find((c: any) => c.id === HIST_CAND_ID);
  expect(hist?.assetId).toBe(HIST_ASSET_ID);
  expect(master.activeSceneTakeId == null).toBeTruthy();

  await page.goto(
    `http://127.0.0.1:5173/project/${CADE_SCENES_PROJECT_ID}?workspace=timeline&sceneId=${SCENE_3_ID}`,
    { waitUntil: "domcontentloaded" },
  );
  await expect(page.getByTestId("timeline-spoken-language")).toBeAttached({ timeout: 60_000 });
  await page.reload({ waitUntil: "domcontentloaded" });
  const reloaded = await fetchMaster(request, CADE_SCENES_PROJECT_ID, SCENE_3_ID);
  expect(String(reloaded.sceneLanguage || "")).toBe("en");
  expect((reloaded.sceneTakes || []).find((t: any) => t.id === takeA.id)?.status).not.toBe("rendering");
  expect(reloaded.activeSceneTakeId == null).toBeTruthy();
  expect(
    (reloaded.batchBlocks || [])
      .flatMap((blk: any) => blk.candidateVersions || [])
      .find((c: any) => c.id === HIST_CAND_ID)?.assetId,
  ).toBe(HIST_ASSET_ID);
});
