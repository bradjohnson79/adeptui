import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { ensureKorriCharacter, openVoiceStudio } from "../m42/helpers/korriVoice";

type RuntimeStatus = {
  ok?: boolean;
  providerId?: string;
  providerVersion?: string;
  installed?: boolean;
  ready?: boolean;
  availableOnDisk?: boolean;
  modelRevision?: string | null;
  runtimeRoot?: string;
  manifestPath?: string;
  message?: string;
  mock?: boolean;
  language?: Record<string, unknown>;
  capabilityMetadata?: { language?: Record<string, unknown> };
};

type Capabilities = {
  ok?: boolean;
  providerId?: string;
  providerVersion?: string;
  status?: string;
  installed?: boolean;
  ready?: boolean;
  supportsLiveGeneration?: boolean;
  supportsEmotionVectors?: boolean;
  supportedEmotionVectors?: string[];
  directionModes?: string[];
  presetsAvailable?: number;
  message?: string;
  mock?: boolean;
  language?: Record<string, unknown>;
  capabilityMetadata?: { language?: Record<string, unknown> };
};

type VoiceWorkspaceRecord = {
  activeVoiceProfileId?: string | null;
  activeVoice?: {
    id?: string;
    name?: string;
    version?: string | number | null;
    version_number?: string | number | null;
    approval_status?: string | null;
    status?: string | null;
  } | null;
  voices?: Array<{
    id?: string;
    name?: string;
    version?: string | number | null;
    version_number?: string | number | null;
    approval_status?: string | null;
    status?: string | null;
  }>;
};

type ApprovedVoiceIdentity = {
  id: string;
  name: string;
  version?: string | number | null;
};

type VoicePerformanceRecord = {
  id: string;
  projectId: string;
  characterId: string;
  voiceIdentityId: string;
  dialogueText: string;
  approvedTakeId?: string | null;
  timelineLinkage?: Record<string, unknown>;
  lipsyncLinkage?: Record<string, unknown>;
  takes?: Array<{
    id: string;
    label?: string;
    status: string;
    audioAssetId?: string | null;
  }>;
};

type VoicePerformanceTakeList = {
  recordId: string;
  approvedTakeId?: string | null;
  takes: Array<{
    id: string;
    label?: string;
    status: string;
    audioAssetId?: string | null;
    errorMessage?: string | null;
  }>;
  mock?: boolean;
};

function extractLanguageMetadata(...sources: unknown[]): Record<string, unknown> | null {
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    const record = source as {
      language?: Record<string, unknown>;
      capabilityMetadata?: { language?: Record<string, unknown> };
      metadata?: { language?: Record<string, unknown> };
    };
    if (record.language && typeof record.language === "object") return record.language;
    if (record.capabilityMetadata?.language && typeof record.capabilityMetadata.language === "object") {
      return record.capabilityMetadata.language;
    }
    if (record.metadata?.language && typeof record.metadata.language === "object") {
      return record.metadata.language;
    }
  }
  return null;
}

function assertM410RuntimeAndCapabilities(runtime: RuntimeStatus, capabilities: Capabilities): void {
  expect(runtime.ok, "runtime status should be reachable").toBeTruthy();
  expect(capabilities.ok, "capabilities should be reachable").toBeTruthy();
  expect(runtime.mock, "runtime status must not be mock").not.toBe(true);
  expect(capabilities.mock, "capabilities must not be mock").not.toBe(true);
  expect(runtime.providerId).toBe("index-tts2-local");
  expect(capabilities.providerId).toBe("index-tts2-local");
  expect(capabilities.directionModes || []).toEqual(expect.arrayContaining(["codirector", "manual"]));
  expect(capabilities.supportedEmotionVectors || []).toEqual(
    expect.arrayContaining(["joy", "sadness", "anger", "fear", "surprise", "disgust", "contempt"]),
  );

  const language = extractLanguageMetadata(capabilities, runtime);
  expect(language, "M4.10 capability metadata must expose language honesty").toBeTruthy();
  expect(language?.accent).toBe("experimental");
  expect(language?.mixed_language ?? language?.mixedLanguage).toBe("not_recommended");
}

async function getJson<T>(request: APIRequestContext, url: string): Promise<T> {
  const response = await request.get(url);
  expect(response.ok(), `GET ${url} failed: ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

async function postJson<T>(
  request: APIRequestContext,
  url: string,
  data?: Record<string, unknown>,
): Promise<{ response: Awaited<ReturnType<APIRequestContext["post"]>>; body: T }> {
  const response = await request.post(url, { data: data || {} });
  expect(response.ok(), `POST ${url} failed: ${response.status()} ${await response.text()}`).toBeTruthy();
  return { response, body: (await response.json()) as T };
}

function resolveApprovedVoice(body: VoiceWorkspaceRecord): ApprovedVoiceIdentity | null {
  const fromActive = body.activeVoice;
  if (fromActive?.id && String(fromActive.approval_status || fromActive.status || "").toLowerCase() === "approved") {
    return {
      id: String(fromActive.id),
      name: String(fromActive.name || "Approved Voice"),
      version: fromActive.version ?? fromActive.version_number ?? null,
    };
  }

  for (const voice of body.voices || []) {
    if (voice?.id && String(voice.approval_status || voice.status || "").toLowerCase() === "approved") {
      return {
        id: String(voice.id),
        name: String(voice.name || "Approved Voice"),
        version: voice.version ?? voice.version_number ?? null,
      };
    }
  }
  return null;
}

async function ensureSceneId(request: APIRequestContext, projectId: string): Promise<string> {
  const scenesResponse = await request.get(`/api/projects/${projectId}/scenes`);
  expect(scenesResponse.ok(), `GET /api/projects/${projectId}/scenes failed`).toBeTruthy();
  const scenes = (await scenesResponse.json()) as Array<{ id?: string }>;
  const existing = scenes.find((scene) => scene?.id);
  if (existing?.id) return String(existing.id);

  const created = await request.post(`/api/projects/${projectId}/scenes`, {
    data: { name: `M410 Voice Performance Scene ${Date.now()}` },
  });
  expect(created.ok(), `POST /api/projects/${projectId}/scenes failed: ${created.status()} ${await created.text()}`).toBeTruthy();
  const body = (await created.json()) as { id?: string };
  expect(body.id).toBeTruthy();
  return String(body.id);
}

async function expectVisible(locator: Locator): Promise<boolean> {
  if ((await locator.count()) === 0) return false;
  try {
    return await locator.first().isVisible();
  } catch {
    return false;
  }
}

async function expectStudioIaVisible(page: Page): Promise<void> {
  await expect(page.getByTestId("voice-studio-ia")).toBeVisible();
  await expect(page.getByTestId("voice-identity-tab")).toBeVisible();
  await expect(page.getByTestId("voice-performance-tab")).toBeVisible();
  await expect(page.getByTestId("voice-scene-dialogue-tab")).toBeVisible();
  await expect(page.getByTestId("voice-takes-tab")).toBeVisible();
}

async function openVoicePerformanceStudio(page: Page): Promise<void> {
  await page.getByTestId("voice-performance-tab").click();
  await expect(page.getByTestId("voice-performance-studio")).toBeVisible({ timeout: 30_000 });
}

async function waitForStableTakeList(
  request: APIRequestContext,
  recordId: string,
  minimumTakes: number,
  timeoutMs = 300_000,
): Promise<VoicePerformanceTakeList> {
  const deadline = Date.now() + timeoutMs;
  let last: VoicePerformanceTakeList | null = null;

  while (Date.now() < deadline) {
    const body = await getJson<VoicePerformanceTakeList>(request, `/api/voice-performance/m410/records/${recordId}/takes`);
    last = body;
    const takes = body.takes || [];
    const completeEnough =
      takes.length >= minimumTakes
      && takes.every((take) => ["completed", "approved", "failed", "cancelled"].includes(String(take.status || "")));
    if (completeEnough) {
      return body;
    }
    await pageWait(4_000);
  }

  throw new Error(
    `Timed out waiting for M4.10 takes for record ${recordId}. Last statuses: ${JSON.stringify(
      last?.takes?.map((take) => ({ id: take.id, status: take.status, errorMessage: take.errorMessage })),
    )}`,
  );
}

async function postTimelineWithConfirm(
  request: APIRequestContext,
  recordId: string,
): Promise<Record<string, unknown>> {
  const first = await request.post(`/api/voice-performance/m410/records/${recordId}/timeline`, {
    data: { trackId: "dialogue-main", startMs: 0, confirmReplace: false },
  });
  if (first.ok()) return (await first.json()) as Record<string, unknown>;

  const detail = await first.json().catch(async () => ({ message: await first.text() }));
  const code = String((detail as any)?.detail?.code || (detail as any)?.code || "");
  if (code.toLowerCase().includes("confirm")) {
    const confirmed = await request.post(`/api/voice-performance/m410/records/${recordId}/timeline`, {
      data: { trackId: "dialogue-main", startMs: 0, confirmReplace: true },
    });
    expect(confirmed.ok(), `confirmed timeline placement failed: ${confirmed.status()} ${await confirmed.text()}`).toBeTruthy();
    return (await confirmed.json()) as Record<string, unknown>;
  }

  throw new Error(`timeline placement failed: ${JSON.stringify(detail)}`);
}

async function postLipsyncWithConfirm(
  request: APIRequestContext,
  recordId: string,
): Promise<Record<string, unknown>> {
  const first = await request.post(`/api/voice-performance/m410/records/${recordId}/lipsync`, {
    data: { confirm: false, setSceneAudioAsset: true },
  });
  if (first.ok()) return (await first.json()) as Record<string, unknown>;

  const detail = await first.json().catch(async () => ({ message: await first.text() }));
  const code = String((detail as any)?.detail?.code || (detail as any)?.code || "");
  if (code.toLowerCase().includes("confirm")) {
    const confirmed = await request.post(`/api/voice-performance/m410/records/${recordId}/lipsync`, {
      data: { confirm: true, setSceneAudioAsset: true },
    });
    expect(confirmed.ok(), `confirmed lipsync prepare failed: ${confirmed.status()} ${await confirmed.text()}`).toBeTruthy();
    return (await confirmed.json()) as Record<string, unknown>;
  }

  throw new Error(`lipsync prepare failed: ${JSON.stringify(detail)}`);
}

async function pageWait(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

test.describe.configure({ mode: "serial", timeout: 600_000 });

test.describe("M4.10 Voice Performance Studio", () => {
  test("Voice Studio IA, identity gate, approved workspace, and viewports stay visible", async ({
    page,
    request,
  }) => {
    const { projectId, characterId } = await ensureKorriCharacter(request);
    const [runtime, capabilities, workspace] = await Promise.all([
      getJson<RuntimeStatus>(request, "/api/voice-performance/m410/runtime/status"),
      getJson<Capabilities>(request, "/api/voice-performance/m410/capabilities"),
      getJson<VoiceWorkspaceRecord>(request, `/api/projects/${projectId}/characters/${characterId}/voice`),
    ]);

    assertM410RuntimeAndCapabilities(runtime, capabilities);

    await page.setViewportSize({ width: 1366, height: 768 });
    await openVoiceStudio(page, projectId);
    await expectStudioIaVisible(page);

    await openVoicePerformanceStudio(page);
    const gateVisible = await expectVisible(page.getByTestId("vp-voice-identity-required"));

    if (gateVisible) {
      await expect(page.getByTestId("vp-open-voice-identity")).toBeVisible();
    } else {
      await expect(page.getByTestId("vp-direction-codirector")).toBeVisible();
      await expect(page.getByTestId("vp-direction-manual")).toBeVisible();
      await expect(page.getByTestId("vp-dialogue")).toBeVisible();
      await expect(page.getByTestId("vp-performance-plan")).toBeVisible();
      await expect(page.getByTestId("vp-emotion")).toBeVisible();
      await expect(page.getByTestId("vp-intensity")).toBeVisible();
      await expect(page.getByTestId("vp-delivery")).toBeVisible();
      await expect(page.getByTestId("vp-pacing")).toBeVisible();
      await expect(page.getByTestId("vp-breath")).toBeVisible();
      await expect(page.getByTestId("vp-emphasis")).toBeVisible();
      await expect(page.getByTestId("vp-subtext")).toBeVisible();
      await expect(page.getByTestId("vp-advanced-toggle")).toBeVisible();

      const advancedDetails = page.locator("details").filter({ has: page.getByTestId("vp-advanced-toggle") });
      await expect.poll(async () => advancedDetails.first().evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
    }

    const approvedVoice = resolveApprovedVoice(workspace);
    if (!gateVisible && approvedVoice) {
      expect(approvedVoice.id).toBeTruthy();
    }

    await page.setViewportSize({ width: 1920, height: 1080 });
    await expectStudioIaVisible(page);
    await expect(page.getByTestId("voice-performance-tab")).toBeVisible();
  });

  test("Live API-backed M4.10 flow generates, approves, persists, and survives reload when ready", async ({
    page,
    request,
  }) => {
    const { projectId, characterId } = await ensureKorriCharacter(request);
    const [runtime, capabilities, workspace] = await Promise.all([
      getJson<RuntimeStatus>(request, "/api/voice-performance/m410/runtime/status"),
      getJson<Capabilities>(request, "/api/voice-performance/m410/capabilities"),
      getJson<VoiceWorkspaceRecord>(request, `/api/projects/${projectId}/characters/${characterId}/voice`),
    ]);

    assertM410RuntimeAndCapabilities(runtime, capabilities);

    const approvedVoice = resolveApprovedVoice(workspace);
    test.skip(!approvedVoice, "No approved voice identity is available for the live M4.10 flow.");
    test.skip(
      !(runtime.ready || capabilities.ready || capabilities.supportsLiveGeneration),
      `IndexTTS2 runtime is not ready for live M4.10 generation: ${capabilities.message || runtime.message || "not ready"}`,
    );

    const sceneId = await ensureSceneId(request, projectId);
    const dialogueText = `M410 certification line ${Date.now()}: Korri keeps the sarcasm light, then lands the last phrase with protective resolve.`;
    const baseCreate = await postJson<VoicePerformanceRecord>(request, "/api/voice-performance/m410/records", {
      projectId,
      sceneId,
      characterId,
      voiceIdentityId: approvedVoice!.id,
      voiceIdentityVersion: approvedVoice!.version == null ? undefined : String(approvedVoice!.version),
      dialogueText,
      directionMode: "codirector",
      emotionSource: "codirector",
      emotionVector: { sadness: 0.35, contempt: 0.65 },
      performancePlan: {
        source: "codirector",
        emotionLabel: "Protective sarcasm",
        intensity: "medium",
        delivery: "dry, then gently protective",
        pacing: "measured with a soft landing",
        breath: "tight on the first half, open on the second",
        emphasis: "land 'protective resolve'",
        subtext: "She is teasing, but her guard drops by the end.",
        notes: "Let the teasing lead into warmth.",
        editable: true,
      },
      manualPlan: {
        source: "manual",
        intensity: "medium",
        editable: true,
      },
      codirectorPlan: {
        source: "codirector",
        emotionLabel: "Protective sarcasm",
        intensity: "medium",
        editable: true,
      },
      consentAck: {
        source: "playwright-m410-certification",
        acknowledgedAt: new Date().toISOString(),
      },
    });

    const created = baseCreate.body;
    expect(created.id).toBeTruthy();
    expect(created.voiceIdentityId).toBe(approvedVoice!.id);

    const refreshedPlan = await postJson<VoicePerformanceRecord>(
      request,
      `/api/voice-performance/m410/records/${created.id}/performance-plan`,
      {
        context: {
          parenthetical: "Light sarcasm, then sincere concern.",
          sceneProgression: "The back half should soften and feel protectively intimate.",
        },
      },
    );
    expect(refreshedPlan.body.id).toBe(created.id);

    const generated = await postJson<{ ok?: boolean; takes?: Array<{ id: string }>; mock?: boolean }>(
      request,
      `/api/voice-performance/m410/records/${created.id}/generate-takes`,
      {
        count: 1,
        labels: ["M410 Certification Take 1"],
      },
    );
    expect(generated.body.ok).toBeTruthy();
    expect(generated.body.mock, "live take generation must not be mock").not.toBe(true);

    const takeList = await waitForStableTakeList(request, created.id, 1);
    expect(takeList.mock).not.toBe(true);
    const completedTake =
      takeList.takes.find((take) => take.status === "completed" || take.status === "approved") || null;
    expect(
      completedTake,
      `expected at least one completed take, got ${JSON.stringify(
        takeList.takes.map((take) => ({ id: take.id, status: take.status, errorMessage: take.errorMessage })),
      )}`,
    ).toBeTruthy();
    expect(completedTake?.audioAssetId, "completed take should have audioAssetId").toBeTruthy();

    const approved = await postJson<{
      ok?: boolean;
      approvedTakeId?: string;
      takes?: Array<{ id: string; status: string }>;
      mock?: boolean;
    }>(
      request,
      `/api/voice-performance/m410/records/${created.id}/takes/${completedTake!.id}/approve`,
      { approvedBy: "playwright" },
    );
    expect(approved.body.ok).toBeTruthy();
    expect(approved.body.mock).not.toBe(true);
    expect(approved.body.approvedTakeId).toBe(completedTake!.id);

    const timeline = await postTimelineWithConfirm(request, created.id);
    expect(timeline.ok).toBe(true);
    expect(timeline.recordId).toBe(created.id);

    const lipsync = await postLipsyncWithConfirm(request, created.id);
    expect(lipsync.ok).toBe(true);
    expect(lipsync.recordId).toBe(created.id);

    const persisted = await getJson<VoicePerformanceRecord>(request, `/api/voice-performance/m410/records/${created.id}`);
    expect(persisted.approvedTakeId).toBe(completedTake!.id);
    expect(String(persisted.timelineLinkage?.approvedTakeId || "")).toBe(completedTake!.id);
    expect(String(persisted.lipsyncLinkage?.takeId || "")).toBe(completedTake!.id);

    await openVoiceStudio(page, projectId);
    await expectStudioIaVisible(page);
    await openVoicePerformanceStudio(page);
    await expect(page.getByTestId("vp-dialogue")).toBeVisible();
    await expect(page.getByTestId("vp-send-timeline")).toBeEnabled();
    await expect(page.getByTestId("vp-prepare-lipsync")).toBeEnabled();
    await expect(page.getByTestId("vp-take-card").first()).toBeVisible({ timeout: 30_000 });

    await page.reload();
    await openVoiceStudio(page, projectId);
    await expectStudioIaVisible(page);
    await openVoicePerformanceStudio(page);
    await expect(page.getByTestId("vp-dialogue")).toBeVisible();
    await expect(page.getByTestId("vp-send-timeline")).toBeEnabled();
    await expect(page.getByTestId("vp-prepare-lipsync")).toBeEnabled();
    await expect(page.getByTestId("vp-take-card").first()).toBeVisible({ timeout: 30_000 });
  });
});
