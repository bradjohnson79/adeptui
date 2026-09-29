/**
 * Master-only Timeline / Inspector Playwright helpers.
 * Product PUT /director is a hard fail. Never seed via GET/PUT /director.
 */
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
export const UI = process.env.ADEPT_UI_ORIGIN || "http://127.0.0.1:5173";
export const PROJECT_ID =
  process.env.ADEPT_E2E_PROJECT_ID ||
  process.env.ADEPT_PROJECT_ID ||
  "dd136516-6df8-4b08-8edd-a8f5e1173470";
export const EXISTING_SCENE_ID =
  process.env.ADEPT_E2E_SCENE_ID || "b02b6cba-5a6d-4958-a868-85407fcee6a8";

export type MasterPrompt = {
  id?: string;
  start?: number;
  length?: number;
  text?: string;
  productionPrompt?: string | null;
};

export type MasterVisual = {
  id?: string;
  kind?: string;
  start?: number;
  length?: number;
  label?: string;
  assetId?: string | null;
};

export type SceneMaster = {
  batchBlocks?: Array<{
    id?: string;
    label?: string;
    generatorId?: string | null;
    duration?: { plannedDuration?: number };
    promptSegments?: MasterPrompt[];
    visualClips?: MasterVisual[];
  }>;
};

export function flattenMasterPrompts(master: SceneMaster): MasterPrompt[] {
  return (master.batchBlocks || []).flatMap((batch) => batch.promptSegments || []);
}

export function flattenMasterVisuals(master: SceneMaster): MasterVisual[] {
  return (master.batchBlocks || []).flatMap((batch) => batch.visualClips || []);
}

export async function getSceneRow(
  request: APIRequestContext,
  sceneId: string,
): Promise<{ director_json?: string; prompt?: string }> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

export function timelineMasterDump(directorJson: string | undefined): string {
  try {
    const blob = JSON.parse(directorJson || "{}") as { timelineMaster?: unknown };
    return JSON.stringify(blob.timelineMaster ?? null);
  } catch {
    return "null";
  }
}

export async function patchSceneMetadata(
  request: APIRequestContext,
  sceneId: string,
  promptIntelligence: Record<string, unknown>,
) {
  const res = await request.patch(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/metadata`,
    { data: { promptIntelligence } },
  );
  expect(res.ok(), await res.text()).toBeTruthy();
}

export async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          return (await request.get(`${API}/api/healthz`, { timeout: 10_000 })).ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

export async function getMaster(request: APIRequestContext, sceneId: string): Promise<SceneMaster> {
  const res = await request.get(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.master || body) as SceneMaster;
}

export async function listScenes(request: APIRequestContext): Promise<Array<{ id: string; name?: string }>> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  return Array.isArray(scenes) ? scenes : [];
}

export async function createNamedScene(
  request: APIRequestContext,
  name: string,
  opts?: { durationSec?: number; prompt?: string; engine?: string },
) {
  const res = await request.post(`${API}/api/projects/${PROJECT_ID}/scenes`, {
    data: {
      name,
      engine: opts?.engine || "minimax-h3",
      duration_sec: opts?.durationSec ?? 15,
      prompt: opts?.prompt || "",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<{ id: string; name?: string }>;
}

export async function deleteScene(request: APIRequestContext, sceneId: string) {
  await request.delete(`${API}/api/projects/${PROJECT_ID}/scenes/${sceneId}`);
}

export async function cleanupScenesByPrefix(request: APIRequestContext, prefix: string) {
  for (const scene of await listScenes(request)) {
    if (String(scene.name || "").startsWith(prefix)) {
      await deleteScene(request, scene.id);
    }
  }
}

async function postRematerialize(
  request: APIRequestContext,
  sceneId: string,
  durationSeconds: number,
  extra?: Record<string, unknown>,
) {
  return request.post(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/execution-windows/rematerialize`,
    { data: { durationSeconds, generatorId: "minimax-h3", ...extra } },
  );
}

export async function rematerialize(
  request: APIRequestContext,
  sceneId: string,
  durationSeconds: number,
) {
  let res = await postRematerialize(request, sceneId, durationSeconds);
  let body = await res.json();
  if (body?.ok === false && (body.error === "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE" || body.requiresNewSceneTake)) {
    const minted = await request.post(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/scene-takes`,
      { data: { intent: "execution_revision", reason: "generator_switch_window_topology_change" } },
    );
    expect(minted.ok(), await minted.text()).toBeTruthy();
    const take = await minted.json();
    const allowSceneTakeId = String(
      take.currentSceneTakeId || take.takeId || take.take?.id || take.id || take.master?.currentSceneTakeId || "",
    );
    expect(allowSceneTakeId, "minted SceneTake").toBeTruthy();
    res = await postRematerialize(request, sceneId, durationSeconds, {
      allowSceneTakeId,
      previousSceneTakeId: body.currentSceneTakeId || body.previousSceneTakeId || undefined,
    });
    body = await res.json();
  }
  expect(res.ok(), JSON.stringify(body)).toBeTruthy();
  expect(body?.ok, JSON.stringify(body)).toBeTruthy();
  return getMaster(request, sceneId);
}

export async function ensureBatch(request: APIRequestContext, sceneId: string, durationSeconds = 15) {
  let master = await getMaster(request, sceneId);
  let batch = (master.batchBlocks || [])[0];
  if (!batch?.id) {
    master = await rematerialize(request, sceneId, durationSeconds);
    batch = (master.batchBlocks || [])[0];
  }
  expect(batch?.id, "master batch").toBeTruthy();
  return { master, batchId: String(batch!.id) };
}

export async function patchBatchPrompts(
  request: APIRequestContext,
  sceneId: string,
  batchId: string,
  promptSegments: MasterPrompt[],
) {
  const res = await request.patch(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches/${batchId}`,
    { data: { promptSegments } },
  );
  expect(res.ok(), await res.text()).toBeTruthy();
}

export function installDirectorWriteGuard(page: Page) {
  const hits: string[] = [];
  page.on("request", (req) => {
    const url = req.url();
    if (/\/scenes\/[^/]+\/director(?:\/|\?|$)/.test(url) && !/director-timeline|director-sequences/.test(url)) {
      hits.push(`${req.method()} ${url}`);
    }
  });
  return {
    assertNone: () => {
      expect(hits, `product /scenes/{id}/director traffic must be 0, saw: ${hits.join(" | ")}`).toEqual([]);
    },
    count: () => hits.length,
  };
}

export async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${UI}/project/${PROJECT_ID}?workspace=timeline&sceneId=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

export async function openInspector(page: Page) {
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

export function parseSse(body: string): Record<string, unknown>[] {
  const events: Record<string, unknown>[] = [];
  for (const line of body.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      events.push(JSON.parse(payload) as Record<string, unknown>);
    } catch {
      /* ignore */
    }
  }
  return events;
}
