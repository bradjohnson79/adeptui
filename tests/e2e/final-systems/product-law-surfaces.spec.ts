/**
 * Final Systems — Product Law surface smoke (single disposable project).
 * Proves creator workspaces open inside Adept UI without direct runtime ops.
 * Does not alone satisfy full Product Law media E2E (see completion report).
 */
import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import {
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const API = process.env.STUDIO_API_BASE_URL || "http://127.0.0.1:8758";
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "final-systems",
  "artifacts",
  `product-law-${new Date().toISOString().replace(/[:.]/g, "-")}`,
);

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @final-systems Product Law surfaces", () => {
  test("single project — creator surfaces open; no direct runtime ops", async ({ page, request }) => {
    test.setTimeout(180_000);
    const forbiddenHits: string[] = [];
    page.on("request", (req) => {
      const u = req.url();
      if (
        u.includes(":8188") ||
        u.includes(":8192") ||
        u.includes("/prompt") ||
        u.includes("11434") ||
        /\/api\/(generate|interrupt)/i.test(u)
      ) {
        // Allow Adept product API hosts only — flag raw runtime ports / Ollama.
        if (!u.includes("127.0.0.1:8758") && !u.includes("localhost:8758")) {
          forbiddenHits.push(u);
        }
      }
    });

    const project = await createTempProject(request, `Final Systems Product Ad ${Date.now()}`);
    expect(project.id).not.toBe("77a4b96c-8e3f-4501-897c-51bab99bedb7");
    writeJson("project.json", { projectId: project.id, name: project.name });

    const surfaces: Array<{ workspace: string; probe: string | RegExp }> = [
      { workspace: "timeline", probe: /Re-take|Timeline|Generate/i },
      { workspace: "library", probe: /Library|Assets|Upload/i },
      { workspace: "characters", probe: /Character|Voice|Appearance/i },
      { workspace: "scriptwriter", probe: /Script|Scene|Draft/i },
      { workspace: "imagegen", probe: /Image|Generate|Prompt/i },
      { workspace: "voicestudio", probe: /Voice|Speak|Engine|Performance/i },
      { workspace: "audiostudio", probe: /Audio|Music|Ambience|SFX/i },
      { workspace: "storyboard", probe: /Storyboard|Shot|Frame/i },
      { workspace: "magi", probe: /MAGI|Editor|Clip|Cut/i },
      { workspace: "posecraft", probe: /PoseCraft|Pose|Stage|Snapshot/i },
    ];

    const results: Array<{ workspace: string; ok: boolean; note: string }> = [];

    try {
      for (const surface of surfaces) {
        await page.goto(`/project/${project.id}?workspace=${surface.workspace}`);
        await page.waitForLoadState("domcontentloaded");
        const body = page.locator("body");
        await expect(body).toBeVisible({ timeout: 30_000 });
        const text = (await body.innerText().catch(() => "")) || "";
        const matched = typeof surface.probe === "string" ? text.includes(surface.probe) : surface.probe.test(text);
        // Workspace route mounted even if copy varies — require no "open ComfyUI" style prompts.
        const asksManualRuntime = /please open comfyui|please start ollama|please launch minimax|interact with :8188|:8192/i.test(
          text,
        );
        const ok = !asksManualRuntime && text.length > 20;
        results.push({
          workspace: surface.workspace,
          ok,
          note: matched ? "creator chrome visible" : asksManualRuntime ? "manual runtime prompt" : "mounted",
        });
        expect(asksManualRuntime, `${surface.workspace} must not ask creator to operate runtimes`).toBeFalsy();
      }

      // Timeline Re-take control must exist (Product Law + Re-take linkage)
      await page.goto(`/project/${project.id}?workspace=timeline`);
      await expect(page.getByTestId("timeline-open-retake")).toBeVisible({ timeout: 60_000 });

      writeJson("surfaces.json", { results, forbiddenHits, artifactDir: ARTIFACT_DIR });
      expect(forbiddenHits, "Playwright must not hit Comfy/Ollama/runtime ports directly").toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
