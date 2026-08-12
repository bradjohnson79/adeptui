import fs from "node:fs";
import path from "node:path";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../../helpers/app";

export {
  TINY_MP4,
  TINY_PNG,
  TINY_WAV,
  getConversation,
  openCoDirectorFullScreen,
  sendChatTurn,
  uploadProjectAsset,
} from "./audit";

export const MANUAL_HANDOFF_ID = "77a4b96c-8e3f-4501-897c-51bab99bedb7";
export const MANUAL_HANDOFF_NAME = "Manual Beta Handoff";

type ProjectSummary = {
  id: string;
  name: string;
  asset_count?: number;
  assets?: Array<unknown>;
};

export type RunContext = {
  runId: string;
  artifactDir: string;
  projectName: string;
  createdProjectIds: string[];
};

export type HandoffSnapshot =
  | {
      missing: true;
      id: string;
      name: string;
    }
  | {
      missing?: false;
      id: string;
      name: string;
      assetCount: number;
      chatCount: number;
      wikiCount: number;
      planCount: number;
    };

function uniqueIds(ids: Iterable<string>) {
  return Array.from(new Set(Array.from(ids).filter(Boolean)));
}

async function listProjects(request: APIRequestContext): Promise<ProjectSummary[]> {
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectSummary[];
}

async function getConversationCount(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/conversations/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return Array.isArray(body.messages) ? body.messages.length : 0;
}

async function getWikiCount(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.hasContent ? 1 : 0;
}

async function getPlanCount(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/plans/active`);
  if (res.status() === 404) return 0;
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return body.status === "active" && body.plan ? 1 : 0;
}

function projectIdFromActiveCard(page: Page) {
  return page
    .locator("[data-testid^='project-card-'][data-active-project='true']")
    .first()
    .getAttribute("data-testid")
    .then((testId) => testId?.replace(/^project-card-/, "") || null);
}

export function createRunContext(): RunContext {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const runId = `CODIRECTOR-AUTONOMOUS-CERT-${timestamp}`;
  return {
    runId,
    artifactDir: path.join(
      "docs",
      "release-gate",
      "codirector-final",
      "artifacts",
      "autonomous-cert",
      runId,
    ),
    projectName: `CODIRECTOR-CERT-${timestamp}`,
    createdProjectIds: [],
  };
}

export function ensureArtifactDir(dir: string) {
  fs.mkdirSync(dir, { recursive: true });
}

export function writeJson(dir: string, name: string, data: unknown) {
  ensureArtifactDir(dir);
  fs.writeFileSync(path.join(dir, name), JSON.stringify(data, null, 2));
}

export async function captureHandoffSnapshot(request: APIRequestContext): Promise<HandoffSnapshot> {
  const res = await request.get(`${API}/api/projects/${MANUAL_HANDOFF_ID}`);
  if (res.status() === 404) {
    return {
      missing: true,
      id: MANUAL_HANDOFF_ID,
      name: MANUAL_HANDOFF_NAME,
    };
  }
  expect(res.ok(), await res.text()).toBeTruthy();
  const project = (await res.json()) as ProjectSummary;
  return {
    id: project.id,
    name: project.name,
    assetCount: project.asset_count ?? project.assets?.length ?? 0,
    chatCount: await getConversationCount(request, MANUAL_HANDOFF_ID),
    wikiCount: await getWikiCount(request, MANUAL_HANDOFF_ID),
    planCount: await getPlanCount(request, MANUAL_HANDOFF_ID),
  };
}

export function expectHandoffUnchanged(before: HandoffSnapshot, after: HandoffSnapshot) {
  expect(after).toEqual(before);
}

export function monitorProjectCreatePosts(page: Page) {
  let count = 0;
  const handler = (req: { method: () => string; url: () => string }) => {
    try {
      const url = new URL(req.url());
      if (req.method() === "POST" && url.pathname === "/api/projects") {
        count += 1;
      }
    } catch {
      throw new Error("Failed to inspect project creation request URL.");
    }
  };
  page.on("request", handler);
  return {
    getCount: () => count,
    dispose: () => page.off("request", handler),
  };
}

export async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

export async function createProjectViaHomeUi(page: Page, request: APIRequestContext, name: string) {
  await gotoHome(page);

  const primaryEntry = page.getByTestId("create-project-open");
  if (await primaryEntry.isVisible().catch(() => false)) {
    await primaryEntry.click();
  } else {
    await page.getByRole("button", { name: /^Project$/ }).click();
    await page.getByRole("menuitem", { name: "Create project" }).click();
  }

  await expect(page.getByTestId("create-project-modal-panel")).toBeVisible({ timeout: 15_000 });
  await page.locator("#np-name").fill(name);

  const seriesType = page.getByTestId("project-type-series");
  await expect(seriesType).toBeVisible({ timeout: 15_000 });
  await seriesType.click();

  const explicitSubtype = page.getByTestId("project-subtype-web_series");
  if (await explicitSubtype.isVisible().catch(() => false)) {
    await explicitSubtype.click();
  } else {
    const fallbackSubtype = page
      .locator("[data-testid^='project-subtype-']")
      .filter({ hasText: /web series/i })
      .first();
    if (await fallbackSubtype.isVisible().catch(() => false)) {
      await fallbackSubtype.click();
    }
  }

  await page.getByTestId("create-project-submit").click();
  await expect(page.getByTestId("create-project-modal-panel")).toBeHidden({ timeout: 30_000 });

  const namedCard = page.locator("[data-testid^='project-card-']").filter({ hasText: name }).first();
  const activeBanner = page.getByTestId("home-active-project-banner");
  // Banner and named card can both be present; assert each separately to avoid strict-mode .or() collisions.
  await expect(activeBanner.or(namedCard).first()).toBeVisible({ timeout: 30_000 });
  if (await namedCard.isVisible().catch(() => false)) {
    await expect(namedCard).toContainText(name);
  } else if (await activeBanner.isVisible().catch(() => false)) {
    await expect(activeBanner).toContainText(name);
  }

  const activeCardId = await projectIdFromActiveCard(page);
  if (activeCardId) {
    return activeCardId;
  }

  let createdId: string | null = null;
  await expect
    .poll(async () => {
      const created = (await listProjects(request)).find((project) => project.name === name);
      createdId = created?.id || null;
      return createdId;
    }, { timeout: 30_000 })
    .not.toBeNull();

  expect(createdId, `Unable to resolve created project id for ${name}.`).toBeTruthy();
  return createdId as string;
}

export async function deleteDisposableProjects(
  request: APIRequestContext,
  ids: string[],
  protectedId?: string,
) {
  for (const projectId of uniqueIds(ids)) {
    if (!projectId) continue;
    if (projectId === MANUAL_HANDOFF_ID) continue;
    if (projectId === protectedId) continue;
    const res = await request.delete(`${API}/api/projects/${projectId}`);
    if (res.status() === 404) continue;
    expect(res.ok(), await res.text()).toBeTruthy();
  }
}

/** Delete only CODIRECTOR-CERT* residue; never Manual Beta Handoff. */
export async function deleteCertResidueByNamePrefix(
  request: APIRequestContext,
  namePrefix = "CODIRECTOR-CERT",
) {
  const projects = await listProjects(request);
  const ids = projects
    .filter((project) => project.id !== MANUAL_HANDOFF_ID)
    .filter((project) => project.name.startsWith(namePrefix))
    .map((project) => project.id);
  await deleteDisposableProjects(request, ids);
  return ids;
}

export async function getWiki(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<Record<string, unknown>>;
}

export function expectCreatorSafeReply(text: string) {
  expect(text).toMatch(/\S/);
  expect(text).not.toMatch(/0\.95/);
  expect(text).not.toMatch(/conversation_quality|toolId|requestId|primaryIntent/i);
  expect(text).not.toMatch(/failed to fetch/i);
  expect(text).not.toMatch(/\{"type":/);
  expect(text).not.toMatch(/```json|```proposal/i);
}

export async function openCoDirectorForProject(page: Page, projectId: string) {
  await page.goto(`/co-director?projectId=${encodeURIComponent(projectId)}`);
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await expect(
    page.getByTestId("codirector-composer-input").or(page.getByLabel("Message Co-Director")).first(),
  ).toBeVisible({ timeout: 30_000 });
}
