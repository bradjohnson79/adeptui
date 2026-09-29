/**
 * Active product-contract: Timeline / Co-Director authoring is Master-only.
 * Fail on any product GET/PUT /scenes/{id}/director. director-timeline Master URLs remain allowed.
 */
import { expect, test } from "@playwright/test";
import { openCoDirectorFullScreen, sendChatTurn } from "../codirector/helpers/audit";
import {
  API,
  EXISTING_SCENE_ID,
  PROJECT_ID,
  cleanupScenesByPrefix,
  flattenMasterPrompts,
  flattenMasterVisuals,
  getMaster,
  getSceneRow,
  installDirectorWriteGuard,
  listScenes,
  openInspector,
  openTimeline,
  parseSse,
  patchBatchPrompts,
  patchSceneMetadata,
  timelineMasterDump,
  waitApiReady,
} from "./masterAuthoring";

const PREFIX = "Master Contract Playwright";

async function removePromptIds(request: Parameters<typeof getMaster>[0], sceneId: string, ids: Iterable<string>) {
  const remove = new Set([...ids].filter(Boolean));
  if (!remove.size) return;
  const master = await getMaster(request, sceneId);
  for (const batch of master.batchBlocks || []) {
    if (!batch.id) continue;
    const before = batch.promptSegments || [];
    const after = before.filter((seg) => !remove.has(String(seg.id || "")));
    if (after.length !== before.length) {
      await patchBatchPrompts(request, sceneId, String(batch.id), after);
    }
  }
}

test.describe("Timeline Master authoring contract", () => {
  test.setTimeout(240_000);

  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("A1 A2 A3 — add / edit / delete Timed Prompt via Master only", async ({ page, request }) => {
    await cleanupScenesByPrefix(request, PREFIX);
    const sceneId = EXISTING_SCENE_ID;
    const guard = installDirectorWriteGuard(page);
    const addedIds = new Set<string>();
    try {
      await expect
        .poll(async () => (await getMaster(request, sceneId)).batchBlocks?.length || 0, { timeout: 20_000 })
        .toBeGreaterThan(0);
      await openTimeline(page, sceneId);
      await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("timeline-toolbar-prompt-add")).toBeEnabled();

      const before = flattenMasterPrompts(await getMaster(request, sceneId));
      const beforeIds = new Set(before.map((seg) => String(seg.id || "")));
      const firstExisting = before.find((seg) => seg.id);
      if (firstExisting?.id) {
        await expect(page.getByTestId(`track-clip-prompt-${firstExisting.id}`).first()).toBeVisible({
          timeout: 20_000,
        });
      }

      const writes: string[] = [];
      page.on("request", (req) => {
        const url = req.url();
        if (/\/scenes\/[^/]+\/director(?:\/|\?|$)/.test(url) && !/director-timeline|director-sequences/.test(url)) {
          writes.push(`${req.method()} ${url}`);
          return;
        }
        if (!/director-timeline/.test(url)) return;
        if (req.method() === "GET") return;
        writes.push(`${req.method()} ${url}`);
      });
      await page.getByTestId("timeline-toolbar-prompt-add").click();
      let addedId = "";
      await expect
        .poll(
          async () => {
            const segs = flattenMasterPrompts(await getMaster(request, sceneId));
            const added = segs.filter((seg) => !beforeIds.has(String(seg.id || "")));
            addedId = String(added[0]?.id || "");
            if (addedId) addedIds.add(addedId);
            return added.length;
          },
          { timeout: 20_000 },
        )
        .toBeGreaterThan(0);
      expect(addedId, `A1 toolbar add did not persist a Master row. writes=${writes.join(" | ")}`).toBeTruthy();
      guard.assertNone();

      const clip = page.getByTestId(`track-clip-prompt-${addedId}`).first();
      await expect(clip).toBeVisible({ timeout: 20_000 });
      await clip.click({ force: true });
      await openInspector(page);
      const box = page.getByTestId("timeline-prompt-instruction");
      await expect(box).toBeVisible({ timeout: 20_000 });
      const marker = `MASTER-A2-${Date.now()}`;
      await box.fill(marker);
      await box.blur();
      await expect
        .poll(
          async () => {
            const segs = flattenMasterPrompts(await getMaster(request, sceneId));
            const row = segs.find((seg) => String(seg.id) === addedId);
            return String(row?.text || row?.productionPrompt || "");
          },
          { timeout: 20_000 },
        )
        .toContain(marker);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      const afterReload = flattenMasterPrompts(await getMaster(request, sceneId));
      expect(
        afterReload.some((seg) => String(seg.id) === addedId && String(seg.text || "").includes(marker)),
      ).toBeTruthy();
      await expect(page.getByTestId(`track-clip-prompt-${addedId}`).first()).toBeVisible();

      page.once("dialog", (dialog) => dialog.accept());
      await page.getByTestId(`track-clip-prompt-${addedId}`).first().click({ force: true });
      await page.getByTestId("timeline-toolbar-prompt-remove").click();
      await expect
        .poll(
          async () =>
            flattenMasterPrompts(await getMaster(request, sceneId)).some((seg) => String(seg.id) === addedId),
          { timeout: 20_000 },
        )
        .toBeFalsy();
      addedIds.delete(addedId);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      expect(
        flattenMasterPrompts(await getMaster(request, sceneId)).some((seg) => String(seg.id) === addedId),
      ).toBeFalsy();
      guard.assertNone();
    } finally {
      await removePromptIds(request, sceneId, addedIds);
    }
  });

  test("A4 — live browser Co-Director add-prompt is Master-verified with zero PUT /director", async ({
    page,
    request,
  }) => {
    await cleanupScenesByPrefix(request, PREFIX);
    const sceneId = EXISTING_SCENE_ID;
    const marker = `MASTER-A4-${Date.now()}`;
    const guard = installDirectorWriteGuard(page);
    const addedIds = new Set<string>();
    const beforeById = new Map<string, string>();
    try {
      const before = flattenMasterPrompts(await getMaster(request, sceneId));
      expect(((await getMaster(request, sceneId)).batchBlocks || []).length).toBeGreaterThan(0);
      for (const seg of before) beforeById.set(String(seg.id || ""), String(seg.text || ""));

      await openTimeline(page, sceneId);
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await openCoDirectorFullScreen(page, PROJECT_ID, { workspace: "timeline", sceneId });
      const streamResponse = page.waitForResponse(
        (res) => res.url().includes("/api/codirector/chat/stream") && res.request().method() === "POST",
        { timeout: 180_000 },
      );
      await sendChatTurn(
        page,
        `On the open Timeline scene ${sceneId}, add a 2-second Timed Prompt starting at 0 seconds that says exactly ${marker}. Do not use 20 seconds.`,
      );
      const approve = page.getByTestId("codirector-proposal-approve");
      if (await approve.isVisible().catch(() => false)) {
        await approve.click();
      }
      const response = await streamResponse;
      expect(response.ok(), await response.text()).toBeTruthy();
      const events = parseSse(await response.text());
      const completed = events.filter((evt) => evt.type === "tool_completed") as Array<{
        type?: string;
        invocation?: { result?: { verified?: boolean } };
        result?: { verified?: boolean };
      }>;
      const verified = completed.some(
        (evt) => evt.invocation?.result?.verified === true || evt.result?.verified === true,
      );
      expect(verified, `tool_completed verified:true missing. types=${events.map((e) => e.type).join(",")}`).toBeTruthy();

      let added: { id?: string; text?: string } | undefined;
      await expect
        .poll(
          async () => {
            const segs = flattenMasterPrompts(await getMaster(request, sceneId));
            added = segs.find((seg) => String(seg.text || "").includes(marker));
            if (added?.id && !beforeById.has(String(added.id))) addedIds.add(String(added.id));
            return Boolean(added?.id);
          },
          { timeout: 45_000 },
        )
        .toBeTruthy();

      await openTimeline(page, sceneId);
      await expect(page.getByTestId(`track-clip-prompt-${added!.id}`).first()).toBeVisible({ timeout: 30_000 });
      guard.assertNone();
    } finally {
      await removePromptIds(request, sceneId, addedIds);
      const master = await getMaster(request, sceneId);
      for (const batch of master.batchBlocks || []) {
        if (!batch.id) continue;
        let changed = false;
        const next = (batch.promptSegments || []).map((seg) => {
          const prior = beforeById.get(String(seg.id || ""));
          if (prior !== undefined && String(seg.text || "").includes(marker) && prior !== String(seg.text || "")) {
            changed = true;
            return { ...seg, text: prior };
          }
          return seg;
        });
        if (changed) await patchBatchPrompts(request, sceneId, String(batch.id), next);
      }
    }
  });

  test("A5 — 45s scene is one Scene and three H3 windows", async ({ page, request }) => {
    await cleanupScenesByPrefix(request, PREFIX);
    const sceneId = EXISTING_SCENE_ID;
    const guard = installDirectorWriteGuard(page);
    const master = await getMaster(request, sceneId);
    const windows = master.batchBlocks || [];
    expect(windows.length, "H3 execution windows").toBe(3);
    const scenes = await listScenes(request);
    expect(scenes.filter((row) => row.id === sceneId).length, "the 45s scene stays one row").toBe(1);
    const clones = windows.slice(1).flatMap((batch) =>
      (batch.promptSegments || []).filter((seg) => Number(seg.start || 0) === 0 && Number(seg.length || 0) >= 45),
    );
    expect(clones, "0–45 prompt must not be cloned into windows 2/3").toEqual([]);

    await openTimeline(page, sceneId);
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    const ruler = page.locator(".timeline-ruler, [data-testid='timeline-ruler']").first();
    if (await ruler.isVisible().catch(() => false)) {
      await expect(ruler).toContainText(/45/);
    }
    guard.assertNone();
  });

  test("B4 — browser Image add/remove writes Master.visualClips and survives reload", async ({
    page,
    request,
  }) => {
    await cleanupScenesByPrefix(request, PREFIX);
    const sceneId = EXISTING_SCENE_ID;
    const guard = installDirectorWriteGuard(page);
    const addedIds = new Set<string>();
    const beforeIds = new Set(
      flattenMasterVisuals(await getMaster(request, sceneId))
        .map((clip) => String(clip.id || ""))
        .filter(Boolean),
    );
    try {
      await expect
        .poll(async () => (await getMaster(request, sceneId)).batchBlocks?.length || 0, { timeout: 20_000 })
        .toBeGreaterThan(0);
      await openTimeline(page, sceneId);
      await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("timeline-toolbar-image-add")).toBeEnabled({ timeout: 30_000 });
      const patchVisual = page.waitForRequest(
        (req) =>
          req.method() === "PATCH" &&
          /\/director-timeline\/.*\/batches\//.test(req.url()) &&
          Boolean(req.postData()?.includes("visualClips") || req.postData()?.includes("image")),
        { timeout: 20_000 },
      );
      await page.getByTestId("timeline-toolbar-image-add").click();
      await patchVisual;
      let addedId = "";
      await expect
        .poll(
          async () => {
            const clips = flattenMasterVisuals(await getMaster(request, sceneId));
            const added = clips.filter((clip) => !beforeIds.has(String(clip.id || "")));
            addedId = String(added[0]?.id || "");
            if (addedId) addedIds.add(addedId);
            return added.length;
          },
          { timeout: 45_000 },
        )
        .toBeGreaterThan(0);
      expect(addedId, "B4 Image add did not persist Master.visualClips").toBeTruthy();
      const addedRow = flattenMasterVisuals(await getMaster(request, sceneId)).find(
        (clip) => String(clip.id) === addedId,
      );
      expect(addedRow?.kind, "B4 clip kind").toBe("image");
      guard.assertNone();

      const clip = page.getByTestId(`track-clip-image-${addedId}`).first();
      await expect(clip).toBeVisible({ timeout: 20_000 });
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      expect(
        flattenMasterVisuals(await getMaster(request, sceneId)).some((clip) => String(clip.id) === addedId),
      ).toBeTruthy();
      await expect(page.getByTestId(`track-clip-image-${addedId}`).first()).toBeVisible();

      await page.getByTestId(`track-clip-image-${addedId}`).first().click({ force: true });
      await page.getByTestId("timeline-toolbar-image-remove").click();
      await expect
        .poll(
          async () =>
            flattenMasterVisuals(await getMaster(request, sceneId)).some((clip) => String(clip.id) === addedId),
          { timeout: 20_000 },
        )
        .toBeFalsy();
      addedIds.delete(addedId);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      expect(
        flattenMasterVisuals(await getMaster(request, sceneId)).some((clip) => String(clip.id) === addedId),
      ).toBeFalsy();
      guard.assertNone();
    } finally {
      const master = await getMaster(request, sceneId);
      for (const batch of master.batchBlocks || []) {
        if (!batch.id) continue;
        const next = (batch.visualClips || []).filter((clip) => beforeIds.has(String(clip.id || "")));
        if (next.length !== (batch.visualClips || []).length) {
          const res = await request.patch(
            `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches/${batch.id}`,
            { data: { visualClips: next } },
          );
          expect(res.ok(), await res.text()).toBeTruthy();
        }
      }
    }
  });

  test("B5 — Prompt Intelligence metadata cannot overwrite a newer Master", async ({ page, request }) => {
    await cleanupScenesByPrefix(request, PREFIX);
    const sceneId = EXISTING_SCENE_ID;
    const guard = installDirectorWriteGuard(page);
    const { batchId } = await (async () => {
      const master = await getMaster(request, sceneId);
      const batch = (master.batchBlocks || [])[0];
      expect(batch?.id, "B5 master batch").toBeTruthy();
      return { batchId: String(batch!.id) };
    })();
    const beforePrompts = flattenMasterPrompts(await getMaster(request, sceneId));
    await openTimeline(page, sceneId);
    await openInspector(page);
    await expect(page.getByTestId("prompt-intelligence-panel")).toBeVisible({ timeout: 20_000 });

    const marker = `B5-MASTER-${Date.now()}`;
    try {
      const nextPrompts = beforePrompts.length
        ? beforePrompts.map((seg, index) => (index === 0 ? { ...seg, text: `${seg.text || ""}\n${marker}` } : seg))
        : [{ start: 0, length: 2, text: marker }];
      await patchBatchPrompts(request, sceneId, batchId, nextPrompts);
      const afterServerMaster = JSON.stringify(await getMaster(request, sceneId));
      const afterServerBlob = timelineMasterDump((await getSceneRow(request, sceneId)).director_json);
      expect(afterServerMaster).toContain(marker);

      await patchSceneMetadata(request, sceneId, {
        source: "excision-b5",
        appliedAt: new Date().toISOString(),
        staleBrowser: true,
      });
      await request.patch(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}`, {
        data: {
          prompt: `stale-browser-pi ${marker}`,
          director_json: JSON.stringify({ timelineMaster: { wiped: true }, promptIntelligence: { stale: true } }),
        },
      });

      const afterMetaMaster = JSON.stringify(await getMaster(request, sceneId));
      const afterMetaBlob = timelineMasterDump((await getSceneRow(request, sceneId)).director_json);
      expect(afterMetaMaster, "B5 GET /master must stay byte-for-byte after PI metadata + stale blob PATCH").toBe(
        afterServerMaster,
      );
      if (afterServerBlob !== "null") {
        expect(afterMetaBlob, "B5 timelineMaster blob must stay byte-for-byte").toBe(afterServerBlob);
        expect(afterMetaBlob).not.toContain("wiped");
      }
      expect(
        flattenMasterPrompts(await getMaster(request, sceneId)).some((seg) => String(seg.text || "").includes(marker)),
      ).toBeTruthy();
      guard.assertNone();
    } finally {
      if (beforePrompts.length) {
        await patchBatchPrompts(request, sceneId, batchId, beforePrompts);
      }
    }
  });
});
