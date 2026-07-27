import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.9 Production Suite fixture-mode acceptance.
 * On-tests need ADEPT_M29_FIXTURE_MODE=1 and STUDIO_FEATURE_*_PRODUCTION_V1=1 for M2.9 flags.
 * Scenario 1 requires flags OFF (skipped when suite enables M2.9 flags).
 *
 * Recommended Run A (flags ON):
 *   set all STUDIO_FEATURE_*_PRODUCTION_V1=1 (+ control) and ADEPT_M29_FIXTURE_MODE=1
 * Recommended Run B (flags OFF): filter `-g "1 flags off"` with those flags =0
 */
/** API flag name -> the key it is published under in `/api/health`.operator. */
const M29_FLAGS: Record<string, string> = {
  image_production_v1: "imageProductionEnabled",
  frame_production_v1: "frameProductionEnabled",
  video_production_v1: "videoProductionEnabled",
  director_timeline_v1: "directorTimelineEnabled",
  lipsync_production_v1: "lipsyncProductionEnabled",
  audio_production_v1: "audioProductionEnabled",
  editing_production_v1: "editingProductionEnabled",
  render_production_v1: "renderProductionEnabled",
  codirector_production_control_v1: "codirectorProductionControlEnabled",
};
const M29_FLAG_NAMES = Object.keys(M29_FLAGS);

test.describe("Co-Director M2.9 Production Suite @critical @isolated", () => {
  // Scenario 1 forces the flags off for itself and hands back exactly what it found, so the
  // specs that need audio + director timeline ON are unaffected by the order they run in.
  let m29FlagsToRestore: Record<string, boolean> | null = null;

  test.afterEach(async ({ request }) => {
    if (!m29FlagsToRestore) return;
    const flags = m29FlagsToRestore;
    m29FlagsToRestore = null;
    await request.post("/api/e2e/feature-flags", { data: { flags } });
  });

  async function waitForHealth(request: import("@playwright/test").APIRequestContext) {
    let lastStatus = 0;
    for (let i = 0; i < 60; i++) {
      try {
        const health = await request.get("/api/health");
        lastStatus = health.status();
        if (health.ok()) return health.json();
      } catch {
        /* booting */
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`API /api/health not ready (last status ${lastStatus})`);
  }

  async function m29FlagsOn(request: import("@playwright/test").APIRequestContext) {
    const h = await waitForHealth(request);
    const op = h?.operator || {};
    return Boolean(
      op.imageProductionEnabled &&
        op.frameProductionEnabled &&
        op.videoProductionEnabled &&
        op.directorTimelineEnabled &&
        op.lipsyncProductionEnabled &&
        op.audioProductionEnabled &&
        op.editingProductionEnabled &&
        op.renderProductionEnabled &&
        op.codirectorProductionControlEnabled &&
        op.productionExecutiveEnabled,
    );
  }

  async function requireM29(request: import("@playwright/test").APIRequestContext) {
    // Default e2e-start only leaves the M3.0 sound-path flags on (audio + director). The
    // section / fixture journeys need the whole M2.9 surface, so flip every flag on for the
    // duration of this test and restore afterward — same control the flags-off case uses.
    if (await m29FlagsOn(request)) return;
    const health = await waitForHealth(request);
    const op = health?.operator || {};
    const previous = Object.fromEntries(
      M29_FLAG_NAMES.map((name) => [name, Boolean(op[M29_FLAGS[name]])]),
    );
    const on = await request.post("/api/e2e/feature-flags", {
      data: { flags: Object.fromEntries(M29_FLAG_NAMES.map((name) => [name, true])) },
    });
    test.skip(!on.ok(), `E2E feature-flag control unavailable (${on.status()})`);
    m29FlagsToRestore = previous;
    test.skip(
      !(await m29FlagsOn(request)),
      "M2.9 feature flags not enabled - set STUDIO_FEATURE_*_PRODUCTION_V1=1 and ADEPT_M29_FIXTURE_MODE=1",
    );
  }

  async function expectOk(
    response: import("@playwright/test").APIResponse,
    label: string,
  ) {
    if (!response.ok()) {
      const body = await response.text();
      throw new Error(`${label} failed: ${response.status()} ${body}`);
    }
    return response.json();
  }

  test("1 flags off: production suite routes hidden", async ({ page, request }) => {
    const health = await waitForHealth(request);
    const op = health?.operator || {};
    // The nav link and the workspace appear when *any* M2.9 flag is on (see StudioChrome), and
    // E2E now ships audio + director timeline ON for the M3.0 sound-path proof. Rather than
    // skipping this scenario away, turn every M2.9 flag off for the duration of this test
    // through the E2E-only control, then hand back whatever was there before.
    const previous = Object.fromEntries(
      M29_FLAG_NAMES.map((name) => [name, Boolean(op[M29_FLAGS[name]])]),
    );
    const off = await request.post("/api/e2e/feature-flags", {
      data: { flags: Object.fromEntries(M29_FLAG_NAMES.map((name) => [name, false])) },
    });
    test.skip(!off.ok(), `E2E feature-flag control unavailable (${off.status()})`);
    m29FlagsToRestore = previous;

    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });

    await page.goto("/");
    await expect(page.getByTestId("nav-production-suite")).toHaveCount(0);

    await page.goto("/production-suite");
    await expect(page.getByTestId("m29-suite-unavailable")).toBeVisible({ timeout: 15_000 });

    const img = await request.post("/api/codirector/m29/image/generate", {
      data: { projectId: "x", prompt: "nope" },
    });
    expect([403, 404]).toContain(img.status());
    expect(errors.filter((e) => !/favicon|ResizeObserver/i.test(e)).length).toBe(0);
  });

  test("2 sections visible when flags on", async ({ page, request }) => {
    await requireM29(request);
    const project = await createTempProject(request, `M29-2 ${Date.now()}`);
    await page.goto(`/production-suite?projectId=${project.id}`);
    await expect(page.getByTestId("m29-suite-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("m29-section-image")).toBeVisible();
    await expect(page.getByTestId("m29-section-frames")).toBeVisible();
    await expect(page.getByTestId("m29-section-video")).toBeVisible();
    await expect(page.getByTestId("m29-section-timeline")).toBeVisible();
    await expect(page.getByTestId("m29-section-lipsync")).toBeVisible();
    await expect(page.getByTestId("m29-section-audio")).toBeVisible();
    await expect(page.getByTestId("m29-section-edit")).toBeVisible();
    await expect(page.getByTestId("m29-section-render")).toBeVisible();
    await expect(page.getByTestId("m29-section-control")).toBeVisible();
  });

  test("3 image generate fixture path", async ({ page, request }) => {
    await requireM29(request);
    const project = await createTempProject(request, `M29-3 ${Date.now()}`);
    await page.goto(`/production-suite?projectId=${project.id}`);
    await expect(page.getByTestId("m29-suite-page")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("m29-section-image").click();
    await page.getByTestId("m29-run-btn").click();
    await expect(page.getByTestId("m29-msg")).toHaveText("OK", { timeout: 20_000 });
    const text = await page.getByTestId("m29-result").innerText();
    expect(text).toContain("assetId");
    expect(text.toLowerCase()).toContain("fixture");
  });

  test("4 integrated journey: multi-section fixture handoffs", async ({ page, request }) => {
    await requireM29(request);
    const project = await createTempProject(request, `M29-4 ${Date.now()}`);
    const pid = project.id;

    const img = await expectOk(
      await request.post("/api/codirector/m29/image/generate", {
        data: { projectId: pid, prompt: "journey still" },
      }),
      "image/generate",
    );
    expect(img.fixture === true || String(img.provider || "").toLowerCase().includes("fixture")).toBeTruthy();
    const imageVersionId = img.versionId || img.id || img.assetVersionId;

    const frames = await expectOk(
      await request.post("/api/codirector/m29/frames/generate", {
        data: { projectId: pid, count: 2, sequence: true, shotId: "shot-a", prompt: "first last" },
      }),
      "frames/generate",
    );
    expect(Array.isArray(frames.frames) ? frames.frames.length : 0).toBeGreaterThanOrEqual(2);

    const video = await expectOk(
      await request.post("/api/codirector/m29/video/generate", {
        data: { projectId: pid, prompt: "slow dolly", mode: "text_to_video" },
      }),
      "video/generate",
    );
    const videoAssetId = video.assetId || video.id;

    const audio = await expectOk(
      await request.post("/api/codirector/m29/audio/generate", {
        data: { projectId: pid, kind: "dialogue", prompt: "line one", durationSec: 1.5 },
      }),
      "audio/generate",
    );
    const audioAssetId = audio.assetId || audio.cueId || audio.id;

    await expectOk(
      await request.post("/api/codirector/m29/lipsync/mouth-rectangle", {
        data: {
          projectId: pid,
          rectangles: [{ x: 0.4, y: 0.55, w: 0.2, h: 0.1, t: 0 }],
        },
      }),
      "lipsync/mouth-rectangle",
    );
    await expectOk(
      await request.post("/api/codirector/m29/lipsync/mouth-track", {
        data: { projectId: pid, videoAssetId },
      }),
      "lipsync/mouth-track",
    );
    await expectOk(
      await request.post("/api/codirector/m29/lipsync/generate", {
        data: { projectId: pid, audioAssetId, videoAssetId },
      }),
      "lipsync/generate",
    );

    await expectOk(
      await request.post("/api/codirector/m29/editing/sfx-cue", {
        data: { projectId: pid, prompt: "door close", startSec: 0.2, durationSec: 0.5 },
      }),
      "editing/sfx-cue",
    );
    await expectOk(
      await request.post("/api/codirector/m29/editing/music-cue", {
        data: { projectId: pid, prompt: "soft bed", startSec: 0, durationSec: 2 },
      }),
      "editing/music-cue",
    );

    const editBlocked = await request.post("/api/codirector/m29/editing/apply", {
      data: { projectId: pid, ops: [{ op: "trim", in: 0, out: 1 }], approved: false },
    });
    expect(editBlocked.status()).toBe(403);
    await expectOk(
      await request.post("/api/codirector/m29/editing/apply", {
        data: { projectId: pid, ops: [{ op: "trim", in: 0, out: 1 }], approved: true },
      }),
      "editing/apply",
    );

    const prop = await expectOk(
      await request.post("/api/codirector/m29/timeline/propose", {
        data: {
          projectId: pid,
          notes: "assemble journey",
          clips: [
            { assetId: videoAssetId || "vid", startSec: 0, durationSec: 2 },
            { assetId: audioAssetId || "aud", startSec: 0, durationSec: 1.5 },
          ],
        },
      }),
      "timeline/propose",
    );
    const proposalId = prop.id;
    const applyBlocked = await request.post(`/api/codirector/m29/timeline/${proposalId}/apply`, {
      data: { actor: "user" },
    });
    expect(applyBlocked.status()).toBe(403);
    await expectOk(
      await request.post(`/api/codirector/m29/timeline/${proposalId}/approve`, {
        data: { actor: "user" },
      }),
      "timeline/approve",
    );
    await expectOk(
      await request.post(`/api/codirector/m29/timeline/${proposalId}/apply`, {
        data: { actor: "user" },
      }),
      "timeline/apply",
    );

    const rend = await expectOk(
      await request.post("/api/codirector/m29/render", {
        data: { projectId: pid, kind: "scene_render" },
      }),
      "render",
    );
    const manifestId = rend.manifestId || rend.id;
    if (manifestId) {
      await expectOk(await request.get(`/api/codirector/m29/render/${manifestId}`), "render/get");
    }

    const ctrl = await expectOk(
      await request.post("/api/codirector/m29/control/decompose", {
        data: {
          projectId: pid,
          requestText: "generate image and video then render timeline",
          enqueue: true,
        },
      }),
      "control/decompose",
    );
    expect(ctrl.steps.length).toBeGreaterThan(1);

    if (imageVersionId) {
      await expectOk(
        await request.post(`/api/codirector/m29/image/${imageVersionId}/approve`, {
          data: { actor: "user" },
        }),
        "image/approve",
      );
    }

    await page.goto(`/production-suite?projectId=${pid}`);
    await expect(page.getByTestId("m29-suite-page")).toBeVisible({ timeout: 20_000 });
    for (const section of [
      "image",
      "frames",
      "video",
      "timeline",
      "lipsync",
      "audio",
      "edit",
      "render",
      "control",
    ]) {
      await expect(page.getByTestId(`m29-section-${section}`)).toBeVisible();
    }
    await page.getByTestId("m29-section-control").click();
    await page.getByTestId("m29-run-btn").click();
    await expect(page.getByTestId("m29-msg")).toHaveText("OK", { timeout: 20_000 });
  });
});
