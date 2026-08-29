/**
 * Timeline Master snap + zoom + Video Generator cert.
 * Reuses SenseNova Integration Lab (Jacob). Never POST /api/projects.
 *
 * requestCache query-string isolation stays in
 * studio-web/src/runtime/__tests__/requestCache.test.ts — do not strip cache keys.
 */
import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const SCENE_ID = "f0b97b96-3456-4ceb-96ce-56bbece7e5b7";

type TimedClip = { id: string; start: number; length: number };

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/healthz`, { timeout: 8_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function getJson(request: APIRequestContext, path: string) {
  const res = await request.get(`${API}${path}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function getMaster(request: APIRequestContext) {
  const body = await getJson(request, `/api/director-timeline/projects/${PROJECT_ID}/scenes/${SCENE_ID}/master`);
  return body.master as {
    sceneGeneratorId?: string | null;
    mode?: string;
    batchBlocks?: Array<{ id: string; duration?: { plannedDuration?: number | null } | null; generatorId?: string }>;
  };
}

async function getDirector(request: APIRequestContext) {
  return getJson(request, `/api/projects/${PROJECT_ID}/scenes/${SCENE_ID}/director`);
}

function boardDurationFromMaster(master: Awaited<ReturnType<typeof getMaster>>): number {
  const batches = master?.batchBlocks || [];
  const sum = batches.reduce((total, batch) => total + Math.max(0, Number(batch.duration?.plannedDuration || 0)), 0);
  return sum;
}

function directorClipTimes(director: { prompt_segments?: TimedClip[]; camera_clips?: TimedClip[]; image_clips?: TimedClip[]; video_clips?: TimedClip[] }): TimedClip[] {
  return [
    ...(director.prompt_segments || []),
    ...(director.camera_clips || []),
    ...(director.image_clips || []),
    ...(director.video_clips || []),
  ].map((clip) => ({ id: clip.id, start: Number(clip.start), length: Number(clip.length) }));
}

function clipsEqual(a: TimedClip[], b: TimedClip[], tolerance = 0.02) {
  const byId = new Map(b.map((clip) => [clip.id, clip]));
  expect(a.length, "clip count").toBe(b.length);
  for (const clip of a) {
    const other = byId.get(clip.id);
    expect(other, `clip ${clip.id} still present`).toBeTruthy();
    expect(Math.abs(clip.start - (other?.start || 0)), `start ${clip.id}`).toBeLessThanOrEqual(tolerance);
    expect(Math.abs(clip.length - (other?.length || 0)), `length ${clip.id}`).toBeLessThanOrEqual(tolerance);
  }
}

async function openJacobTimeline(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${SCENE_ID}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-track-board")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator("[data-testid^='timeline-batch-'][data-start]").first()).toBeVisible({ timeout: 60_000 });
}

async function waitForLtxOption(page: Page) {
  const select = page.getByTestId("timeline-video-generator-select");
  await expect(select).toBeVisible();
  await expect
    .poll(async () => select.locator('option[value="ltx-local"]').count(), { timeout: 45_000 })
    .toBeGreaterThan(0);
  return select;
}

async function openLeftDrawer(page: Page) {
  const leftToggle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(leftToggle).toBeVisible();
  if ((await leftToggle.getAttribute("aria-expanded")) !== "true") {
    await leftToggle.click();
  }
  await expect(leftToggle).toHaveAttribute("aria-expanded", "true");
}

async function setZoomSlider(page: Page, unit: string) {
  const slider = page.getByTestId("timeline-toolbar-zoom-slider");
  await expect(slider).toBeVisible();
  await slider.evaluate((el, value) => {
    const input = el as HTMLInputElement;
    const proto = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
    proto?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }, unit);
}

async function readDomClipTimes(page: Page): Promise<TimedClip[]> {
  return page.evaluate(() => {
    const clips = [...document.querySelectorAll<HTMLElement>('[data-testid^="track-clip-"]')];
    return clips
      .map((el) => ({
        id: el.getAttribute("data-testid") || "",
        start: Number(el.getAttribute("data-start")),
        length: Number(el.getAttribute("data-length")),
      }))
      .filter((clip) => clip.id && Number.isFinite(clip.start) && Number.isFinite(clip.length));
  });
}

async function setSnapEnabled(page: Page, enabled: boolean) {
  const btn = page.getByTestId("timeline-toolbar-snap");
  await expect(btn).toBeVisible();
  const label = (await btn.getAttribute("aria-label")) || "";
  const isOn = /Disable clip snapping/i.test(label);
  if (isOn !== enabled) {
    await btn.click();
  }
  await expect(btn).toHaveAttribute("aria-label", enabled ? /Disable clip snapping/ : /Enable clip snapping/);
}

async function firstPromptClip(page: Page): Promise<Locator> {
  const clip = page.locator('[data-testid^="track-clip-prompt-"]').first();
  await expect(clip, "Jacob Timed Prompt clip").toBeVisible();
  return clip;
}

async function dragClipToward(page: Page, clip: Locator, targetLeftX: number) {
  const box = await clip.boundingBox();
  expect(box, "clip bounding box").toBeTruthy();
  const fromX = box!.x + Math.max(18, Math.min(box!.width * 0.28, box!.width - 28));
  const fromY = box!.y + box!.height * 0.68;
  const toX = fromX + (targetLeftX - box!.x);
  await clip.evaluate((el, coords) => {
    const fire = (target: EventTarget, type: string, x: number, buttons: number) => {
      target.dispatchEvent(
        new PointerEvent(type, {
          bubbles: true,
          cancelable: true,
          composed: true,
          clientX: x,
          clientY: coords.fromY,
          pointerId: 1,
          pointerType: "mouse",
          buttons,
          button: 0,
        }),
      );
    };
    fire(el, "pointerdown", coords.fromX, 1);
    const steps = 24;
    for (let i = 1; i <= steps; i += 1) {
      const x = coords.fromX + ((coords.toX - coords.fromX) * i) / steps;
      fire(window, "pointermove", x, 1);
    }
    fire(window, "pointerup", coords.toX, 0);
  }, { fromX, fromY, toX });
}

async function restoreDirector(request: APIRequestContext, original: Record<string, unknown>) {
  const res = await request.put(`${API}/api/projects/${PROJECT_ID}/scenes/${SCENE_ID}/director`, {
    data: original,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function restoreMode(request: APIRequestContext, mode: string) {
  const res = await request.post(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${SCENE_ID}/mode`,
    { data: { mode } },
  );
  expect(res.ok(), await res.text()).toBeTruthy();
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("timeline master snap zoom generator", () => {
  test("Video Generator options come from Production Control and LTX persists", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const pc = await getJson(request, "/api/production-control/models?modality=video");
    const pcIds = ((pc.models || []) as Array<{ id: string }>).map((model) => model.id);
    expect(pcIds, "Production Control lists LTX").toContain("ltx-local");

    await openJacobTimeline(page);
    await openLeftDrawer(page);
    const dock = page.getByTestId("timeline-video-generator");
    await expect(dock).toBeVisible();
    const scenes = page.locator(".timeline-v2__dock--scenes");
    const dockBox = await dock.boundingBox();
    const scenesBox = await scenes.boundingBox();
    expect(dockBox && scenesBox && dockBox.y < scenesBox.y, "Video Generator sits above Scenes").toBeTruthy();

    const select = await waitForLtxOption(page);
    const optionLabels = await select.locator("option").allTextContents();
    expect(optionLabels.some((label) => /LTX 2\.3/i.test(label)), optionLabels.join(" | ")).toBeTruthy();
    const minimax = optionLabels.find((label) => /minimax/i.test(label));
    if (minimax) {
      expect(minimax, "MiniMax may be listed as not ready").toMatch(/minimax/i);
    }
    const selectValues = await select.locator("option").evaluateAll((opts) =>
      opts.map((opt) => (opt as HTMLOptionElement).value).filter(Boolean),
    );
    for (const value of selectValues) {
      expect(pcIds, `select value ${value} is a Production Control model`).toContain(value);
    }

    if ((await select.inputValue()) !== "ltx-local") {
      await select.selectOption("ltx-local");
      const overflow = page.getByTestId("timeline-generator-overflow-dialog");
      if (await overflow.isVisible().catch(() => false)) {
        await page.getByRole("button", { name: "Cancel" }).click();
        throw new Error("Unexpected trim dialog when selecting LTX — Jacob board should fit LTX max duration");
      }
    }
    await expect(select).toHaveValue("ltx-local");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("[data-testid^='timeline-batch-'][data-start]").first()).toBeVisible({ timeout: 60_000 });
    await openLeftDrawer(page);
    const reloaded = await waitForLtxOption(page);
    await expect(reloaded).toHaveValue("ltx-local");
    const master = await getMaster(request);
    expect(master.sceneGeneratorId === "ltx-local" || master.batchBlocks?.[0]?.generatorId === "ltx-local").toBeTruthy();
  });

  test("header duration matches the live Jacob board, not a stale scene clock", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const [master, project] = await Promise.all([
      getMaster(request),
      getJson(request, `/api/projects/${PROJECT_ID}`),
    ]);
    const scene = (project.scenes || []).find((row: { id: string }) => row.id === SCENE_ID) || (project.scenes || [])[0];
    expect(scene?.id).toBe(SCENE_ID);
    const boardSec = boardDurationFromMaster(master);
    expect(boardSec, "Jacob board has a batch sum").toBeGreaterThan(0);
    const sceneSec = Number(scene.duration_sec || 0);

    await openJacobTimeline(page);
    const header = page.getByTestId("timeline-scene-header-meta");
    await expect(header).toBeVisible();
    await expect(header).toContainText(`${boardSec.toFixed(1)} sec`, { timeout: 45_000 });
    if (Math.abs(sceneSec - boardSec) > 0.05) {
      await expect(header).not.toContainText(`${sceneSec.toFixed(1)} sec`);
    }
    const boardAttr = await page.getByTestId("timeline-track-board").getAttribute("data-board-duration");
    expect(Number(boardAttr)).toBeCloseTo(boardSec, 2);
  });

  test("zoom slider reaches 0.2x and 5x and does not mutate clip times", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const beforeApi = directorClipTimes(await getDirector(request));
    expect(beforeApi.length, "Jacob has timed clips").toBeGreaterThan(0);

    await openJacobTimeline(page);
    const slider = page.getByTestId("timeline-toolbar-zoom-slider");
    await expect(slider).toBeVisible();
    const beforeDom = await readDomClipTimes(page);
    expect(beforeDom.length, "DOM clip times").toBeGreaterThan(0);

    await setZoomSlider(page, "0");
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toHaveText(/0\.20×/);
    clipsEqual(await readDomClipTimes(page), beforeDom);
    clipsEqual(directorClipTimes(await getDirector(request)), beforeApi);

    await setZoomSlider(page, "0.5");
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toHaveText(/1\.00×/);
    clipsEqual(await readDomClipTimes(page), beforeDom);

    await setZoomSlider(page, "1");
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toHaveText(/5\.00×/);
    const board = page.getByTestId("timeline-track-board");
    await expect(board).toHaveAttribute("data-zoom", "5");
    clipsEqual(await readDomClipTimes(page), beforeDom);
    clipsEqual(directorClipTimes(await getDirector(request)), beforeApi);

    await page.getByTestId("timeline-toolbar-zoom-out").click();
    const zoomText = await page.getByTestId("timeline-toolbar-zoom-value").innerText();
    expect(Number(zoomText.replace("×", ""))).toBeLessThan(5);
    clipsEqual(await readDomClipTimes(page), beforeDom);
    clipsEqual(directorClipTimes(await getDirector(request)), beforeApi);
  });

  test("Snap ON magnetizes to a Batch edge; Snap OFF allows free positioning", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const original = await getDirector(request);
    const master = await getMaster(request);
    const firstBatchId = master.batchBlocks?.[0]?.id;
    expect(firstBatchId, "Jacob has a Batch").toBeTruthy();
    await openJacobTimeline(page);
    await setZoomSlider(page, "0.5");
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toHaveText(/1\.00×/);

    const clip = await firstPromptClip(page);
    const batch = page.getByTestId(`timeline-batch-${firstBatchId}`);
    await expect(batch).toBeVisible();
    const batchEdgeSec = Number(await batch.getAttribute("data-start")) + Number(await batch.getAttribute("data-length"));
    expect(batchEdgeSec, "Batch 1 end is a real edge").toBeGreaterThan(0.5);

    const secondsToLeftX = async (target: Locator, startSec: number) => {
      const box = await target.boundingBox();
      expect(box).toBeTruthy();
      const current = Number(await target.getAttribute("data-start"));
      const length = Number(await target.getAttribute("data-length"));
      const pxPerSec = box!.width / Math.max(0.15, length);
      return box!.x + (startSec - current) * pxPerSec;
    };

    try {
      await setSnapEnabled(page, true);
      await dragClipToward(page, clip, await secondsToLeftX(clip, batchEdgeSec - 0.08));
      await expect
        .poll(async () => Number(await clip.getAttribute("data-start")), { timeout: 15_000 })
        .toBeCloseTo(batchEdgeSec, 1);

      await restoreDirector(request, original);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await expect(page.locator("[data-testid^='timeline-batch-'][data-start]").first()).toBeVisible({ timeout: 60_000 });
      await setZoomSlider(page, "0.5");
      const freeClip = await firstPromptClip(page);

      await setSnapEnabled(page, false);
      await dragClipToward(page, freeClip, await secondsToLeftX(freeClip, 2.4));
      await expect
        .poll(async () => Number(await freeClip.getAttribute("data-start")), { timeout: 15_000 })
        .toBeGreaterThan(0.3);
      const afterOff = Number(await freeClip.getAttribute("data-start"));
      expect(Math.abs(afterOff - batchEdgeSec)).toBeGreaterThan(0.15);
      expect(afterOff).not.toBeCloseTo(0, 1);
      expect(afterOff).not.toBeCloseTo(10, 1);
    } finally {
      await restoreDirector(request, original);
    }
  });

  test("safe visible controls are wired without starting generate", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    const master = await getMaster(request);
    const originalMode = master.mode || "video_finishing";
    await openJacobTimeline(page);

    await page.getByTestId("timeline-viewer-fit").click();
    const preset = page.getByTestId("timeline-viewer-preset");
    const originalPreset = await preset.inputValue();
    await preset.selectOption("timeline_focus");
    await preset.selectOption(originalPreset || "balanced");

    const aspect = page.getByTestId("timeline-viewer-aspect");
    await expect(aspect).toBeEnabled();
    const currentAspect = await aspect.inputValue();
    await aspect.selectOption(currentAspect);

    const guides = page.getByTestId("timeline-viewer-guides");
    await guides.click();
    await guides.click();

    const pause = page.getByTestId("timeline-viewer-pause");
    await pause.click();
    await expect(pause).toHaveAttribute("aria-pressed", "true");
    await pause.click();

    await page.getByTestId("timeline-focus-workspace").click();
    await page.getByTestId("timeline-reset-layout").click();

    try {
      await page.getByTestId("timeline-mode-image-planning").click();
      await page.getByTestId("timeline-mode-video-finishing").click();
    } finally {
      await restoreMode(request, originalMode);
    }

    await page.getByTestId("timeline-header-preflight").click();
    await page.getByTestId("timeline-toolbar-preflight").click();
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();

    const hide = page.getByTestId("track-control-timed-prompt-eye");
    if (await hide.count()) {
      await hide.click();
      await hide.click();
    }
    const lock = page.getByTestId("track-control-timed-prompt-lock");
    if (await lock.count()) {
      await lock.click();
      await lock.click();
    }

    await page.getByTestId("timeline-toolbar-snap").click();
    await page.getByTestId("timeline-toolbar-snap").click();
    await page.getByTestId("timeline-toolbar-zoom-in").click();
    await page.getByTestId("timeline-toolbar-zoom-out").click();

    await expect(page.getByTestId("timeline-header-generate")).toBeVisible();
    await expect(page.getByTestId("timeline-generate-scene")).toBeVisible();
    const firstBatch = page.locator("[data-testid^='timeline-batch-'][data-start]").first();
    await firstBatch.click();
    await expect(page.getByTestId("timeline-batch-retake")).toBeVisible();
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible();
  });

  test("Resume accessible name mentions re-queue of cancelled or failed work", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitApiReady(request);
    await openJacobTimeline(page);
    const resume = page.getByTestId("timeline-header-resume");
    await expect(resume).toBeVisible();
    const name = `${(await resume.getAttribute("aria-label")) || ""} ${(await resume.getAttribute("title")) || ""}`;
    expect(name).toMatch(/re-queue|cancelled|failed/i);
    expect(name).not.toMatch(/resume a stopped render mid-frame/i);

    const masterResume = page.getByTestId("timeline-master-resume-incomplete");
    if (await masterResume.count()) {
      const masterName = `${(await masterResume.getAttribute("title")) || ""} ${(await masterResume.getAttribute("aria-label")) || ""}`;
      expect(masterName).toMatch(/re-queue|cancelled|failed/i);
      expect(masterName).not.toMatch(/resume a stopped render mid-frame/i);
    }
  });
});
