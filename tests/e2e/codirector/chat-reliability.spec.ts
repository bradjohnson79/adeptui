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
  // Scoped to the global FAB's own class — the page also has "Ask Co-Director" launcher
  // buttons and a banner button whose accessible names contain "Co-Director" as a substring.
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
 * These specs exercise the provider-neutral Co-Director gateway (/api/codirector/*) end to
 * end through the mock provider (STUDIO_E2E defaults ADEPT_CODIRECTOR_PROVIDER=mock). The
 * core regression they guard against: the browser must never render a bare
 * "Failed to fetch" / "I couldn't reach the local model." string, regardless of provider state.
 */
test.describe("@critical @isolated codirector chat reliability", () => {
  test.beforeEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("ready mock provider completes a chat turn", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir Ready ${Date.now()}`);

    try {
      await openCoDirector(page, project.id);
      await sendMessage(page, "Tell me about writing a script for this scene.");

      const assistantBubble = page.locator(".codirector-msg.assistant .codirector-msg-bubble").last();
      await expect(assistantBubble).toContainText("[mock]", { timeout: 20_000 });

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);
      expect(bodyText).not.toMatch(/I couldn't reach the local model/i);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("provider unavailable surfaces a structured error, never a bare fetch failure", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir Down ${Date.now()}`);

    try {
      await setMockScenario(request, "connection_refused");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Build a scene for me.");

      const errorCard = page.locator(".codirector-error-card");
      await expect(errorCard).toBeVisible({ timeout: 20_000 });
      await expect(errorCard).toContainText(/could not reach|offline|unavailable/i);
      await expect(errorCard.getByRole("button", { name: "Retry" })).toBeVisible();
      await expect(errorCard.getByRole("button", { name: "Open Settings" })).toBeVisible();

      // The user's message must be preserved in the transcript, not silently dropped.
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(
        "Build a scene for me.",
      );

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);
      expect(bodyText).not.toMatch(/I couldn't reach the local model/i);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("no models installed blocks send with an actionable message", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `CoDir NoModels ${Date.now()}`);

    try {
      await setMockScenario(request, "no_models");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Write me a prompt.");

      const errorCard = page.locator(".codirector-error-card");
      await expect(errorCard).toBeVisible({ timeout: 20_000 });
      await expect(errorCard).toContainText(/model/i);

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/failed to fetch/i);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("health endpoint classifies mock scenarios via the gateway", async ({ request }) => {
    await waitForAppReady(request);

    await setMockScenario(request, "connection_refused");
    let health = await (await request.get(`${API}/api/codirector/providers/mock/health`)).json();
    expect(health.reachable).toBe(false);
    expect(health.code).toBe("CONNECTION_REFUSED");

    await setMockScenario(request, "no_models");
    health = await (await request.get(`${API}/api/codirector/providers/mock/health`)).json();
    expect(health.reachable).toBe(true);
    expect(health.modelAvailable).toBe(false);
    expect(health.code).toBe("NO_MODELS_INSTALLED");

    await setMockScenario(request, null);
    health = await (await request.get(`${API}/api/codirector/providers/active/health`)).json();
    expect(health.status).toBe("Ready");
    expect(health.reachable).toBe(true);
  });
});
