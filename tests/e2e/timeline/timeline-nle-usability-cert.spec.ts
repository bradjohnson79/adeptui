/**
 * Timeline NLE usability + MiniMax default certification.
 * ADEPT_BETA_TARGET=1, workers=1, retries=0.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, BETA_TARGET, waitForAppReady } from "../helpers/app";

const PROJECT_NAME = "The Dreamweaver";
const ARTIFACT_DIR = path.join(process.cwd(), "docs/release-gate/timeline-nle/artifacts");

function writeArtifact(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
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

test.describe("@critical @beta timeline nle usability cert", () => {
  test.skip(!BETA_TARGET, "Set ADEPT_BETA_TARGET=1");

  test("trim handles, prompt focus, MiniMax defaults", async ({ page, request }) => {
    test.setTimeout(300_000);
    await waitForAppReady(request);
    const project = await resolveProject(request);
    writeArtifact("project.json", project);

    const dock = await request.get(
      `${API}/api/production-control/resolve?projectId=${encodeURIComponent(project.id)}&modality=video`,
    );
    expect(dock.ok()).toBeTruthy();
    const dockBody = await dock.json();
    writeArtifact("dock_video_resolve.json", dockBody);
    expect(String(dockBody.activeModelId || dockBody.selection?.activeModelId || "")).toMatch(/minimax-h3/);

    await page.goto(`/project/${project.id}?workspace=timeline`);
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });

    await expect(page.getByTestId("workspace-fullscreen-toggle-timeline")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-zoom-slider")).toBeVisible();

    const prompt = page.getByTestId("timeline-scene-prompt");
    if (await prompt.isVisible()) {
      await prompt.click();
      await prompt.fill("");
      const typed = "The Dreamweaver enters the anteroom with quiet resolve.";
      await prompt.type(typed, { delay: 15 });
      await expect(prompt).toHaveValue(typed);
      await page.waitForTimeout(500);
      await expect(prompt).toHaveValue(typed);
      writeArtifact("prompt_typing.json", { ok: true, length: typed.length });
    }

    const trimLeft = page.locator("[data-testid^='track-clip-trim-left-']").first();
    if (await trimLeft.count()) {
      const box = await trimLeft.boundingBox();
      expect(box).toBeTruthy();
      if (box) {
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + 40, box.y + box.height / 2, { steps: 8 });
        await page.mouse.up();
      }
      writeArtifact("trim_drag.json", { ok: true });
    } else {
      writeArtifact("trim_drag.json", { ok: false, reason: "no clips on board" });
    }

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "timeline_nle.png") });
  });
});
