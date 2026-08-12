import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join("docs", "release-gate", "home", "artifacts", "entry-contract");
const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
const MANUAL_HANDOFF_NAME = "Manual Beta Handoff";
const RUN_ID = `ENTRY-CLOSURE-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const RECENT_KEY = "adept_ui_recent_projects";

type ProjectSummary = {
  id: string;
  name: string;
  archived?: number;
  asset_count?: number;
  scene_count?: number;
};

type HandoffSnapshot = {
  id: string;
  name: string;
  apiStatus: number;
  api200: boolean;
  sceneCount: number;
  assetCount: number;
  chatCount: number;
  wikiCount: number;
  planCount: number;
  proposalCount: number;
  approvalCount: number;
  jobCount: number;
  exportCount: number;
};

function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

function writeJson(filename: string, value: unknown) {
  fs.writeFileSync(path.join(ARTIFACT_DIR, filename), JSON.stringify(value, null, 2));
}

function uniqueIds(ids: Iterable<string>) {
  return Array.from(new Set(Array.from(ids).filter(Boolean)));
}

function projectIdFromUrl(url: string): string | null {
  return (
    /\/project\/([^/?#]+)/.exec(url)?.[1]
    || /[?&]projectId=([^&#]+)/.exec(url)?.[1]
    || null
  );
}

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary[];
}

async function createDisposableProject(request: APIRequestContext, suffix: string): Promise<ProjectSummary> {
  const name = `${RUN_ID} ${suffix}`;
  const res = await request.post(`${API}/api/projects`, { data: { name } });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary;
}

async function archiveProject(request: APIRequestContext, projectId: string, archived: boolean) {
  const res = await request.post(`${API}/api/projects/${projectId}/archive?archived=${archived ? "true" : "false"}`);
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function deleteProjectIfPresent(request: APIRequestContext, projectId: string) {
  const res = await request.delete(`${API}/api/projects/${projectId}`);
  if (res.status() === 404) {
    return;
  }
  expect(res.ok(), await res.text()).toBeTruthy();
}

async function getConversationCount(request: APIRequestContext, projectId: string): Promise<number> {
  const res = await request.get(`${API}/api/codirector/conversations/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return Array.isArray(body.messages) ? body.messages.length : 0;
}

async function getWikiCount(request: APIRequestContext, projectId: string): Promise<number> {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.hasContent ? 1 : 0;
}

async function getPlanCount(request: APIRequestContext, projectId: string): Promise<number> {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/plans/active`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.status === "active" && body.plan ? 1 : 0;
}

async function getProposalCounts(request: APIRequestContext, projectId: string): Promise<{ total: number; approved: number }> {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/proposals`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const proposals = Array.isArray(body.proposals) ? body.proposals : [];
  return {
    total: proposals.length,
    approved: proposals.filter((proposal: { status?: string }) =>
      String(proposal.status || "").toLowerCase().includes("approved")).length,
  };
}

async function getJobCounts(request: APIRequestContext, projectId: string): Promise<{ total: number; exportCount: number }> {
  const res = await request.get(`${API}/api/projects/${projectId}/jobs`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const jobs = (await res.json()) as Array<{ kind?: string }>;
  return {
    total: jobs.length,
    exportCount: jobs.filter((job) => job.kind === "export").length,
  };
}

async function captureHandoffSnapshot(request: APIRequestContext): Promise<HandoffSnapshot> {
  const res = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);
  const apiStatus = res.status();
  expect(apiStatus, await res.text()).toBe(200);
  const project = (await res.json()) as ProjectSummary & {
    assets?: Array<unknown>;
    scenes?: Array<unknown>;
  };
  const proposalCounts = await getProposalCounts(request, MANUAL_HANDOFF_ID);
  const jobCounts = await getJobCounts(request, MANUAL_HANDOFF_ID);
  return {
    id: project.id,
    name: project.name,
    apiStatus,
    api200: res.ok(),
    sceneCount: project.scene_count ?? project.scenes?.length ?? 0,
    assetCount: project.asset_count ?? project.assets?.length ?? 0,
    chatCount: await getConversationCount(request, MANUAL_HANDOFF_ID),
    wikiCount: await getWikiCount(request, MANUAL_HANDOFF_ID),
    planCount: await getPlanCount(request, MANUAL_HANDOFF_ID),
    proposalCount: proposalCounts.total,
    approvalCount: proposalCounts.approved,
    jobCount: jobCounts.total,
    exportCount: jobCounts.exportCount,
  };
}

function expectEmptyHandoff(snapshot: HandoffSnapshot) {
  expect(snapshot.id).toBe(MANUAL_HANDOFF_ID);
  expect(snapshot.name).toBe(MANUAL_HANDOFF_NAME);
  expect(snapshot.api200).toBeTruthy();
  expect(snapshot.sceneCount).toBeLessThanOrEqual(1);
  expect(snapshot.assetCount).toBe(0);
  expect(snapshot.chatCount).toBe(0);
  expect(snapshot.wikiCount).toBe(0);
  expect(snapshot.planCount).toBe(0);
  expect(snapshot.proposalCount).toBe(0);
  expect(snapshot.approvalCount).toBe(0);
  expect(snapshot.jobCount).toBe(0);
  expect(snapshot.exportCount).toBe(0);
}

function monitorProjectCreatePosts(page: Page) {
  let count = 0;
  const handler = (req: { method: () => string; url: () => string }) => {
    try {
      const url = new URL(req.url());
      if (req.method() === "POST" && url.pathname === "/api/projects") {
        count += 1;
      }
    } catch {
      /* ignore */
    }
  };
  page.on("request", handler);
  return {
    getCount: () => count,
    dispose: () => page.off("request", handler),
  };
}

async function openChromeCreateProject(page: Page) {
  await page.getByTestId("ds-menubar").getByRole("button", { name: /^Project$/ }).click();
  await page.getByRole("menuitem", { name: "Create project" }).click();
}

async function openSetupWizard(page: Page) {
  await page.getByTestId("ds-menubar").getByRole("button", { name: /^Setup$/ }).click();
  const wizard = page.getByRole("menuitem", { name: "Wizard" });
  await expect(wizard).toBeVisible({ timeout: 10_000 });
  await wizard.click();
}

async function submitCreateProject(page: Page, name: string, urlPattern: RegExp) {
  const nameInput = page.locator("#np-name");
  await expect(nameInput).toBeVisible({ timeout: 15_000 });
  await nameInput.fill(name);
  await page.getByTestId("create-project-submit").click();
  await expect(page).toHaveURL(urlPattern, { timeout: 30_000 });
  const id = projectIdFromUrl(page.url());
  expect(id).toBeTruthy();
  return id as string;
}

async function submitCreateProjectOnHome(page: Page, name: string) {
  const nameInput = page.locator("#np-name");
  await expect(nameInput).toBeVisible({ timeout: 15_000 });
  await nameInput.fill(name);
  await page.getByTestId("create-project-submit").click();
  await expect(page).toHaveURL(/\/$/, { timeout: 30_000 });
  await expect(page.getByTestId("create-project-modal")).toBeHidden({ timeout: 30_000 });
  const activeCard = page.locator("[data-testid^='project-card-'][data-active-project='true']").first();
  await expect(activeCard).toBeVisible({ timeout: 30_000 });
  const testId = await activeCard.getAttribute("data-testid");
  const id = testId?.replace(/^project-card-/, "") || "";
  expect(id).toBeTruthy();
  return id;
}

test.describe.serial("Home project entry closure @critical", () => {
  test.beforeAll(async () => {
    ensureArtifactDir();
  });

  test("ENTRY-CLOSURE-01 whole-application project entry contract stays explicit", async ({ page, request }) => {
    test.slow();

    const createdProjects = new Map<string, string>();
    const deletedProjects: string[] = [];

    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);

    const handoffBefore = await captureHandoffSnapshot(request);
    writeJson("handoff-before.json", handoffBefore);
    expectEmptyHandoff(handoffBefore);

    try {
      await test.step("Scenario A: home chrome create stays explicit until confirmed", async () => {
        const monitor = monitorProjectCreatePosts(page);
        try {
          await gotoHome(page);
          await openChromeCreateProject(page);
          await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          expect(monitor.getCount()).toBe(0);
          const name = `${RUN_ID} Home Chrome`;
          const projectId = await submitCreateProjectOnHome(page, name);
          createdProjects.set(projectId, name);
          expect(monitor.getCount()).toBe(1);
          await page.screenshot({ path: path.join(ARTIFACT_DIR, "appchrome-home-create.png"), fullPage: true });
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario B: project chrome create routes through Home instead of silent POST", async () => {
        const sourceId = Array.from(createdProjects.keys())[0];
        const monitor = monitorProjectCreatePosts(page);
        try {
          await page.goto(`/project/${sourceId}`);
          await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });
          await openChromeCreateProject(page);
          await expect(page).toHaveURL(/[?&]create=1.*pendingKind=project/, { timeout: 10_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          expect(monitor.getCount()).toBe(0);
          await page.getByTestId("create-project-cancel").click();
          await expect(page).toHaveURL(new RegExp(`/project/${sourceId.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}$`), {
            timeout: 10_000,
          });
          expect(monitor.getCount()).toBe(0);
          await openChromeCreateProject(page);
          await expect(page).toHaveURL(/[?&]create=1.*pendingKind=project/, { timeout: 10_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          const name = `${RUN_ID} Project Chrome`;
          const projectId = await submitCreateProject(page, name, /\/project\/[^/?#]+$/);
          createdProjects.set(projectId, name);
          expect(monitor.getCount()).toBe(1);
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario C: Co-Director project entry preserves the return destination", async () => {
        const monitor = monitorProjectCreatePosts(page);
        try {
          await page.goto("/co-director");
          await expect(page.getByTestId("app-chrome")).toBeVisible({ timeout: 30_000 });
          await openChromeCreateProject(page);
          await expect(page).toHaveURL(/[?&]create=1.*pendingKind=co-director/, { timeout: 10_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          expect(monitor.getCount()).toBe(0);
          await page.getByTestId("create-project-cancel").click();
          await expect(page).toHaveURL(/\/co-director$/, { timeout: 10_000 });
          expect(monitor.getCount()).toBe(0);
          await openChromeCreateProject(page);
          await expect(page).toHaveURL(/[?&]create=1.*pendingKind=co-director/, { timeout: 10_000 });
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
          const name = `${RUN_ID} CoDirector Return`;
          const projectId = await submitCreateProject(page, name, /\/co-director\?projectId=/);
          createdProjects.set(projectId, name);
          expect(monitor.getCount()).toBe(1);
          await page.screenshot({ path: path.join(ARTIFACT_DIR, "codirector-return-create.png"), fullPage: true });
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario D: backend rejects nameless project creates", async () => {
        const blank = await request.post(`${API}/api/projects`, { data: { name: "   " } });
        expect(blank.ok(), await blank.text()).toBeFalsy();
        expect(blank.status()).toBe(422);

        const missing = await request.post(`${API}/api/projects`, { data: {} });
        expect(missing.ok(), await missing.text()).toBeFalsy();
        expect(missing.status()).toBe(422);
      });

      await test.step("Scenario E: stale recent ids clear without replacement create", async () => {
        const target = await createDisposableProject(request, "Stale Target");
        createdProjects.set(target.id, target.name);
        const monitor = monitorProjectCreatePosts(page);
        try {
          await page.goto("/");
          await page.evaluate(
            ({ key, targetId }) => {
              localStorage.setItem(
                key,
                JSON.stringify([
                  { id: "missing-project", name: "Missing" },
                  { id: targetId, name: "Fresh Target" },
                ]),
              );
            },
            { key: RECENT_KEY, targetId: target.id },
          );
          await gotoHome(page);
          await expect(page.getByText(target.name, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
          await openSetupWizard(page);
          await expect(page).toHaveURL(new RegExp(`/project/${target.id.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\?.*workspace=setup`), {
            timeout: 30_000,
          });
          expect(monitor.getCount()).toBe(0);
          const recentValue = await page.evaluate((key) => localStorage.getItem(key), RECENT_KEY);
          expect(recentValue || "[]").not.toContain("missing-project");
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario F: archived projects are ineligible for preferred entry", async () => {
        const eligible = await createDisposableProject(request, "Eligible Active");
        const archived = await createDisposableProject(request, "Eligible Archived");
        createdProjects.set(eligible.id, eligible.name);
        createdProjects.set(archived.id, archived.name);
        await archiveProject(request, archived.id, true);
        const monitor = monitorProjectCreatePosts(page);
        try {
          await page.goto("/");
          await page.evaluate(
            ({ key, archivedId, eligibleId }) => {
              localStorage.setItem(
                key,
                JSON.stringify([
                  { id: archivedId, name: "Archived First" },
                  { id: eligibleId, name: "Eligible Second" },
                ]),
              );
            },
            { key: RECENT_KEY, archivedId: archived.id, eligibleId: eligible.id },
          );
          await gotoHome(page);
          await expect(page.getByText(eligible.name, { exact: true }).first()).toBeVisible({ timeout: 30_000 });
          await openSetupWizard(page);
          await expect(page).toHaveURL(new RegExp(`/project/${eligible.id.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\?.*workspace=setup`), {
            timeout: 30_000,
          });
          expect(monitor.getCount()).toBe(0);
          const recentValue = await page.evaluate((key) => localStorage.getItem(key), RECENT_KEY);
          expect(recentValue || "[]").not.toContain(archived.id);
        } finally {
          monitor.dispose();
        }
      });

      await test.step("Scenario G: create failure keeps the drawer open and retry succeeds", async () => {
        let failedOnce = false;
        const routeHandler = async (route: Parameters<Page["route"]>[1] extends infer T ? T : never) => {
          const req = route.request();
          const url = new URL(req.url());
          if (!failedOnce && req.method() === "POST" && url.pathname === "/api/projects") {
            failedOnce = true;
            await route.fulfill({
              status: 500,
              contentType: "application/json",
              body: JSON.stringify({ detail: { message: "Injected entry-contract failure" } }),
            });
            return;
          }
          await route.continue();
        };
        await page.route("**/api/projects", routeHandler);
        try {
          await page.goto("/?create=1&pendingKind=project&pendingWorkspace=timeline");
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 30_000 });
          await page.locator("#np-name").fill(`${RUN_ID} Retry Flow`);
          await page.getByTestId("create-project-submit").click();
          await expect(page.getByTestId("create-project-error")).toBeVisible();
          await expect(page.getByTestId("create-project-modal-panel")).toBeVisible();
        } finally {
          await page.unroute("**/api/projects", routeHandler);
        }
        const projectId = await submitCreateProject(page, `${RUN_ID} Retry Flow`, /\/project\/[^/?#]+\?workspace=timeline/);
        createdProjects.set(projectId, `${RUN_ID} Retry Flow`);
        await page.screenshot({ path: path.join(ARTIFACT_DIR, "failure-retry-success.png"), fullPage: true });
      });

      await test.step("Scenario H: deleting one disposable project does not delete another project's chat", async () => {
        const doomed = await createDisposableProject(request, "Delete Doomed");
        const survivor = await createDisposableProject(request, "Delete Survivor");
        createdProjects.set(doomed.id, doomed.name);
        createdProjects.set(survivor.id, survivor.name);

        const saveConversation = async (projectId: string, message: string) => {
          const res = await request.post(`${API}/api/codirector/conversations/${projectId}`, {
            data: {
              messages: [{ id: `msg-${projectId}`, role: "user", content: message }],
              model: null,
              provider_id: null,
            },
          });
          expect(res.ok(), await res.text()).toBeTruthy();
        };
        await saveConversation(doomed.id, "Delete me");
        await saveConversation(survivor.id, "Keep me");

        await deleteProjectIfPresent(request, doomed.id);
        deletedProjects.push(doomed.id);
        createdProjects.delete(doomed.id);

        const doomedGet = await request.get(`${API}/api/projects/${doomed.id}`);
        expect(doomedGet.status()).toBe(404);
        const survivorConversation = await request.get(`${API}/api/codirector/conversations/${survivor.id}`);
        expect(survivorConversation.ok(), await survivorConversation.text()).toBeTruthy();
        const survivorBody = await survivorConversation.json();
        expect(Array.isArray(survivorBody.messages) ? survivorBody.messages.length : 0).toBe(1);
      });

      await test.step("Scenario I: handoff project stays untouched during the run", async () => {
        const handoffMid = await captureHandoffSnapshot(request);
        writeJson("handoff-mid.json", handoffMid);
        expect(handoffMid).toEqual(handoffBefore);
      });
    } finally {
      for (const projectId of uniqueIds(createdProjects.keys())) {
        const projectName = createdProjects.get(projectId) || "";
        if (!projectName.startsWith(RUN_ID)) {
          continue;
        }
        await deleteProjectIfPresent(request, projectId);
        deletedProjects.push(projectId);
      }

      const handoffAfter = await captureHandoffSnapshot(request);
      writeJson("handoff-after.json", handoffAfter);
      expectEmptyHandoff(handoffAfter);
      expect(handoffAfter).toEqual(handoffBefore);

      const finalProjects = await listProjects(request);
      writeJson("cleanup-summary.json", {
        runId: RUN_ID,
        deletedProjects: uniqueIds(deletedProjects),
        remainingRunProjects: finalProjects.filter((project) => project.name.startsWith(RUN_ID)),
        handoffAfter,
      });
      expect(finalProjects.filter((project) => project.name.startsWith(RUN_ID))).toEqual([]);
    }
  });
});
