import { expect, test, type APIRequestContext } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

const CADE_PROMPT = `I would like you to build a scene in Timeline where we will have an establishing shot scene, where we will use the Earth Horizon Environment Reference Sheet as the scene. We will also use the Venture Spaceship Prop Reference Sheet, and also the Cade's Starfighter prop reference sheet.

The scene is that we will see the Venture Spaceship in orbit above the Earth's horizon. We will see a blue portal effect showing Cade's Starfighter appear. It will maneuver itself so that it remains directly above the Venture undetected. We want to appear of sizes between these two vessels. The Venture is over a kilometer long, and Cade's Starfighter is 9.8 meters long.

This scene will be created in Timeline using MiniMax H3, Megapixels 2.0 quality, 21:9 frame ratio. And will have a single batch runtime of 10 seconds.`;

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";

test.use({ extraHTTPHeaders: {} });

function extractAction(prompt: string): string {
  const match = prompt.split(/\nACTION\n/i)[1] || "";
  return match.split(/\n[A-Z][A-Z /]+\n/)[0] || match;
}

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

test.describe("Co-Director scene intent synthesis", () => {
  test("Cade establishing request becomes verified cinematic ACTION", async ({ request }) => {
    test.setTimeout(180_000);
    const events = await streamChat(request, CADE_PROMPT);
    const exec = events.find(
      (evt) => evt.type === "execution_status" && evt.execution?.plan_data?.sceneProduction,
    );
    expect(exec, "execution_status with sceneProduction").toBeTruthy();
    const plan = exec.execution.plan_data;
    expect(plan.preparationReady).toBeTruthy();
    const found = (plan.events || []).filter((evt: any) => evt.type === "reference_found");
    expect(JSON.stringify(found)).toMatch(/Earth Horizon/i);
    expect(JSON.stringify(found)).toMatch(/Venture/i);
    expect(JSON.stringify(found)).toMatch(/Starfighter/i);
    expect(JSON.stringify(found)).toMatch(/Global Prop Reference Sheet|Prop Reference Sheet/i);
    const prompt = String(plan.compiledPrompt || "");
    expect(prompt).toContain("%VentureSpaceship");
    expect(prompt).not.toContain("%VentureSpaceship2");
    expect(prompt).not.toContain("%VentureSpaceship3");
    expect(prompt).not.toContain("%VentureSpaceship4");
    expect(prompt).toMatch(/%CadeS?Starfighter/);
    expect(prompt).toContain("#EarthHorizon");
    expect(prompt).not.toContain("#EarthHorizon2");
    const action = extractAction(prompt);
    expect(action).toBeTruthy();
    expect(action).not.toMatch(/I would like you/i);
    expect(action).not.toMatch(/build a scene in Timeline/i);
    expect(action).not.toMatch(/reference sheet/i);
    expect(action).not.toMatch(/frame ratio/i);
    expect(action).not.toMatch(/runtime of 10 seconds/i);
    expect(action).toMatch(/orbit/i);
    expect(action).toMatch(/portal/i);
    expect(action).toMatch(/Starfighter/i);
    expect(action).toMatch(/above/i);
    expect(action).toMatch(/undetected|unnoticed/i);
    expect(action).toMatch(/smaller|tiny|fraction/i);
    const intent = plan.directorIntent || {};
    expect(intent.environment?.tag || "").toMatch(/#EarthHorizon/);
    expect(JSON.stringify(intent.subjects || [])).toMatch(/%VentureSpaceship/);
    expect(intent.action_text || action).not.toMatch(/I would like you/i);
  });

  test("Co-Director card shows preparation decisions, not request copy", async ({ page }) => {
    test.setTimeout(180_000);
    await openCoDirectorFullScreen(page, PROJECT_ID, { workspace: "timeline" });
    await sendChatTurn(page, CADE_PROMPT);
    const card = page.getByTestId("scene-production-card");
    await expect(card).toBeVisible({ timeout: 90_000 });
    const events = page.getByTestId("scene-production-events");
    await expect(events).toContainText(/Earth Horizon/i);
    await expect(events).toContainText(/Venture/i);
    await expect(events).toContainText(/Starfighter/i);
    await expect(events).toContainText(/Scale relationship identified/i);
    await expect(events).toContainText(/Cinematic action synthesized/i);
    const prompt = page.getByTestId("scene-compiled-prompt");
    await expect(prompt).toContainText(/ACTION/i);
    await expect(prompt).not.toContainText("I would like you");
    await expect(prompt).toContainText(/portal/i);
    await expect(page.getByTestId("scene-director-breakdown")).toContainText(/Earth Horizon/i);
    await expect(page.getByTestId("generate-in-timeline")).toBeVisible();
  });
});
