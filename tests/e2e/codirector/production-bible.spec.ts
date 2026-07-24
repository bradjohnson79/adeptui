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

async function openBibleWorkspace(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=bible`);
  await expect(page.getByRole("heading", { name: "Production Bible" })).toBeVisible({ timeout: 30_000 });
}

/** Creates the Bible for a project directly via the API (import preview -> confirm) so tests
 * that only care about a *later* step (proposals, staleness) don't repeat the import UI flow. */
async function createBibleViaApi(request: APIRequestContext, projectId: string) {
  const preview = await (
    await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/preview`, { data: {} })
  ).json();
  const res = await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/confirm`, {
    data: { entities: preview.entities, facts: preview.facts, summary: preview.summary },
  });
  expect(res.ok()).toBeTruthy();
  return res.json();
}

/**
 * Co-Director Milestone 2.1: versioned Production Bible + durable proposal approvals.
 * Covers the two contractual guarantees the plan calls out: (1) the model can never mutate
 * the Bible directly — proposals always require an explicit user decision, and (2) staleness
 * is detected and surfaced rather than silently double-applied.
 */
test.describe("@critical @isolated codirector production bible", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("import preview -> confirm creates version 1 in the Bible workspace", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Import ${Date.now()}`);

    try {
      await openBibleWorkspace(page, project.id);
      await expect(page.getByText("This project doesn't have a Production Bible yet.")).toBeVisible();

      await page.getByRole("button", { name: "Import from project" }).click();
      await expect(page.getByRole("heading", { name: "Create Production Bible — Preview" })).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.locator(".ms-list").first()).toContainText(/project_profile/i);

      await page.getByRole("button", { name: "Confirm — create version 1" }).click();
      await expect(page.getByRole("heading", { name: "Production Bible" })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText(/Version 1 of 1/)).toBeVisible({ timeout: 15_000 });

      const bible = await (await request.get(`${API}/api/codirector/projects/${project.id}/bible`)).json();
      expect(bible.currentVersion.versionNumber).toBe(1);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("approving a Co-Director proposal creates a new Bible version — the model never writes directly", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Approve ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      await setMockScenario(request, "proposal_character_update");

      await openCoDirector(page, project.id);
      await sendMessage(page, "She has a scar now, established in this scene.");

      const proposalCard = page.locator(".codirector-proposal-card");
      await expect(proposalCard).toBeVisible({ timeout: 20_000 });
      await expect(proposalCard.locator(".codirector-proposal-title")).toContainText("Update Ava's appearance");
      // The raw ```proposal JSON fence must never be shown to the user.
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).not.toContainText(
        "```proposal",
      );

      await proposalCard.getByRole("button", { name: "Approve" }).click();
      await expect(proposalCard).toBeHidden({ timeout: 20_000 });
      await expect(
        page.locator(".codirector-msg.assistant .codirector-msg-bubble").last(),
      ).toContainText(/approved and applied/i);

      const bible = await (await request.get(`${API}/api/codirector/projects/${project.id}/bible`)).json();
      expect(bible.currentVersion.versionNumber).toBe(2);
      const ava = bible.currentVersion.entities.find((e: { entityKey: string }) => e.entityKey === "ava");
      expect(ava).toBeTruthy();
      expect(JSON.stringify(ava.data)).toContain("scar");

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});

test.describe("@isolated codirector production bible secondary flows", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("manually adding an entity in the Bible workspace creates a new version", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Manual ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      await openBibleWorkspace(page, project.id);
      await expect(page.getByText(/Version 1 of 1/)).toBeVisible({ timeout: 15_000 });

      await page.locator(".page select").first().selectOption("character");
      await page.getByPlaceholder("key (e.g. ava)").fill("nova");
      await page.getByPlaceholder("Display name").fill("Nova");
      await page.getByPlaceholder("Description").fill("A new supporting character.");
      await page.getByRole("button", { name: "Add (new version)" }).click();

      await expect(page.getByText("New Bible version created.")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText(/Version 2 of 2/)).toBeVisible({ timeout: 15_000 });
      await expect(page.locator(".ms-list strong", { hasText: "Nova" })).toBeVisible();

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("rejecting a proposal discards it without touching the Bible", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Reject ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      await setMockScenario(request, "proposal_character_update");

      await openCoDirector(page, project.id);
      await sendMessage(page, "Update her look.");

      const proposalCard = page.locator(".codirector-proposal-card");
      await expect(proposalCard).toBeVisible({ timeout: 20_000 });
      await proposalCard.getByRole("button", { name: "Reject" }).click();
      await expect(proposalCard).toBeHidden({ timeout: 20_000 });

      const bible = await (await request.get(`${API}/api/codirector/projects/${project.id}/bible`)).json();
      expect(bible.currentVersion.versionNumber).toBe(1);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("a malformed proposal fence surfaces a structured error, never raw JSON", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Malformed ${Date.now()}`);

    try {
      await setMockScenario(request, "malformed_proposal");
      await openCoDirector(page, project.id);
      await sendMessage(page, "Propose a change.");

      const errorCard = page.locator(".codirector-error-card");
      await expect(errorCard).toBeVisible({ timeout: 20_000 });
      await expect(errorCard).toContainText(/proposal/i);

      // The assistant's reply still finishes and is shown (cleaned) — the malformed fence is
      // non-fatal for the turn; only the raw JSON block itself must never reach the user.
      await expect(page.locator(".codirector-msg.assistant .codirector-msg-bubble").last()).toContainText("[mock]");

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/"entityMutations"/);
      expect(bodyText).not.toMatch(/```proposal/);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("a proposal that goes stale can only be cancelled, never approved as-is", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `Bible Stale ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      await setMockScenario(request, "proposal_character_update");

      await openCoDirector(page, project.id);
      await sendMessage(page, "Update her look.");

      const proposalCard = page.locator(".codirector-proposal-card");
      await expect(proposalCard).toBeVisible({ timeout: 20_000 });
      await setMockScenario(request, null);

      // The Bible moves on independently of the pending proposal — it's now stale.
      const bumpRes = await request.post(`${API}/api/codirector/projects/${project.id}/bible/versions`, {
        data: {
          mutations: {
            entityMutations: [{ entityType: "prop", entityKey: "lantern", displayName: "Lantern" }],
            factMutations: [],
          },
        },
      });
      expect(bumpRes.ok()).toBeTruthy();

      // Force the panel to refetch proposals against the now-current Bible version.
      await page.reload();
      await openCoDirector(page, project.id);

      const staleCard = page.locator(".codirector-proposal-card");
      await expect(staleCard).toBeVisible({ timeout: 20_000 });
      await expect(staleCard.locator(".codirector-proposal-stale")).toBeVisible();
      await expect(staleCard.getByRole("button", { name: "Approve" })).toHaveCount(0);

      await staleCard.getByRole("button", { name: "Cancel proposal" }).click();
      await expect(staleCard).toBeHidden({ timeout: 20_000 });

      const bible = await (await request.get(`${API}/api/codirector/projects/${project.id}/bible`)).json();
      expect(bible.currentVersion.versionNumber).toBe(2);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
