import { expect, test, type Page, type Route } from "@playwright/test";
import {
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});
test.afterEach(async ({ page, request }) => {
  await resetLiveBetaTestSurface(request, page);
});

function componentFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: "qwen_image_2512_models",
    name: "Qwen Image 2512",
    description: "Stylized local image model.",
    required: false,
    status: "ready",
    group: "Image",
    subgroup: "Local Models",
    surfaceGroups: ["Image"],
    lifecycle_status_label: "Ready",
    bestFor: ["Anime illustrations"],
    badges: ["Anime"],
    ...overrides,
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockAiGuidedLifecycle(page: Page, state: { statusById: Record<string, string> }) {
  await page.route("**/api/setup/status", async (route) => {
    await fulfillJson(route, {
      overall_status: "additional_setup_required",
      counts: { ready: 1, not_installed: 1, needs_attention: 1 },
      components: [
        componentFixture(),
        componentFixture({
          id: "hunyuan_video_13b",
          name: "Hunyuan Video 13B",
          description: "Advanced local video model.",
          status: state.statusById.hunyuan_video_13b,
          group: "Video",
          subgroup: "Local Models",
          surfaceGroups: ["Video"],
          lifecycle_status_label: state.statusById.hunyuan_video_13b === "ready" ? "Ready" : "Not Installed",
          bestFor: ["Long-form local video", "High-fidelity motion", "short film", "make a short film"],
          badges: ["Video", "Local GPU"],
        }),
        componentFixture({
          id: "flux1_dev_local",
          name: "FLUX.1 Dev",
          description: "Photoreal local image model.",
          status: state.statusById.flux1_dev_local,
          lifecycle_status_label: state.statusById.flux1_dev_local === "ready" ? "Ready" : "Repair Required",
          bestFor: ["Photoreal characters"],
          badges: ["Photoreal"],
        }),
        componentFixture({
          id: "index_tts2",
          name: "IndexTTS2",
          description: "Voice runtime.",
          status: "error",
          group: "Voice",
          subgroup: "Local Models",
          surfaceGroups: ["Voice"],
          lifecycle_status_label: "Repair Required",
          bestFor: ["Voice performance"],
          badges: ["Voice"],
        }),
        componentFixture({
          id: "ace_step_local",
          name: "ACE-Step Music Runtime",
          description: "Local music runtime.",
          status: "not_installed",
          group: "Music",
          subgroup: "Local Runtimes",
          surfaceGroups: ["Music"],
          lifecycle_status_label: "Not Installed",
          bestFor: ["Music beds"],
          badges: ["Music"],
        }),
        componentFixture({
          id: "longcat-video-avatar-1-5-local",
          name: "LongCat Avatar 1.5",
          description: "Avatar runtime.",
          status: "not_installed",
          group: "Avatar",
          subgroup: "Local Models",
          surfaceGroups: ["Avatar", "Motion"],
          lifecycle_status_label: "Not Installed",
          bestFor: ["Talking avatars"],
          badges: ["Avatar"],
        }),
        componentFixture({
          id: "fal_key",
          name: "fal.ai API Key",
          description: "Hosted provider credentials.",
          status: "ready",
          group: "API Providers",
          subgroup: "Credentials",
          surfaceGroups: ["API Providers"],
          lifecycle_status_label: "Ready",
          bestFor: ["Hosted providers"],
          badges: ["Cloud"],
        }),
        componentFixture({
          id: "pack_essential_photoreal",
          name: "Essential Photoreal Pack",
          description: "Creative pack for photoreal work.",
          status: "ready",
          group: "Creative Packs",
          subgroup: "Essential Packs",
          surfaceGroups: ["Creative Packs"],
          lifecycle_status_label: "Ready",
          bestFor: ["Photoreal faces"],
          badges: ["Creative Pack"],
        }),
      ],
    });
  });

  await page.route("**/api/setup/install-jobs**", async (route) => {
    await fulfillJson(route, { jobs: [] });
  });

  await page.route("**/api/capabilities**", async (route) => {
    await fulfillJson(route, {
      schemaVersion: 1,
      generatedAt: "2026-08-02T00:00:00Z",
      correlationId: "caps-ai-guided",
      counts: { blocked: 0 },
      capabilities: [],
      blockers: [],
      callable: [],
      readinessTotal: 0,
      deferred: [],
      probeWarnings: [],
    });
  });

  await page.route("**/api/setup/lifecycle/cloud-providers", async (route) => {
    await fulfillJson(route, {
      count: 1,
      items: [
        {
          providerId: "fal",
          displayName: "fal.ai",
          statusLabel: "Configured",
          configured: true,
          operations: ["image", "video"],
          modelFamilies: ["flux", "hunyuan"],
        },
      ],
    });
  });

  await page.route("**/api/setup/lifecycle/monitor", async (route) => {
    await fulfillJson(route, { count: 0, items: [] });
  });
}

test.describe("@critical ai-guided setup lifecycle", () => {
  test("mode chooser and AI-guided lifecycle panel render", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `AI Guided Setup ${Date.now()}`);
    try {
      await mockAiGuidedLifecycle(page, {
        statusById: { hunyuan_video_13b: "not_installed", flux1_dev_local: "error" },
      });
      await openSetup(page, project.id);

      await expect(page.getByRole("heading", { name: "Setup Mode" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Guided", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "AI-Guided", exact: true })).toBeVisible();
      await expect(page.getByRole("button", { name: "Manual", exact: true })).toBeVisible();

      await page.getByRole("button", { name: "AI-Guided", exact: true }).click();
      await expect(page.getByRole("heading", { name: "AI-Guided Setup" })).toBeVisible();
      await expect(page.getByText("Recommended For This Goal")).toBeVisible();
      await expect(page.getByText("Lifecycle Groups")).toBeVisible();
      await expect(page.getByText("Cloud Providers")).toBeVisible();
      for (const group of ["Music", "Avatar", "API Providers", "Creative Packs"]) {
        const summary = page.locator("summary").filter({ hasText: group }).first();
        await expect(summary).toBeVisible();
        await summary.click();
      }
      await expect(page.getByText("ACE-Step Music Runtime")).toBeVisible();
      await expect(page.getByText("LongCat Avatar 1.5").first()).toBeVisible();
      await expect(page.getByText("fal.ai API Key").first()).toBeVisible();
      await expect(page.getByText("Essential Photoreal Pack").first()).toBeVisible();
      await expect(page.getByText("Source Manager runs verified sources")).toBeVisible();
      await expect(page.getByRole("link", { name: /Open Source Manager/i })).toHaveCount(0);

      await expect(page.getByText("Try prompts like")).toBeVisible();
      await expect(page.getByText("make a short film")).toBeVisible();
      await page.getByPlaceholder("Describe the film, video, scene, or production you want to create...").fill("anime poster");
      await expect(page.getByText("Strong fit for anime and stylized illustration work.")).toBeVisible();
      await page.getByPlaceholder("Describe the film, video, scene, or production you want to create...").fill("make a short film");
      await expect(page.getByText("Best fit for short-film and cinematic video generation.")).toBeVisible();
      await expect(page.getByText("Hunyuan Video 13B").first()).toBeVisible();
      await expect(page.locator(".setup-requirement").filter({ hasText: "Not Installed" }).first()).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("focused AI-guided deep link reviews plan and records calibrate plus certify", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `AI Guided Focus ${Date.now()}`);
    const state = { statusById: { hunyuan_video_13b: "not_installed", flux1_dev_local: "error" } };
    let lastPlanRequest: Record<string, unknown> | null = null;
    let calibrateCalls = 0;
    let certifyCalls = 0;
    try {
      await mockAiGuidedLifecycle(page, state);
      await page.route("**/api/setup/lifecycle/install-plan", async (route) => {
        lastPlanRequest = route.request().postDataJSON() as Record<string, unknown>;
        await fulfillJson(route, {
          componentId: "hunyuan_video_13b",
          componentName: "Hunyuan Video 13B",
          requiresRuntimeConfirmation: true,
          requiresModelDownloadConfirmation: true,
          steps: ["Verify GPU runtime", "Download official model", "Run post-install health check"],
          warnings: ["Large download"],
        });
      });
      await page.route("**/api/setup/lifecycle/components/hunyuan_video_13b/calibrate", async (route) => {
        calibrateCalls += 1;
        await fulfillJson(route, { ok: true });
      });
      await page.route("**/api/setup/lifecycle/components/hunyuan_video_13b/certify", async (route) => {
        certifyCalls += 1;
        await fulfillJson(route, { ok: true });
      });

      await page.goto(`/project/${project.id}?workspace=setup&setupMode=ai_guided&setupComponent=hunyuan_video_13b`);
      await expect(page.getByRole("heading", { name: "AI-Guided Setup" })).toBeVisible();
      await expect(page.getByText("Opened for Hunyuan Video 13B.")).toBeVisible();

      await page.getByRole("button", { name: "Review Plan" }).first().click();
      await expect(page.getByText("Hunyuan Video 13B plan")).toBeVisible();
      expect(lastPlanRequest).toMatchObject({ componentId: "hunyuan_video_13b", action: "install" });

      await page.getByRole("button", { name: "Calibrate + Certify" }).first().click();
      await expect(page.getByText("Hunyuan Video 13B calibration and certification recorded.")).toBeVisible();
      expect(calibrateCalls).toBe(1);
      expect(certifyCalls).toBe(1);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("verify refresh propagates ready state for focused component", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `AI Guided Verify ${Date.now()}`);
    const state = { statusById: { hunyuan_video_13b: "not_installed", flux1_dev_local: "error" } };
    try {
      await mockAiGuidedLifecycle(page, state);
      await page.route("**/api/setup/lifecycle/components/flux1_dev_local/verify", async (route) => {
        state.statusById.flux1_dev_local = "ready";
        await fulfillJson(route, { ok: true, statusLabel: "Ready" });
      });

      await page.goto(`/project/${project.id}?workspace=setup&setupMode=ai_guided&setupComponent=flux1_dev_local`);
      await expect(page.getByText("Opened for FLUX.1 Dev.")).toBeVisible();

      await page.getByRole("button", { name: "Verify" }).first().click();
      await expect(page.locator(".setup-requirement").filter({ hasText: "Ready" }).first()).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("root AI-guided redirect preserves source and component", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `AI Guided Redirect ${Date.now()}`);
    try {
      await mockAiGuidedLifecycle(page, {
        statusById: { hunyuan_video_13b: "not_installed", flux1_dev_local: "error" },
      });
      await page.goto("/?setupMode=ai_guided&setupSource=production_dock&setupComponent=flux1_dev_local#ai-guided-setup-heading");
      await expect.poll(() => page.url()).toContain("/project/");
      await expect.poll(() => page.url()).toContain("workspace=setup");
      await expect.poll(() => page.url()).toContain("setupMode=ai_guided");
      await expect.poll(() => page.url()).toContain("setupComponent=flux1_dev_local");
      await expect.poll(() => page.url()).toContain("setupSource=production_dock");
      await expect(page.getByRole("heading", { name: "AI-Guided Setup" })).toBeVisible();
      await expect(page.getByText("Opened for FLUX.1 Dev.")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});

