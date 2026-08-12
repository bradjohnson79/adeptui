/**
 * Scenarios A–B: Register external model folder (path only), Ollama-style layout,
 * drive unavailable / restore honesty.
 */
import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const API = process.env.STUDIO_API_BASE_URL || "http://127.0.0.1:8758";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical local model folder discovery", () => {
  test("A: register folder path-only without copy; B: drive unavailable keeps registration", async ({
    page,
    request,
  }) => {
    const project = await createTempProject(request, `Model Storage ${Date.now()}`);
    const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "adept-model-"));
    const modelDir = path.join(fixtureRoot, "tiny-gguf");
    fs.mkdirSync(modelDir);
    const ggufPath = path.join(modelDir, "tiny.gguf");
    fs.writeFileSync(ggufPath, "GGUF\0fixture");

    try {
      // API-level register (path only)
      const reg = await request.post(`${API}/api/model-storage/folders/register`, {
        data: { path: modelDir, category: "llm", importIntoLibrary: false },
      });
      expect(reg.ok()).toBeTruthy();
      const regBody = await reg.json();
      expect(regBody.copied).toBeFalsy();
      expect(regBody.folder?.imported).toBeFalsy();
      expect(fs.existsSync(ggufPath)).toBeTruthy();

      // Fake Ollama store — manifests resolve, blobs never listed as models
      const ollama = path.join(fixtureRoot, "ollama-store");
      fs.mkdirSync(path.join(ollama, "blobs"), { recursive: true });
      const man = path.join(ollama, "manifests", "registry.ollama.ai", "library", "demo", "7b");
      fs.mkdirSync(path.dirname(man), { recursive: true });
      fs.writeFileSync(man, "{}");
      fs.writeFileSync(path.join(ollama, "blobs", "sha256-deadbeef"), "x");
      const classify = await request.post(`${API}/api/model-storage/classify`, {
        data: { path: ollama },
      });
      expect(classify.ok()).toBeTruthy();
      const cBody = await classify.json();
      expect(cBody.classification?.runtimeType).toBe("ollama");
      const names = (cBody.classification?.models || []).map((m: { name: string }) => m.name).join(" ");
      expect(names).toContain("demo");
      expect(names).not.toContain("sha256");

      await openSetup(page, project.id);
      await expect(page.getByTestId("model-storage-panel")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("model-storage-folder-list")).toContainText("tiny-gguf", {
        timeout: 15_000,
      });

      // Drive unavailable: point at missing path
      const missing = path.join(fixtureRoot, "gone-drive", "models");
      const probe = await request.post(`${API}/api/model-storage/validate`, {
        data: { path: missing, runtimeType: "gguf" },
      });
      const probeBody = await probe.json();
      expect(probeBody.validation?.status).toBe("Drive Unavailable");
      expect(probeBody.validation?.silentSwitchForbidden).toBeTruthy();
      expect(probeBody.validation?.autoRedownloadForbidden).toBeTruthy();

      // Restore: register real path again via UI paste
      await page.getByTestId("model-storage-manual-path").fill(modelDir);
      await page.getByTestId("model-storage-register").click();
      await expect(page.getByTestId("model-storage-folder-list")).toContainText(modelDir, {
        timeout: 15_000,
      });
    } finally {
      await deleteProject(request, project.id);
      try {
        fs.rmSync(fixtureRoot, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
    }
  });
});
