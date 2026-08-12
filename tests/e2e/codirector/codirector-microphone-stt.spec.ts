import { expect, test, type Page } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import { openCoDirectorFullScreen, sendChatTurn } from "./helpers/audit";

type SpeechScenario =
  | { type: "success"; transcript: string }
  | { type: "error"; error: string };

async function installSpeechRecognitionMock(page: Page, scenarios: SpeechScenario[]) {
  await page.addInitScript((queuedScenarios: SpeechScenario[]) => {
    type BrowserSpeechScenario =
      | { type: "success"; transcript: string }
      | { type: "error"; error: string };

    const queue = [...queuedScenarios];

    class MockSpeechRecognition {
      continuous = false;
      interimResults = true;
      lang = "en-US";
      onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      private scenario: BrowserSpeechScenario =
        queue.shift() || { type: "success", transcript: "Let us begin with the main character." };
      private emitted = false;

      start() {
        if (this.scenario.type === "error") {
          window.setTimeout(() => {
            this.onerror?.({ error: this.scenario.type === "error" ? this.scenario.error : "unknown" });
            this.onend?.();
          }, 25);
        }
      }

      stop() {
        if (this.emitted || this.scenario.type !== "success") {
          window.setTimeout(() => this.onend?.(), 0);
          return;
        }
        this.emitted = true;
        window.setTimeout(() => {
          this.onresult?.({
            results: [[{ transcript: this.scenario.type === "success" ? this.scenario.transcript : "" }]],
          });
        }, 25);
        window.setTimeout(() => this.onend?.(), 50);
      }

      abort() {
        this.emitted = true;
        window.setTimeout(() => {
          this.onerror?.({ error: "aborted" });
          this.onend?.();
        }, 0);
      }
    }

    (window as Window & { SpeechRecognition?: typeof MockSpeechRecognition }).SpeechRecognition = MockSpeechRecognition;
    (window as Window & { webkitSpeechRecognition?: typeof MockSpeechRecognition }).webkitSpeechRecognition =
      MockSpeechRecognition;
  }, scenarios);
}

test.describe("@critical @isolated codirector microphone stt", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("speech transcript lands in the composer, stays editable, and does not auto-send", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir STT ${Date.now()}`);
    const transcript = "Let us begin with the main character.";
    const editedTranscript = `${transcript} Focus on the choice she makes at the harbor gate.`;

    try {
      await installSpeechRecognitionMock(page, [{ type: "success", transcript }]);
      await openCoDirectorFullScreen(page, project.id);

      await page.getByTestId("codirector-mic-button").click();
      await expect(page.getByTestId("codirector-stt-status")).toContainText(/Listening/i);
      await page.getByTestId("codirector-mic-button").click();

      await expect(page.getByTestId("codirector-composer-input")).toHaveValue(transcript, { timeout: 15_000 });
      await expect(page.getByTestId("codirector-stt-status")).toHaveCount(0);
      await expect(page.locator(".codirector-msg.user")).toHaveCount(0);

      await page.getByTestId("codirector-composer-input").fill(editedTranscript);
      const assistantReply = await sendChatTurn(page, editedTranscript);
      expect(assistantReply).toMatch(/\S/);

      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(editedTranscript);

      await page.reload();
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: editedTranscript })).toHaveCount(1, {
        timeout: 15_000,
      });

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("permission denial surfaces a creator-friendly error", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir STT Denied ${Date.now()}`);

    try {
      await installSpeechRecognitionMock(page, [{ type: "error", error: "not-allowed" }]);
      await openCoDirectorFullScreen(page, project.id);

      await page.getByTestId("codirector-mic-button").click();

      await expect(page.getByTestId("codirector-stt-error")).toContainText(/permission was denied/i, {
        timeout: 15_000,
      });
      await expect(page.getByTestId("codirector-composer-input")).toHaveValue("");
      await expect(page.getByTestId("codirector-stt-status")).toHaveCount(0);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("cancel exits listening without sending or leaving a transcript behind", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `CoDir STT Cancel ${Date.now()}`);

    try {
      await installSpeechRecognitionMock(page, [{ type: "success", transcript: "This should never be inserted." }]);
      await openCoDirectorFullScreen(page, project.id);

      await page.getByTestId("codirector-mic-button").click();
      await expect(page.getByTestId("codirector-stt-status")).toContainText(/Listening/i);
      await page.getByTestId("codirector-stt-cancel").click();

      await expect(page.getByTestId("codirector-stt-status")).toHaveCount(0);
      await expect(page.getByTestId("codirector-composer-input")).toHaveValue("");
      await expect(page.locator(".codirector-msg.user")).toHaveCount(0);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
