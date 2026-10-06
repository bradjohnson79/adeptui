/**
 * Co-Director project grounding on the real Korri Anadriya project.
 * Never POST /api/projects.
 */
import { expect, test, type Page } from "@playwright/test";

async function sendGroundingTurn(page: Page, text: string, expected: RegExp) {
  const bubbles = page.locator(".codirector-msg.assistant .codirector-msg-bubble");
  const before = await bubbles.count();
  await page.getByTestId("codirector-composer-input").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect
    .poll(
      async () => {
        const count = await bubbles.count();
        if (count <= before) return "";
        return (await bubbles.nth(before).innerText()).trim();
      },
      { timeout: 60_000 },
    )
    .toMatch(expected);
  return (await bubbles.nth(before).innerText()).trim();
}

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const WALK_ID = process.env.ADEPT_SCENE_ID || "b5282a4c-07eb-40db-9d5b-1512eac74dca";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const TWO_ENTITY =
  "Create a shot with @Korri and @Anadriya walking through the Venture corridor.";

type SceneRow = { id: string; name?: string };

async function waitForTimeline(page: Page) {
  await expect(page.getByTestId("timeline-transport-play")).toBeVisible({ timeout: 60_000 });
}

async function openLeftDrawer(page: Page) {
  const handle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(handle).toBeVisible({ timeout: 20_000 });
  if ((await handle.getAttribute("aria-expanded")) !== "true") {
    const box = await handle.boundingBox();
    if (box) await handle.click({ position: { x: Math.max(2, box.width / 2), y: 16 } });
    else await handle.click();
  }
  await expect(handle).toHaveAttribute("aria-expanded", "true", { timeout: 10_000 });
}

async function selectSceneFromDrawer(page: Page, sceneId: string) {
  await openLeftDrawer(page);
  const block = page.getByTestId(`scene-block-${sceneId}`);
  await expect(block).toBeAttached({ timeout: 30_000 });
  await block.evaluate((el) => el.scrollIntoView({ block: "center", inline: "nearest" }));
  await block.click();
}

async function openCoDirectorPopup(page: Page) {
  await page.getByTestId("chrome-codirector").click();
  const shell = page.getByTestId("codirector-shell");
  await expect(shell).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 20_000 });
  return shell;
}

test.describe("Co-Director project grounding — Korri Anadriya", () => {
  test("bound project, selected scene, characters, voices, @entities, global unbound", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
    expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
    const project = (await projectRes.json()) as { name?: string; scenes?: SceneRow[] };
    const scenes = project.scenes || [];
    const walk = scenes.find((s) => s.id === WALK_ID) || scenes.find((s) => /Venture Corridor Walk/i.test(s.name || ""));
    const dialogue = scenes.find((s) => /Venture Corridor Dialogue/i.test(s.name || ""));
    const scene1 = scenes.find((s) => /^(Scene 1|Scene One)$/i.test(s.name || "")) || scenes[0];
    expect(walk?.id, "Venture Corridor Walk must exist").toBeTruthy();

    const inspectRes = await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/turn-grounding`, {
      data: {
        text: TWO_ENTITY,
        sceneId: walk!.id,
        workspace: "timeline",
      },
    });
    expect(inspectRes.ok(), await inspectRes.text()).toBeTruthy();
    const inspect = await inspectRes.json();
    expect(inspect.sessionStatus).toBe("bound");
    expect(inspect.projectId).toBe(PROJECT_ID);
    expect(inspect.activeSceneId).toBe(walk!.id);
    const entityNames = (inspect.entities?.characters || []).map((row: { name?: string }) => row.name);
    expect(entityNames).toEqual(expect.arrayContaining(["Korri", "Anadriya"]));
    expect(entityNames).toHaveLength(2);
    for (const row of inspect.entities.characters as Array<{
      name: string;
      characterId: string;
      crsAssetId: string;
    }>) {
      expect(row.characterId, `${row.name} characterId`).toBeTruthy();
      expect(row.crsAssetId, `${row.name} CRS assetId`).toBeTruthy();
    }
    expect(inspect.routeLock?.requestedModelId || "").toBe("");
    const snapshotNames = (inspect.snapshot?.characters || []).map((row: { name?: string }) => row.name);
    expect(snapshotNames).toEqual(expect.arrayContaining(["Korri", "Anadriya"]));
    const voices = inspect.snapshot?.voiceAssignments || [];
    expect(voices.length, "canonical voice assignments must exist").toBeGreaterThanOrEqual(2);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/project/${PROJECT_ID}?workspace=timeline&sceneId=${walk!.id}`, {
      waitUntil: "domcontentloaded",
    });
    await waitForTimeline(page);
    await expect(page).toHaveURL(new RegExp(`sceneId=${walk!.id}`));

    const streamBodies: Array<Record<string, unknown>> = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/api/codirector/chat/stream")) {
        try {
          streamBodies.push(JSON.parse(req.postData() || "{}") as Record<string, unknown>);
        } catch {
          /* ignore */
        }
      }
    });

    const shell = await openCoDirectorPopup(page);
    await expect(shell).toHaveAttribute("data-project-id", PROJECT_ID);
    await expect(shell).toHaveAttribute("data-scene-id", walk!.id);
    await expect(shell).toHaveAttribute("data-workspace", "timeline");
    await expect(page.getByTestId("codirector-context-chip-scene")).toContainText(/Venture Corridor Walk/i);

    const charactersReply = await sendGroundingTurn(
      page,
      "Who are the active characters in this project?",
      /Korri/i,
    );
    expect(charactersReply).toMatch(/Anadriya/i);
    expect(charactersReply).not.toMatch(/no active characters/i);

    const voicesReply = await sendGroundingTurn(
      page,
      "What voices are assigned to Korri and Anadriya?",
      /Korri Clone|Anadriya Clone|qwen3-tts/i,
    );
    expect(voicesReply).not.toMatch(/no assigned voices|have no assigned/i);
    for (const voice of voices as Array<{ voiceName?: string; engine?: string; characterName?: string }>) {
      if (voice.voiceName) expect(voicesReply).toContain(voice.voiceName);
      if (voice.engine) expect(voicesReply).toContain(voice.engine);
    }

    const sceneReply = await sendGroundingTurn(
      page,
      "What scene are we working on?",
      /Venture Corridor Walk/i,
    );
    expect(sceneReply).not.toMatch(/generic corridor|I don't know|no scene/i);

    expect(streamBodies.length).toBeGreaterThan(0);
    for (const body of streamBodies) {
      expect(body.project_id, JSON.stringify(body)).toBe(PROJECT_ID);
      expect(body.scene_id, JSON.stringify(body)).toBe(walk!.id);
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitForTimeline(page);
    await expect(page).toHaveURL(new RegExp(`sceneId=${walk!.id}`));
    await openCoDirectorPopup(page);
    const afterRefresh = await sendGroundingTurn(page, "What scene are we working on?", /Venture Corridor Walk/i);
    expect(afterRefresh).toMatch(/Venture Corridor Walk/i);
    const afterRefreshCast = await sendGroundingTurn(page, "Who is in this project?", /Korri/i);
    expect(afterRefreshCast).toMatch(/Anadriya/i);

    if (scene1?.id && scene1.id !== walk!.id) {
      await selectSceneFromDrawer(page, scene1.id);
      await expect(page).toHaveURL(new RegExp(`sceneId=${scene1.id}`), { timeout: 15_000 });
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-scene-id", scene1.id);
      const scene1Reply = await sendGroundingTurn(
        page,
        "What scene are we working on?",
        new RegExp(scene1.name?.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") || "Scene", "i"),
      );
      expect(scene1Reply).toContain(scene1.name || "");
    }
    if (dialogue?.id) {
      await selectSceneFromDrawer(page, dialogue.id);
      await expect(page).toHaveURL(new RegExp(`sceneId=${dialogue.id}`), { timeout: 15_000 });
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-scene-id", dialogue.id);
      const dialogueReply = await sendGroundingTurn(
        page,
        "What scene are we working on?",
        /Venture Corridor Dialogue/i,
      );
      expect(dialogueReply).toMatch(/Venture Corridor Dialogue/i);
    }
    await selectSceneFromDrawer(page, walk!.id);
    await expect(page).toHaveURL(new RegExp(`sceneId=${walk!.id}`), { timeout: 15_000 });
    await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-scene-id", walk!.id);
    const walkAgain = await sendGroundingTurn(page, "What scene are we working on?", /Venture Corridor Walk/i);
    expect(walkAgain).toMatch(/Venture Corridor Walk/i);

    await page.goto("/co-director", { waitUntil: "domcontentloaded" });
    const globalShell = page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-shell"));
    await expect(globalShell.first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("codirector-no-project-banner")).toBeVisible();
    await expect(globalShell.first()).toHaveAttribute("data-project-id", "no_project");
  });
});
