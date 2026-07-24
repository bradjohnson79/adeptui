import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

async function setMockScenario(request: APIRequestContext, scenario: string | null) {
  const res = await request.post(`${API}/api/e2e/codirector/scenario`, {
    data: { scenario },
  });
  expect(res.ok()).toBeTruthy();
}

async function openCoDirector(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}`);
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  await fab.click();
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

async function sendMessage(page: Page, text: string) {
  const textarea = page.getByLabel("Message Co-Director");
  await textarea.fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

/**
 * Covers the remaining Co-Director Milestone-1 reliability surface: incremental token
 * streaming + Stop Generating, retry-without-duplicate, and reload-time persistence.
 */
test.describe("@critical @isolated codirector streaming, cancel, retry, persistence", () => {
  test.beforeEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("reply streams incrementally and a Stop Generating control is available while busy", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir Stream ${Date.now()}`);

    try {
      await setMockScenario(request, "slow");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Write me a short script outline.");

      // While the mock streams, the send control flips to a Stop Generating button.
      const stopButton = page.getByRole("button", { name: "Stop generating" });
      await expect(stopButton).toBeVisible({ timeout: 5_000 });

      // Tokens should render before the turn completes (partial content, not just the final string).
      const assistantBubble = page.locator(".codirector-msg.assistant .codirector-msg-bubble").last();
      await expect(assistantBubble).not.toHaveText("", { timeout: 5_000 });

      await expect(page.getByRole("button", { name: "Send message" })).toBeVisible({ timeout: 10_000 });
      await expect(assistantBubble).toContainText("[mock]", { timeout: 10_000 });

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);

      observer.assertHealthyBrowser();
    } finally {
      await setMockScenario(request, null);
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("Stop Generating cancels the turn without showing an error and preserves the transcript", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir Cancel ${Date.now()}`);

    try {
      await setMockScenario(request, "slow");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Draft a long scene breakdown for me please.");

      const stopButton = page.getByRole("button", { name: "Stop generating" });
      await expect(stopButton).toBeVisible({ timeout: 5_000 });
      await stopButton.click();

      // Composer returns to normal (Send button back, not stuck busy) and no error card appears.
      await expect(page.getByRole("button", { name: "Send message" })).toBeVisible({ timeout: 10_000 });
      await expect(page.locator(".codirector-error-card")).toHaveCount(0);

      // The user's message must still be there — a cancel is not a failure.
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(
        "Draft a long scene breakdown for me please.",
      );

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);

      observer.assertHealthyBrowser();
    } finally {
      await setMockScenario(request, null);
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("retrying a failed send does not duplicate the user's message", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir RetryDedupe ${Date.now()}`);
    const text = "Unique retry probe message.";

    try {
      await setMockScenario(request, "connection_refused");
      await openCoDirector(page, project.id);
      await sendMessage(page, text);

      const errorCard = page.locator(".codirector-error-card");
      await expect(errorCard).toBeVisible({ timeout: 20_000 });

      // Fix the provider, then retry from the error card (not the composer) — this must
      // resend the existing transcript, not append a second copy of the user's message.
      await setMockScenario(request, null);
      await errorCard.getByRole("button", { name: "Retry" }).click();

      const assistantBubble = page.locator(".codirector-msg.assistant .codirector-msg-bubble").last();
      await expect(assistantBubble).toContainText("[mock]", { timeout: 20_000 });

      const userBubbles = page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: text });
      await expect(userBubbles).toHaveCount(1);

      observer.assertHealthyBrowser();
    } finally {
      await setMockScenario(request, null);
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("conversation persists across a reload via the server-side conversation API", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir Persist ${Date.now()}`);
    const text = "Persistence probe message.";

    try {
      await openCoDirector(page, project.id);
      await sendMessage(page, text);

      const assistantBubble = page.locator(".codirector-msg.assistant .codirector-msg-bubble").last();
      await expect(assistantBubble).toContainText("[mock]", { timeout: 20_000 });

      // The gateway persists the turn server-side; confirm directly before reloading the page.
      const convoRes = await request.get(`${API}/api/codirector/conversations/${project.id}`);
      expect(convoRes.ok()).toBeTruthy();
      const convo = await convoRes.json();
      expect(convo.messages.some((m: { role: string; content: string }) => m.role === "user" && m.content === text)).toBe(
        true,
      );

      await page.reload();
      await openCoDirector(page, project.id);

      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: text })).toHaveCount(1, {
        timeout: 15_000,
      });
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble", { hasText: "[mock]" })).toHaveCount(
        1,
      );

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
