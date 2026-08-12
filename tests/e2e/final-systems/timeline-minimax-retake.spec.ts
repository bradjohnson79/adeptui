/**
 * Phase — Timeline MiniMax Re-take (Final Systems locked gate).
 * Single disposable project. Take 1 from UI-generated H3 job + library asset.
 */
import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import {
  BASELINE_PROMPT,
  RETAKE_DELTA,
  generateTake1ViaTimelineUi,
} from "./helpers/finalSystemsCert";
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
  `retake-${new Date().toISOString().replace(/[:.]/g, "-")}`,
);

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

async function ensureScene(request: any, projectId: string): Promise<string> {
  const list = await request.get(`${API}/api/projects/${projectId}/scenes`);
  const body = await list.json();
  const scenes = body.scenes || body || [];
  if (Array.isArray(scenes) && scenes[0]?.id) return scenes[0].id;
  const created = await request.post(`${API}/api/projects/${projectId}/scenes`, {
    data: { title: "Product Ad Shot", prompt: BASELINE_PROMPT },
  });
  const c = await created.json();
  return c.id || c.scene?.id;
}

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @final-systems Timeline MiniMax Re-take", () => {
  test("Phase — UI Take 1, cancel then successful Add as Alternate Take + reload", async ({ page, request }) => {
    test.setTimeout(45 * 60_000);
    const project = await createTempProject(request, `Final Systems Product Ad ${Date.now()}`);
    const projectId = project.id;
    writeJson("project.json", { projectId, name: project.name || project.title });

    try {
      expect(projectId).not.toBe("77a4b96c-8e3f-4501-897c-51bab99bedb7");

      const sceneId = await ensureScene(request, projectId);
      const { take1Id: take1, shotId, baselineBody } = await generateTake1ViaTimelineUi(
        page,
        request,
        projectId,
        sceneId,
        BASELINE_PROMPT,
      );
      writeJson("baseline.json", baselineBody);

      await page.getByTestId("timeline-open-retake").click();
      await expect(page.getByTestId("timeline-retake-drawer")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("timeline-retake-engine")).toContainText("MiniMax H3");
      const drawer = page.getByTestId("timeline-retake-drawer");
      await drawer.getByTestId("timeline-retake-delta").fill(RETAKE_DELTA);

      await drawer.getByTestId("minimax-h3-prepare").click();
      await expect(drawer.getByTestId("minimax-h3-generate")).toBeVisible({ timeout: 60_000 });
      const jobPost = page.waitForResponse(
        (r) => r.url().includes("/api/minimax-h3/jobs") && r.request().method() === "POST",
        { timeout: 60_000 },
      );
      await drawer.getByTestId("minimax-h3-generate").click();
      const jobRes = await jobPost;
      const jobBody = await jobRes.json().catch(() => ({}));
      const cancelJobId = jobBody.jobId as string;
      expect(cancelJobId, "cancel attempt must create a job").toBeTruthy();

      await expect
        .poll(async () => {
          const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${cancelJobId}`);
          const j = await r.json();
          return j.job?.status;
        }, { timeout: 120_000, intervals: [2_000, 5_000] })
        .toMatch(/running|completed|failed|cancelled/);

      const cancelBtn = drawer.getByTestId("minimax-h3-cancel");
      const cancelEnabled = await cancelBtn.isEnabled().catch(() => false);
      if ((await cancelBtn.isVisible().catch(() => false)) && cancelEnabled) {
        await cancelBtn.click();
      } else {
        const planId = jobBody.planId;
        await request.post(`${API}/api/minimax-h3/jobs/cancel`, {
          data: { projectId, planId, jobId: cancelJobId, reason: "final-systems-cancel-probe" },
        });
      }

      await expect
        .poll(async () => {
          const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${cancelJobId}`);
          return (await r.json()).job?.status;
        }, { timeout: 60_000 })
        .toMatch(/cancelled|failed|completed/);

      const afterCancel = await request.get(
        `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
      );
      const afterCancelBody = await afterCancel.json();
      expect(afterCancelBody.shot?.takes?.length).toBe(1);
      writeJson("after-cancel.json", afterCancelBody);

      await page.getByTestId("timeline-open-retake").click();
      await expect(page.getByTestId("timeline-retake-drawer")).toBeVisible({ timeout: 15_000 });
      const drawer2 = page.getByTestId("timeline-retake-drawer");
      await drawer2.getByTestId("timeline-retake-delta").fill(RETAKE_DELTA);
      await drawer2.getByTestId("minimax-h3-prepare").click();
      await expect(drawer2.getByTestId("minimax-h3-generate")).toBeVisible({ timeout: 60_000 });
      const successPost = page.waitForResponse(
        (r) => r.url().includes("/api/minimax-h3/jobs") && r.request().method() === "POST",
        { timeout: 60_000 },
      );
      await drawer2.getByTestId("minimax-h3-generate").click();
      const successBody = await (await successPost).json();
      const successJobId = successBody.jobId as string;
      expect(successJobId).toBeTruthy();
      expect(successJobId).not.toBe(cancelJobId);

      let successJob: any;
      await expect
        .poll(async () => {
          const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${successJobId}`);
          successJob = (await r.json()).job;
          return successJob?.status;
        }, { timeout: 25 * 60_000, intervals: [5_000, 15_000] })
        .toBe("completed");

      writeJson("success-job.json", successJob);
      const prov = successJob.provenance || {};
      expect(prov.apiUsed).toBe(false);
      expect(prov.ltxUsed).toBe(false);
      expect(prov.deployment).toBe("private-local");
      expect(String(prov.runtime || "")).toContain("route-a");

      await expect(page.getByTestId("timeline-retake-add-alternate")).toBeVisible({ timeout: 120_000 });
      await page.getByTestId("timeline-retake-add-alternate").click();
      await expect(page.getByTestId("timeline-retake-takes")).toContainText("Take 2", { timeout: 30_000 });

      const withAlt = await request.get(
        `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
      );
      const withAltBody = await withAlt.json();
      expect(withAltBody.shot?.takes?.length).toBe(2);
      const take2 = withAltBody.shot.takes.find((t: any) => t.takeNumber === 2 || t.retake);
      expect(take2?.sourceTakeId).toBe(take1);
      expect(take2?.provenance?.retake).toBe(true);
      expect(take2?.provenance?.ltxUsed).toBe(false);
      writeJson("with-alternate.json", withAltBody);

      await page.getByTestId(`timeline-take-activate-${take2.takeId}`).click();
      await expect
        .poll(async () => {
          const r = await request.get(
            `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
          );
          return (await r.json()).shot?.activeTakeId;
        }, { timeout: 15_000 })
        .toBe(take2.takeId);

      await page.reload();
      await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${encodeURIComponent(sceneId)}`);
      await page.getByTestId("timeline-open-retake").click();
      await expect(page.getByTestId("timeline-retake-takes")).toContainText("Take 1", { timeout: 30_000 });
      await expect(page.getByTestId("timeline-retake-takes")).toContainText("Take 2");

      const afterReload = await request.get(
        `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
      );
      const reloadBody = await afterReload.json();
      expect(reloadBody.shot?.takes?.length).toBe(2);
      expect(reloadBody.shot?.activeTakeId).toBe(take2.takeId);
      expect(reloadBody.shot?.takes?.[0]?.takeId).toBe(take1);
      writeJson("after-reload.json", reloadBody);
      writeJson("verdict-seed.json", {
        productLaw: "single_project_adept_ui_only",
        take1Source: "ui_h3_job_with_library_asset",
        retakeGate: "PASS_SEED",
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      await deleteProject(request, projectId);
    }
  });
});
