import { test, expect, type APIRequestContext } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";

/**
 * M3.0 Completion Phase 3: feature-flag plumbing the browser depends on.
 *
 * `unifiedExperienceEnabled` decides which Co-Director surface renders, so it has to be
 * serialized honestly on both health payloads and has to track the actual flag rather than
 * a hard-coded default. The M2.9 sound-path flags are asserted here too, because the B4
 * proof is meaningless if the E2E stack silently starts with them off.
 */

const UNIFIED = "codirector_unified_experience_v1";

async function operatorFlags(request: APIRequestContext) {
  const res = await request.get(`${API}/api/health`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()).operator as Record<string, unknown>;
}

// The provider health payload is what the web app polls to decide which surface to render.
async function codirectorHealth(request: APIRequestContext) {
  const res = await request.get(`${API}/api/codirector/providers/active/health`);
  expect(res.ok(), `co-director health returned ${res.status()}`).toBeTruthy();
  return (await res.json()) as Record<string, unknown>;
}

async function setUnified(request: APIRequestContext, enabled: boolean) {
  const res = await request.post(`${API}/api/e2e/feature-flags`, {
    data: { flags: { [UNIFIED]: enabled } },
  });
  expect(res.ok(), `feature-flag control returned ${res.status()}`).toBeTruthy();
  return res.json();
}

test.describe("@critical m30-completion feature flags", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test.afterAll(async ({ request }) => {
    await request.post(`${API}/api/e2e/feature-flags`, { data: { flags: { [UNIFIED]: false } } });
  });

  test("E2E stack starts with the M2.9 sound-path flags on", async ({ request }) => {
    const op = await operatorFlags(request);
    expect(op.audioProductionEnabled, "STUDIO_FEATURE_AUDIO_PRODUCTION_V1").toBe(true);
    expect(op.directorTimelineEnabled, "STUDIO_FEATURE_DIRECTOR_TIMELINE_V1").toBe(true);
    // Flags that are deliberately still off, so the flags-off assertions stay meaningful.
    expect(op.imageProductionEnabled).toBe(false);
    expect(op.videoProductionEnabled).toBe(false);
  });

  test("unifiedExperienceEnabled is serialized on both health payloads and tracks the flag", async ({
    request,
  }) => {
    await setUnified(request, false);
    let op = await operatorFlags(request);
    let cd = await codirectorHealth(request);
    expect(op).toHaveProperty("unifiedExperienceEnabled");
    expect(cd).toHaveProperty("unifiedExperienceEnabled");
    expect(op.unifiedExperienceEnabled).toBe(false);
    expect(cd.unifiedExperienceEnabled).toBe(false);

    const applied = await setUnified(request, true);
    expect(applied.flags[UNIFIED]).toBe(true);

    op = await operatorFlags(request);
    cd = await codirectorHealth(request);
    expect(op.unifiedExperienceEnabled, "/api/health must follow the flag").toBe(true);
    expect(cd.unifiedExperienceEnabled, "co-director health drives the UI switch").toBe(true);

    // The M2.14 status endpoint is the third reader and must agree.
    const status = await request.get(`${API}/api/codirector/m214/status`);
    expect(status.ok()).toBeTruthy();
    const body = await status.json();
    expect(body.enabled).toBe(true);
    expect(body.flagDefault, "the shipped default must stay off").toBe(false);

    await setUnified(request, false);
    expect((await codirectorHealth(request)).unifiedExperienceEnabled).toBe(false);
  });

  test("the flag control refuses unknown flags", async ({ request }) => {
    const res = await request.post(`${API}/api/e2e/feature-flags`, {
      data: { flags: { not_a_real_flag_v1: true } },
    });
    expect(res.status()).toBe(400);
  });

  test("the Co-Director surface follows the flag in the browser", async ({ page, request }) => {
    await setUnified(request, false);
    await page.goto("/co-director");
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("m214-unified-workspace")).toHaveCount(0);

    await setUnified(request, true);
    await page.goto("/co-director");
    await expect(page.getByTestId("m214-unified-workspace")).toBeVisible({ timeout: 20_000 });

    await setUnified(request, false);
    await page.goto("/co-director");
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 20_000 });
  });
});
