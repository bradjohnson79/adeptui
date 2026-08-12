import { expect, test, type Page, type Route } from "@playwright/test";
import {
  API,
  createTempProject,
  deleteProject,
  openSetup,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import type { APIRequestContext } from "@playwright/test";

async function waitForStack(request: APIRequestContext) {
  try {
    await waitForAppReady(request);
  } catch {
    await expect
      .poll(
        async () => {
          try {
            return (await request.get(`${API}/api/health`)).ok();
          } catch {
            return false;
          }
        },
        { timeout: 120_000 }
      )
      .toBeTruthy();
  }
}

test.beforeEach(async ({ page, request }) => {
  await waitForStack(request);
  await resetLiveBetaTestSurface(request, page);
});
test.afterEach(async ({ page, request }) => {
  await resetLiveBetaTestSurface(request, page);
});

const PACK = {
  id: "pack_essential_photoreal",
  name: "Photoreal Essential Pack",
  description: "Official pack for cinematic photoreal workflows.",
};

function componentFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: PACK.id,
    name: PACK.name,
    description: PACK.description,
    required: true,
    status: "not_installed",
    installer: "asset_pack",
    verifier: "asset_pack",
    source_available: true,
    source_valid: true,
    expected_download_bytes: 1024 * 1024 * 4,
    recommended_vram_gb: 12,
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

async function installJobMocks(page: Page, opts?: {
  componentStatus?: string;
  sourceAvailable?: boolean;
  sourceValid?: boolean;
  initialJobs?: Record<string, unknown>[];
}) {
  const state = {
    componentStatus: opts?.componentStatus || "not_installed",
    sourceAvailable: opts?.sourceAvailable ?? true,
    sourceValid: opts?.sourceValid ?? true,
    jobs: (opts?.initialJobs || []) as Record<string, unknown>[],
  };

  await page.route("**/api/setup/status", async (route) => {
    await fulfillJson(route, {
      overall_status: "additional_setup_required",
      counts: { ready: 0, not_installed: 1, needs_attention: state.componentStatus === "error" ? 1 : 0 },
      components: [
        componentFixture({
          status: state.componentStatus,
          source_available: state.sourceAvailable,
          source_valid: state.sourceValid,
          issue_summary: state.componentStatus === "error" ? "Previous install failed." : null,
          last_verified_at: state.componentStatus === "ready" ? "2026-08-01T20:00:00Z" : null,
        }),
      ],
    });
  });

  await page.route("**/api/setup/components/*/suggested-path", async (route) => {
    await fulfillJson(route, {
      component_id: PACK.id,
      suggested_path: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
      path_selector: "directory",
    });
  });

  await page.route("**/api/setup/install-jobs/events**", async (route) => {
    await route.abort();
  });

  await page.route("**/api/setup/install-jobs**", async (route) => {
    const url = route.request().url();
    const isCollection =
      /\/api\/setup\/install-jobs\/?(\?|$)/.test(url) && !/\/api\/setup\/install-jobs\/[^?/]+/.test(url);
    if (route.request().method() === "GET" && isCollection) {
      await fulfillJson(route, { jobs: state.jobs });
      return;
    }
    if (route.request().method() !== "POST" || !isCollection) {
      await route.fallback();
      return;
    }
    state.jobs = [
      {
        id: "job-photoreal-1",
        componentId: PACK.id,
        componentName: PACK.name,
        state: "downloading",
        phase: "downloading",
        providerId: "official-github",
        destinationRoot: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
        progress: {
          percent: 44,
          bytesDownloaded: 1835008,
          bytesTotal: 4194304,
          speedBytesPerSecond: 524288,
          etaSeconds: 6,
          currentFile: "photoreal-pack.zip",
          currentStep: "Downloading official pack",
        },
        capabilities: {
          canPause: true,
          canResume: false,
          canCancel: true,
          canRetry: false,
          canRepair: false,
        },
        updatedAt: "2026-08-01T20:44:00Z",
      },
    ];
    await fulfillJson(route, { job: state.jobs[0], created: true });
  });

  await page.route("**/api/downloads**", async (route) => {
    await fulfillJson(route, { operations: [] });
  });

  await page.route("**/api/capabilities**", async (route) => {
    await fulfillJson(route, {
      schemaVersion: 1,
      generatedAt: "2026-08-01T20:44:00Z",
      correlationId: "caps-1",
      counts: { blocked: 0 },
      capabilities: [],
      blockers: [],
      callable: [],
      readinessTotal: 0,
      deferred: [],
      probeWarnings: [],
    });
  });

  return state;
}

async function sourceManagerMocks(page: Page, opts?: {
  sourceAvailable?: boolean;
  sourceValid?: boolean;
}) {
  const state = {
    sourceAvailable: opts?.sourceAvailable ?? false,
    sourceValid: opts?.sourceValid ?? false,
    saved: false,
  };

  await page.route("**/api/source-manager/overview", async (route) => {
    await fulfillJson(route, {
      schemaVersion: 3,
      providers: [],
      sources: [],
      activeDownloads: [],
      installHistory: [],
      messages: { intro: "Mocked Source Manager" },
    });
  });

  await page.route("**/api/source-manager/voice-models", async (route) => {
    await fulfillJson(route, { components: [], count: 0 });
  });

  await page.route("**/api/install-history", async (route) => {
    await fulfillJson(route, { entries: [], count: 0 });
  });

  await page.route("**/api/setup/install-jobs/events**", async (route) => {
    await route.abort();
  });

  await page.route("**/api/setup/install-jobs?*", async (route) => {
    await fulfillJson(route, { jobs: [] });
  });

  await page.route("**/api/downloads**", async (route) => {
    await fulfillJson(route, { operations: [] });
  });

  await page.route("**/api/setup/status", async (route) => {
    await fulfillJson(route, {
      components: [
        componentFixture({
          source_available: state.sourceAvailable,
          source_valid: state.sourceValid,
          status: state.saved ? "not_installed" : "source_pending",
        }),
      ],
    });
  });

  await page.route("**/api/capabilities**", async (route) => {
    await fulfillJson(route, {
      schemaVersion: 1,
      generatedAt: "2026-08-01T20:44:00Z",
      correlationId: "caps-2",
      counts: { blocked: 1, deferred_version_1_2: 0 },
      capabilities: [],
      blockers: [
        {
          capabilityId: "models.video.ready",
          displayName: "Video model install",
          subsystem: "models",
          status: "blocked",
          message: "Required pack is missing.",
          recommendedAction: "install_comfyui_extensions",
          componentIds: [PACK.id],
        },
      ],
      callable: [],
      readinessTotal: 1,
      deferred: [],
      probeWarnings: [],
    });
  });

  const verifiedSource = {
    ok: true,
    provider: "github",
    repository: "AdeptFilmWorks/photoreal-pack",
    revision: "v1.0.0",
    selected_file: "photoreal-pack.zip",
    compatibility: "Verified for this component",
    message: "Source verified.",
    blocking_errors: [],
    warnings: [],
  };

  // AddSourceWorkflow validates via Setup, not Source Manager.
  await page.route("**/api/setup/sources/verify", async (route) => {
    await fulfillJson(route, verifiedSource);
  });
  await page.route("**/api/source-manager/sources/verify", async (route) => {
    await fulfillJson(route, { legacy: verifiedSource, ...verifiedSource });
  });

  await page.route("**/api/source-manager/components/*/source", async (route) => {
    if (route.request().method() === "POST") {
      state.saved = true;
      state.sourceAvailable = true;
      state.sourceValid = true;
      await fulfillJson(route, {
        assignment: { componentId: PACK.id },
        source: { id: "src-photoreal" },
      });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/source-manager/**/assign**", async (route) => {
    state.saved = true;
    state.sourceAvailable = true;
    state.sourceValid = true;
    await fulfillJson(route, {
      assignment: { componentId: PACK.id },
      source: { id: "src-photoreal" },
    });
  });

  return state;
}

test.describe("@critical @isolated setup install progress", () => {
  test("restores install progress after reload", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Install Progress ${Date.now()}`);
    try {
      await installJobMocks(page);
      await openSetup(page, project.id);

      const card = page.getByTestId(`setup-card-${PACK.id}`);
      await card.getByRole("button", { name: /^(Download and Install|Install|Continue Install)$/i }).click();
      await page.getByTestId("install-preflight-confirm").check();
      await expect(page.getByTestId("install-preflight-submit")).toBeEnabled({ timeout: 15_000 });
      await page.getByTestId("install-preflight-submit").click();

      await expect(page.getByTestId(`install-progress-${PACK.id}`)).toBeVisible();
      await expect(page.getByTestId("install-progress-current-file")).toContainText("photoreal-pack.zip");

      // Keep manual Setup (component grid + progress cards) after reload; AI-Guided mode hides them.
      await page.goto(`/project/${project.id}?workspace=setup&setupMode=manual&r=${Date.now()}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.locator(".setup-component-grid").first()).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId(`install-progress-${PACK.id}`)).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("install-progress-current-file")).toContainText("photoreal-pack.zip");
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("shows failure and repair actions", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Install Repair ${Date.now()}`);
    try {
      const state = await installJobMocks(page, {
        componentStatus: "error",
        initialJobs: [
          {
            id: "job-photoreal-failed",
            componentId: PACK.id,
            componentName: PACK.name,
            state: "failed",
            phase: "downloading",
            providerId: "official-github",
            destinationRoot: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
            progress: {
              percent: 57,
              bytesDownloaded: 2392064,
              bytesTotal: 4194304,
              currentFile: "photoreal-pack.zip",
            },
            error: {
              code: "download_http_error",
              kind: "download failed",
              message: "Official download returned HTTP 500.",
              retryable: true,
              repairable: true,
            },
            capabilities: { canRetry: true, canRepair: true, canCancel: false },
            updatedAt: "2026-08-01T20:45:00Z",
          },
        ],
      });

      await page.route("**/api/setup/install-jobs/job-photoreal-failed/repair", async (route) => {
        state.jobs = [
          {
            id: "job-photoreal-failed",
            componentId: PACK.id,
            componentName: PACK.name,
            state: "installing",
            phase: "installing",
            providerId: "official-github",
            destinationRoot: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
            progress: {
              percent: 72,
              bytesDownloaded: 4194304,
              bytesTotal: 4194304,
              currentFile: "manifest.json",
              currentStep: "Repairing files",
            },
            capabilities: { canPause: false, canResume: false, canCancel: true },
            updatedAt: "2026-08-01T20:46:00Z",
          },
        ];
        await fulfillJson(route, { job: state.jobs[0] });
      });

      await openSetup(page, project.id);
      await expect(page.getByTestId("install-error-panel")).toBeVisible();
      await page.getByTestId("install-error-repair").click();
      await expect(page.getByTestId(`install-progress-${PACK.id}`)).toHaveAttribute("data-state", "installing");
      await expect(page.getByText(/Repairing files/i)).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("opens required components panel from blocked capability action", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Source Manager Blocker ${Date.now()}`);
    try {
      await sourceManagerMocks(page);
      await page.goto(`/source-manager?projectId=${project.id}`);
      await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
      await page.getByTestId("capability-action-models.video.ready").click();
      await expect(page).toHaveURL(
        new RegExp(
          `/project/${project.id.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\?.*setupMode=ai_guided.*setupComponent=${PACK.id}.*workspace=setup`,
        ),
      );
      await expect(page.getByRole("heading", { name: "AI-Guided Setup" })).toBeVisible();
      await expect(page.getByText(new RegExp(`Opened for ${PACK.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`))).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("shows multi-phase stepper and keeps details collapsed by default", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Install Phases ${Date.now()}`);
    try {
      await installJobMocks(page, {
        initialJobs: [
          {
            id: "job-photoreal-phases",
            componentId: PACK.id,
            componentName: PACK.name,
            state: "downloading",
            phase: "downloading",
            stallStatus: "none",
            phaseSteps: [
              { id: "preparing", label: "Preparing runtime", status: "complete" },
              { id: "downloading", label: "Downloading model", status: "active" },
              { id: "verifying_download", label: "Verifying files", status: "pending" },
              { id: "installing", label: "Installing dependencies", status: "pending" },
              { id: "configuring", label: "Configuring provider", status: "pending" },
              { id: "verifying_install", label: "Final health check", status: "pending" },
            ],
            progress: {
              percent: 43,
              bytesDownloaded: 1800000000,
              bytesTotal: 4000000000,
              currentFile: "photoreal-pack.zip",
              phaseSteps: [
                { id: "preparing", label: "Preparing runtime", status: "complete" },
                { id: "downloading", label: "Downloading model", status: "active" },
                { id: "verifying_download", label: "Verifying files", status: "pending" },
                { id: "installing", label: "Installing dependencies", status: "pending" },
                { id: "configuring", label: "Configuring provider", status: "pending" },
                { id: "verifying_install", label: "Final health check", status: "pending" },
              ],
            },
            capabilities: { canPause: true, canCancel: true },
            updatedAt: "2026-08-01T20:45:00Z",
          },
        ],
      });
      await openSetup(page, project.id);
      await expect(page.getByTestId("install-phase-steps")).toBeVisible();
      await expect(page.getByTestId("install-details-drawer")).toHaveCount(0);
      await page.getByTestId("install-details-toggle").click();
      await expect(page.getByTestId("install-details-drawer")).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("allows cancelling an active install job", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Install Cancel ${Date.now()}`);
    try {
      const state = await installJobMocks(page, {
        initialJobs: [
          {
            id: "job-photoreal-cancel",
            componentId: PACK.id,
            componentName: PACK.name,
            state: "downloading",
            phase: "downloading",
            providerId: "official-github",
            destinationRoot: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
            progress: {
              percent: 28,
              bytesDownloaded: 1179648,
              bytesTotal: 4194304,
              currentFile: "photoreal-pack.zip",
              currentStep: "Downloading official pack",
            },
            capabilities: { canPause: true, canResume: false, canCancel: true },
            updatedAt: "2026-08-01T20:47:00Z",
          },
        ],
      });

      await page.route("**/api/setup/install-jobs/job-photoreal-cancel/cancel", async (route) => {
        state.jobs = [
          {
            id: "job-photoreal-cancel",
            componentId: PACK.id,
            componentName: PACK.name,
            state: "cancelled",
            phase: "cancelled",
            providerId: "official-github",
            destinationRoot: "C:\\AdeptFilmWorks\\Installs\\Photoreal",
            message: "Install cancelled safely.",
            capabilities: { canCancel: false, canRetry: true, canRepair: false },
            updatedAt: "2026-08-01T20:48:00Z",
          },
        ];
        await fulfillJson(route, { job: state.jobs[0] });
      });

      await openSetup(page, project.id);
      await expect(page.getByTestId(`install-progress-${PACK.id}`)).toBeVisible();
      await page.getByRole("button", { name: "Cancel" }).click();
      await expect(page.getByTestId(`install-progress-${PACK.id}`)).toHaveAttribute("data-state", "cancelled");
      await expect(page.getByText("Install cancelled safely.")).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("comfy extension restart guidance and node-ready repair path", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    const project = await createTempProject(request, `Comfy Ext ${Date.now()}`);
    const comfyId = "comfyui_hunyuan_nodes";
    try {
      const state = {
        jobs: [
          {
            id: "job-comfy-ext",
            componentId: comfyId,
            componentName: "Hunyuan ComfyUI Extension",
            state: "configuring",
            phase: "restart_required",
            kind: "comfy_extension",
            message: "Installation complete. ComfyUI must restart before the new nodes become available.",
            raw: { awaitingRestart: true, nodesReady: false },
            recoveryActions: [
              { action: "restart_comfyui", label: "Restart ComfyUI", description: "Restart and probe" },
              { action: "restart_later", label: "Restart Later", description: "Wait" },
            ],
            capabilities: { canRepair: true },
            updatedAt: "2026-08-01T20:45:00Z",
          },
        ] as Record<string, unknown>[],
      };

      await page.route("**/api/setup/status", async (route) => {
        await fulfillJson(route, {
          overall_status: "additional_setup_required",
          counts: { ready: 0, not_installed: 1, needs_attention: 1 },
          components: [
            {
              id: comfyId,
              name: "Hunyuan ComfyUI Extension",
              description: "ComfyUI custom nodes",
              required: false,
              status: "error",
              installer: "comfy_extension",
              verifier: "comfy_extension_nodes",
              source_available: true,
              source_valid: true,
            },
          ],
        });
      });
      await page.route("**/api/setup/install-jobs**", async (route) => {
        const url = new URL(route.request().url());
        if (route.request().method() === "GET" && !url.pathname.endsWith("/events")) {
          await fulfillJson(route, { jobs: state.jobs });
          return;
        }
        await route.fallback();
      });
      await page.route("**/api/setup/install-jobs/events**", async (route) => {
        await route.abort();
      });
      await page.route("**/api/setup/install-jobs/job-comfy-ext/repair", async (route) => {
        const body = route.request().postDataJSON() as { action?: string };
        if (body?.action === "restart_comfyui" || body?.action === "reverify") {
          state.jobs = [
            {
              id: "job-comfy-ext",
              componentId: comfyId,
              componentName: "Hunyuan ComfyUI Extension",
              state: "ready",
              phase: "completed",
              kind: "comfy_extension",
              message: "6 of 6 nodes detected. Capability ready.",
              progress: { percent: 100 },
              raw: { nodesReady: true, awaitingRestart: false },
              updatedAt: "2026-08-01T20:46:00Z",
            },
          ];
        }
        await fulfillJson(route, { job: state.jobs[0] });
      });
      await page.route("**/api/downloads**", async (route) => {
        await fulfillJson(route, { operations: [] });
      });
      await page.route("**/api/setup/operations**", async (route) => {
        await fulfillJson(route, { operations: [] });
      });

      await openSetup(page, project.id);
      await expect(page.getByTestId(`install-progress-${comfyId}`)).toBeVisible();
      await expect(page.getByTestId("install-restart-comfyui")).toBeVisible();
      await page.getByTestId("install-restart-comfyui").click();
      await expect(page.getByTestId(`install-progress-${comfyId}`)).toHaveAttribute("data-state", "ready");
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("validates and saves a source from the add source workflow", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForStack(request);
    try {
      await sourceManagerMocks(page);
      await page.goto("/source-manager");
      await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
      await page.goto("/source-manager?componentId=pack_essential_photoreal#required-components");
      await expect(page.getByTestId("required-components-panel")).toBeVisible();

      await page.getByRole("button", { name: "Add Source" }).click();
      await expect(page.getByTestId("add-source-workflow")).toBeVisible();
      await page.getByTestId("source-url-input").fill("https://github.com/AdeptFilmWorks/photoreal-pack/releases/tag/v1.0.0");
      await page.getByTestId("source-revision-input").fill("v1.0.0");
      await page.getByTestId("verify-source-button").click();
      await expect(page.getByTestId("source-verification-summary")).toBeVisible();
      await page.getByTestId("save-source-override-button").click();
      await expect(page.getByTestId("add-source-workflow")).toHaveCount(0);
      observer.assertHealthyBrowser();
    } finally {
      observer.flush();
    }
  });
});
