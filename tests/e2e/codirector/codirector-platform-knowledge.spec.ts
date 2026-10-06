/**
 * Co-Director Adept system + generator knowledge foundation.
 * Live retrieval — no test-only knowledge injection.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

async function askKnowledge(
  request: APIRequestContext,
  projectId: string,
  message: string,
  workspace = "timeline",
): Promise<string> {
  const res = await request.post(`${API}/api/codirector/chat/stream`, {
    data: {
      messages: [{ role: "user", content: message }],
      project_id: projectId,
      workspace,
      mode: "chat",
    },
    timeout: 60_000,
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const text = (await res.body()).toString("utf8");
  let assistant = "";
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data:")) continue;
    const payload = trimmed.slice("data:".length).trim();
    if (!payload) continue;
    try {
      const evt = JSON.parse(payload) as { type?: string; content?: string; text?: string };
      if ((evt.type === "assistant" || evt.type === "completed" || evt.type === "completion") && evt.content) {
        assistant = String(evt.content);
      }
      if (evt.type === "delta" && evt.text) assistant += String(evt.text);
    } catch {
      /* ignore keep-alives */
    }
  }
  return assistant.trim();
}

test.describe("Co-Director platform knowledge foundation", () => {
  test.describe.configure({ timeout: 180_000 });

  test("hamburger gone; live knowledge answers Adept contracts; reload keeps retrieval", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `CD Knowledge ${Date.now()}`);
    try {
      const timeline = await askKnowledge(request, project.id, "What is Timeline?");
      expect(timeline.toLowerCase()).toMatch(/picture|prompt name|reference-to-video|video/);
      expect(timeline.toLowerCase()).not.toContain("wide area network");
      expect(timeline.toLowerCase()).not.toMatch(/first and last frame video/);

      const wan = await askKnowledge(request, project.id, "What is WAN?");
      expect(wan.toLowerCase()).toContain("retired");
      expect(wan.toLowerCase()).not.toContain("wide area network");
      expect(wan.toLowerCase()).not.toMatch(/first and last frame video/);

      const wanNet = await askKnowledge(
        request,
        project.id,
        "What does WAN mean in computer networking?",
      );
      expect(wanNet.toLowerCase()).toContain("wide area network");

      const wanT2v = await askKnowledge(request, project.id, "Can WAN make this text-only shot?");
      expect(wanT2v.toLowerCase()).toMatch(/retired|do not restore/);

      const ltx = await askKnowledge(request, project.id, "What does LTX need to generate a video here?");
      expect(ltx.toLowerCase()).toMatch(/ltx|picture|image|start/);

      const h3 = await askKnowledge(request, project.id, "What's the difference between MiniMax H3 here and Route A?");
      expect(h3.toLowerCase()).toMatch(/minimax|h3|route a/);

      const ers = await askKnowledge(request, project.id, "Which generator creates an Environment Reference Sheet?");
      expect(ers).toMatch(/GPT Image 2/);
      expect(ers.toLowerCase()).not.toMatch(/qwen(?:.+)fallback|fallback(?:.+)qwen/);

      const pose = await askKnowledge(request, project.id, "Is PoseCraft a Co-Director Express tool?");
      expect(pose.toLowerCase()).toContain("not");
      expect(pose.toLowerCase()).toContain("express");

      const spatial = await askKnowledge(request, project.id, "What does Spatial Map do?");
      expect(spatial.toLowerCase()).toMatch(/rectangular|atlas/);
      expect(spatial.toLowerCase()).not.toContain("circular viewport");

      const crs = await askKnowledge(request, project.id, "What's a CRS and where is it used?");
      expect(crs.toLowerCase()).toMatch(/character/);

      const voice = await askKnowledge(
        request,
        project.id,
        "How does a character's approved voice reach Timeline Lip Sync?",
      );
      expect(voice.toLowerCase()).toMatch(/voice|timeline|lip/);

      const demand = await askKnowledge(request, project.id, "LTX says On Demand. Does that mean it is broken?");
      expect(demand.toLowerCase()).toContain("on demand");
      expect(demand.toLowerCase()).not.toMatch(/\boffline\b/);

      await openCoDirectorFullScreen(page, project.id, { workspace: "timeline" });
      await expect(page.getByTestId("codirector-menu-button")).toHaveCount(0);
      await expect(page.getByTestId("codirector-nav-drawer")).toHaveCount(0);
      await expect(page.getByTestId("codirector-content-tab-wiki")).toBeVisible();
      await expect(page.getByTestId("codirector-content-group-more")).toHaveCount(0);
      // Hydrate API-streamed history before counting a new UI turn.
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(
        /on demand|GPT Image 2|retired|PoseCraft|Spatial Map|character|timeline/i,
        { timeout: 30_000 },
      );

      const uiWan = await sendChatTurn(page, "What is WAN?");
      expect(uiWan.toLowerCase()).toContain("retired");
      expect(uiWan.toLowerCase()).not.toContain("wide area network");

      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("codirector-menu-button")).toHaveCount(0);
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(
        /retired|minimax h3|ltx 2.5|do not restore/i,
        { timeout: 30_000 },
      );
      const uiAgain = await sendChatTurn(page, "Which generator creates an Environment Reference Sheet?");
      expect(uiAgain).toMatch(/GPT Image 2/);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
