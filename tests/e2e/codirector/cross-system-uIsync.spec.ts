import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

/**
 * c5-cross-system UI synchronization certification (Phase 12).
 *
 * Certifies that the creator-facing native UI (Timeline / Scene Inspector)
 * reflects a Co-Director tool mutation AFTER the creator approves the
 * proposal card in the Co-Director panel — WITHOUT a manual page reload.
 *
 * The scripted mock provider (ADEPT_CODIRECTOR_PROVIDER=mock +
 * ADEPT_CODIRECTOR_MOCK_SCENARIO=scripted) emits deterministic
 * `mutation_proposal` tool fences so the chat path produces a real approval
 * card whose approve runs the REAL apply handler (no handler mocked). The
 * e2e-start.mjs webServer boots the API + Vite with STUDIO_E2E=1 so the
 * /api/e2e/codirector/* controls are mounted.
 *
 * What this spec asserts:
 *   - Approving a `timeline.propose_add_batch` proposal card causes the
 *     Timeline batch lane to show the new batch with no manual reload.
 *   - Approving a `set_scene_prompt` proposal card causes the Scene
 *     Prompt field in the Inspector to update with no manual reload.
 *
 * If the app's own refresh mechanism does NOT pick the change up, the test
 * fails — that is the honest UI-sync evidence (Build Law #31). The audit doc
 * (CODIRECTOR_CROSS_SYSTEM_WORKFLOW_AUDIT.md §4.1.2/§4.1.3) flags that
 * `approveProposal` only dispatches `adept:codirector-plan-workspace-refresh`
 * for `production_plan.*` tools and that the Timeline/Scene UI has no
 * post-approve refresh listener; this spec makes that gap executable.
 */

async function setScenario(request: APIRequestContext, scenario: string | null) {
  const res = await request.post(`${API}/api/e2e/codirector/scenario`, { data: { scenario } });
  expect(res.ok(), `set scenario ${scenario}`).toBeTruthy();
}

async function installScript(request: APIRequestContext, steps: Record<string, unknown>[]) {
  const res = await request.post(`${API}/api/e2e/codirector/script`, { data: { steps } });
  expect(res.ok(), "install script").toBeTruthy();
}

async function clearScript(request: APIRequestContext) {
  await request.delete(`${API}/api/e2e/codirector/script`);
  await setScenario(request, null);
}

async function firstSceneId(request: APIRequestContext, projectId: string): Promise<string> {
  const project = await (await request.get(`${API}/api/projects/${projectId}`)).json();
  const scenes = project.scenes as { id: string }[];
  expect(scenes.length, "project has a default scene").toBeGreaterThan(0);
  return scenes[0].id;
}

async function openCoDirector(page: Page, _projectId: string) {
  // The Co-Director panel is opened from the top-nav chrome button
  // (data-testid="chrome-codirector"), present on every workspace including
  // Timeline. The landing page also has a floating `button.codirector-fab`.
  // The Timeline right-rail "Co-Director" tab is only a placeholder that itself
  // calls openCoDirector(), so we open the real panel via the chrome button.
  const chromeBtn = page.getByTestId("chrome-codirector");
  const fab = page.locator("button.codirector-fab");
  const opener = await Promise.race([
    chromeBtn.waitFor({ state: "visible", timeout: 30_000 }).then(() => "chrome" as const),
    fab.waitFor({ state: "visible", timeout: 30_000 }).then(() => "fab" as const),
  ]);
  if (opener === "chrome") {
    await chromeBtn.click();
  } else {
    await fab.click();
  }
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

async function sendMessage(page: Page, text: string) {
  await page.getByLabel("Message Co-Director").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

async function batchCount(page: Page): Promise<number> {
  // c5: in the Timeline Generator workspace, batch blocks are rendered in the
  // bottom track lane (data-testid="timeline-batch-lane"), not the separate
  // Timeline Master panel.
  const lane = page.getByTestId("timeline-batch-lane");
  await expect(lane).toBeVisible({ timeout: 30_000 });
  return await lane.locator("button[data-testid^='timeline-batch-']").count();
}

test.describe("@isolated codirector cross-system UI sync", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await clearScript(request);
  });

  test.afterEach(async ({ request }) => {
    await clearScript(request);
  });

  test("approving a timeline.propose_add_batch card updates the Timeline batch lane without a reload", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Cross UISync Batch ${Date.now()}`);

    try {
      const sid = await firstSceneId(request, project.id);
      // Scripted mock: a creator message matching "add a timeline batch" emits a
      // mutation_proposal fence for timeline.propose_add_batch. timelineRevision is
      // intentionally omitted so the apply handler skips the revision guard.
      await setScenario(request, "scripted");
      await installScript(request, [
        {
          match: "add a timeline batch",
          reply: "[mock] I'd like to add a new batch to the Timeline. Nothing changes until you approve it.",
          tool: {
            toolId: "timeline.propose_add_batch",
            responseType: "mutation_proposal",
            arguments: {
              sceneId: sid,
              label: "Co-Director Batch",
              plannedDuration: 4.0,
            },
          },
          followUpReply: "[mock] Approved — the new batch is on your Timeline now.",
        },
      ]);

      // Open the Timeline workspace and capture the initial batch count.
      await page.goto(`/project/${project.id}?workspace=timeline`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 30_000 });
      const before = await batchCount(page);

      // Open Co-Director and ask for the batch.
      await openCoDirector(page, project.id);
      await sendMessage(page, "Please add a timeline batch for the rooftop beat.");

      // Approve the proposal card — this runs the REAL apply handler.
      const card = page.locator(".codirector-proposal-card");
      await expect(card).toBeVisible({ timeout: 30_000 });
      await expect(card).toContainText(/needs your approval/i);
      await card.getByRole("button", { name: "Approve" }).click();
      await expect(card).toBeHidden({ timeout: 30_000 });

      // UI SYNC assertion: the Timeline batch lane must show the new batch
      // WITHOUT a manual page reload (the app's own refresh mechanism).
      await expect
        .poll(async () => batchCount(page), { timeout: 30_000 })
        .toBeGreaterThan(before);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("approving a set_scene_prompt card updates the Scene Prompt field without a reload", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Cross UISync ScenePrompt ${Date.now()}`);

    try {
      const sid = await firstSceneId(request, project.id);
      const newPrompt = "Co-Director scene prompt update — slow dolly through the rain.";
      await setScenario(request, "scripted");
      await installScript(request, [
        {
          match: "update the scene prompt",
          reply: "[mock] I'd like to update the Scene Prompt. Nothing changes until you approve it.",
          tool: {
            toolId: "set_scene_prompt",
            responseType: "mutation_proposal",
            arguments: {
              sceneId: sid,
              prompt: newPrompt,
            },
          },
          followUpReply: "[mock] Approved — the Scene Prompt is updated now.",
        },
      ]);

      // Open the Timeline workspace (Inspector shows the Scene Prompt field).
      await page.goto(`/project/${project.id}?workspace=timeline`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 30_000 });
      const promptField = page.getByTestId("timeline-scene-prompt");
      await expect(promptField).toBeVisible({ timeout: 30_000 });
      const before = (await promptField.inputValue()) || "";

      // Open Co-Director and ask for the scene prompt update.
      await openCoDirector(page, project.id);
      await sendMessage(page, "Please update the scene prompt for the rooftop beat.");

      const card = page.locator(".codirector-proposal-card");
      await expect(card).toBeVisible({ timeout: 30_000 });
      await card.getByRole("button", { name: "Approve" }).click();
      await expect(card).toBeHidden({ timeout: 30_000 });

      // UI SYNC assertion: the Scene Prompt field must reflect the new prompt
      // WITHOUT a manual page reload.
      await expect(promptField).toHaveValue(newPrompt, { timeout: 30_000 });
      expect(before).not.toBe(newPrompt);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
