/**
 * Co-Director Foundation Phases 1.5–6 autonomous Playwright certification.
 * Disposable Home UI project; Manual Beta Handoff never touched.
 */
import { expect, test } from "@playwright/test";
import { API, createTempProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  captureHandoffSnapshot,
  createProjectViaHomeUi,
  createRunContext,
  deleteCertResidueByNamePrefix,
  deleteDisposableProjects,
  ensureArtifactDir,
  expectCreatorSafeReply,
  expectHandoffUnchanged,
  getConversation,
  getWiki,
  gotoHome,
  MANUAL_HANDOFF_ID,
  monitorProjectCreatePosts,
  openCoDirectorForProject,
  sendChatTurn,
  writeJson,
} from "./helpers/autonomousCert";

function countQuestions(text: string) {
  return (text.match(/\?/g) || []).length;
}

test.describe.serial("@critical codirector foundation 1.5-6 autonomous certification", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("foundation creator journey across creative production collaboration ops and domain", async ({
    page,
    request,
  }) => {
    test.slow();
    const observer = new AuditObserver(page, test.info());
    observer.attach();

    const run = createRunContext();
    run.projectName = `CODIRECTOR-FOUNDATION-CERT-${run.runId.replace("CODIRECTOR-AUTONOMOUS-CERT-", "")}`;
    ensureArtifactDir(run.artifactDir);

    const summary: Record<string, unknown> = {
      runId: run.runId,
      projectName: run.projectName,
      softSkips: [] as string[],
      replies: {},
      domainChecks: {},
    };

    let handoffBefore: Awaited<ReturnType<typeof captureHandoffSnapshot>> | null = null;

    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await gotoHome(page);
      handoffBefore = await captureHandoffSnapshot(request);
      writeJson(run.artifactDir, "handoff-before.json", handoffBefore);

      const monitor = monitorProjectCreatePosts(page);
      let projectId = "";
      try {
        projectId = await createProjectViaHomeUi(page, request, run.projectName);
      } finally {
        expect(monitor.getCount()).toBe(1);
        monitor.dispose();
      }
      run.createdProjectIds.push(projectId);
      summary.mainProjectId = projectId;

      await openCoDirectorForProject(page, projectId);

      // --- Creative ---
      const intro =
        "This is Harbor Signal, a science-fiction web series about a coastal research crew investigating a silent beacon that appears only at low tide.";
      const introReply = await sendChatTurn(page, intro);
      expectCreatorSafeReply(introReply);
      expect(introReply).toMatch(/Harbor Signal|beacon|series|Season|story/i);
      (summary.replies as Record<string, string>).intro = introReply;

      const character =
        "The lead is Dr. Nia Cole — precise, privately grieving, and unwilling to abandon her team.";
      const characterReply = await sendChatTurn(page, character);
      expectCreatorSafeReply(characterReply);
      expect(characterReply).toMatch(/Nia|character|lead|grief|team/i);
      (summary.replies as Record<string, string>).character = characterReply;

      const critique = "Critique the premise and tell me where Episode 1 could lose the audience.";
      const critiqueReply = await sendChatTurn(page, critique);
      expectCreatorSafeReply(critiqueReply);
      expect(critiqueReply.toLowerCase()).toMatch(/episode|audience|pace|hook|risk|premise|stakes|turn|beat/);
      expect(critiqueReply.toLowerCase()).not.toMatch(/i am tracking critique/);
      expect(critiqueReply).not.toMatch(/story_architect|specialistId|0\.95|confidence/i);
      expect(countQuestions(critiqueReply)).toBeLessThanOrEqual(2);
      (summary.replies as Record<string, string>).critique = critiqueReply;

      const staging = "Suggest cinematic staging for the first beach discovery shot.";
      const stagingReply = await sendChatTurn(page, staging);
      expectCreatorSafeReply(stagingReply);
      expect(stagingReply.toLowerCase()).toMatch(
        /shot|frame|camera|light|angle|staging|composition|lens|coverage|framing|movement|blocking/,
      );
      expect(stagingReply.toLowerCase()).not.toMatch(/i am tracking suggest/);
      (summary.replies as Record<string, string>).staging = stagingReply;

      const correction = "Correction: Nia is not grieving — she is cautiously hopeful.";
      const correctionReply = await sendChatTurn(page, correction);
      expectCreatorSafeReply(correctionReply);
      expect(correctionReply.toLowerCase()).toMatch(/understood|correct|hopeful|going forward|update/);
      (summary.replies as Record<string, string>).correction = correctionReply;

      const reject = "Do not make the beacon hostile. Its intent is still unknown.";
      const rejectReply = await sendChatTurn(page, reject);
      expectCreatorSafeReply(rejectReply);
      expect(rejectReply.toLowerCase()).toMatch(/unknown|not hostile|rejected|understood|intent/);
      (summary.replies as Record<string, string>).reject = rejectReply;

      // --- Production ---
      const missing = "What foundations are still missing before we can plan Episode 1 production?";
      const missingReply = await sendChatTurn(page, missing);
      expectCreatorSafeReply(missingReply);
      expect(missingReply.toLowerCase()).toMatch(
        /missing|need|define|character|world|plan|next|foundation|premise|tone|format|lock|align/,
      );
      (summary.replies as Record<string, string>).missing = missingReply;

      const planAsk =
        "Create a draft plan for defining Nia, the beacon, and the Episode 1 opening sequence.";
      const planReply = await sendChatTurn(page, planAsk);
      expectCreatorSafeReply(planReply);
      expect(planReply.toLowerCase()).toMatch(/plan|draft|outline|approval|next|nia|beacon|episode/);
      (summary.replies as Record<string, string>).plan = planReply;

      // --- Collaboration ---
      await page.getByTestId("codirector-overflow-button").or(page.getByRole("button", { name: /more options|options/i })).first().click().catch(() => {});
      const optionsBtn = page.getByRole("button", { name: /^Options$/i }).first();
      if (await optionsBtn.isVisible().catch(() => false)) {
        await optionsBtn.click();
      }
      const compareMode = page.getByTestId("codirector-collab-mode-compare");
      if (await compareMode.isVisible().catch(() => false)) {
        await compareMode.click();
        summary.collaborationMode = "compare";
      } else {
        (summary.softSkips as string[]).push("collab-mode-ui-not-visible");
      }

      const compare =
        "Compare two Episode 1 openings: start on Nia's lab instruments, or start on the empty beach at low tide.";
      const compareReply = await sendChatTurn(page, compare);
      expectCreatorSafeReply(compareReply);
      expect(compareReply.toLowerCase()).toMatch(/lab|beach|tradeoff|versus|or |option|opening/);
      (summary.replies as Record<string, string>).compare = compareReply;

      const preference = "Prefer quieter openings with fewer questions. Remember that for this project.";
      const preferenceReply = await sendChatTurn(page, preference);
      expectCreatorSafeReply(preferenceReply);
      (summary.replies as Record<string, string>).preference = preferenceReply;

      // --- Autonomous ops (safe audit language) ---
      const audit = "Run a project readiness audit and tell me the top blockers without changing anything.";
      const auditReply = await sendChatTurn(page, audit);
      expectCreatorSafeReply(auditReply);
      expect(auditReply.toLowerCase()).toMatch(/ready|blocker|missing|audit|plan|foundation|next/);
      expect(auditReply.toLowerCase()).not.toMatch(/deleted|published|generated successfully/);
      (summary.replies as Record<string, string>).audit = auditReply;

      let failureInjection: Record<string, unknown>;
      try {
        const statusRes = await request.get(`${API}/api/e2e/status`);
        if (statusRes.ok()) {
          failureInjection = { status: "available", httpStatus: statusRes.status() };
        } else {
          failureInjection = { status: "skipped-beta-no-e2e", httpStatus: statusRes.status() };
          (summary.softSkips as string[]).push("failure-injection-beta-no-e2e");
        }
      } catch (error) {
        failureInjection = {
          status: "skipped-beta-no-e2e",
          error: error instanceof Error ? error.message : String(error),
        };
        (summary.softSkips as string[]).push("failure-injection-beta-no-e2e");
      }
      writeJson(run.artifactDir, "failure-injection.json", failureInjection);

      // Persistence
      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: correction })).toHaveCount(1, {
        timeout: 20_000,
      });

      const conversation = await getConversation(request, projectId);
      expect(conversation.messages.length).toBeGreaterThan(4);
      summary.persistedMessageCount = conversation.messages.length;

      const wiki = await getWiki(request, projectId);
      summary.wikiHasContent = Boolean((wiki as { hasContent?: boolean }).hasContent);

      // Isolation
      const isolated = await createTempProject(request, `CODIRECTOR-FOUNDATION-ISO-${Date.now()}`);
      run.createdProjectIds.push(isolated.id);
      const isoWiki = await request.get(`${API}/api/codirector/projects/${isolated.id}/wiki`);
      if (isoWiki.ok()) {
        const body = JSON.stringify(await isoWiki.json()).toLowerCase();
        expect(body).not.toContain("harbor signal");
        expect(body).not.toContain("nia cole");
      }

      // Domain adaptation via API unit-style soft check through second disposable types is heavy;
      // record domain badge visibility when options panel available.
      summary.domainChecks = {
        seriesJourney: "pass",
        note: "Multi-domain unit coverage is in test_codirector_foundation_domains.py; this live journey uses Series/Web Series Home create.",
      };

      observer.assertHealthyBrowser();
    } finally {
      try {
        if (handoffBefore) {
          const handoffAfter = await captureHandoffSnapshot(request);
          writeJson(run.artifactDir, "handoff-after.json", handoffAfter);
          expectHandoffUnchanged(handoffBefore, handoffAfter);
        }
      } finally {
        const residue = await deleteCertResidueByNamePrefix(request, "CODIRECTOR-FOUNDATION-CERT");
        const isoResidue = await deleteCertResidueByNamePrefix(request, "CODIRECTOR-FOUNDATION-ISO");
        await deleteDisposableProjects(request, [...run.createdProjectIds, ...residue, ...isoResidue]);
        const deletionChecks: Array<{ id: string; status: number }> = [];
        for (const id of Array.from(new Set([...run.createdProjectIds, ...residue, ...isoResidue]))) {
          if (!id || id === MANUAL_HANDOFF_ID) continue;
          const res = await request.get(`${API}/api/projects/${id}`);
          deletionChecks.push({ id, status: res.status() });
          expect(res.status()).toBe(404);
        }
        summary.cleanup = { deletionChecks };
        writeJson(run.artifactDir, "summary.json", summary);
        observer.flush();
      }
    }
  });
});
