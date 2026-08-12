/**
 * Professional Wiki Intelligence + Reorganize Wiki certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/professional-wiki/artifacts");

function ensureDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}
function writeArtifact(name: string, data: unknown) {
  ensureDir();
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function resolveProject(request: APIRequestContext) {
  const forced = (process.env.ADEPT_PROJECT_ID || "").trim();
  if (forced) return { id: forced, name: PROJECT_NAME };
  const res = await request.get(`${API}/api/projects`);
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const projects = Array.isArray(body) ? body : body.projects || body.items || [];
  const named = projects.find((p: { name?: string }) => p.name === PROJECT_NAME);
  expect(named, `${PROJECT_NAME} must exist`).toBeTruthy();
  return named as { id: string; name: string };
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta professional wiki intelligence cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("professional TOC + reorganize + undo + isolation", async ({ page, request }) => {
    test.setTimeout(600_000);
    await waitForAppReady(request);
    ensureDir();
    const project = await resolveProject(request);
    writeArtifact("project.json", { id: project.id, name: project.name });

    const wikiBefore = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
    expect(wikiBefore.ok()).toBeTruthy();
    const beforeBody = await wikiBefore.json();
    writeArtifact("wiki_before.json", {
      hasContent: beforeBody.hasContent,
      toc: beforeBody.toc,
      professionalToc: beforeBody.professionalToc,
      projection: beforeBody.projection,
    });
    expect(beforeBody.projection || beforeBody.professionalToc).toBeTruthy();

    const health = await request.get(`${API}/api/codirector/projects/${project.id}/wiki/health`);
    expect(health.ok()).toBeTruthy();
    writeArtifact("wiki_health.json", await health.json());

    const toolCtx = await request.get(`${API}/api/codirector/projects/${project.id}/wiki/tool-context`);
    expect(toolCtx.ok()).toBeTruthy();
    const toolBody = await toolCtx.json();
    expect(toolBody.projectId).toBe(project.id);
    writeArtifact("wiki_tool_context.json", toolBody);

    await openCoDirectorFullScreen(page, project.id);
    await page.getByTestId("codirector-content-tab-wiki").click();
    await expect(page.getByTestId("project-wiki-reorganize")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("project-wiki-rebuild")).toBeVisible();
    await expect(page.getByTestId("project-wiki-diagnostic")).toBeVisible();

    await page.getByTestId("project-wiki-reorganize").click();
    await expect(page.getByTestId("project-wiki-reorganize-dialog")).toBeVisible();
    await expect(page.getByTestId("project-wiki-reorganize-scopes")).toBeVisible();
    await page.getByTestId("project-wiki-reorganize-confirm").click();

    await expect(page.getByTestId("project-wiki-reorganize-summary")).toBeVisible({ timeout: 120_000 });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "reorganize_summary.png") });

    const reorg = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: {
        domains: ["characters", "locations", "story", "world", "timeline", "wardrobe", "props", "canon"],
        useSpecialists: true,
        preserveLockedCanon: true,
        createUndoSnapshot: true,
      },
    });
    expect(reorg.ok()).toBeTruthy();
    const reorgBody = await reorg.json();
    writeArtifact("reorganize_job.json", reorgBody);
    expect(reorgBody.ok).toBeTruthy();
    expect(reorgBody.job?.status).toMatch(/COMPLETE|PARTIAL/);
    expect(Array.isArray(reorgBody.specialistsActivated)).toBeTruthy();
    expect((reorgBody.specialistsActivated || []).length).toBeGreaterThan(0);
    expect(reorgBody.job?.tocRebuilt).toBeTruthy();

    const wikiAfter = await request.get(`${API}/api/codirector/projects/${project.id}/wiki`);
    const afterBody = await wikiAfter.json();
    writeArtifact("wiki_after.json", {
      hasContent: afterBody.hasContent,
      toc: afterBody.toc,
      professionalToc: afterBody.professionalToc,
    });
    expect(afterBody.hasContent).toBeTruthy();
    const charEntries = afterBody.sections?.characters?.entries || [];
    const falseLeft = charEntries.filter((e: { text?: string }) =>
      /^(she|here|research|episode|series synopsis)\b/i.test(String(e.text || "").split(":")[0].trim()),
    );
    expect(falseLeft.length).toBe(0);

    // Idempotency — second run should succeed
    const reorg2 = await request.post(`${API}/api/codirector/projects/${project.id}/wiki/reorganize`, {
      data: { useSpecialists: true, createUndoSnapshot: true },
    });
    expect(reorg2.ok()).toBeTruthy();
    const reorg2Body = await reorg2.json();
    writeArtifact("reorganize_idempotent.json", reorg2Body);

    const jobId = String(reorgBody.job?.id || "");
    if (jobId) {
      const undo = await request.post(
        `${API}/api/codirector/projects/${project.id}/wiki/reorganize/${jobId}/undo`,
      );
      expect(undo.ok()).toBeTruthy();
      const undoBody = await undo.json();
      writeArtifact("reorganize_undo.json", undoBody);
      expect(undoBody.ok).toBeTruthy();
    }

    // Project isolation — other project wiki health must not reference this project
    const projectsRes = await request.get(`${API}/api/projects`);
    const projectsBody = await projectsRes.json();
    const projects = Array.isArray(projectsBody) ? projectsBody : projectsBody.projects || [];
    const other = projects.find((p: { id?: string; name?: string }) => p.id && p.id !== project.id);
    if (other?.id) {
      const otherWiki = await request.get(`${API}/api/codirector/projects/${other.id}/wiki`);
      expect(otherWiki.ok()).toBeTruthy();
      const otherBody = await otherWiki.json();
      expect(otherBody.projectId).toBe(other.id);
    }

    await page.reload();
    await openCoDirectorFullScreen(page, project.id);
    await page.getByTestId("codirector-content-tab-wiki").click();
    await expect(page.getByTestId("project-wiki-toc")).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "wiki_reload.png") });

    writeArtifact("cert_summary.json", {
      projectId: project.id,
      reorganizeStatus: reorgBody.job?.status,
      specialistsActivated: reorgBody.specialistsActivated,
      falseCharactersRemaining: falseLeft.length,
      tocCount: (afterBody.toc || []).length,
    });
  });
});
