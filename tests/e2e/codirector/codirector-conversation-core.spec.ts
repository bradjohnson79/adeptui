import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import { getConversation, openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

function expectCreatorSafe(text: string) {
  expect(text).toMatch(/\S/);
  expect(text).not.toMatch(/0\.95/);
  expect(text).not.toMatch(/conversation_quality|primaryIntent|toolId/i);
  expect(text).not.toMatch(/failed to fetch/i);
  expect(text).not.toMatch(/\{"type":/);
}

test.describe("@critical @isolated codirector conversation core", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("intro, inquiry, stage focus, wiki safety, correction, and reload", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir Conversation Core ${Date.now()}`);

    const intro =
      "I am going to tell you about my web series, The Dreamweaver, its lore, characters, connection to The Adept Chronicles, and the first season we will build.";
    const nextStep = "What should we do next?";
    const lore = "Let me begin with the Dreamweaver itself.";
    const character = "I want to start with the main character.";
    const facility = "The mysterious signal came from the research facility under the harbor.";
    const correction = "Correction: the signal came from a crashed probe, not the facility.";

    try {
      await openCoDirectorFullScreen(page, project.id);

      const introReply = await sendChatTurn(page, intro);
      expectCreatorSafe(introReply);
      expect(introReply).toMatch(/Dreamweaver/i);
      expect(introReply).not.toMatch(/\?.*\?.*\?/);

      const nextReply = await sendChatTurn(page, nextStep);
      expectCreatorSafe(nextReply);
      expect(nextReply.toLowerCase()).toMatch(/recommend|next|foundation|character|world|season/);

      const wikiAfterQuestion = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
      expect(wikiAfterQuestion.ok()).toBeTruthy();
      const wikiJson = JSON.stringify(await wikiAfterQuestion.json());
      expect(wikiJson).not.toContain(nextStep);

      const loreReply = await sendChatTurn(page, lore);
      expectCreatorSafe(loreReply);
      expect(loreReply.toLowerCase()).toMatch(/keep going|with you|continue|ready/);

      const characterReply = await sendChatTurn(page, character);
      expectCreatorSafe(characterReply);
      expect(characterReply.toLowerCase()).toMatch(/lead|character/);
      expect((characterReply.match(/\?/g) || []).length).toBeLessThanOrEqual(2);

      await sendChatTurn(page, facility);
      const correctionReply = await sendChatTurn(page, correction);
      expectCreatorSafe(correctionReply);
      expect(correctionReply.toLowerCase()).toMatch(/understood|corrected|probe|going forward/);

      const wikiAfterCorrection = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
      expect(wikiAfterCorrection.ok()).toBeTruthy();
      const wikiBody = JSON.stringify(await wikiAfterCorrection.json());
      expect(wikiBody.toLowerCase()).toMatch(/probe|facility|superseded|confirmed|proposed/);

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/conversation_quality|primaryIntent|blockedItems/i);

      const conversation = await getConversation(request, project.id);
      expect(
        conversation.messages.some((m) => m.role === "user" && m.content.includes(correction)),
      ).toBeTruthy();

      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: correction })).toHaveCount(1, {
        timeout: 15_000,
      });

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
