import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

async function setMockScenario(request: APIRequestContext, scenario: string | null) {
  const res = await request.post(`${API}/api/e2e/codirector/scenario`, { data: { scenario } });
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
  await page.getByLabel("Message Co-Director").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

async function sceneNames(request: APIRequestContext, projectId: string): Promise<string[]> {
  const project = await (await request.get(`${API}/api/projects/${projectId}`)).json();
  return (project.scenes as { name: string }[]).map((s) => s.name);
}

async function invocations(request: APIRequestContext, projectId: string) {
  const body = await (await request.get(`${API}/api/codirector/projects/${projectId}/tool-invocations`)).json();
  return body.invocations as { toolId: string; status: string; kind: string; proposalId: string | null }[];
}

/**
 * Co-Director Milestone 2.2: the bounded tool registry.
 *
 * These specs exist to pin the two guarantees the registry is built around, from the browser's
 * point of view: a read tool may run on its own but can only ever *read*, and anything that
 * changes the project appears as an approval card first — the model never applies it. Each test
 * therefore asserts the state of the project both before and after the user's decision.
 */
test.describe("@critical @isolated codirector bounded tools", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("a read tool runs inline, shows a status line, and never leaks the tool fence", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Read ${Date.now()}`);

    try {
      await setMockScenario(request, "read_tool_success");
      await openCoDirector(page, project.id);
      await sendMessage(page, "How many scenes are in this project?");

      const status = page.locator(".codirector-tool-status");
      await expect(status).toBeVisible({ timeout: 20_000 });
      await expect(status).toContainText(/list scenes/i);

      // The follow-up answer is what lands in the transcript — not the model's tool request.
      const lastBubble = page.locator(".codirector-msg.assistant .codirector-msg-bubble").last();
      await expect(lastBubble).toContainText(/Based on that lookup/i, { timeout: 20_000 });

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/```tool/);
      expect(bodyText).not.toMatch(/"responseType"/);

      const ledger = await invocations(request, project.id);
      expect(ledger.filter((i) => i.toolId === "list_scenes" && i.status === "succeeded")).toHaveLength(1);
      // A read tool must not have changed anything.
      expect(await sceneNames(request, project.id)).toEqual(["Scene 1"]);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("a mutating tool becomes an approval card and only applies after Approve", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Approve ${Date.now()}`);

    try {
      await setMockScenario(request, "mutation_tool_execution_success");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Add a rooftop standoff scene.");

      const card = page.locator(".codirector-proposal-card");
      await expect(card).toBeVisible({ timeout: 20_000 });
      await expect(card).toContainText(/needs your approval/i);
      await expect(card.locator(".codirector-proposal-title")).toContainText(/scene/i);

      // Nothing is applied while the card is pending — this is the whole invariant.
      expect(await sceneNames(request, project.id)).toEqual(["Scene 1"]);

      await card.getByRole("button", { name: "Approve" }).click();
      await expect(card).toBeHidden({ timeout: 20_000 });
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(
        /Approved/i,
      );

      expect(await sceneNames(request, project.id)).toEqual(["Scene 1", "Rooftop Standoff"]);
      const ledger = await invocations(request, project.id);
      const applied = ledger.find((i) => i.toolId === "create_scene");
      expect(applied?.status).toBe("succeeded");
      expect(applied?.proposalId).toBeTruthy();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("rejecting a tool proposal leaves the project untouched", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Reject ${Date.now()}`);

    try {
      await setMockScenario(request, "mutation_tool_proposal");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Add a rooftop standoff scene.");

      const card = page.locator(".codirector-proposal-card");
      await expect(card).toBeVisible({ timeout: 20_000 });
      await card.getByRole("button", { name: "Reject" }).click();
      await expect(card).toBeHidden({ timeout: 20_000 });

      expect(await sceneNames(request, project.id)).toEqual(["Scene 1"]);
      expect(await invocations(request, project.id)).toEqual([]);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});

test.describe("@isolated codirector bounded tools secondary flows", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("a blocked capability is reported plainly and the turn still finishes", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Blocked ${Date.now()}`);

    try {
      await setMockScenario(request, "read_tool_blocked_capability");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Is the render backend ready?");

      const status = page.locator(".codirector-tool-status");
      await expect(status).toBeVisible({ timeout: 20_000 });
      await expect(status).toContainText(/couldn't check/i);

      // A blocked tool is not a failed turn: the assistant still answers.
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(/\S/, {
        timeout: 20_000,
      });

      const ledger = await invocations(request, project.id);
      expect(ledger[0]?.status).toBe("blocked");

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("an unconfigured capability blocks the tool without breaking the chat", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Unconfigured ${Date.now()}`);

    try {
      await setMockScenario(request, "capability_not_configured");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Can you use visual references here?");

      await expect(page.locator(".codirector-tool-status")).toContainText(/couldn't check/i, { timeout: 20_000 });
      const ledger = await invocations(request, project.id);
      expect(ledger[0]?.status).toBe("blocked");
      expect(await sceneNames(request, project.id)).toEqual(["Scene 1"]);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("a tool proposal that goes stale can only be cancelled", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Stale ${Date.now()}`);

    try {
      await setMockScenario(request, "mutation_tool_stale");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Add a rooftop standoff scene.");
      await expect(page.locator(".codirector-proposal-card")).toBeVisible({ timeout: 20_000 });
      await setMockScenario(request, null);

      // The project moves on underneath the pending proposal.
      const added = await request.post(`${API}/api/projects/${project.id}/scenes`, {
        data: { name: "Added Meanwhile" },
      });
      expect(added.ok()).toBeTruthy();

      await page.reload();
      await openCoDirector(page, project.id);

      const staleCard = page.locator(".codirector-proposal-card");
      await expect(staleCard).toBeVisible({ timeout: 20_000 });
      await expect(staleCard.locator(".codirector-proposal-stale")).toBeVisible();
      await expect(staleCard.getByRole("button", { name: "Approve" })).toHaveCount(0);

      await staleCard.getByRole("button", { name: "Cancel proposal" }).click();
      await expect(staleCard).toBeHidden({ timeout: 20_000 });

      expect(await sceneNames(request, project.id)).toEqual(["Scene 1", "Added Meanwhile"]);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("a tool that fails while applying reports the failure and changes nothing", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `Tools Exec Fail ${Date.now()}`);

    try {
      await setMockScenario(request, "mutation_tool_execution_failure");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Add a rooftop standoff scene.");

      const card = page.locator(".codirector-proposal-card");
      await expect(card).toBeVisible({ timeout: 20_000 });
      await card.getByRole("button", { name: "Approve" }).click();

      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText(
        /couldn't approve/i,
        { timeout: 20_000 },
      );
      expect(await sceneNames(request, project.id)).toEqual(["Scene 1"]);

      // The failure is durable evidence, not just a chat message: the attempt is logged and the
      // proposal is left in a terminal `failed` state rather than silently retryable.
      const ledger = await invocations(request, project.id);
      expect(ledger[0]?.status).toBe("failed");
      const proposals = await (
        await request.get(`${API}/api/codirector/projects/${project.id}/proposals`)
      ).json();
      expect(proposals.proposals[0].status).toBe("failed");

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("the tool catalog and availability are exposed for the open project", async ({ request }) => {
    const project = await createTempProject(request, `Tools Catalog ${Date.now()}`);

    try {
      const catalog = await (await request.get(`${API}/api/codirector/tools`)).json();
      const ids = (catalog.tools as { toolId: string }[]).map((t) => t.toolId);
      // The registry is closed: the catalog must be exactly this set. A new tool has to be
      // added here deliberately, which is the point — no shell, filesystem, SQL, or
      // arbitrary-execution tool can appear without this assertion failing first.
      expect([...ids].sort()).toEqual(
        [
          "create_scene",
          "get_active_scene",
          "get_bible_entity",
          "get_comfyui_health",
          "get_current_bible_version",
          "get_engine_capabilities",
          "get_project_profile",
          "get_project_status",
          "get_provider_health",
          "get_reference_capabilities",
          "get_relevant_bible_context",
          "get_scene",
          "get_selected_model",
          "get_source_manager_status",
          "list_bible_entities",
          "list_scenes",
          "record_director_decision",
          "set_scene_prompt",
          "update_scene_title",
        ].sort(),
      );

      const availability = await (
        await request.get(`${API}/api/codirector/projects/${project.id}/tools/availability`)
      ).json();
      const listScenes = (availability.availability as { toolId: string; available: boolean }[]).find(
        (a) => a.toolId === "list_scenes",
      );
      expect(listScenes?.available).toBeTruthy();

      // A mutating tool cannot be run through the read endpoint.
      const attempt = await request.post(`${API}/api/codirector/projects/${project.id}/tools/read`, {
        data: { toolId: "create_scene", arguments: { name: "Sneaky" } },
      });
      expect(attempt.status()).toBe(400);
      expect((await attempt.json()).detail.code).toBe("TOOL_KIND_MISMATCH");
      const project_ = await (await request.get(`${API}/api/projects/${project.id}`)).json();
      expect(project_.scenes).toHaveLength(1);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
