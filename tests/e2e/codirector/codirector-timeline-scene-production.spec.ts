import { expect, test, type APIRequestContext } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const CADE_PROMPT = `I would like you to build a scene in Timeline where we will have an establishing shot scene, where we will use the Earth Horizon Environment Reference Sheet as the scene. We will also use the Venture Spaceship Prop Reference Sheet, and also the Cade's Starfighter prop reference sheet.

The scene is that we will see the Venture Spaceship in orbit above the Earth's horizon. We will see a blue portal effect showing Cade's Starfighter appear. It will maneuver itself so that it remains directly above the Venture undetected. We want to appear of sizes between these two vessels. The Venture is over a kilometer long, and Cade's Starfighter is 9.8 meters long.

This scene will be created in Timeline using MiniMax H3, Megapixels 2.0 quality, 21:9 frame ratio. And will have a single batch runtime of 10 seconds.`;

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";

test.use({ extraHTTPHeaders: {} });

async function streamChat(request: APIRequestContext, message: string) {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: PROJECT_ID,
      mode: "chat",
      workspace_tab: "timeline",
    },
    timeout: 180_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const text = (await res.body()).toString("utf8");
  const events: Record<string, any>[] = [];
  for (const line of text.split("\n")) {
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

test.describe("Co-Director Timeline scene production", () => {
  test("Cade Scenes chat stream prepares a Timeline shot", async ({ request }) => {
    test.setTimeout(180_000);
    const events = await streamChat(request, CADE_PROMPT);
    const exec = events.find(
      (evt) => evt.type === "execution_status" && evt.execution?.plan_data?.sceneProduction,
    );
    expect(exec, "execution_status with sceneProduction").toBeTruthy();
    const plan = exec.execution.plan_data;
    expect(plan.preparationReady).toBeTruthy();
    expect(plan.sceneId).toBeTruthy();
    expect(plan.shotId).toBeTruthy();
    expect(String(plan.generatorId)).toMatch(/minimax-h3/i);
    expect(plan.durationSeconds).toBe(10);
    expect(plan.aspectRatio).toBe("21:9");
    expect(String(plan.quality || "")).toMatch(/megapixels-2/i);
    expect(plan.batchCount).toBe(1);
    const found = (plan.events || []).filter((evt: any) => evt.type === "reference_found");
    expect(found.length).toBeGreaterThanOrEqual(3);
    expect(JSON.stringify(found)).toMatch(/Starfighter/i);
    expect(JSON.stringify(found)).toMatch(/Venture/i);
    expect(JSON.stringify(found)).toMatch(/Earth Horizon|horizon/i);
    expect(String(plan.compiledPrompt || "")).toMatch(/scale|dwarf|kilometer|9\.8/i);
    expect(exec.execution.status).toBe("preview");

    const masterRes = await request.get(
      `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${plan.sceneId}/master`,
    );
    expect(masterRes.ok()).toBeTruthy();
    const masterBody = await masterRes.json();
    const batches = masterBody.master?.batchBlocks || [];
    const shot = batches.find((item: any) => item.id === plan.shotId);
    expect(shot, "prepared shot on Timeline master").toBeTruthy();
    expect(String(shot.generatorId || masterBody.master?.sceneGeneratorId || "")).toMatch(/minimax-h3/i);
    const prompt = String((shot.promptSegments || [])[0]?.text || "");
    expect(prompt).toMatch(/SPATIAL|scale|dwarf/i);
  });

  test("Cade Scenes Co-Director UI shows Generate in Timeline, not fake 0/1", async ({ page }) => {
    test.setTimeout(180_000);
    await openCoDirectorFullScreen(page, PROJECT_ID, { workspace: "timeline" });
    await sendChatTurn(page, CADE_PROMPT);

    const card = page.getByTestId("scene-production-card");
    await expect(card).toBeVisible({ timeout: 90_000 });
    await expect(card).toContainText(/MiniMax H3/i);
    await expect(card).toContainText("10");
    await expect(card).toContainText("21:9");
    await expect(card).toContainText(/Megapixels 2/i);
    const events = page.getByTestId("scene-production-events");
    await expect(events).toContainText(/Starfighter/i);
    await expect(events).toContainText(/Venture/i);
    await expect(events).toContainText(/Earth Horizon|horizon/i);
    await expect(page.getByTestId("scene-compiled-prompt")).toContainText(/scale|dwarf|kilometer|9\.8/i);
    await expect(page.getByTestId("generate-in-timeline")).toBeVisible();
    await expect(page.getByTestId("open-in-timeline")).toBeVisible();
    await expect(page.getByText("Generating shot — 0/1 complete")).toHaveCount(0);
    await expect(page.getByText("Approve Generation")).toHaveCount(0);
  });
});
