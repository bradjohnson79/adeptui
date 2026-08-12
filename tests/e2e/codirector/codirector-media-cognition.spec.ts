import { expect, test } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import { TINY_PNG, getConversation, openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

test.describe("@critical @isolated codirector media cognition", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("attached reference image is associated honestly and persists without leaking local paths", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir Media ${Date.now()}`);
    const imageName = `dreamweaver-reference-${Date.now()}.png`;

    try {
      await openCoDirectorFullScreen(page, project.id);

      await page.getByTestId("codirector-file-input").setInputFiles({
        name: imageName,
        mimeType: "image/png",
        buffer: TINY_PNG,
      });

      const tray = page.getByTestId("codirector-attachment-tray");
      await expect(tray).toBeVisible({ timeout: 15_000 });
      await expect(tray).toContainText(imageName);

      const fileAccept = await page
        .getByTestId("codirector-file-input")
        .evaluate((node) => (node as HTMLInputElement).accept);
      expect.soft(fileAccept).toMatch(/audio/i);

      const prompt =
        "Use the attached image as a reference for Dreamweaver. Tell me only what you can safely infer, and say so plainly if visual analysis is unavailable.";
      const assistantReply = await sendChatTurn(page, prompt);

      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(
        new RegExp(`Attached:\\s+${imageName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i"),
        { timeout: 20_000 },
      );

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/\b[A-Z]:\\(?:[^\\\r\n]+\\)+[^\\\r\n]*/);

      if (/visual analysis is unavailable|can't view|cannot view|unable to view|do not have.*vision|don't have.*vision/i.test(assistantReply)) {
        expect(assistantReply).not.toMatch(/\bI can see\b|\bthe image shows\b|\bdepicts\b/i);
      }

      const conversation = await getConversation(request, project.id);
      const persistedUserMessage = [...conversation.messages]
        .reverse()
        .find((message) => message.role === "user" && message.content.includes(prompt));
      expect(persistedUserMessage).toBeTruthy();
      expect(JSON.stringify(persistedUserMessage)).not.toMatch(/\b[A-Z]:\\(?:[^\\\r\n]+\\)+[^\\\r\n]*/);

      await page.reload();
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: imageName })).toHaveCount(1, {
        timeout: 15_000,
      });

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
