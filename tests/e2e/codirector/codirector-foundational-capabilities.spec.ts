import { expect, test } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  expectFixedViewportFraming,
  getConversation,
  openCoDirectorFullScreen,
  sendChatTurn,
} from "./helpers/audit";

function expectCreatorSafeReply(text: string) {
  expect(text).toMatch(/\S/);
  expect(text).not.toMatch(/failed to fetch/i);
  expect(text).not.toMatch(/I couldn't reach the local model/i);
  expect(text).not.toMatch(/0\.95\s+Next:\s+Continue with the recommended direction/i);
}

test.describe("@critical @isolated codirector foundational capabilities", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("co-director grounds Dreamweaver chat, keeps questions out of canon, and survives reload", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await page.setViewportSize({ width: 1440, height: 900 });
    const project = await createTempProject(request, `CoDir Foundational ${Date.now()}`);
    const introduction =
      "This project is called Dreamweaver. It is a mythic drama about a harbor child who hears a lantern calling her into an older memory-world.";
    const nextStepQuestion = "What should we do next?";
    const correction =
      "Correction: Dreamweaver is not cyberpunk. Keep it tactile, tide-worn, and grounded in hand-built harbor details.";

    try {
      await openCoDirectorFullScreen(page, project.id);
      await expectFixedViewportFraming(page);

      const introReply = await sendChatTurn(page, introduction);
      expectCreatorSafeReply(introReply);

      const nextReply = await sendChatTurn(page, nextStepQuestion);
      expectCreatorSafeReply(nextReply);

      const wikiRes = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
      if (wikiRes.ok()) {
        const wiki = JSON.stringify(await wikiRes.json());
        expect(wiki).not.toContain(nextStepQuestion);
      }

      const correctionReply = await sendChatTurn(page, correction);
      expectCreatorSafeReply(correctionReply);

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);

      const conversation = await getConversation(request, project.id);
      expect(
        conversation.messages.some((message) => message.role === "user" && message.content.includes(correction)),
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
