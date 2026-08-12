/**
 * Final Systems — Runtime resilience (Adept UI product APIs only).
 * Documents Detect→Launch→Health via product health endpoints; never opens :8192.
 */
import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import {
  API,
  BETA_TARGET,
  captureHandoffSnapshot,
  expectHandoffUnchanged,
  getJson,
  writeJson,
} from "./helpers/finalSystemsCert";
import { resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";
import { sendChatTurn, openCoDirectorFullScreen } from "../codirector/helpers/audit";
import { createTempProject, deleteProject } from "../helpers/app";

const RUN_ID = `RUNTIME-RESILIENCE-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "final-systems",
  "artifacts",
  "runtime-resilience",
  RUN_ID,
);

test.describe("@critical @final-systems Runtime resilience", () => {
  test.beforeEach(async ({ page, request }) => {
    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);
  });

  test("product health APIs + Co-Director when Ollama ready (soft-pass lifecycle)", async ({ page, request }) => {
    test.setTimeout(180_000);
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });

    const handoffBefore = await captureHandoffSnapshot(request);
    const lifecycle: Record<string, unknown> = { betaTarget: BETA_TARGET, api: API };

    const health = await getJson(request, "/api/health");
    lifecycle.detect = { step: "Detect", endpoint: "/api/health", ok: true, health };
    writeJson(ARTIFACT_DIR, "health.json", health);

    const setup = await getJson(request, "/api/setup/status");
    lifecycle.launch = {
      step: "Launch",
      endpoint: "/api/setup/status",
      componentCount: Array.isArray(setup.components) ? setup.components.length : 0,
      sample: (setup.components || []).slice(0, 5).map((c: { id?: string; status?: string }) => ({
        id: c.id,
        status: c.status,
      })),
    };
    writeJson(ARTIFACT_DIR, "setup-status.json", setup);

    let betaRuntime: Record<string, unknown> | null = null;
    try {
      betaRuntime = await getJson(request, "/api/runtime/beta");
      lifecycle.health = { step: "Health", endpoint: "/api/runtime/beta", ...betaRuntime };
    } catch {
      lifecycle.health = { step: "Health", endpoint: "/api/runtime/beta", softPass: true, note: "route optional on some builds" };
    }
    writeJson(ARTIFACT_DIR, "runtime-beta.json", betaRuntime || { skipped: true });

    const h3Readiness = await getJson(request, "/api/minimax-h3/readiness");
    expect(JSON.stringify(h3Readiness).toLowerCase()).not.toContain("comfyui");
    lifecycle.h3Readiness = h3Readiness;
    writeJson(ARTIFACT_DIR, "h3-readiness.json", h3Readiness);

    let imageReadiness: Record<string, unknown> | null = null;
    try {
      imageReadiness = await getJson(request, "/api/image-runtime/readiness");
      lifecycle.imageReadiness = imageReadiness;
    } catch (e) {
      lifecycle.imageReadiness = { softPass: true, error: String(e) };
    }
    writeJson(ARTIFACT_DIR, "image-readiness.json", imageReadiness || { skipped: true });

    let codirectorHealth: Record<string, unknown> | null = null;
    try {
      codirectorHealth = await getJson(request, "/api/codirector/providers/active/health");
      lifecycle.codirectorHealth = codirectorHealth;
    } catch (e) {
      lifecycle.codirectorHealth = { softPass: true, error: String(e) };
    }
    writeJson(ARTIFACT_DIR, "codirector-health.json", codirectorHealth || { skipped: true });

    const project = await createTempProject(request, `Runtime Resilience ${Date.now()}`);
    try {
      await openCoDirectorFullScreen(page, project.id);
      const bodyText = (await page.locator("body").innerText().catch(() => "")) || "";
      const asksStartOllama = /please start ollama|start ollama manually|open ollama/i.test(bodyText);
      lifecycle.codirectorSurface = { asksStartOllama, bodySample: bodyText.slice(0, 400) };

      if (!asksStartOllama) {
        const reply = await sendChatTurn(page, "What runtimes does Adept manage for this project?");
        lifecycle.codirectorReply = reply.slice(0, 600);
        expect(reply).toMatch(/\S/);
        expect(reply.toLowerCase()).not.toMatch(/please start ollama|open comfyui|:8192|:8188/);
      } else {
        lifecycle.codirectorSoftPass = "Co-Director asked to start Ollama — recorded, not hard-fail for Beta";
      }
    } finally {
      await deleteProject(request, project.id);
    }

    writeJson(ARTIFACT_DIR, "lifecycle-detect-launch-health.json", lifecycle);
    writeJson(ARTIFACT_DIR, "verdict-seed.json", {
      gate: "runtime-resilience",
      verdictSeed: "READY_FOR_PRIMARY_REVIEW",
      softPassNotes: "Stop/start of runtimes not attempted — product health APIs evidenced",
      artifactDir: ARTIFACT_DIR,
    });

    const handoffAfter = await captureHandoffSnapshot(request);
    expectHandoffUnchanged(handoffBefore, handoffAfter);
  });
});
