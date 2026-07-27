import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

/**
 * M3.0 Completion Phase 2 (blocker B10): a Bible proposal approved in the browser must
 * really apply, and a rejected one must change nothing.
 *
 * The defect this guards was invisible until apply time: the mock provider proposed a
 * character field name that `CharacterData` forbids, so the user clicked Approve and the
 * write failed afterwards. Both outcomes are therefore read back from the API rather than
 * inferred from the toast.
 */

async function setMockScenario(request: APIRequestContext, scenario: string | null) {
  const res = await request.post(`${API}/api/e2e/codirector/scenario`, { data: { scenario } });
  expect(res.ok()).toBeTruthy();
}

async function createBibleViaApi(request: APIRequestContext, projectId: string) {
  const preview = await (
    await request.post(`${API}/api/codirector/projects/${projectId}/bible/import/preview`, {
      data: {},
    })
  ).json();
  const res = await request.post(
    `${API}/api/codirector/projects/${projectId}/bible/import/confirm`,
    { data: { entities: preview.entities, facts: preview.facts, summary: preview.summary } },
  );
  expect(res.ok()).toBeTruthy();
}

async function readBible(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/bible`);
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<{
    currentVersion: {
      versionNumber: number;
      entities: Array<{ entityKey: string; data: Record<string, string> }>;
    };
  }>;
}

async function openCoDirectorAndPropose(page: Page, projectId: string, message: string) {
  await page.goto(`/project/${projectId}`);
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  await fab.click();
  const textarea = page.getByLabel("Message Co-Director");
  await expect(textarea).toBeVisible({ timeout: 15_000 });
  await textarea.fill(message);
  await page.getByRole("button", { name: "Send message" }).click();
  const card = page.locator(".codirector-proposal-card");
  await expect(card).toBeVisible({ timeout: 20_000 });
  return card;
}

test.describe("@critical @isolated m30-completion bible apply in browser (B10)", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
    await setMockScenario(request, null);
  });

  test.afterEach(async ({ request }) => {
    await setMockScenario(request, null);
  });

  test("approving in the browser writes version 2 with the character detail", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `B10 Approve ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      await setMockScenario(request, "proposal_character_update");

      const card = await openCoDirectorAndPropose(
        page,
        project.id,
        "She has a scar now, established in this scene.",
      );
      await card.getByRole("button", { name: "Approve" }).click();
      await expect(card).toBeHidden({ timeout: 20_000 });

      const bible = await readBible(request, project.id);
      expect(bible.currentVersion.versionNumber).toBe(2);
      const ava = bible.currentVersion.entities.find((e) => e.entityKey === "ava");
      expect(ava, "approved proposal must create the character entity").toBeTruthy();
      // The exact field CharacterData accepts — the old `appearance` key failed at apply.
      expect(ava?.data.appearanceSummary).toContain("scar");

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("rejecting in the browser leaves the Bible at version 1", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    const project = await createTempProject(request, `B10 Reject ${Date.now()}`);

    try {
      await createBibleViaApi(request, project.id);
      const before = await readBible(request, project.id);
      expect(before.currentVersion.versionNumber).toBe(1);

      await setMockScenario(request, "proposal_character_update");
      const card = await openCoDirectorAndPropose(page, project.id, "Update her look.");
      await card.getByRole("button", { name: "Reject" }).click();
      await expect(card).toBeHidden({ timeout: 20_000 });

      const after = await readBible(request, project.id);
      expect(after.currentVersion.versionNumber).toBe(1);
      expect(after.currentVersion.entities.some((e) => e.entityKey === "ava")).toBe(false);

      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("the proposed payload only uses fields the Bible schema accepts", async ({ request }) => {
    const project = await createTempProject(request, `B10 Shape ${Date.now()}`);
    try {
      await createBibleViaApi(request, project.id);
      await setMockScenario(request, "proposal_character_update");

      const chat = await request.post(`${API}/api/codirector/chat`, {
        data: {
          messages: [{ role: "user", content: "She has a scar now" }],
          project_id: project.id,
        },
      });
      expect(chat.ok()).toBeTruthy();
      const proposal = (await chat.json()).proposal;
      const data = proposal.payload.entityMutations[0].data as Record<string, unknown>;
      expect(Object.keys(data)).toContain("appearanceSummary");
      expect(Object.keys(data)).not.toContain("appearance");

      // Approving over the API must succeed, not just look approved in the UI.
      const receipt = await request.post(
        `${API}/api/codirector/projects/${project.id}/proposals/${proposal.id}/approve`,
        { data: { decidedBy: "user" } },
      );
      expect(receipt.ok()).toBeTruthy();
      expect((await receipt.json()).status).toBe("success");
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
