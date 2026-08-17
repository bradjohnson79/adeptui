/**
 * Timeline Draft-First + Aspect Ratio + Video Reference — mocked UI suite.
 * Does not burn GPU or hosted credits. Live Stop/Promote/Seedance are gated
 * separately by ADEPT_TIMELINE_DRAFT_LIVE=1.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline/artifacts-draft-aspect");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf8");
}

async function firstScene(request: APIRequestContext, projectId: string) {
  const list = await request.get(`${API}/api/projects/${projectId}/scenes`);
  expect(list.ok()).toBeTruthy();
  const body = await list.json();
  const scenes = body.scenes || body || [];
  if (Array.isArray(scenes) && scenes[0]?.id) return scenes[0] as { id: string; name?: string };
  const created = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { title: "Draft Aspect Scene", prompt: "wide draft preview", duration_sec: 5 },
  });
  expect(created.ok()).toBeTruthy();
  const c = await created.json();
  return { id: String(c.id || c.scene?.id), name: c.name || c.title };
}

async function openTimeline(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}?workspace=timeline`);
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

test.describe.configure({ mode: "serial", retries: 0 });

test.describe("@critical @beta timeline draft-first aspect video-ref UI", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("draft chrome, four aspects, video-ref track, generator honesty", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createTempProject(request, `Draft Aspect UI ${Date.now()}`);
    const scene = await firstScene(request, project.id);
    writeArtifact("project.json", { project, scene });

    await request.patch(`${API}/api/projects/${project.id}/scenes/${scene.id}`, {
      data: { aspect_ratio: "16:9" },
    });

    const masterRes = await request.get(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/master`,
    );
    expect(masterRes.ok()).toBeTruthy();
    const master = await masterRes.json();
    const batchId = master.master?.batchBlocks?.[0]?.id;
    expect(batchId).toBeTruthy();
    await request.patch(
      `${API}/api/director-timeline/projects/${project.id}/scenes/${scene.id}/batches/${batchId}`,
      { data: { generatorId: "ltx-local", promptSegments: [{ text: "draft preview walk", start: 0, length: 5, role: "primary", strength: 1, anchorIds: [], executionStrategy: "compiled" }] } },
    );

    await page.route("**/director-timeline/**/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ok: true,
          mock: true,
          generatorId: "ltx-local",
          hostedCancelSupport: "supported",
        }),
      });
    });

    await openTimeline(page, project.id);
    await expect(page.getByTestId("timeline-viewer-aspect")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);
    await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);

    const batchChip = page.getByTestId(`timeline-batch-${batchId}`);
    if (await batchChip.count()) {
      await batchChip.click();
    }

    await expect(page.getByTestId("timeline-batch-generator")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("timeline-batch-generator").selectOption("ltx-local");
    await expect(page.getByTestId("timeline-draft-mode")).toBeVisible();
    await expect(page.getByTestId("timeline-draft-mode")).toBeChecked();
    await expect(page.getByTestId("timeline-draft-pathway-copy")).toContainText("Low-resolution preview");
    await expect(page.getByTestId("timeline-generate-draft")).toBeVisible();

    for (const ratio of ["1:1", "4:3", "16:9", "21:9"]) {
      await page.getByTestId("timeline-viewer-aspect").selectOption(ratio);
      await expect(page.getByTestId("timeline-viewer-aspect")).toHaveValue(ratio);
    }
    await page.getByTestId("timeline-viewer-aspect").selectOption("21:9");

    await page.getByTestId("timeline-generate-draft").click();
    await expect(page.getByTestId("timeline-generate-draft")).toBeVisible();

    await page.getByTestId("timeline-batch-generator").selectOption("seedance-api");
    await expect(page.getByTestId("timeline-draft-pathway-copy")).toContainText("economical preview");

    await page.getByTestId("timeline-batch-generator").selectOption("kling-api");
    await expect(page.getByTestId("timeline-draft-pathway-copy")).toContainText("Draft unavailable");
    await expect(page.getByTestId("timeline-draft-mode")).toBeDisabled();

    await page.reload();
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("timeline-viewer-aspect")).toHaveValue("21:9");
    writeArtifact("ui.json", { ok: true, aspect: "21:9" });

    await deleteProject(request, project.id);
  });
});
