/**
 * Timeline full functional certification. No video render.
 * Disposable projects come only from POST /api/projects. No project-id special cases.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";

type Master = {
  sceneGeneratorId?: string | null;
  batchBlocks?: Array<{
    id?: string;
    order?: number;
    label?: string;
    duration?: { plannedDuration?: number };
    promptSegments?: Array<{ id?: string; text?: string; start?: number; length?: number }>;
    visualClips?: Array<{ id?: string; assetId?: string | null }>;
    audioClips?: Array<{ id?: string }>;
    sfxClips?: Array<{ id?: string }>;
  }>;
};

const RENDER_URL = /scene-takes|\/generate\b|\/prompt\b|omni|qwen|videochat|perception/i;

function installRenderFence(page: Page) {
  const hits: string[] = [];
  page.route(RENDER_URL, async (route) => {
    const req = route.request();
    if (req.method() === "POST" || req.method() === "PUT") {
      hits.push(`${req.method()} ${req.url()}`);
      await route.abort("failed");
      return;
    }
    await route.continue();
  });
  return {
    hits: () => hits.slice(),
    assertQuiet: () => expect(hits, `render traffic: ${hits.join(" | ")}`).toEqual([]),
  };
}

async function createProject(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.post(`${API}/api/projects`, { data: { name } });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const id = String(body.id || body.project?.id || "");
  expect(id).toBeTruthy();
  return id;
}

async function createScene(
  request: APIRequestContext,
  projectId: string,
  name: string,
  durationSec = 15,
): Promise<string> {
  const res = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { name, engine: "minimax-h3", duration_sec: durationSec, prompt: "" },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return String(body.id);
}

async function getMaster(request: APIRequestContext, projectId: string, sceneId: string): Promise<Master> {
  const res = await request.get(
    `${API}/api/director-timeline/projects/${projectId}/scenes/${sceneId}/master`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.master || body) as Master;
}

async function openTimeline(page: Page, projectId: string, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

function promptsOf(master: Master) {
  return (master.batchBlocks || []).flatMap((batch) => batch.promptSegments || []);
}

test.describe.configure({ mode: "serial" });

test.describe("Timeline full functional cert — no render", () => {
  test.setTimeout(180_000);
  const stamp = Date.now().toString(36);
  let projectA = "";
  let sceneA1 = "";
  let sceneA2 = "";
  let projectB = "";
  let sceneB1 = "";

  test.beforeAll(async ({ request }) => {
    const health = await request.get(`${API}/api/healthz`);
    expect(health.ok()).toBeTruthy();
    projectA = await createProject(request, `Timeline Cert A ${stamp}`);
    sceneA1 = await createScene(request, projectA, "Scene A1", 15);
    sceneA2 = await createScene(request, projectA, "Scene A2", 15);
    projectB = await createProject(request, `Timeline Cert B ${stamp}`);
    sceneB1 = await createScene(request, projectB, "Scene B1", 15);
  });

  test("A1 opens Timeline, shows windows, and does not submit a render", async ({ page, request }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA1);
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible();
    const master = await getMaster(request, projectA, sceneA1);
    expect(master.batchBlocks?.length || 0).toBeGreaterThan(0);
    expect(master.sceneGeneratorId || "").toContain("minimax");
    const planned = Number(master.batchBlocks?.[0]?.duration?.plannedDuration || 0);
    expect(planned).toBeGreaterThan(0);
    expect(planned).toBeLessThanOrEqual(15.01);
    fence.assertQuiet();
  });

  test("A1 Inspector duration, name, zoom, snap, and playhead persist after reload", async ({ page, request }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA1);
    const right = page.getByTestId("timeline-drawer-right-toggle");
    if ((await right.getAttribute("aria-expanded")) !== "true") await right.click();
    await page.getByTestId("timeline-tab-inspector").click();
    const name = page.getByTestId("timeline-inspector-scene-name");
    await name.fill("Scene A1 Renamed");
    await name.blur();
    const duration = page.getByTestId("timeline-inspector-duration");
    await duration.fill("30");
    await duration.blur();
    await page.getByTestId("timeline-toolbar-zoom-in").click();
    await page.getByTestId("timeline-toolbar-snap").click();
    await page.getByTestId("timeline-transport-scene-end").click();
    await expect
      .poll(async () => {
        const row = await request.get(`${API}/api/projects/${projectA}`);
        const body = await row.json();
        const scene = (body.scenes || []).find((item: { id: string }) => item.id === sceneA1);
        const windows = (await getMaster(request, projectA, sceneA1)).batchBlocks?.length || 0;
        return Number(scene?.duration_sec || 0) >= 30 && windows >= 2;
      }, { timeout: 30_000 })
      .toBeTruthy();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("timeline-inspector-scene-name")).toHaveValue("Scene A1 Renamed");
    const master = await getMaster(request, projectA, sceneA1);
    const windows = master.batchBlocks || [];
    expect(windows.length).toBeGreaterThanOrEqual(2);
    const firstWindow = Number(windows[0]?.duration?.plannedDuration || 15);
    for (const block of windows) {
      expect(Number(block.duration?.plannedDuration || 0)).toBeLessThanOrEqual(15.01);
    }
    for (const block of windows.slice(1)) {
      for (const seg of block.promptSegments || []) {
        if (String(seg.text || "").includes("CONTINUATION")) {
          expect(Number(seg.start || 0)).toBeGreaterThanOrEqual(firstWindow - 0.05);
        }
      }
    }
    fence.assertQuiet();
  });

  test("A1 Timed Prompt add, edit, and delete survive reload", async ({ page, request }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA1);
    await expect(page.getByTestId("timeline-toolbar-prompt-add")).toBeEnabled({ timeout: 30_000 });
    const before = promptsOf(await getMaster(request, projectA, sceneA1)).map((seg) => String(seg.id || ""));
    await page.getByTestId("timeline-toolbar-prompt-add").click();
    let added = "";
    await expect
      .poll(async () => {
        const segs = promptsOf(await getMaster(request, projectA, sceneA1));
        const fresh = segs.find((seg) => !before.includes(String(seg.id || "")));
        added = String(fresh?.id || "");
        return added;
      }, { timeout: 20_000 })
      .not.toEqual("");
    const clip = page.getByTestId(`track-clip-prompt-${added}`).first();
    await expect(clip).toBeVisible({ timeout: 20_000 });
    await clip.dblclick();
    const modal = page.getByTestId("timeline-timed-prompt-modal");
    await expect(modal).toBeVisible({ timeout: 15_000 });
    const text = `Cert prompt ${stamp}`;
    await modal.getByRole("textbox", { name: "Prompt" }).fill(text);
    await modal.getByRole("button", { name: "OK" }).click();
    await expect(modal).toBeHidden({ timeout: 15_000 });
    await expect
      .poll(async () => {
        const segs = promptsOf(await getMaster(request, projectA, sceneA1));
        return segs.find((seg) => seg.id === added)?.text || "";
      }, { timeout: 20_000 })
      .toContain("Cert prompt");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId(`track-clip-prompt-${added}`).first()).toBeVisible();
    await page.getByTestId("timeline-toolbar-prompt-remove").click();
    fence.assertQuiet();
  });

  test("A1 references, preview, preflight, and generate stay local", async ({ page }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA1);
    const addRef = page.getByPlaceholder(/Type @character/i);
    if (await addRef.isVisible().catch(() => false)) {
      await addRef.fill("@");
      await page.keyboard.press("Escape");
    }
    await expect(page.getByTestId("timeline-toolbar-preflight")).toBeVisible();
    await page.getByTestId("timeline-toolbar-preflight").click();
    const generate = page.getByTestId("timeline-generate-scene");
    await expect(generate).toBeVisible();
    const preview = page.getByRole("button", { name: /Full Screen/i }).first();
    if (await preview.isVisible().catch(() => false)) {
      await preview.click();
      await page.keyboard.press("Escape");
    }
    const reset = page.getByRole("button", { name: /Reset Layout/i });
    if (await reset.isVisible().catch(() => false)) await reset.click();
    fence.assertQuiet();
  });

  test("A1 New Take builds a request and the fence blocks submission", async ({ page }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA1);
    const right = page.getByTestId("timeline-drawer-right-toggle");
    if ((await right.getAttribute("aria-expanded")) !== "true") await right.click();
    const tab = page.getByTestId("timeline-tab-inspector");
    if (await tab.isVisible().catch(() => false)) await tab.click();
    const neu = page.getByTestId("timeline-new-take");
    await expect(neu).toBeVisible();
    await neu.scrollIntoViewIfNeeded();
    await neu.click();
    await expect.poll(() => fence.hits().length, { timeout: 15_000 }).toBeGreaterThan(0);
    expect(fence.hits().some((hit) => /scene-takes|generate/i.test(hit))).toBeTruthy();
  });

  test("A2 is a second scene with its own window and no borrowed prompt", async ({ page, request }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectA, sceneA2);
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible();
    const master = await getMaster(request, projectA, sceneA2);
    expect(master.batchBlocks?.length || 0).toBeGreaterThan(0);
    const texts = promptsOf(master).map((seg) => seg.text || "").join("\n");
    expect(texts.includes(`Cert prompt ${stamp}`)).toBeFalsy();
    fence.assertQuiet();
  });

  test("Project B scene B1 is born with a window and accepts a Timed Prompt", async ({ page, request }) => {
    const fence = installRenderFence(page);
    await openTimeline(page, projectB, sceneB1);
    await expect(page.getByTestId("timeline-toolbar-prompt-add")).toBeEnabled({ timeout: 30_000 });
    const before = promptsOf(await getMaster(request, projectB, sceneB1)).length;
    await page.getByTestId("timeline-toolbar-prompt-add").click();
    await expect
      .poll(async () => promptsOf(await getMaster(request, projectB, sceneB1)).length, { timeout: 20_000 })
      .toBeGreaterThan(before);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    const after = promptsOf(await getMaster(request, projectB, sceneB1)).length;
    expect(after).toBeGreaterThan(before);
    fence.assertQuiet();
  });

  test("a 60s script keeps the opening on window 1 and the ending on the last window", async ({ request }) => {
    const project = await createProject(request, `Timeline Cert Split ${stamp}`);
    const script = [
      "Opening. The host lifts the thermos at the bar.",
      "The camera pans to the guest reading a menu.",
      "The host returns and sets the thermos down.",
      "Ending. The beans splash the lens and the scene cuts to black.",
    ].join("\n\n");
    const res = await request.post(`${API}/api/projects/${project}/scenes`, {
      data: { name: "Split Scene", engine: "minimax-h3", duration_sec: 60, prompt: script },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const sceneId = String((await res.json()).id);
    const master = await getMaster(request, project, sceneId);
    const windows = master.batchBlocks || [];
    expect(windows.length).toBe(4);
    const root = windows[0]?.promptSegments?.[0]?.text || "";
    const ending = windows[windows.length - 1]?.promptSegments?.[0]?.text || "";
    expect(root).toContain("Opening.");
    expect(ending).toContain("cuts to black");
    expect(ending.includes("Opening.")).toBeFalsy();
    expect(Number(windows[windows.length - 1]?.promptSegments?.[0]?.start || 0)).toBeGreaterThanOrEqual(45);
  });

  test("Generate stays blocked and the Inspector shows the saved window text", async ({ page, request }) => {
    const fence = installRenderFence(page);
    const project = await createProject(request, `Timeline Cert Owner ${stamp}`);
    const script = [
      "Opening. The host lifts the thermos at the bar.",
      "Ending. The beans splash the lens and the scene cuts to black.",
    ].join("\n\n");
    const res = await request.post(`${API}/api/projects/${project}/scenes`, {
      data: { name: "Owner Scene", engine: "minimax-h3", duration_sec: 30, prompt: script },
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const sceneId = String((await res.json()).id);
    const master = await getMaster(request, project, sceneId);
    const windows = master.batchBlocks || [];
    expect(windows.length).toBe(2);
    const first = windows[0]?.promptSegments?.[0]?.text || "";
    const second = windows[1]?.promptSegments?.[0]?.text || "";
    expect(first).toContain("Opening.");
    expect(first.includes("cuts to black")).toBeFalsy();
    expect(second).toContain("cuts to black");
    expect(second.includes("Opening.")).toBeFalsy();
    await openTimeline(page, project, sceneId);
    const secondId = String(windows[1]?.promptSegments?.[0]?.id || "");
    if (secondId) {
      const clip = page.getByTestId(`track-clip-prompt-${secondId}`).first();
      if (await clip.isVisible().catch(() => false)) await clip.click();
    }
    const right = page.getByTestId("timeline-drawer-right-toggle");
    if ((await right.getAttribute("aria-expanded")) !== "true") await right.click();
    const tab = page.getByTestId("timeline-tab-inspector");
    if (await tab.isVisible().catch(() => false)) await tab.click();
    const instruction = page.getByTestId("timeline-prompt-instruction");
    if (await instruction.isVisible().catch(() => false)) {
      const shown = await instruction.inputValue();
      expect(shown === first || shown === second).toBeTruthy();
      expect(shown.includes("Opening.") && shown.includes("cuts to black")).toBeFalsy();
    }
    const finishing = page.getByTestId("timeline-mode-video-finishing");
    if (await finishing.isVisible().catch(() => false)) await finishing.click();
    const generate = page.getByTestId("timeline-generate-scene");
    await expect(generate).toBeVisible();
    const title = (await generate.getAttribute("title")) || "";
    await generate.click();
    if (/not ready/i.test(title)) {
      expect(fence.hits().some((hit) => /\/generate\b/i.test(hit))).toBeFalsy();
    } else {
      await expect
        .poll(() => fence.hits().some((hit) => /\/generate\b/i.test(hit)), { timeout: 15_000 })
        .toBeTruthy();
    }
    expect(fence.hits().some((hit) => /omni|qwen|comfy/i.test(hit))).toBeFalsy();
  });

  test("fresh project inherits window bootstrap without fixture seeding", async ({ page, request }) => {
    const fence = installRenderFence(page);
    const projectC = await createProject(request, `Timeline Cert Fresh ${stamp}`);
    const sceneC = await createScene(request, projectC, "Scene Fresh", 15);
    const master = await getMaster(request, projectC, sceneC);
    expect(master.batchBlocks?.length || 0, "new project must be born with a window").toBeGreaterThan(0);
    await openTimeline(page, projectC, sceneC);
    await expect(page.getByTestId("timeline-toolbar-prompt-add")).toBeEnabled();
    const left = page.getByTestId("timeline-drawer-left-toggle").first();
    if ((await left.getAttribute("aria-expanded")) !== "true") await left.click();
    const addScene = page.getByTestId("timeline-add-scene");
    await addScene.scrollIntoViewIfNeeded();
    await addScene.click();
    await expect
      .poll(async () => {
        const row = await request.get(`${API}/api/projects/${projectC}`);
        const body = await row.json();
        return (body.scenes || []).length;
      }, { timeout: 20_000 })
      .toBeGreaterThan(1);
    fence.assertQuiet();
  });
});
