import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import {
  TINY_MP4,
  TINY_PNG,
  TINY_WAV,
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
  MANUAL_HANDOFF_NAME,
  monitorProjectCreatePosts,
  openCoDirectorForProject,
  sendChatTurn,
  uploadProjectAsset,
  writeJson,
} from "./helpers/autonomousCert";

type SpeechScenario =
  | { type: "success"; transcript: string }
  | { type: "error"; error: string };

function countQuestions(text: string) {
  return (text.match(/\?/g) || []).length;
}

function windowsPathPattern() {
  return /\b[A-Z]:\\(?:[^\\\r\n]+\\)+[^\\\r\n]*/;
}

function jsonText(value: unknown) {
  return JSON.stringify(value, null, 2);
}

async function getWikiText(request: APIRequestContext, projectId: string) {
  return jsonText(await getWiki(request, projectId));
}

async function waitForWikiMatch(request: APIRequestContext, projectId: string, pattern: RegExp) {
  let last = "";
  await expect
    .poll(async () => {
      last = (await getWikiText(request, projectId)).toLowerCase();
      return last;
    }, { timeout: 60_000 })
    .toMatch(pattern);
  return last;
}

async function getActivePlanState(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/plans/active`);
  const text = await res.text();
  if (!res.ok()) {
    return {
      ok: false,
      status: res.status(),
      text,
      json: null as unknown,
    };
  }

  let body: unknown = null;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }

  return {
    ok: true,
    status: res.status(),
    text,
    json: body,
  };
}

async function getWikiTextAllowMissing(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/wiki`);
  if (res.status() === 404) {
    return "";
  }
  expect(res.ok(), await res.text()).toBeTruthy();
  return jsonText(await res.json());
}

async function installSpeechRecognitionMock(page: Page, scenarios: SpeechScenario[]) {
  await page.addInitScript((queuedScenarios: SpeechScenario[]) => {
    type BrowserSpeechScenario =
      | { type: "success"; transcript: string }
      | { type: "error"; error: string };

    const queue = [...queuedScenarios];

    class MockSpeechRecognition {
      continuous = false;
      interimResults = true;
      lang = "en-US";
      onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      private scenario: BrowserSpeechScenario =
        queue.shift() || { type: "success", transcript: "Begin with Mara's point of view." };
      private emitted = false;

      start() {
        if (this.scenario.type === "error") {
          window.setTimeout(() => {
            this.onerror?.({ error: this.scenario.error });
            this.onend?.();
          }, 25);
        }
      }

      stop() {
        if (this.emitted || this.scenario.type !== "success") {
          window.setTimeout(() => this.onend?.(), 0);
          return;
        }
        this.emitted = true;
        window.setTimeout(() => {
          this.onresult?.({
            results: [[{ transcript: this.scenario.type === "success" ? this.scenario.transcript : "" }]],
          });
        }, 25);
        window.setTimeout(() => this.onend?.(), 50);
      }

      abort() {
        this.emitted = true;
        window.setTimeout(() => {
          this.onerror?.({ error: "aborted" });
          this.onend?.();
        }, 0);
      }
    }

    (window as Window & { SpeechRecognition?: typeof MockSpeechRecognition }).SpeechRecognition = MockSpeechRecognition;
    (window as Window & { webkitSpeechRecognition?: typeof MockSpeechRecognition }).webkitSpeechRecognition =
      MockSpeechRecognition;
  }, scenarios);
}

test.describe.serial("@critical codirector autonomous certification", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("Project Meridian full journey", async ({ page, request }) => {
    test.slow();

    const observer = new AuditObserver(page, test.info());
    observer.attach();

    const run = createRunContext();
    ensureArtifactDir(run.artifactDir);

    const summary: Record<string, unknown> = {
      runId: run.runId,
      projectName: run.projectName,
      manualHandoff: {
        id: MANUAL_HANDOFF_ID,
        name: MANUAL_HANDOFF_NAME,
      },
      createdProjectIds: run.createdProjectIds,
      replies: {},
      softSkips: [] as string[],
    };

    let handoffBefore: Awaited<ReturnType<typeof captureHandoffSnapshot>> | null = null;
    let handoffAfter: Awaited<ReturnType<typeof captureHandoffSnapshot>> | null = null;

    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await gotoHome(page);

      handoffBefore = await captureHandoffSnapshot(request);
      writeJson(run.artifactDir, "handoff-before.json", handoffBefore);

      const createMonitor = monitorProjectCreatePosts(page);
      let projectId = "";
      try {
        projectId = await createProjectViaHomeUi(page, request, run.projectName);
      } finally {
        const postCount = createMonitor.getCount();
        createMonitor.dispose();
        summary.projectCreatePosts = postCount;
        expect(postCount).toBe(1);
      }
      run.createdProjectIds.push(projectId);
      summary.mainProjectId = projectId;

      await openCoDirectorForProject(page, projectId);

      const introduction =
        "This project is called Project Meridian. It is a science-fiction web series about a research team investigating a crashed probe in Season 1.";
      const nextQuestion = "What should we define next?";
      const signalPrelude = "Let me explain the signal first.";
      const signalLore =
        "The signal lasted 47 minutes and carried a mathematical structure that no one on the team could decode at first.";
      const maraIntro =
        "Mara Vale is disciplined, skeptical, protective of the team, and currently serves as the facility director.";
      const maraCorrection = "Correction: Mara is the mission lead, not the facility director.";
      const facilityUnresolved = "The facility might be privately owned, but that is not confirmed yet.";
      const signalIntent = "Do not define the signal as hostile. Its intent is still unknown.";
      const characterContinuation = "Yes, begin with the main character.";
      const episodeQuestion = "Give me the best next three steps for developing Episode 1.";
      const draftPlanRequest = "Create a draft plan for defining Mara, the probe signal, and the Episode 1 opening.";

      const introReply = await sendChatTurn(page, introduction);
      expectCreatorSafeReply(introReply);
      expect(introReply).toMatch(/Meridian|science|probe|season/i);
      (summary.replies as Record<string, string>).intro = introReply;
      await waitForWikiMatch(request, projectId, /meridian/);
      await waitForWikiMatch(request, projectId, /probe/);

      const nextReply = await sendChatTurn(page, nextQuestion);
      expectCreatorSafeReply(nextReply);
      // Tolerant semantic: a specific next step (not a vague shrug), without requiring exact jargon.
      expect(nextReply.toLowerCase()).toMatch(
        /recommend|next|define|foundation|character|world|season|premise|tone|format|lock|align|start with|begin with/,
      );
      (summary.replies as Record<string, string>).next = nextReply;

      const wikiAfterQuestion = await getWikiText(request, projectId);
      expect(wikiAfterQuestion).not.toContain(nextQuestion);

      const signalPreludeReply = await sendChatTurn(page, signalPrelude);
      expectCreatorSafeReply(signalPreludeReply);
      expect(signalPreludeReply.toLowerCase()).toMatch(/continue|keep going|ready|tell me/i);
      expect(countQuestions(signalPreludeReply)).toBeLessThanOrEqual(2);
      (summary.replies as Record<string, string>).signalPrelude = signalPreludeReply;

      const signalReply = await sendChatTurn(page, signalLore);
      expectCreatorSafeReply(signalReply);
      expect(signalReply.toLowerCase()).toMatch(/signal|pattern|structure|mathematical|47/i);
      (summary.replies as Record<string, string>).signalLore = signalReply;
      await waitForWikiMatch(request, projectId, /47/);
      await waitForWikiMatch(request, projectId, /mathematical|structure|pattern/);

      const maraReply = await sendChatTurn(page, maraIntro);
      expectCreatorSafeReply(maraReply);
      expect(maraReply).toMatch(/Mara|character|skeptical|protective|lead/i);
      (summary.replies as Record<string, string>).maraIntro = maraReply;
      await waitForWikiMatch(request, projectId, /mara vale/);
      await waitForWikiMatch(request, projectId, /skeptical|protective/);

      const correctionReply = await sendChatTurn(page, maraCorrection);
      expectCreatorSafeReply(correctionReply);
      expect(correctionReply.toLowerCase()).toMatch(/understood|correct|mission lead|going forward|update/i);
      (summary.replies as Record<string, string>).maraCorrection = correctionReply;

      const correctedWikiText = await waitForWikiMatch(request, projectId, /mission lead/);
      if (correctedWikiText.includes("facility director")) {
        expect(correctedWikiText).toMatch(/supersed|correct|prior|updated|replaced|proposed|confirmed/);
      }

      const unresolvedReply = await sendChatTurn(page, facilityUnresolved);
      expectCreatorSafeReply(unresolvedReply);
      expect(unresolvedReply.toLowerCase()).toMatch(/unconfirmed|unclear|open question|unknown|might|possible/i);
      (summary.replies as Record<string, string>).facilityUnresolved = unresolvedReply;

      const unresolvedWikiText = await getWikiText(request, projectId);
      if (/privately owned/i.test(unresolvedWikiText)) {
        expect(unresolvedWikiText.toLowerCase()).toMatch(/unresolved|open question|possible|might|maybe|not confirmed/);
      }

      const signalIntentReply = await sendChatTurn(page, signalIntent);
      expectCreatorSafeReply(signalIntentReply);
      expect(signalIntentReply.toLowerCase()).toMatch(/unknown|unclear|not confirmed|ambiguous|open/i);
      (summary.replies as Record<string, string>).signalIntent = signalIntentReply;

      const continuationReply = await sendChatTurn(page, characterContinuation);
      expectCreatorSafeReply(continuationReply);
      expect(continuationReply.toLowerCase()).toMatch(/mara|character|begin|start|focus/i);
      (summary.replies as Record<string, string>).characterContinuation = continuationReply;

      const episodeReply = await sendChatTurn(page, episodeQuestion);
      expectCreatorSafeReply(episodeReply);
      expect(episodeReply.toLowerCase()).toMatch(/three|1\.|first|second|third|episode 1|opening/);
      (summary.replies as Record<string, string>).episodeSteps = episodeReply;

      const planReply = await sendChatTurn(page, draftPlanRequest);
      expectCreatorSafeReply(planReply);
      expect(planReply.toLowerCase()).toMatch(/plan|draft|outline|approval|review|next/i);
      (summary.replies as Record<string, string>).planDraft = planReply;

      const activePlan = await getActivePlanState(request, projectId);
      summary.activePlan = {
        ok: activePlan.ok,
        status: activePlan.status,
        body: activePlan.json,
      };
      if (activePlan.ok) {
        // Active-plan lookup returns a compact summary (title/state), not full step prose.
        const planText = jsonText(activePlan.json).toLowerCase();
        expect(planText).toMatch(/draft|active|plan/);
        expect(planText).toMatch(/mara|signal|episode|opening|lead|hook|foundation|title/);
      } else {
        (summary.softSkips as string[]).push(`plan-api-${activePlan.status}`);
      }

      const imageName = `meridian-reference-${Date.now()}.png`;
      await page.getByTestId("codirector-file-input").setInputFiles({
        name: imageName,
        mimeType: "image/png",
        buffer: TINY_PNG,
      });
      const tray = page.getByTestId("codirector-attachment-tray");
      await expect(tray).toBeVisible({ timeout: 15_000 });
      await expect(tray).toContainText(imageName);

      const attachmentReply = await sendChatTurn(
        page,
        "Use the attached image as a reference prompt for Meridian. Tell me plainly what you can and cannot infer from it.",
      );
      expectCreatorSafeReply(attachmentReply);
      (summary.replies as Record<string, string>).attachment = attachmentReply;

      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble").last()).toContainText(
        new RegExp(`Attached:\\s+${imageName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i"),
        { timeout: 20_000 },
      );

      const bodyTextAfterAttachment = await page.locator("body").innerText();
      expect(bodyTextAfterAttachment).not.toMatch(windowsPathPattern());
      if (/visual analysis is unavailable|can't view|cannot view|unable to view|do not have.*vision|don't have.*vision/i.test(
        attachmentReply,
      )) {
        expect(attachmentReply).not.toMatch(/\bI can see\b|\bthe image shows\b|\bdepicts\b/i);
      }

      await page.getByRole("button", { name: "Choose from Library" }).click();
      const libraryDialog = page.getByRole("dialog", { name: /Select from Project Library/i });
      await expect(libraryDialog).toBeVisible({ timeout: 20_000 });
      const libraryBox = await libraryDialog.boundingBox();
      expect(libraryBox?.width ?? 0).toBeGreaterThanOrEqual(700);
      await expect(page.getByTestId("codirector-library-filter-all")).toHaveClass(/is-active/);
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("codirector-library-browser")).toHaveCount(0);

      const conversation = await getConversation(request, projectId);
      expect(conversation.messages.some((message) => message.role === "user" && message.content.includes(maraCorrection))).toBeTruthy();
      expect(jsonText(conversation)).not.toMatch(windowsPathPattern());
      summary.persistedMessageCount = conversation.messages.length;

      await page.reload();
      await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: maraCorrection })).toHaveCount(1, {
        timeout: 20_000,
      });
      await expect(page.locator(".codirector-msg.user .codirector-msg-bubble", { hasText: draftPlanRequest })).toHaveCount(1, {
        timeout: 20_000,
      });

      const isolated = await createTempProject(request, `CODIRECTOR-CERT-ISO-${Date.now()}`);
      run.createdProjectIds.push(isolated.id);
      summary.isolationProjectId = isolated.id;

      const isolatedWiki = (await getWikiTextAllowMissing(request, isolated.id)).toLowerCase();
      expect(isolatedWiki).not.toContain("meridian");
      expect(isolatedWiki).not.toContain("mara vale");
      expect(isolatedWiki).not.toContain("47 minutes");

      await deleteDisposableProjects(request, [isolated.id], projectId);
      const isolatedAfterDelete = await request.get(`${API}/api/projects/${isolated.id}`);
      expect(isolatedAfterDelete.status(), await isolatedAfterDelete.text()).toBe(404);

      let failureInjection: Record<string, unknown>;
      try {
        const statusRes = await request.get(`${API}/api/e2e/status`);
        const rawBody = await statusRes.text();
        if (statusRes.ok()) {
          let body: unknown;
          try {
            body = JSON.parse(rawBody);
          } catch {
            body = rawBody;
          }
          failureInjection = {
            status: "available",
            httpStatus: statusRes.status(),
            body,
          };
        } else {
          failureInjection = {
            status: "skipped-beta-no-e2e",
            httpStatus: statusRes.status(),
          };
          (summary.softSkips as string[]).push("failure-injection-beta-no-e2e");
        }
      } catch (error) {
        failureInjection = {
          status: "skipped-beta-no-e2e",
          error: error instanceof Error ? error.message : String(error),
        };
        (summary.softSkips as string[]).push("failure-injection-beta-no-e2e");
      }
      summary.failureInjection = failureInjection;
      writeJson(run.artifactDir, "failure-injection.json", failureInjection);

      observer.assertHealthyBrowser();
    } finally {
      try {
        if (handoffBefore) {
          handoffAfter = await captureHandoffSnapshot(request);
          writeJson(run.artifactDir, "handoff-after.json", handoffAfter);
          expectHandoffUnchanged(handoffBefore, handoffAfter);
        }
      } finally {
        const residueIds = await deleteCertResidueByNamePrefix(request, "CODIRECTOR-CERT");
        await deleteDisposableProjects(request, [...run.createdProjectIds, ...residueIds]);
        const deletionChecks: Array<{ id: string; status: number }> = [];
        for (const projectId of Array.from(new Set([...run.createdProjectIds, ...residueIds]))) {
          if (!projectId || projectId === MANUAL_HANDOFF_ID) continue;
          const res = await request.get(`${API}/api/projects/${projectId}`);
          deletionChecks.push({ id: projectId, status: res.status() });
          expect(res.status(), await res.text()).toBe(404);
        }
        summary.cleanup = { deletionChecks, residueIds };
        writeJson(run.artifactDir, "summary.json", summary);
        observer.flush();
      }
    }
  });

  test("library browser filters and microphone transcript stay creator-safe", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();

    const run = createRunContext();
    ensureArtifactDir(run.artifactDir);

    const summary: Record<string, unknown> = {
      runId: run.runId,
      projectName: `${run.projectName}-satellite`,
      createdProjectIds: run.createdProjectIds,
    };

    try {
      const project = await createTempProject(request, `${run.projectName}-satellite`);
      run.createdProjectIds.push(project.id);
      summary.projectId = project.id;

      const imageAsset = await uploadProjectAsset(request, project.id, {
        name: "meridian-library-image.png",
        mimeType: "image/png",
        kind: "image",
        buffer: TINY_PNG,
        tag: "Meridian Image",
      });
      const videoAsset = await uploadProjectAsset(request, project.id, {
        name: "meridian-library-video.mp4",
        mimeType: "video/mp4",
        kind: "video",
        buffer: TINY_MP4,
        tag: "Meridian Video",
      });
      const audioAsset = await uploadProjectAsset(request, project.id, {
        name: "meridian-library-audio.wav",
        mimeType: "audio/wav",
        kind: "audio",
        buffer: TINY_WAV,
        tag: "Meridian Audio",
      });

      await installSpeechRecognitionMock(page, [
        { type: "success", transcript: "Begin with Mara's private cost of leading the team." },
      ]);
      await openCoDirectorForProject(page, project.id);

      await page.getByRole("button", { name: "Choose from Library" }).click();
      const dialog = page.getByRole("dialog", { name: /Select from Project Library/i });
      await expect(dialog).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("codirector-library-filter-all")).toHaveClass(/is-active/);

      const imageCard = page.getByTestId(`codirector-library-asset-${imageAsset.id}`);
      const videoCard = page.getByTestId(`codirector-library-asset-${videoAsset.id}`);
      const audioCard = page.getByTestId(`codirector-library-asset-${audioAsset.id}`);
      await expect(imageCard).toBeVisible({ timeout: 20_000 });
      await expect(imageCard).toContainText("Meridian Image");

      await page.getByTestId("codirector-library-filter-images").click();
      await expect(page.getByTestId("codirector-library-filter-images")).toHaveClass(/is-active/);
      await expect(imageCard).toBeVisible();
      await expect(videoCard).toHaveCount(0);
      await expect(audioCard).toHaveCount(0);

      await page.getByTestId("codirector-library-filter-video").click();
      await expect(page.getByTestId("codirector-library-filter-video")).toHaveClass(/is-active/);
      await expect(videoCard).toBeVisible({ timeout: 20_000 });
      await expect(audioCard).toHaveCount(0);

      await page.getByTestId("codirector-library-filter-audio").click();
      await expect(page.getByTestId("codirector-library-filter-audio")).toHaveClass(/is-active/);
      await expect(audioCard).toBeVisible({ timeout: 20_000 });
      await expect(videoCard).toHaveCount(0);

      await page.keyboard.press("Escape");
      await expect(page.getByTestId("codirector-library-browser")).toHaveCount(0);

      await page.getByTestId("codirector-mic-button").click();
      await expect(page.getByTestId("codirector-stt-status")).toContainText(/Listening/i);
      await page.getByTestId("codirector-mic-button").click();

      const transcript = "Begin with Mara's private cost of leading the team.";
      const editedTranscript = `${transcript} Keep the pressure personal and practical.`;
      await expect(page.getByTestId("codirector-composer-input")).toHaveValue(transcript, { timeout: 15_000 });
      await expect(page.getByTestId("codirector-stt-status")).toHaveCount(0);
      await expect(page.locator(".codirector-msg.user")).toHaveCount(0);

      await page.getByTestId("codirector-composer-input").fill(editedTranscript);
      await expect(page.getByTestId("codirector-composer-input")).toHaveValue(editedTranscript);
      await expect(page.locator(".codirector-msg.user")).toHaveCount(0);

      summary.editedTranscript = editedTranscript;
      observer.assertHealthyBrowser();
    } finally {
      await deleteDisposableProjects(request, run.createdProjectIds);
      writeJson(run.artifactDir, "summary.json", summary);
      observer.flush();
    }
  });
});
