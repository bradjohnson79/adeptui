import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

/**
 * Use Existing Voice → Project Library audio → character assignment (live smoke).
 *
 * Disposable project + character + uploaded WAV. Drives the real creator path:
 * Voice Creator (Standard voice-identity tab AND Express Co-Director panel) →
 * Use Existing Voice → Select from Library → audio-only modal → preview →
 * Use this Voice → assigned card with player → reload persistence →
 * Co-Director inspect_character_voice → authority packet consumed by Timeline.
 *
 * Requires live Vite (:5173) + Studio API (:8758): ADEPT_BETA_TARGET=1.
 */

const CHARACTER_NAME = "SmokeVox";
const AUDIO_TAG = "SmokeVox Voice Sample";
const IMAGE_TAG = "SmokeVox Reference Image";

// Renkoka is the Owner-pinned Global Character carrying both an ElevenLabs
// provider binding and an approved Library voice-reference asset. Read-only
// checks only — never mutated here.
const RENKOKA_PROJECT_ID = "bd6a5e6a-33c2-44a8-a115-8d37301d9d56";
const RENKOKA_CHARACTER_ID = "5d5b99cf-9a85-4d34-877d-d90d0ec2af22";
const RENKOKA_REFERENCE_ASSET_ID = "f16135fc-cbdd-417a-ac2e-f03466125827";

function makeWavBuffer(seconds = 1.5, freq = 440, sampleRate = 16000): Buffer {
  const frames = Math.floor(seconds * sampleRate);
  const dataSize = frames * 2;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write("WAVE", 8);
  buf.write("fmt ", 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20); // PCM
  buf.writeUInt16LE(1, 22); // mono
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 2, 28);
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(dataSize, 40);
  for (let i = 0; i < frames; i++) {
    const t = i / sampleRate;
    const sample = Math.round(Math.sin(2 * Math.PI * freq * t) * 12000);
    buf.writeInt16LE(sample, 44 + i * 2);
  }
  return buf;
}

// 1x1 transparent PNG.
const PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

async function uploadAsset(
  request: APIRequestContext,
  projectId: string,
  file: { name: string; mimeType: string; buffer: Buffer },
  tag: string,
  kind: string,
): Promise<string> {
  const res = await request.post(`/api/projects/${projectId}/assets`, {
    multipart: {
      file,
      tag,
      kind,
    },
  });
  expect(res.ok(), `upload ${kind} asset failed: ${res.status()}`).toBeTruthy();
  const body = await res.json();
  const id = String(body.id || "");
  expect(id).toBeTruthy();
  return id;
}

async function selectCharacterInVoiceStudio(page: Page, projectId: string, name: string): Promise<void> {
  await page.goto(`/project/${projectId}?workspace=voicestudio`);
  await expect(page.getByTestId("voice-studio-shell")).toBeVisible({ timeout: 45_000 });

  const activeName = page.getByTestId("voice-studio-active-name");
  const workspace = page.getByTestId("voice-creator-workspace");
  const card = page.locator(`[data-testid="voice-studio-open-character"][data-character-name="${name}"]`);

  // The shell settles into either a restored workspace or the chooser grid.
  await expect(workspace.or(card.first())).toBeVisible({ timeout: 60_000 });
  const currentName = ((await activeName.textContent().catch(() => "")) || "").trim();
  if (currentName !== name) {
    if (await workspace.isVisible().catch(() => false)) {
      await page.getByTestId("voice-studio-choose-another").click();
    }
    await expect(card).toBeVisible({ timeout: 45_000 });
    await card.click();
  }
  await expect(workspace).toBeVisible({ timeout: 30_000 });
  await expect(activeName).toHaveText(name, { timeout: 30_000 });
}

test.describe("Use Existing Voice → Project Library audio", () => {
  test.describe.configure({ mode: "serial" });

  let projectId = "";
  let characterId = "";
  let audioAssetId = "";
  let imageAssetId = "";

  test.beforeAll(async ({ request }) => {
    const created = await request.post("/api/projects", {
      data: { name: `Voice Library Smoke ${Date.now()}` },
    });
    expect(created.ok(), `create project failed: ${created.status()}`).toBeTruthy();
    projectId = String((await created.json()).id || "");
    expect(projectId).toBeTruthy();

    const character = await request.post(`/api/projects/${projectId}/characters`, {
      data: { name: CHARACTER_NAME },
    });
    expect(character.ok(), `create character failed: ${character.status()}`).toBeTruthy();
    characterId = String((await character.json()).id || "");
    expect(characterId).toBeTruthy();

    audioAssetId = await uploadAsset(
      request,
      projectId,
      { name: "smokevox-voice-sample.wav", mimeType: "audio/wav", buffer: makeWavBuffer() },
      AUDIO_TAG,
      "audio",
    );
    imageAssetId = await uploadAsset(
      request,
      projectId,
      { name: "smokevox-reference.png", mimeType: "image/png", buffer: Buffer.from(PNG_BASE64, "base64") },
      IMAGE_TAG,
      "image",
    );
  });

  test("Standard: Library picker is audio-only, previews, assigns, and persists across reload", async ({
    page,
  }) => {
    await selectCharacterInVoiceStudio(page, projectId, CHARACTER_NAME);

    // Voice Identity tab is the default stage; make it explicit.
    const identityTab = page.getByTestId("voice-identity-tab");
    if (await identityTab.count()) await identityTab.click();

    // §1/§8 — Use Existing Voice shows the creator-facing Library action.
    await page.getByTestId("vs-method-existing").click();
    await expect(page.getByTestId("vip-existing-section")).toBeVisible();
    await page.getByTestId("vs-existing-library").click();

    // §2 — the same Project Library modal opens locked to audio.
    const modal = page.getByTestId("timeline-add-from-project-library");
    await expect(modal).toBeVisible({ timeout: 30_000 });
    await expect(modal).toHaveAttribute("data-media-kind", "audio");
    await expect(modal.getByTestId(`library-card-${audioAssetId}`)).toBeVisible({ timeout: 30_000 });
    await expect(modal.getByTestId(`library-card-${imageAssetId}`)).toHaveCount(0);
    // No kind-filter buttons leak in audio mode (all/image/video hidden).
    await expect(modal.getByRole("button", { name: "image", exact: true })).toHaveCount(0);
    await expect(modal.getByRole("button", { name: "video", exact: true })).toHaveCount(0);
    await expect(modal.getByRole("button", { name: "all", exact: true })).toHaveCount(0);

    // §3 — in-modal audio preview: player present and loads real metadata.
    const player = modal.getByTestId(`library-card-audio-${audioAssetId}`);
    await expect(player).toBeVisible();
    const duration = await player.evaluate(
      (el: HTMLAudioElement) =>
        new Promise<number>((resolve) => {
          if (el.readyState >= 1 && Number.isFinite(el.duration)) return resolve(el.duration);
          el.addEventListener("loadedmetadata", () => resolve(el.duration), { once: true });
          el.addEventListener("error", () => resolve(Number.NaN), { once: true });
          el.load();
        }),
    );
    expect(duration, "audio preview must load metadata (duration)").toBeGreaterThan(0);

    // §4 — select the asset and confirm with the creator-facing label.
    // Click the card's name row: the inline <audio> player intentionally
    // swallows clicks so playback never toggles selection.
    await modal.getByTestId(`library-card-${audioAssetId}`).locator("span").first().click();
    const confirm = modal.getByTestId("timeline-add-from-project-library-add");
    await expect(confirm).toBeEnabled();
    await expect(confirm).toHaveText("Use this Voice");
    await confirm.click();
    await expect(modal).toHaveCount(0);

    // §10 — assigned card: name, Assigned state, playable audio.
    const assigned = page.getByTestId("vs-existing-assigned");
    await expect(assigned).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("vs-existing-assigned-state")).toHaveText("Assigned");
    await expect(page.getByTestId("vs-existing-assigned-name")).toContainText(AUDIO_TAG);
    const assignedPlayer = page.getByTestId("vs-existing-assigned-player");
    await expect(assignedPlayer).toBeVisible();
    await expect(assignedPlayer).toHaveAttribute("src", new RegExp(audioAssetId));

    // §11 — persistence: full reload, same character, same method.
    await page.reload();
    await selectCharacterInVoiceStudio(page, projectId, CHARACTER_NAME);
    await page.getByTestId("vs-method-existing").click();
    await expect(page.getByTestId("vs-existing-assigned")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("vs-existing-assigned-name")).toContainText(AUDIO_TAG);
  });

  test("Express + authority + Co-Director resolve the same assignment", async ({ page, request }) => {
    // §11 — Express (Co-Director Voice Creator) resolves the same reference.
    await openCoDirectorFullScreen(page, projectId);
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const region = page.locator('[aria-label="Working relationship"]').first();
      if (!(await region.isVisible().catch(() => false))) break;
      const skip = region.getByRole("button", { name: /Skip for now/i }).first();
      if (await skip.isVisible().catch(() => false)) {
        await skip.click({ force: true }).catch(() => undefined);
        await page.waitForTimeout(400);
      } else {
        break;
      }
    }
    const voiceCreatorTab = page.getByTestId("codirector-content-tab-voice_creator");
    await expect(voiceCreatorTab).toBeVisible({ timeout: 30_000 });
    await voiceCreatorTab.click({ force: true });
    await expect(page.getByTestId("voice-creator-express")).toBeVisible({ timeout: 45_000 });

    await page.getByTestId("vs-character-select").click();
    await page
      .getByTestId("vs-character-select-option")
      .filter({ hasText: CHARACTER_NAME })
      .first()
      .click();
    await page.getByTestId("vs-method-existing").click();
    await expect(page.getByTestId("vs-existing-assigned")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("vs-existing-assigned-name")).toContainText(AUDIO_TAG);
    await expect(page.getByTestId("vs-existing-assigned-player")).toHaveAttribute(
      "src",
      new RegExp(audioAssetId),
    );

    // §13 — the authority packet Timeline/H3 consumes exposes the reference.
    const authority = await request.get(
      `/api/projects/${projectId}/characters/${characterId}/voice/authority`,
    );
    expect(authority.ok(), `authority read failed: ${authority.status()}`).toBeTruthy();
    const authBody = await authority.json();
    expect(authBody.approvedVoiceReferenceAssetId).toBe(audioAssetId);
    expect(String(authBody.approvedVoiceReferenceAssetName || "")).toContain(AUDIO_TAG);

    // Workspace read carries the same reference on the active voice.
    const workspace = await request.get(`/api/projects/${projectId}/characters/${characterId}/voice`);
    expect(workspace.ok(), `voice workspace read failed: ${workspace.status()}`).toBeTruthy();
    const wsBody = await workspace.json();
    expect(String(wsBody?.activeVoice?.approvedVoiceReferenceAssetId || "")).toBe(audioAssetId);
    expect(String(wsBody?.activeVoice?.approvedVoiceReferenceAssetName || "")).toContain(AUDIO_TAG);

    // §14 — Co-Director observes the same assignment through its read tool.
    const tool = await request.post(`/api/codirector/projects/${projectId}/tools/read`, {
      data: { toolId: "inspect_character_voice", arguments: { characterId } },
    });
    expect(tool.ok(), `inspect_character_voice failed: ${tool.status()}`).toBeTruthy();
    const toolBody = JSON.stringify(await tool.json());
    expect(toolBody).toContain(audioAssetId);
    expect(toolBody).toContain('"hasApprovedVoiceReference":true');
  });

  test("Global Character (Renkoka, read-only): ElevenLabs binding preserved alongside Library reference", async ({
    request,
  }) => {
    // §9/§12 — a Global Character keeps her provider voice identity AND the
    // approved Library voice-reference asset; the packet Timeline resolves
    // exposes both. Read-only: no mutation of the Owner-pinned character.
    const authority = await request.get(
      `/api/projects/${RENKOKA_PROJECT_ID}/characters/${RENKOKA_CHARACTER_ID}/voice/authority`,
    );
    expect(authority.ok(), `Renkoka authority read failed: ${authority.status()}`).toBeTruthy();
    const body = await authority.json();
    expect(body.approvedVoiceReferenceAssetId).toBe(RENKOKA_REFERENCE_ASSET_ID);
    expect(String(body.approvedVoiceReferenceAssetName || "")).not.toBe("");
    expect(body.provider).toBe("elevenlabs");
    expect(String(body.providerVoiceId || "")).not.toBe("");
    expect(body.approved).toBe(true);
  });
});
