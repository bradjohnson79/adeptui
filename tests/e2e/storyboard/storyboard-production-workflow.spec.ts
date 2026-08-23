/**
 * Image Generator color grade + Storyboard Studio production workflow.
 * Schnick Coffee live project when ADEPT_SCHNICK_PROJECT_ID / default ID is present.
 */
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.ADEPT_WEB_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.ADEPT_API_URL || process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT =
  process.env.ADEPT_SCHNICK_PROJECT_ID ||
  process.env.ADEPT_PROJECT_ID ||
  "2347bf46-3762-4763-86c5-4a6032522278";
const ARTIFACTS = path.resolve("artifacts/storyboard-production");

function ensureDir(dir: string) {
  fs.mkdirSync(dir, { recursive: true });
}

test.describe("Image Generator color grade + Storyboard production", () => {
  test("category excludes Storyboard and color grade compiles teal vs natural", async ({
    page,
    request,
  }) => {
    ensureDir(ARTIFACTS);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({
      timeout: 60_000,
    });
    const category = page.getByTestId("cis-category");
    await expect(category).toBeVisible();
    const options = await category.locator("option").allTextContents();
    expect(options).not.toContain("Storyboard");
    expect(options).toContain("General");
    await expect(page.getByTestId("cis-color-grade")).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACTS, "imagegen-color-grade.png"), fullPage: true });

    const natural = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/cinematic/compile-preview`,
      {
        data: {
          prompt: "Korri tastes Schnick Coffee",
          projectId: PROJECT,
          controls: { category: "general", colorGradePreset: "natural", aspectRatio: "16:9", shotIntent: "medium" },
        },
      }
    );
    expect(natural.ok()).toBeTruthy();
    const teal = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/cinematic/compile-preview`,
      {
        data: {
          prompt: "Korri tastes Schnick Coffee",
          projectId: PROJECT,
          controls: { category: "general", colorGradePreset: "teal_orange", aspectRatio: "16:9", shotIntent: "medium" },
        },
      }
    );
    expect(teal.ok()).toBeTruthy();
    const naturalBody = await natural.json();
    const tealBody = await teal.json();
    const cinematic = tealBody.imageProductBody?.cinematic || {};
    expect(cinematic.colorGradePreset).toBe("teal_orange");
    const naturalPrompt = String(naturalBody.promptIntel?.expandedPrompt || "");
    const tealPrompt = String(tealBody.promptIntel?.expandedPrompt || "");
    expect(tealPrompt).toContain("Color grade:");
    expect(tealPrompt).not.toBe(naturalPrompt);
    expect(naturalPrompt).not.toContain("Teal & Orange");
    fs.writeFileSync(
      path.join(ARTIFACTS, "compile-preview-teal.json"),
      JSON.stringify(tealBody, null, 2)
    );
  });

  test("Storyboard Studio library drawer, captions, timeline caption is not dialogue", async ({
    page,
    request,
  }) => {
    ensureDir(ARTIFACTS);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=script`);
    await expect(page.getByRole("heading", { name: /Storyboard Studio/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("sb-library-pane")).toBeVisible();
    await expect(page.getByTestId("sb-generate-missing")).toBeVisible();
    await expect(page.getByTestId("sb-compose-2k")).toBeVisible();
    await page.screenshot({ path: path.join(ARTIFACTS, "storyboard-library.png"), fullPage: true });

    const caption = "Korri reacts to the taste of Schnick Coffee";
    const ws = await request.get(`${API}/api/storyboard-studio/projects/${PROJECT}/workspace`);
    expect(ws.ok()).toBeTruthy();
    const workspace = await ws.json();
    const panel = (workspace.panels || []).find((p: { panelId?: string }) => p.panelId);
    if (panel?.panelId) {
      const patched = await request.patch(
        `${API}/api/storyboard-studio/projects/${PROJECT}/panels/${panel.panelId}`,
        { data: { label: caption } }
      );
      expect(patched.ok()).toBeTruthy();
      const prep = await request.post(
        `${API}/api/storyboard-studio/projects/${PROJECT}/prepare-timeline`,
        { data: { documentId: workspace.document?.id, panelIds: [panel.panelId], approvedOnly: false } }
      );
      expect(prep.ok()).toBeTruthy();
      const proposal = (await prep.json()).proposal;
      const shot = (proposal.shots || []).find((s: { panelId: string }) => s.panelId === panel.panelId);
      expect(shot.label).toBe(caption);
      expect(shot.dialogue || "").not.toContain("reacts to the taste");
      fs.writeFileSync(path.join(ARTIFACTS, "timeline-prep.json"), JSON.stringify(proposal, null, 2));
    }

    const missing = await request.post(
      `${API}/api/storyboard-studio/projects/${PROJECT}/generate-missing`,
      { data: { family: "qwen2512", pageIndex: 0 } }
    );
    expect(missing.ok()).toBeTruthy();
    const missingBody = await missing.json();
    fs.writeFileSync(path.join(ARTIFACTS, "generate-missing.json"), JSON.stringify(missingBody, null, 2));
  });
});
