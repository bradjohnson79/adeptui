import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const FRESH_PROMPT = `I would like you to build a scene in Timeline where we will use the Earth Horizon Environment Reference Sheet as the scene. We will also use the Venture Spaceship Prop Reference Sheet, and also the Cade's Starfighter prop reference sheet.

The scene is that we will see the Venture Spaceship in orbit above the Earth's horizon. Cade's Starfighter remains above the Venture. Do not reuse Establishing Shot.

This scene will be created in Timeline using MiniMax H3, Megapixels 2.0 quality, 21:9 frame ratio. And will have a single batch runtime of 10 seconds.`;

test.use({ extraHTTPHeaders: {} });

async function streamPrepare(request: APIRequestContext) {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: FRESH_PROMPT }],
      project_id: PROJECT_ID,
      mode: "chat",
      workspace_tab: "timeline",
    },
    timeout: 180_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const events: Record<string, any>[] = [];
  for (const line of (await res.body()).toString("utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      events.push(JSON.parse(payload));
    } catch {
      /* ignore */
    }
  }
  const exec = events.find(
    (evt) => evt.type === "execution_status" && evt.execution?.plan_data?.sceneProduction,
  );
  expect(
    exec,
    `fresh sceneProduction execution; types=${events.map((evt) => evt.type).join(",")}`,
  ).toBeTruthy();
  return exec.execution.plan_data;
}

async function loadShot(request: APIRequestContext, sceneId: string, shotId: string) {
  const masterRes = await request.get(
    `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/master`,
  );
  expect(masterRes.ok()).toBeTruthy();
  const body = await masterRes.json();
  const shot = (body.master?.batchBlocks || []).find((item: any) => item.id === shotId);
  expect(shot, "fresh shot on master").toBeTruthy();
  return { master: body.master, shot };
}

function assertCanonicalBindings(shot: any) {
  const seg = (shot.promptSegments || [])[0] || {};
  const rows = seg.referenceNameBindings || seg.reference_name_bindings || [];
  expect(rows.length).toBeGreaterThanOrEqual(3);
  for (const row of rows) {
    expect(String(row.binding_id || row.bindingId || "")).toMatch(/[0-9a-f-]{16,}/i);
    expect(String(row.type || "")).toMatch(/environment|prop|character/i);
    const tag = String(row.tag || "");
    expect(tag, `tag for ${row.prompt_name || row.promptName}`).toMatch(/^[#%@]/);
  }
  const tags = rows.map((row: any) => String(row.tag || "")).join(" ");
  expect(tags).toMatch(/#EarthHorizon/i);
  expect(tags).toMatch(/%VentureSpaceship/i);
  expect(tags).toMatch(/%CadeSStarfighter/i);
  return rows;
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-timed-prompt-track")).toBeVisible({ timeout: 60_000 });
}

async function openTimedPrompt(page: Page) {
  const clip = page.locator('[data-testid^="track-clip-prompt-"]').first();
  await expect(clip).toBeVisible({ timeout: 30_000 });
  await clip.dblclick();
  const modal = page.getByTestId("timeline-timed-prompt-modal");
  await expect(modal).toBeVisible({ timeout: 20_000 });
  await expect(modal.getByTestId("timed-prompt-references")).toBeVisible();
  await expect(modal.getByTestId("timed-prompt-ref-missing")).toHaveCount(0);
  await expect(modal.getByText("Missing from References")).toHaveCount(0);
  await expect(modal.getByText("was not redirected")).toHaveCount(0);
  await expect(modal.getByTestId("timed-prompt-ref-row-0")).toBeVisible();
  await expect(modal.getByTestId("timed-prompt-ref-row-1")).toBeVisible();
  await expect(modal.getByTestId("timed-prompt-ref-row-2")).toBeVisible();
}

test.describe("Timeline reference persistence + hydration", () => {
  test("fresh Co-Director scene hydrates three FOUND refs after reload", async ({ page, request }) => {
    test.setTimeout(240_000);
    const plan = await streamPrepare(request);
    expect(plan.preparationReady).toBeTruthy();
    const sceneId = String(plan.sceneId);
    const shotId = String(plan.shotId);
    const before = await loadShot(request, sceneId, shotId);
    const beforeRows = assertCanonicalBindings(before.shot);

    await openTimeline(page, sceneId);
    await openTimedPrompt(page);
    await page.getByTestId("timeline-timed-prompt-ok").click();
    await expect(page.getByTestId("timeline-timed-prompt-modal")).toHaveCount(0);

    await page.reload({ waitUntil: "domcontentloaded" });
    await openTimeline(page, sceneId);
    await openTimedPrompt(page);

    const after = await loadShot(request, sceneId, shotId);
    const afterRows = assertCanonicalBindings(after.shot);
    expect(afterRows.map((row: any) => row.binding_id || row.bindingId)).toEqual(
      beforeRows.map((row: any) => row.binding_id || row.bindingId),
    );
    expect(afterRows.map((row: any) => row.asset_id || row.assetId)).toEqual(
      beforeRows.map((row: any) => row.asset_id || row.assetId),
    );
    expect(afterRows.map((row: any) => row.tag)).toEqual(beforeRows.map((row: any) => row.tag));

    const transport = await request.get(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches/${shotId}/reference-transport`,
    );
    expect(transport.ok()).toBeTruthy();
    const transportBody = await transport.json();
    const transportText = JSON.stringify(transportBody);
    expect(transportText).toMatch(/VentureSpaceship/i);
    expect(transportText).not.toMatch(/UploadSmokeAdvancedShip/i);
    const transportIds = (transportBody.timelineReferences || []).map((item: any) => String(item.assetId || ""));
    expect(afterRows.map((row: any) => String(row.asset_id || row.assetId || "")).sort()).toEqual(
      [...transportIds].sort(),
    );

    const generate = await request.post(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${sceneId}/batches/${shotId}/generate`,
      { data: {}, timeout: 60_000 },
    );
    expect(generate.ok(), await generate.text()).toBeTruthy();
    const generateBody = await generate.json();
    expect(generateBody.ok, JSON.stringify(generateBody)).toBeTruthy();
    const generateText = JSON.stringify(generateBody.normalizedRequest || generateBody);
    for (const row of afterRows) {
      const assetId = String(row.asset_id || row.assetId || "");
      if (assetId) expect(generateText).toContain(assetId);
    }
  });
});
