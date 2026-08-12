/**
 * M3.2a — GEN-TOOLS-01..24 (honest skips when BLOCKED / models missing)
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const OUT = path.join("artifacts", "m32a");

test.describe("M3.2a Generation Tools @DETERMINISTIC", () => {
  test.beforeAll(() => {
    fs.mkdirSync(OUT, { recursive: true });
  });

  test("GEN-TOOLS-01 every approved tool has audit status", async ({ request }) => {
    await waitForAppReady(request);
    const catalog = await (await request.get(`${API}/api/generation-tools/catalog`)).json();
    const ids = (catalog.tools as { id: string }[]).map((t) => t.id);
    for (const id of [
      "video.upscale",
      "image.upscale",
      "image.background_remove",
      "image.chroma_key",
      "image.delighting",
      "scriptwriter",
      "audio.music.generate",
      "audio.sfx.generate",
      "video.extend",
      "image.portrait_skin",
      "brand.studio",
    ]) {
      expect(ids, id).toContain(id);
      const st = await (await request.get(`${API}/api/generation-tools/${id}/status`)).json();
      expect(st.status).toBeTruthy();
      expect(["COMPLETE", "PARTIAL", "BLOCKED", "MISSING"]).toContain(st.status);
    }
    fs.writeFileSync(path.join(OUT, "gen-tools-status.json"), JSON.stringify(catalog, null, 2));
  });

  test("GEN-TOOLS-02 delighting is not COMPLETE / not mock-complete", async ({ request }) => {
    await waitForAppReady(request);
    const st = await (await request.get(`${API}/api/generation-tools/image.delighting/status`)).json();
    expect(st.status).toBe("BLOCKED");
    expect(st.available).toBeFalsy();
  });

  test("GEN-TOOLS-03/05/08/11/12/17 UI hub + run paths", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32a UI ${Date.now()}`);
    try {
      // seed image
      const png = Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      );
      const upload = await request.post(`${API}/api/projects/${project.id}/assets`, {
        multipart: {
          file: { name: "px.png", mimeType: "image/png", buffer: png },
          tag: "seed",
          kind: "image",
        },
      });
      expect(upload.ok()).toBeTruthy();
      const asset = await upload.json();

      await page.goto(`/project/${project.id}?workspace=generationtools`);
      await expect(page.getByTestId("generation-tools-hub")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("generation-tools-disclosure")).toContainText(/Paid cloud/i);
      await page.screenshot({ path: path.join(OUT, "tools-hub.png") });

      // Scriptwriter
      await page.getByTestId("gen-tool-scriptwriter").click();
      await page.getByTestId("gen-tool-prompt").fill("A traveler opens a door to tomorrow");
      await page.getByTestId("gen-tool-run").click();
      await expect(page.getByTestId("gen-tool-result")).toBeVisible({ timeout: 30_000 });

      // Chroma via API for determinism
      const chroma = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "image.chroma_key", sourceAssetId: asset.id, keyColor: "green" },
      });
      expect(chroma.ok()).toBeTruthy();
      const chromaBody = await chroma.json();
      expect(chromaBody.parentAssetId).toBe(asset.id);
      expect(chromaBody.assetId).not.toBe(asset.id);

      // Upscale (queue or e2e copy)
      const up = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "image.upscale", sourceAssetId: asset.id },
      });
      expect(up.ok()).toBeTruthy();

      // Music / SFX (may be fixture under E2E)
      const music = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "audio.music.generate", prompt: "soft piano", durationSec: 2 },
      });
      expect(music.ok()).toBeTruthy();
      const sfx = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "audio.sfx.generate", prompt: "whoosh", durationSec: 1 },
      });
      expect(sfx.ok()).toBeTruthy();

      await page.goto(`/project/${project.id}?workspace=audiostudio`);
      await expect(page.getByTestId("audio-studio")).toBeVisible();
      await page.screenshot({ path: path.join(OUT, "audio-studio.png") });

      await page.goto(`/project/${project.id}?workspace=scriptwriter`);
      await expect(page.getByTestId("scriptwriter-workspace")).toBeVisible();
      await page.screenshot({ path: path.join(OUT, "scriptwriter.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("GEN-TOOLS-07 delight blocked on run", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32a delight ${Date.now()}`);
    try {
      const res = await request.post(`${API}/api/projects/${project.id}/generation-tools/run`, {
        data: { toolId: "image.delighting", sourceAssetId: "none" },
      });
      expect(res.status()).toBe(503);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("GEN-TOOLS-10 Co-Director catalog tool exists", async ({ request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32a CD ${Date.now()}`);
    try {
      const tools = await (await request.get(`${API}/api/codirector/projects/${project.id}/tools`)).json();
      const ids = (tools.tools || tools || []).map((t: any) => t.toolId || t.id);
      // catalog shape may nest — also probe definitions via read list
      const flat = JSON.stringify(tools);
      expect(flat).toContain("get_generation_tools_catalog");
      expect(flat).toContain("propose_script_document");
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("GEN-TOOLS-20 paid cloud not silent", async ({ request }) => {
    await waitForAppReady(request);
    const catalog = await (await request.get(`${API}/api/generation-tools/catalog`)).json();
    expect(catalog.disclosure).toMatch(/Paid cloud/i);
    for (const t of catalog.tools) {
      expect(t.cloudPaid).toBeFalsy();
    }
  });
});
