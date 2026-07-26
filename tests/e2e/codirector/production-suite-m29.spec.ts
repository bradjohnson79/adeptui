import { expect, test } from "@playwright/test";
import { createTempProject } from "../helpers/app";

/**
 * M2.9 Production Suite fixture-mode acceptance.
 * On-tests need ADEPT_M29_FIXTURE_MODE=1 and STUDIO_FEATURE_*_V1=1 for M2.9 flags.
 * Scenario 1 requires flags OFF (skipped when suite enables M2.9 flags).
 */
test.describe("Co-Director M2.9 Production Suite @critical @isolated", () => {
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
    const on = await m29FlagsOn(request);
    test.skip(
      !on,
      "M2.9 feature flags not enabled - set STUDIO_FEATURE_*_PRODUCTION_V1=1 and ADEPT_M29_FIXTURE_MODE=1",
    );
  }

  test("1 flags off: production suite routes hidden", async ({ page, request }) => {
    const health = await waitForHealth(request);
    const op = health?.operator || {};
    test.skip(
      Boolean(op.imageProductionEnabled || op.videoProductionEnabled),
      "Flags are ON in this environment - covered by unit test_flags_off_api_404; re-run with STUDIO_FEATURE_*_V1=0",
    );

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

  test("4 integrated journey: image frames video timeline control", async ({ page, request }) => {
    await requireM29(request);
    const project = await createTempProject(request, `M29-4 ${Date.now()}`);

    const img = await request.post("/api/codirector/m29/image/generate", {
      data: { projectId: project.id, prompt: "journey still" },
    });
    expect(img.ok()).toBeTruthy();

    const frames = await request.post("/api/codirector/m29/frames/generate", {
      data: { projectId: project.id, count: 2, sequence: true, shotId: "shot-a" },
    });
    expect(frames.ok()).toBeTruthy();

    const video = await request.post("/api/codirector/m29/video/generate", {
      data: { projectId: project.id, prompt: "slow dolly", mode: "text_to_video" },
    });
    expect(video.ok()).toBeTruthy();

    const prop = await request.post("/api/codirector/m29/timeline/propose", {
      data: { projectId: project.id, notes: "assemble" },
    });
    expect(prop.ok()).toBeTruthy();
    const proposalId = (await prop.json()).id;
    const applyBlocked = await request.post(`/api/codirector/m29/timeline/${proposalId}/apply`, {
      data: { actor: "user" },
    });
    expect(applyBlocked.status()).toBe(403);
    await request.post(`/api/codirector/m29/timeline/${proposalId}/approve`, {
      data: { actor: "user" },
    });
    const applied = await request.post(`/api/codirector/m29/timeline/${proposalId}/apply`, {
      data: { actor: "user" },
    });
    expect(applied.ok()).toBeTruthy();

    const ctrl = await request.post("/api/codirector/m29/control/decompose", {
      data: {
        projectId: project.id,
        requestText: "generate image and video then render timeline",
        enqueue: true,
      },
    });
    expect(ctrl.ok()).toBeTruthy();
    const ctrlBody = await ctrl.json();
    expect(ctrlBody.steps.length).toBeGreaterThan(1);

    await page.goto(`/production-suite?projectId=${project.id}`);
    await expect(page.getByTestId("m29-suite-page")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("m29-section-control").click();
    await page.getByTestId("m29-run-btn").click();
    await expect(page.getByTestId("m29-msg")).toHaveText("OK", { timeout: 20_000 });
  });
});