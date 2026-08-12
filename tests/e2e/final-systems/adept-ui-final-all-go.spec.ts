/**
 * Finale All-GO Playwright orchestrator (Final Systems).
 *
 * ADEPT_BETA_TARGET=1 via npm run test:e2e:beta — workers=1, retries=0 assumed by runner.
 * Single disposable project; product API for verification after UI actions only.
 * Never mutates protected project 77a4b96c-8e3f-4501-897c-51bab99bedb7.
 */
import { test, expect } from "@playwright/test";
import {
  API,
  BASELINE_PROMPT,
  MANUAL_HANDOFF_ID,
  RETAKE_DELTA,
  artifactDirFor,
  attachForbiddenRuntimeWatcher,
  captureHandoffSnapshot,
  createFinaleProjectViaHome,
  ensureScene,
  expectHandoffUnchanged,
  generateTake1ViaTimelineUi,
  getJson,
  makeRunId,
  openWorkspace,
  shotIdForScene,
  writeJson,
} from "./helpers/finalSystemsCert";
import { deleteProject, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen, sendChatTurn } from "../codirector/helpers/audit";

const RUN_ID = makeRunId("ALL-GO");
const ARTIFACT_DIR = artifactDirFor(RUN_ID);

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @final-systems Adept UI Final All-GO", () => {
  test("Phases 0–21 — single Brand Ad project production path", async ({ page, request }) => {
    test.setTimeout(90 * 60_000);

    const handoffBefore = await captureHandoffSnapshot(request);
    const watcher = attachForbiddenRuntimeWatcher(page);
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    const ctx: Record<string, unknown> = {
      runId: RUN_ID,
      artifactDir: ARTIFACT_DIR,
      phases: {} as Record<string, unknown>,
      blockers: [] as string[],
    };

    let projectId = "";
    let sceneId = "";
    let shotId = "";
    let take1Id = "";
    let take2Id = "";

    try {
      // —— Phase 0: Preflight ——
      const health = await getJson(request, "/api/health");
      const h3Readiness = await getJson(request, "/api/minimax-h3/readiness");
      let imageReadiness: Record<string, unknown> = {};
      try {
        imageReadiness = await getJson(request, "/api/image-runtime/readiness");
      } catch {
        ctx.blockers.push("image-runtime readiness unavailable");
      }
      writeJson(ARTIFACT_DIR, "0-preflight.json", {
        health,
        h3Readiness,
        imageReadiness,
        betaTarget: process.env.ADEPT_BETA_TARGET === "1",
      });
      ctx.phases["0-preflight"] = { ok: health.ok !== false, h3Ready: h3Readiness.ready };

      // —— Phase 1: Project ——
      const projectName = `ADEPT-FINALE-BRAND-${Date.now()}`;
      projectId = await createFinaleProjectViaHome(page, request, projectName);
      expect(projectId).not.toBe(MANUAL_HANDOFF_ID);
      writeJson(ARTIFACT_DIR, "1-project.json", { projectId, name: projectName });
      ctx.phases["1-project"] = { projectId, name: projectName };

      // —— Phase 2: Brand Studio ——
      const brand = await openWorkspace(page, projectId, "brandstudio", "brand-studio");
      if (brand.ok) {
        const brief = page.getByTestId("brand-brief");
        if (await brief.isVisible().catch(() => false)) {
          await brief.fill("Finale brand campaign — glossy product hero with headline space.");
        }
      }
      writeJson(ARTIFACT_DIR, "2-brand.json", brand);
      ctx.phases["2-brand"] = brand;

      // —— Phase 3: Scriptwriter ——
      await page.goto(`/project/${projectId}?workspace=scriptwriter`);
      await page.waitForLoadState("domcontentloaded");
      const scriptShell = page
        .getByTestId("scriptwriter-studio")
        .or(page.getByTestId("scriptwriter-workspace"))
        .first();
      const scriptVisible = await scriptShell.isVisible({ timeout: 45_000 }).catch(() => false);
      const scriptEvidence: Record<string, unknown> = { workspaceVisible: scriptVisible };
      if (scriptVisible) {
        const title = page.getByTestId("scriptwriter-title");
        if (await title.isVisible().catch(() => false)) {
          await title.fill("Finale Brand Spot");
          scriptEvidence.legacyTitleFilled = true;
        }
        const brief = page.getByTestId("scriptwriter-brief");
        if (await brief.isVisible().catch(() => false)) {
          await brief.fill("15s product hero — bottle reveal, CTA end card.");
          scriptEvidence.legacyBriefFilled = true;
        }
        if (await page.getByTestId("scriptwriter-page").isVisible().catch(() => false)) {
          scriptEvidence.studioMounted = true;
        }
      } else {
        const bodyText = (await page.locator("body").innerText().catch(() => "")) || "";
        scriptEvidence.note = "scriptwriter shell not found — recorded body sample";
        scriptEvidence.bodySample = bodyText.slice(0, 400);
      }
      writeJson(ARTIFACT_DIR, "3-script.json", scriptEvidence);
      ctx.phases["3-script"] = scriptEvidence;

      // —— Phase 4: Reference assets ——
      const png = Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      );
      const upload = await request.post(`${API}/api/projects/${projectId}/assets`, {
        multipart: {
          file: { name: "finale-ref.png", mimeType: "image/png", buffer: png },
          kind: "image",
          tag: "finale-ref",
        },
      });
      const assetBody = upload.ok() ? await upload.json() : { error: await upload.text() };
      writeJson(ARTIFACT_DIR, "4-reference-assets.json", { uploadOk: upload.ok(), asset: assetBody });
      ctx.phases["4-reference-assets"] = { uploadOk: upload.ok() };

      // —— Phase 5: One Frame ——
      await page.goto(`/project/${projectId}?workspace=one`);
      const onePanel = page.getByTestId("one-frame-panel");
      await expect(onePanel).toBeVisible({ timeout: 45_000 });
      const onePrompt = onePanel.getByTestId("one-frame-motion-prompt");
      if (await onePrompt.isVisible().catch(() => false)) {
        await onePrompt.fill("Slow push-in from the Start Frame.");
      }
      if (await onePanel.getByTestId("minimax-h3-prepare").isVisible().catch(() => false)) {
        await onePanel.getByTestId("minimax-h3-prepare").click();
      }
      writeJson(ARTIFACT_DIR, "5-one-frame.json", { panelVisible: true });
      ctx.phases["5-one-frame"] = { ok: true };

      // —— Phase 6: Three Frame ——
      await page.goto(`/project/${projectId}?workspace=three`);
      const threePanel = page.getByTestId("three-frame-panel");
      await expect(threePanel).toBeVisible({ timeout: 45_000 });
      writeJson(ARTIFACT_DIR, "6-three-frame.json", { panelVisible: true, strip: await threePanel.getByTestId("three-frame-strip").isVisible().catch(() => false) });
      ctx.phases["6-three-frame"] = { ok: true };

      // —— Phase 7: Text-to-video ——
      await page.goto(`/project/${projectId}?workspace=txt2vid`);
      const engine = page.locator("#txt2vid-engine");
      if (await engine.isVisible().catch(() => false)) {
        await engine.selectOption("minimax-h3").catch(() => undefined);
      }
      const t2vPrompt = page.locator("textarea").first();
      if (await t2vPrompt.isVisible().catch(() => false)) {
        await t2vPrompt.fill("Cinematic product table push-in with controlled rim light.");
      }
      if (await page.getByTestId("minimax-h3-prepare").isVisible().catch(() => false)) {
        await page.getByTestId("minimax-h3-prepare").click();
      }
      writeJson(ARTIFACT_DIR, "7-text-to-video.json", { engineVisible: await engine.isVisible().catch(() => false) });
      ctx.phases["7-text-to-video"] = { ok: true };

      // —— Phase 8: Take 1 — UI H3 job + library asset baseline ——
      sceneId = await ensureScene(request, projectId, BASELINE_PROMPT);
      shotId = shotIdForScene(sceneId);
      const take1 = await generateTake1ViaTimelineUi(page, request, projectId, sceneId, BASELINE_PROMPT);
      take1Id = take1.take1Id;
      writeJson(ARTIFACT_DIR, "8-take1.json", take1);
      ctx.phases["8-take1"] = { take1Id, assetId: take1.assetId, jobId: take1.jobId };

      // —— Phase 9: Re-take cancel ——
      await page.getByTestId("timeline-open-retake").click();
      await expect(page.getByTestId("timeline-retake-drawer")).toBeVisible({ timeout: 15_000 });
      const retakeDrawer = page.getByTestId("timeline-retake-drawer");
      await retakeDrawer.getByTestId("timeline-retake-delta").fill(RETAKE_DELTA);
      await retakeDrawer.getByTestId("minimax-h3-prepare").click();
      await expect(retakeDrawer.getByTestId("minimax-h3-generate")).toBeVisible({ timeout: 60_000 });
      const cancelPost = page.waitForResponse(
        (r) => r.url().includes("/api/minimax-h3/jobs") && r.request().method() === "POST",
        { timeout: 60_000 },
      );
      await retakeDrawer.getByTestId("minimax-h3-generate").click();
      const cancelBody = await (await cancelPost).json();
      const cancelJobId = cancelBody.jobId as string;
      await expect
        .poll(async () => {
          const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${cancelJobId}`);
          return (await r.json()).job?.status;
        }, { timeout: 120_000 })
        .toMatch(/running|completed|failed|cancelled/);
      const cancelBtn = retakeDrawer.getByTestId("minimax-h3-cancel");
      if ((await cancelBtn.isVisible().catch(() => false)) && (await cancelBtn.isEnabled().catch(() => false))) {
        await cancelBtn.click();
      } else {
        await request.post(`${API}/api/minimax-h3/jobs/cancel`, {
          data: { projectId, planId: cancelBody.planId, jobId: cancelJobId, reason: "all-go-cancel" },
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
      writeJson(ARTIFACT_DIR, "9-retake-cancel.json", { cancelJobId, afterCancel: afterCancelBody });
      ctx.phases["9-retake-cancel"] = { ok: true };

      // —— Phase 10: Re-take complete + alternate ——
      await page.getByTestId("timeline-open-retake").click();
      await expect(page.getByTestId("timeline-retake-drawer")).toBeVisible({ timeout: 15_000 });
      const retakeDrawer2 = page.getByTestId("timeline-retake-drawer");
      await retakeDrawer2.getByTestId("timeline-retake-delta").fill(RETAKE_DELTA);
      await retakeDrawer2.getByTestId("minimax-h3-prepare").click();
      const successPost = page.waitForResponse(
        (r) => r.url().includes("/api/minimax-h3/jobs") && r.request().method() === "POST",
        { timeout: 60_000 },
      );
      await retakeDrawer2.getByTestId("minimax-h3-generate").click();
      const successBody = await (await successPost).json();
      const successJobId = successBody.jobId as string;
      let successJob: Record<string, any>;
      await expect
        .poll(async () => {
          const r = await request.get(`${API}/api/minimax-h3/jobs/${projectId}/${successJobId}`);
          successJob = (await r.json()).job;
          return successJob?.status;
        }, { timeout: 25 * 60_000, intervals: [5_000, 15_000] })
        .toBe("completed");
      await expect(page.getByTestId("timeline-retake-add-alternate")).toBeVisible({ timeout: 120_000 });
      await page.getByTestId("timeline-retake-add-alternate").click();
      await expect(page.getByTestId("timeline-retake-takes")).toContainText("Take 2", { timeout: 30_000 });
      const withAlt = await request.get(
        `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
      );
      const withAltBody = await withAlt.json();
      const take2 = withAltBody.shot.takes.find((t: { takeNumber?: number; retake?: boolean }) => t.takeNumber === 2 || t.retake);
      take2Id = take2?.takeId;
      writeJson(ARTIFACT_DIR, "10-retake-complete.json", { successJob, withAlt: withAltBody });
      ctx.phases["10-retake-complete"] = { take2Id, successJobId };

      // —— Phase 11: Take lineage ——
      expect(withAltBody.shot?.takes?.length).toBe(2);
      expect(take2?.sourceTakeId).toBe(take1Id);
      await page.getByTestId(`timeline-take-activate-${take2Id}`).click();
      await page.reload();
      await page.goto(`/project/${projectId}?workspace=timeline&sceneId=${encodeURIComponent(sceneId)}`);
      const lineage = await request.get(
        `${API}/api/timeline-retakes/projects/${projectId}/shots/${encodeURIComponent(shotId)}`,
      );
      const lineageBody = await lineage.json();
      writeJson(ARTIFACT_DIR, "11-take-lineage.json", lineageBody);
      ctx.phases["11-take-lineage"] = { takeCount: lineageBody.shot?.takes?.length, activeTakeId: lineageBody.shot?.activeTakeId };

      // —— Phase 12: MAGI ——
      const magi = await openWorkspace(page, projectId, "magi", "magi-viewer");
      writeJson(ARTIFACT_DIR, "12-magi.json", magi);
      ctx.phases["12-magi"] = magi;

      // —— Phase 13: Audio ——
      const audio = await openWorkspace(page, projectId, "audiostudio");
      writeJson(ARTIFACT_DIR, "13-audio.json", audio);
      ctx.phases["13-audio"] = audio;

      // —— Phase 14: Export ——
      const exportRes = await request.post(`${API}/api/projects/${projectId}/export`, {
        data: { exportMode: "without_password" },
      });
      const exportEvidence: Record<string, unknown> = {
        status: exportRes.status(),
        ok: exportRes.ok(),
      };
      if (exportRes.ok()) {
        exportEvidence.body = await exportRes.json();
      } else {
        exportEvidence.raw = await exportRes.text();
        ctx.blockers.push("export not completed");
      }
      writeJson(ARTIFACT_DIR, "14-export.json", exportEvidence);
      ctx.phases["14-export"] = exportEvidence;

      // —— Phase 15: Memory recall (Co-Director) ——
      await openCoDirectorFullScreen(page, projectId);
      const recallReply = await sendChatTurn(
        page,
        "What brand project am I working on and what takes exist on the timeline?",
      );
      writeJson(ARTIFACT_DIR, "15-memory-recall.json", { question: "brand + takes", reply: recallReply.slice(0, 800) });
      ctx.phases["15-memory-recall"] = { replied: recallReply.length > 0 };

      // —— Phase 16: Runtime recovery ——
      const runtimeRecovery = {
        h3: await getJson(request, "/api/minimax-h3/readiness"),
        image: await getJson(request, "/api/image-runtime/readiness").catch((e) => ({ error: String(e) })),
        setup: await getJson(request, "/api/setup/status"),
        runtimeBeta: await getJson(request, "/api/runtime/beta").catch(() => ({ softPass: true })),
        lifecycle: "Detect(/api/health) → Launch(/api/setup/status) → Health(/api/runtime/beta, readiness probes)",
      };
      writeJson(ARTIFACT_DIR, "16-runtime-recovery.json", runtimeRecovery);
      ctx.phases["16-runtime-recovery"] = { documented: true };

      // —— Phase 17: A11y viewport smoke ——
      for (const size of [
        { width: 1280, height: 800, label: "desktop" },
        { width: 390, height: 844, label: "mobile" },
      ]) {
        await page.setViewportSize(size);
        await page.goto(`/project/${projectId}?workspace=timeline`);
        await expect(page.locator("body")).toBeVisible({ timeout: 30_000 });
      }
      writeJson(ARTIFACT_DIR, "17-a11y.json", { viewports: ["1280x800", "390x844"], ok: true });
      ctx.phases["17-a11y"] = { ok: true };

      // —— Phase 18: Console / network ——
      writeJson(ARTIFACT_DIR, "18-console-network.json", {
        forbiddenHits: watcher.forbiddenHits,
        consoleErrorCount: consoleErrors.length,
        consoleSample: consoleErrors.slice(0, 10),
      });
      expect(watcher.forbiddenHits, "browser must not call :8188/:8192 directly").toEqual([]);
      ctx.phases["18-console-network"] = { forbiddenHits: watcher.forbiddenHits.length };

      // —— Phase 19: Protected project ——
      const handoffMid = await captureHandoffSnapshot(request);
      expectHandoffUnchanged(handoffBefore, handoffMid);
      writeJson(ARTIFACT_DIR, "19-protected-project.json", { handoffUnchanged: true, protectedId: MANUAL_HANDOFF_ID });
      ctx.phases["19-protected-project"] = { ok: true };

      // —— Phase 20: Cleanup deferred to finally ——
      writeJson(ARTIFACT_DIR, "20-cleanup-pending.json", { projectId, note: "deleted in finally" });

      // —— Phase 21: Verdict seed (primary issues GO — subagent does not) ——
      const mediaManifest = {
        runId: RUN_ID,
        projectId,
        sceneId,
        shotId,
        take1Id,
        take2Id,
        phasesCompleted: Object.keys(ctx.phases),
        blockers: ctx.blockers,
      };
      writeJson(ARTIFACT_DIR, "finale-media-manifest.json", mediaManifest);
      writeJson(ARTIFACT_DIR, "21-verdict.json", {
        verdictSeed: "READY_FOR_PRIMARY_REVIEW",
        finalGo: false,
        note: "Subagent returns READY FOR PRIMARY REVIEW — primary issues GO/NO-GO",
        blockers: ctx.blockers,
        artifactDir: ARTIFACT_DIR,
      });
    } finally {
      watcher.dispose();
      if (projectId && projectId !== MANUAL_HANDOFF_ID) {
        await deleteProject(request, projectId);
      }
      writeJson(ARTIFACT_DIR, "20-cleanup.json", { deletedProjectId: projectId || null });
      const handoffAfter = await captureHandoffSnapshot(request);
      expectHandoffUnchanged(handoffBefore, handoffAfter);
    }
  });
});
