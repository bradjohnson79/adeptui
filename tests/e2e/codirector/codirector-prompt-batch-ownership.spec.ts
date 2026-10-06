/**
 * Co-Director prompt vs batch ownership — disposable live samples.
 *
 * Cursor types the request. Co-Director prepares. No Timeline repair.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn, TINY_PNG, uploadProjectAsset } from "./helpers/audit";

test.use({ extraHTTPHeaders: {} });

const LEAK = /Spatial Map|PoseCraft|Standalone|Image Runtime|Local Video Runtime|Adept is the filmmaking app/i;

async function seedEnvironment(request: APIRequestContext, projectId: string, name: string, tag: string) {
  const asset = await uploadProjectAsset(request, projectId, {
    name: `${tag}.png`,
    mimeType: "image/png",
    kind: "image",
    buffer: TINY_PNG,
    tag,
  });
  const save = await request.post(`${API}/api/environment-reference-sheets/projects/${projectId}/save`, {
    data: { name, environmentPrompt: `${name} test environment`, referenceImageAssetId: asset.id },
  });
  expect(save.ok(), await save.text()).toBeTruthy();
  const sheetId = (await save.json()).sheet.sheetId as string;
  const approve = await request.post(
    `${API}/api/environment-reference-sheets/projects/${projectId}/${sheetId}/approve-reference`,
    { data: { assetId: asset.id } },
  );
  expect(approve.ok(), await approve.text()).toBeTruthy();
}

async function seedCharacter(request: APIRequestContext, projectId: string, name: string, slug: string) {
  const asset = await uploadProjectAsset(request, projectId, {
    name: `${slug}.png`,
    mimeType: "image/png",
    kind: "image",
    buffer: TINY_PNG,
    tag: slug,
  });
  const create = await request.post(`${API}/api/projects/${projectId}/characters`, {
    data: { name, slug, role: "lead" },
  });
  expect(create.ok(), await create.text()).toBeTruthy();
  const characterId = (await create.json()).id as string;
  const approve = await request.post(
    `${API}/api/projects/${projectId}/characters/${characterId}/approve-candidate`,
    { data: { assetId: asset.id, referenceRole: "hero_identity", sourceType: "upload", ownerConfirmed: true } },
  );
  expect(approve.ok(), await approve.text()).toBeTruthy();
}

function parseSse(body: string) {
  const events: Record<string, any>[] = [];
  for (const line of body.split("\n")) {
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
  return events;
}

async function runThroughCd(page: Page, request: APIRequestContext, projectId: string, message: string) {
  await openCoDirectorFullScreen(page, projectId, { workspace: "timeline" });
  const streamResponse = page.waitForResponse(
    (res) => res.url().includes("/api/codirector/chat/stream") && res.request().method() === "POST",
    { timeout: 180_000 },
  );
  await sendChatTurn(page, message);
  const response = await streamResponse;
  expect(response.ok()).toBeTruthy();
  const events = parseSse(await response.text());
  const exec = events.find((evt) => evt.type === "execution_status" && evt.execution?.plan_data?.sceneProduction);
  expect(exec, "sceneProduction execution").toBeTruthy();
  const plan = exec!.execution.plan_data;
  const assistantBits = events
    .filter((evt) => evt.type === "assistant" && evt.content)
    .map((evt) => String(evt.content));
  const card = page.getByTestId("scene-production-card");
  await expect(card).toBeVisible({ timeout: 60_000 });
  const cardText = (await card.innerText()).replace(/\s+/g, " ").trim();
  const masterRes = await request.get(
    `${API}/api/director-timeline/projects/${projectId}/scenes/${plan.sceneId}/master`,
  );
  expect(masterRes.ok()).toBeTruthy();
  const master = (await masterRes.json()).master;
  return { plan, cardText, master, assistantBits };
}

function timedPrompts(master: any) {
  return (master?.batchBlocks || []).flatMap((b: any) =>
    (b.promptSegments || []).filter((s: any) => String(s.text || "").trim()),
  );
}

test("Disposable A: 30s continuous scene is 1 Timed Prompt and 2 batches", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Prompt Ownership A");
  try {
    await seedEnvironment(request, project.id, "Iron Causeway", "iron_causeway");
    await seedCharacter(request, project.id, "Nia Vale", "nia-vale");
    const message =
      "Create a Timeline scene using the Iron Causeway environment reference sheet as the setting " +
      "with the Character reference of Nia Vale. Nia walks the causeway from left to right in one continuous shot. " +
      "No dialogue. 30 seconds, 2 batches, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runThroughCd(page, request, project.id, message);
    expect(run.plan.preparationReady, JSON.stringify(run.plan.error || run.plan)).toBeTruthy();
    expect(Number(run.plan.batchCount)).toBe(2);
    expect(Number(run.plan.durationSeconds)).toBe(30);
    const tags = (run.plan.references || []).map((r: any) => r.canonical_tag);
    expect(tags).toContain("#IronCauseway");
    expect(tags).toContain("@NiaVale");
    const production = (run.master?.batchBlocks || []).filter((b: any) => b.migrationMetadata?.sourceProductionRequestId);
    expect(production.length).toBe(2);
    const timed = timedPrompts(run.master);
    expect(timed.length).toBe(1);
    expect(Number(timed[0].start || 0)).toBe(0);
    expect(Number(timed[0].length)).toBe(30);
    expect(String(timed[0].text)).toContain("@NiaVale");
    expect(String(timed[0].text)).toContain("#IronCauseway");
    const spoken = `${run.cardText}\n${run.assistantBits.join("\n")}`;
    expect(spoken).not.toMatch(LEAK);
    expect(run.cardText).toMatch(/Scene Prepared/i);
  } finally {
    await deleteProject(request, project.id);
  }
});

test("Disposable B: unrelated establishing scene stays one prompt", async ({ page, request }) => {
  test.setTimeout(240_000);
  const project = await createTempProject(request, "Prompt Ownership B");
  try {
    await seedEnvironment(request, project.id, "Glass Marsh", "glass_marsh");
    const message =
      "Create a Timeline scene using the Glass Marsh environment reference sheet as the setting. " +
      "Slow aerial drift over mist. No characters, no dialogue. 10 seconds, 1 batch, MiniMax H3, 21:9, 1.0 MP.";
    const run = await runThroughCd(page, request, project.id, message);
    expect(run.plan.preparationReady, JSON.stringify(run.plan.error || run.plan)).toBeTruthy();
    const timed = timedPrompts(run.master);
    expect(timed.length).toBe(1);
    expect(Number(timed[0].length)).toBe(10);
    expect(String(timed[0].text)).toContain("#GlassMarsh");
    expect(`${run.cardText}\n${run.assistantBits.join("\n")}`).not.toMatch(LEAK);
  } finally {
    await deleteProject(request, project.id);
  }
});
