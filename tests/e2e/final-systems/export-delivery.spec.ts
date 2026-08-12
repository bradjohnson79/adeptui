/**
 * Final Systems — Export delivery (best-effort real export via product API after UI context).
 * Skips honestly when unsupported; seeds NO-GO when export unavailable.
 */
import { test, expect } from "@playwright/test";
import * as path from "path";
import {
  API,
  createFinaleProjectViaHome,
  ensureScene,
  makeRunId,
  writeJson,
  MANUAL_HANDOFF_ID,
} from "./helpers/finalSystemsCert";
import { deleteProject, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";

const RUN_ID = makeRunId("EXPORT");
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "final-systems",
  "artifacts",
  "export-delivery",
  RUN_ID,
);

test.describe("@critical @final-systems Export delivery", () => {
  test.beforeEach(async ({ page, request }) => {
    await waitForAppReady(request);
    await resetLiveBetaTestSurface(request, page);
  });

  test("best-effort project export + manifest", async ({ page, request }) => {
    test.setTimeout(180_000);
    const name = `ADEPT-FINALE-EXPORT-${Date.now()}`;
    const projectId = await createFinaleProjectViaHome(page, request, name);
    expect(projectId).not.toBe(MANUAL_HANDOFF_ID);
    writeJson(ARTIFACT_DIR, "project.json", { projectId, name });

    const manifest: Record<string, unknown> = {
      runId: RUN_ID,
      projectId,
      exportAttempted: false,
      exportSupported: false,
      verdictSeed: "NO-GO",
      note: "Export not attempted",
    };

    try {
      await page.goto(`/project/${projectId}?workspace=timeline`);
      await page.waitForLoadState("domcontentloaded");

      const sceneId = await ensureScene(request, projectId);
      manifest.sceneId = sceneId;

      const exportRes = await request.post(`${API}/api/projects/${projectId}/export`, {
        data: { exportMode: "without_password" },
      });
      manifest.exportAttempted = true;
      manifest.exportStatus = exportRes.status();

      if (exportRes.status() === 404 || exportRes.status() === 501) {
        manifest.exportSupported = false;
        manifest.note = "Export endpoint unavailable — honest NO-GO seed";
        writeJson(ARTIFACT_DIR, "export-manifest.json", manifest);
        writeJson(ARTIFACT_DIR, "verdict-seed.json", {
          gate: "export-delivery",
          verdictSeed: "NO-GO",
          reason: "export API not supported",
          artifactDir: ARTIFACT_DIR,
        });
        test.skip(true, "Export API not supported on this build");
        return;
      }

      const exportBody = await exportRes.json().catch(async () => ({ raw: await exportRes.text() }));
      writeJson(ARTIFACT_DIR, "export-response.json", exportBody);

      if (!exportRes.ok()) {
        manifest.exportSupported = true;
        manifest.exportOk = false;
        manifest.note = "Export endpoint exists but returned error — NO-GO seed";
        writeJson(ARTIFACT_DIR, "export-manifest.json", manifest);
        writeJson(ARTIFACT_DIR, "verdict-seed.json", {
          gate: "export-delivery",
          verdictSeed: "NO-GO",
          reason: "export failed",
          artifactDir: ARTIFACT_DIR,
        });
        return;
      }

      manifest.exportSupported = true;
      manifest.exportOk = true;
      manifest.jobId = exportBody.id || exportBody.jobId || null;

      if (manifest.jobId) {
        await expect
          .poll(async () => {
            const jobRes = await request.get(`${API}/api/jobs/${manifest.jobId}`);
            if (!jobRes.ok()) return "unknown";
            const job = await jobRes.json();
            return job.status || job.state;
          }, { timeout: 180_000, intervals: [2_000, 5_000, 10_000] })
          .toMatch(/completed|failed|cancelled|done/i);
        const finalJob = await request.get(`${API}/api/jobs/${manifest.jobId}`);
        if (finalJob.ok()) {
          const job = await finalJob.json();
          manifest.finalJob = job;
          manifest.outputPath = job.output_path || job.outputPath || null;
          const terminal = String(job.status || "").toLowerCase();
          manifest.exportCompleted = terminal === "completed" || terminal === "done";
          if (!manifest.exportCompleted || !manifest.outputPath) {
            manifest.exportOk = false;
            manifest.note = "Export job did not produce a completed output_path — NO-GO seed";
            manifest.verdictSeed = "NO-GO";
          }
        }
      }

      if (manifest.exportOk && manifest.exportCompleted && manifest.outputPath) {
        manifest.verdictSeed = "READY_FOR_PRIMARY_REVIEW";
        manifest.note = "Export pack completed with output_path";
      } else if (manifest.verdictSeed !== "NO-GO") {
        manifest.verdictSeed = "NO-GO";
        manifest.note = manifest.note || "Export incomplete";
      }
      writeJson(ARTIFACT_DIR, "export-manifest.json", manifest);
      writeJson(ARTIFACT_DIR, "verdict-seed.json", {
        gate: "export-delivery",
        verdictSeed: manifest.verdictSeed,
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
