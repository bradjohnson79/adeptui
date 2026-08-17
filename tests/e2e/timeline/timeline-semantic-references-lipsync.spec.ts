/**
 * Timeline semantic Prompt references + Lip Sync speakers + Hot Keys.
 * Schnick Coffee only. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

type BindingRow = {
  id: string;
  alias?: string;
  asset_id?: string;
  identity_id?: string;
  media_kind?: string;
  reference_type?: string;
  display_token?: string;
};

type CharacterRow = { id: string; name?: string; active_voice_profile_id?: string | null };

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function firstScene(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  const scene = Array.isArray(scenes) ? scenes[0] : null;
  expect(scene?.id).toBeTruthy();
  return scene as { id: string; name?: string };
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

async function listedBindings(request: APIRequestContext) {
  const listed = await request.get(
    `${API}/api/projects/${PROJECT_ID}/references?scope_type=project&scope_id=${PROJECT_ID}`,
  );
  expect(listed.ok()).toBeTruthy();
  return ((await listed.json()).items || []) as BindingRow[];
}

async function listedCharacters(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/characters`);
  if (!res.ok()) return [] as CharacterRow[];
  const body = await res.json();
  const items = body.items || body.characters || body || [];
  return (Array.isArray(items) ? items : []) as CharacterRow[];
}

test.describe("Timeline semantic references, lip sync, hot keys", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("lanes retired, Prompt tokens persist by id, Inspector/Co-Director remain", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id);

    await expect(page.getByTestId("timeline-image-reference-track")).toHaveCount(0);
    await expect(page.getByTestId("timeline-video-reference-track")).toHaveCount(0);
    await expect(page.getByTestId("timeline-tab-inspector")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-codirector")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-hotkeys")).toBeVisible();
    await expect(page.getByTestId("timeline-generate-scene")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-preflight")).toBeVisible();
    await expect(page.getByTestId("workspace-fullscreen-controls")).toBeVisible();
    await expect(page.getByTestId("timeline-viewer-fullscreen")).toHaveCount(0);

    await page.getByTestId("timeline-tab-codirector").click();
    await expect(page.getByTestId("timeline-codirector-rail")).toBeVisible();
    await page.getByTestId("timeline-tab-inspector").click();
    await expect(page.getByTestId("timeline-inspector")).toBeVisible();

    const bindings = await listedBindings(request);
    const video = bindings.find((item) => item.media_kind === "video") || bindings[0];
    expect(video?.id, "Schnick needs at least one named reference").toBeTruthy();

    await page.getByTestId("timeline-toolbar-prompt-add").click();
    const promptClip = page.locator('[data-testid^="track-clip-prompt-"]').last();
    await expect(promptClip).toBeVisible({ timeout: 20_000 });
    await promptClip.click();
    const input = page.getByTestId("ref-token-input-prompt");
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill(`${video!.media_kind === "video" ? "*" : "#"}${video!.alias || "Ref"}`);
    const row = page.getByTestId(`ref-token-row-${video!.id}`);
    await expect(row).toBeVisible();
    await row.click();

    await expect
      .poll(async () => {
        const director = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
        const tl = await director.json();
        return (tl.prompt_segments || []).some((seg: { reference_binding_ids?: string[] }) =>
          (seg.reference_binding_ids || []).includes(video!.id),
        );
      }, { timeout: 20_000 })
      .toBeTruthy();
  });

  test("Lip Sync without speaker blocks; one Prompt spans Korri then Anadriya", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    const original = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
    expect(original.ok(), await original.text()).toBeTruthy();
    const originalTl = await original.json();

    try {
      const projectRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
      const project = await projectRes.json();
      const assets = project.assets || [];
      const audios = (Array.isArray(assets) ? assets : []).filter((a: { kind?: string }) => a.kind === "audio");
      expect(audios.length, "Schnick Library needs audio for Lip Sync").toBeGreaterThan(0);
      const audioA = audios[0] as { id: string; filename?: string; tag?: string };
      const audioB = (audios[1] || audios[0]) as { id: string; filename?: string; tag?: string };

      const characters = await listedCharacters(request);
      const korriChar = characters.find((item) => /korri/i.test(item.name || ""));
      let anaChar = characters.find((item) => /anadriya/i.test(item.name || ""));
      if (!anaChar) {
        const createdChar = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
          data: { name: "Anadriya", role: "Lead", description: "Korri's scene partner at Schnick Coffee." },
        });
        expect(createdChar.ok(), await createdChar.text()).toBeTruthy();
        const body = await createdChar.json();
        anaChar = { id: body.id, name: body.name || "Anadriya", active_voice_profile_id: body.active_voice_profile_id };
      }
      expect(korriChar?.id, "Schnick needs Korri").toBeTruthy();
      expect(anaChar?.id, "Schnick needs Anadriya").toBeTruthy();
      let bindings = await listedBindings(request);
      const entityNamed = (re: RegExp) =>
        bindings.find(
          (item) =>
            (item.media_kind === "entity" || item.reference_type === "character") &&
            re.test(item.alias || item.display_token || ""),
        );
      const entityOf = (character?: CharacterRow) =>
        (character &&
          bindings.find(
            (item) =>
              item.identity_id === character.id ||
              (item.media_kind === "entity" &&
                (item.alias || "").toLowerCase() === (character.name || "").replace(/\s+/g, "").toLowerCase()),
          )) ||
        undefined;

      const ensureEntity = async (character: CharacterRow) => {
        const existing = entityOf(character);
        if (existing) return existing;
        const image =
          (Array.isArray(assets) ? assets : []).find(
            (a: { kind?: string; tag?: string }) =>
              a.kind === "image" && (a.tag || "").toLowerCase().includes((character.name || "").toLowerCase()),
          ) || (Array.isArray(assets) ? assets : []).find((a: { kind?: string }) => a.kind === "image");
        expect(image?.id, `Library image for ${character.name}`).toBeTruthy();
        const created = await request.post(`${API}/api/projects/${PROJECT_ID}/references`, {
          data: {
            asset_id: (image as { id: string }).id,
            scope_type: "project",
            scope_id: PROJECT_ID,
            reference_type: "character",
            media_kind: "entity",
            identity_id: character.id,
            alias: (character.name || "Character").replace(/\s+/g, ""),
            usage_modes: ["identity", "appearance"],
            reference_roles: ["character"],
          },
        });
        expect(created.ok(), await created.text()).toBeTruthy();
        bindings = await listedBindings(request);
        return entityOf(character) as BindingRow;
      };

      const korri = (korriChar && (await ensureEntity(korriChar))) || entityNamed(/korri/i);
      const ana = (anaChar && (await ensureEntity(anaChar))) || entityNamed(/anadriya/i);
      expect(korri?.id, "Schnick needs a Korri character reference").toBeTruthy();
      expect(ana?.id, "Schnick needs an Anadriya character reference").toBeTruthy();
      if (!korri || !ana) throw new Error("missing character references");

      const missingSpeakerClip = {
        id: "ls-missing",
        start: 0,
        length: 1,
        audio_asset_id: audioA.id,
        speaker_binding_id: null,
        character_id: null,
        character_name: null,
        label: "Missing speaker",
        status: "ready",
      };
      const missingBody = {
        ...originalTl,
        duration_sec: originalTl.duration_sec || 5,
        prompt_segments: originalTl.prompt_segments || [],
        lipsync: {
          ...(originalTl.lipsync || {}),
          tracks: [
            {
              id: originalTl.lipsync?.tracks?.[0]?.id || "ls-track-1",
              slot: 1,
              label: "Lip Sync 1",
              enabled: true,
              clips: [missingSpeakerClip],
            },
          ],
        },
      };
      const putMissing = await request.put(
        `${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`,
        { data: missingBody },
      );
      expect(putMissing.ok(), await putMissing.text()).toBeTruthy();

      const blocked = await request.get(
        `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${scene.id}/preflight`,
      );
      expect(blocked.ok(), await blocked.text()).toBeTruthy();
      const blockedBody = await blocked.json();
      const speakerFinding = (blockedBody.findings || []).find(
        (item: { code?: string; message?: string }) =>
          item.code === "LIPSYNC_SPEAKER_REQUIRED" || /Assign a character to this Lip Sync clip/i.test(item.message || ""),
      );
      expect(speakerFinding, "missing Lip Sync speaker must block").toBeTruthy();

      await openTimeline(page, scene.id);
      await page.getByTestId("track-clip-lipsync-ls-missing").click();
      await expect(page.getByTestId("lipsync-speaker-required")).toBeVisible();
      const speakerInput = page.getByTestId("ref-token-input-lipsyncSpeaker");
      await speakerInput.fill(`#Bar`);
      const imageBinding = bindings.find((item) => item.media_kind === "image");
      if (imageBinding) {
        const imageRow = page.getByTestId(`ref-token-row-${imageBinding.id}`);
        if (await imageRow.count()) {
          await imageRow.click();
          await expect(page.getByText("Lip Sync only accepts @ character tokens.")).toBeVisible();
        }
      }
      await speakerInput.fill(`@${korri.alias || "Korri"}`);
      await page.getByTestId(`ref-token-row-${korri.id}`).click();
      await expect
        .poll(async () => {
          const director = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
          const tl = await director.json();
          const clip = tl.lipsync?.tracks?.[0]?.clips?.find((item: { id?: string }) => item.id === "ls-missing");
          return clip?.speaker_binding_id === korri.id;
        }, { timeout: 20_000 })
        .toBeTruthy();

      const promptId = "prompt-span";
      const spanning = {
        ...originalTl,
        duration_sec: 5,
        prompt_segments: [
          {
            id: promptId,
            start: 0,
            length: 5,
            text: `@${korri.alias || "Korri"} and @${ana.alias || "Anadriya"} share the counter.`,
            weight: 1,
            region: null,
            reference_binding_ids: [korri.id, ana.id],
          },
        ],
        lipsync: {
          ...(originalTl.lipsync || {}),
          tracks: [
            {
              id: "ls-track-korri",
              slot: 1,
              label: "Lip Sync 1",
              enabled: true,
              clips: [
                {
                  id: "ls-korri",
                  start: 0,
                  length: 2.5,
                  audio_asset_id: audioA.id,
                  speaker_binding_id: korri.id,
                  character_id: korri.identity_id || korriChar?.id || null,
                  character_name: korri.alias || "Korri",
                  label: "Korri",
                  status: "ready",
                },
              ],
            },
            {
              id: "ls-track-ana",
              slot: 2,
              label: "Lip Sync 2",
              enabled: true,
              clips: [
                {
                  id: "ls-ana",
                  start: 2.5,
                  length: 2.5,
                  audio_asset_id: audioB.id,
                  speaker_binding_id: ana.id,
                  character_id: ana.identity_id || anaChar?.id || null,
                  character_name: ana.alias || "Anadriya",
                  label: "Anadriya",
                  status: "ready",
                },
              ],
            },
          ],
        },
      };
      const putSpan = await request.put(
        `${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`,
        { data: spanning },
      );
      expect(putSpan.ok(), await putSpan.text()).toBeTruthy();
      const putJson = await putSpan.json();
      const livePrompt = (putJson.prompt_segments || []).find((item: { reference_binding_ids?: string[] }) =>
        (item.reference_binding_ids || []).includes(korri.id) && (item.reference_binding_ids || []).includes(ana.id),
      );
      expect(livePrompt?.id, "PUT must keep one Prompt with both character IDs").toBeTruthy();
      expect(livePrompt.start).toBe(0);
      expect(livePrompt.length).toBe(5);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByText(/Loading Timeline tracks/)).toHaveCount(0, { timeout: 60_000 });
      await expect(page.getByTestId(`prompt-token-summary-${livePrompt.id}`)).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId(`prompt-token-summary-${livePrompt.id}`)).toContainText("@");
      await expect(page.getByTestId("track-clip-lipsync-ls-korri")).toContainText("@");
      await expect(page.getByTestId("track-clip-lipsync-ls-ana")).toContainText("@");

      const saved = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`);
      const savedTl = await saved.json();
      const prompt = (savedTl.prompt_segments || []).find((item: { id?: string }) => item.id === livePrompt.id);
      expect(prompt?.start).toBe(0);
      expect(prompt?.length).toBe(5);
      expect(prompt?.reference_binding_ids).toEqual([korri.id, ana.id]);
      expect(savedTl.prompt_segments.filter((item: { id?: string }) => item.id === livePrompt.id)).toHaveLength(1);

      const ready = await request.get(
        `${API}/api/director-timeline/projects/${PROJECT_ID}/scenes/${scene.id}/preflight`,
      );
      expect(ready.ok()).toBeTruthy();
      const readyBody = await ready.json();
      expect(
        (readyBody.findings || []).some((item: { code?: string }) => item.code === "LIPSYNC_SPEAKER_REQUIRED"),
      ).toBeFalsy();

      expect(prompt?.voice_profile_id || prompt?.active_voice_profile_id).toBeFalsy();
    } finally {
      await request.put(`${API}/api/projects/${PROJECT_ID}/scenes/${scene.id}/director`, {
        data: originalTl,
      });
    }
  });

  test("Hot Keys pane, defaults, Space, custom assign, conflict, typing safety, reload, reset", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await page.addInitScript(() => {
      // Clear once per browser context so reload can prove persistence.
      if (!sessionStorage.getItem("adept_timeline_hotkeys_cleared")) {
        window.localStorage.removeItem("adept_timeline_hotkeys_v1");
        sessionStorage.setItem("adept_timeline_hotkeys_cleared", "1");
      }
    });
    await openTimeline(page, scene.id);

    await page.getByTestId("timeline-tab-hotkeys").click();
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
    await expect(page.getByTestId("hotkey-row-generateScene")).toContainText("Generate Scene");
    await expect(page.getByTestId("hotkey-capture-generateScene")).toContainText("G");
    await expect(page.getByTestId("hotkey-row-playPause")).toBeVisible();
    await expect(page.getByTestId("hotkey-row-preflight")).toBeVisible();

    await page.getByTestId("timeline-tab-inspector").click();
    const pause = page.getByTestId("timeline-viewer-pause");
    const beforePressed = await pause.getAttribute("aria-pressed");
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
    await page.keyboard.press("Space");
    await expect.poll(async () => pause.getAttribute("aria-pressed")).not.toEqual(beforePressed);
    await page.keyboard.press("Space");
    await expect.poll(async () => pause.getAttribute("aria-pressed")).toEqual(beforePressed);

    await page.getByTestId("timeline-tab-hotkeys").click();
    await page.getByTestId("hotkey-capture-playPause").click();
    await page.getByTestId("hotkey-capture-playPause").press("k");
    await page.getByTestId("hotkey-save").click();
    await expect(page.getByText("Saved")).toBeVisible();
    await expect(page.getByTestId("hotkey-capture-playPause")).toContainText("K");

    await page.getByTestId("hotkey-capture-preflight").click();
    await page.getByTestId("hotkey-capture-preflight").press("g");
    await expect(page.getByTestId("hotkey-conflict")).toBeVisible();
    await expect(page.getByTestId("hotkey-conflict")).toContainText("Generate Scene");
    await page.getByTestId("hotkey-conflict-replace").click();
    await page.getByTestId("hotkey-save").click();
    await expect(page.getByText("Saved")).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("timeline-tab-hotkeys").click();
    await expect(page.getByTestId("hotkey-capture-playPause")).toContainText("K");

    await page.getByTestId("timeline-tab-inspector").click();
    const midPressed = await pause.getAttribute("aria-pressed");
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur?.());
    await page.keyboard.press("k");
    await expect.poll(async () => pause.getAttribute("aria-pressed")).not.toEqual(midPressed);

    await page.getByTestId("timeline-toolbar-prompt-add").click();
    const promptClip = page.locator('[data-testid^="track-clip-prompt-"]').last();
    await promptClip.click();
    const instruction = page.getByTestId("timeline-prompt-instruction");
    await expect(instruction).toBeVisible();
    const pausedWhileTyping = await pause.getAttribute("aria-pressed");
    const generateHits: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/generate") && req.method() === "POST") generateHits.push(req.url());
    });
    await instruction.click();
    await instruction.pressSequentially("Korri grabs the cup", { delay: 15 });
    await page.waitForTimeout(400);
    expect(generateHits).toEqual([]);
    expect(await pause.getAttribute("aria-pressed")).toEqual(pausedWhileTyping);

    const tokenInput = page.getByTestId("ref-token-input-prompt");
    await tokenInput.fill("@");
    await expect(page.getByTestId("ref-token-autocomplete-prompt")).toBeVisible();

    await page.getByTestId("timeline-tab-hotkeys").click();
    await page.getByTestId("hotkey-reset").click();
    await expect(page.getByTestId("hotkey-capture-generateScene")).toContainText("G");
    await expect(page.getByTestId("hotkey-capture-playPause")).toContainText("Space");

    await expect(page.getByTestId("timeline-generate-scene")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-preflight")).toBeVisible();
    await page.getByTestId("timeline-toolbar-preflight").click();
    await page.getByTestId("timeline-tab-inspector").click();
    await expect(page.getByTestId("timeline-inspector")).toBeVisible();
  });
});
