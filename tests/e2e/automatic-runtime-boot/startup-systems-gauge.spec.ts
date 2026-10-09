import { test, expect } from "@playwright/test";

/**
 * Startup Systems Gauge — modal UX certification via mocked runtime statuses.
 * Certifies J5-7 (appearance, auto-close, failure) WITHOUT touching real services.
 * The real cold-start is certified separately by the primary agent's live journey.
 */

const ALL_ONLINE = {
  comfyui: { status: "running", ownership: "owned" },
  studioApi: { status: "running", ownership: "owned" },
  ollama: { status: "running", ownership: "external" },
  tunnel: { status: "stopped", ownership: "external" },
  gpu: { detected: true },
  routeA: { status: "stopped", ownership: "external", port: 8192, adeptOwnedReady: false },
  gpuAdmission: { dualResident: false, comfyuiAllowed: true, routeAAllowed: true },
  preferences: { comfyuiBackgroundManagerEnabled: true, localhostBackgroundManagerEnabled: true, startWithWindows: true, remoteAccessEnabled: false },
  adeptRuntime: {
    configured: true, taskRegistered: true, startWithWindows: true, serviceState: "running",
    comfyState: "ready", worker: "qwen_ready", falConnected: true, creatorMessage: "ready",
    comfyPid: 19500, owned: true, managerPid: 71956, studioApiPid: 29940, studioApiOwned: true,
    studioApiHealth: "healthy", studioApiChild: { pid: 29940, owned: true, health: "healthy", port: 8758 },
    comfyChild: { pid: 19500, owned: true, health: "ready", port: 8188 },
  },
};

const STARTING = JSON.parse(JSON.stringify(ALL_ONLINE)) as typeof ALL_ONLINE;
STARTING.adeptRuntime!.serviceState = "starting";
STARTING.adeptRuntime!.comfyState = "starting";
STARTING.adeptRuntime!.managerPid = 71956;
STARTING.comfyui.status = "starting";
STARTING.adeptRuntime!.studioApiHealth = "healthy";

const COMFY_FAILED = JSON.parse(JSON.stringify(ALL_ONLINE)) as typeof ALL_ONLINE;
COMFY_FAILED.comfyui.status = "error";
COMFY_FAILED.adeptRuntime!.comfyState = "offline";

const GO_CERT = {
  verdict: "GO",
  headline: "ADEPT UI READY — GO",
  progressPct: 100,
  checks: [
    { id: "studio_api_health", system: "Studio API", check: "healthz", result: "PASS", detail: "HTTP 200", required: true, durationMs: 8 },
    { id: "timeline", system: "Timeline", check: "1.0 MP 16:9 reference contract", result: "PASS", detail: "1376x768", required: true, durationMs: 11 },
  ],
  failed: [],
  optional: [],
};

const NO_GO_CERT = {
  verdict: "NO-GO",
  headline: "ADEPT UI STARTUP — NO-GO",
  progressPct: 80,
  checks: [
    { id: "timeline", system: "Timeline", check: "1.0 MP 16:9 reference contract", result: "FAIL", detail: "1376x768 refused", required: true, durationMs: 14 },
  ],
  failed: [{ system: "Timeline", check: "1.0 MP 16:9 reference contract", detail: "1376x768 refused", result: "FAIL" }],
  optional: [],
};

const OPTIONAL_CERT = {
  ...GO_CERT,
  optional: [{ system: "Image Generator", check: "hosted catalog", detail: "No hosted image provider is configured." }],
};

async function mockBoot(page: import("@playwright/test").Page, body: unknown) {
  await page.route("**/api/boot/certification", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

async function gotoHome(page: import("@playwright/test").Page) {
  await page.goto("/?__startup_test=1", { waitUntil: "domcontentloaded" });
  // Shorten the failure timeout so the failure test doesn't wait 120s.
  await page.addInitScript(() => {
    (window as unknown as { __ADEPT_STARTUP_TIMEOUT_MS?: number }).__ADEPT_STARTUP_TIMEOUT_MS = 3000;
  });
}

test.describe("Startup Systems Gauge modal", () => {
  test("warm launch — all required online → modal skipped (no flash)", async ({ page }) => {
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) }));
    await page.route("**/api/setup/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ components: [], firstRunSetupComplete: true }) }));
    await mockBoot(page, GO_CERT);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("startup-systems-gauge")).toHaveCount(0);
  });

  test("cold launch — modal appears, shows STARTING, then ALL SYSTEMS ONLINE and auto-closes", async ({ page }) => {
    let phase = 0;
    await page.route("**/api/healthz", (r) => {
      // phase 0: down; phase >=1: up
      if (phase === 0) return r.fulfill({ status: 503, body: "down" });
      return r.fulfill({ status: 200, body: "ok" });
    });
    await page.route("**/api/setup/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ components: [], firstRunSetupComplete: true }) }));
    await page.route("**/api/runtime-manager/status", (r) => {
      if (phase < 2) return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STARTING) });
      return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) });
    });
    await mockBoot(page, GO_CERT);
    await page.addInitScript(() => {
      (window as unknown as { __ADEPT_STARTUP_TIMEOUT_MS?: number }).__ADEPT_STARTUP_TIMEOUT_MS = 60000;
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    // Modal appears (cold).
    await expect(page.getByTestId("startup-systems-gauge")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("startup-system-studio_api")).toBeVisible();
    await expect(page.getByTestId("startup-system-creator_engine")).toBeVisible();

    // Advance: Studio API comes up, Comfy still starting.
    phase = 1;
    await page.waitForTimeout(1500);
    await expect(page.getByTestId("startup-system-studio_api")).toContainText(/ONLINE|STARTING/);

    // Advance: all online.
    phase = 2;
    await expect(page.getByTestId("startup-gauge-message")).toHaveText(/ALL REQUIRED SYSTEMS ONLINE/, { timeout: 20_000 });
    // Auto-closes after the brief hold.
    await expect(page.getByTestId("startup-systems-gauge")).toBeHidden({ timeout: 10_000 });
  });

  test("failure — required system reports error → FAILED block with recovery controls (no fake ONLINE)", async ({ page }) => {
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(COMFY_FAILED) }));
    await mockBoot(page, GO_CERT);
    await page.addInitScript(() => {
      (window as unknown as { __ADEPT_STARTUP_TIMEOUT_MS?: number }).__ADEPT_STARTUP_TIMEOUT_MS = 3000;
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("startup-systems-gauge")).toBeVisible({ timeout: 10_000 });
    // Comfy reported error → FAILED block appears.
    await expect(page.getByTestId("startup-gauge-failed")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("startup-gauge-retry")).toBeVisible();
    await expect(page.getByTestId("startup-gauge-details")).toBeVisible();
    await expect(page.getByTestId("startup-gauge-exit")).toBeVisible();
    // No fake ONLINE: the Creator Engine row must NOT say ONLINE.
    const creator = page.getByTestId("startup-system-creator_engine");
    await expect(creator).not.toContainText(/ONLINE/);
    await page.screenshot({ path: "test-results/startup-gauge-failed.png", fullPage: true });
  });

  test("required certification failure stays on the boot manager", async ({ page }) => {
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) }));
    await mockBoot(page, NO_GO_CERT);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("startup-systems-gauge")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("boot-verdict")).toHaveText("ADEPT UI SETUP REQUIRED");
    await expect(page.getByTestId("boot-ready")).toHaveCount(0);
    await expect(page.getByTestId("startup-gauge-exit")).toHaveCount(0);
  });

  test("retry failed checks reaches GO without restarting healthy services", async ({ page }) => {
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) }));
    let startCalls = 0;
    await page.route("**/api/runtime-manager/start", async (r) => {
      startCalls += 1;
      await r.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
    await page.route("**/api/setup/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ components: [], firstRunSetupComplete: true }) }));
    await page.route("**/api/boot/certification**", (r) => {
      const body = r.request().method() === "POST" ? GO_CERT : NO_GO_CERT;
      return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("boot-verdict")).toHaveText("ADEPT UI SETUP REQUIRED", { timeout: 10_000 });
    await page.getByTestId("boot-retry").click();
    await expect(page.getByTestId("boot-ready")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("startup-systems-gauge")).toHaveCount(0);
    expect(startCalls).toBe(0);
  });

  test("a later passing certification clears the startup attention", async ({ page }) => {
    const opened = Date.now();
    let startCalls = 0;
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) }));
    await page.route("**/api/runtime-manager/start", async (r) => {
      startCalls += 1;
      await r.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });
    await page.route("**/api/setup/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ components: [], firstRunSetupComplete: true }) }));
    await page.route("**/api/boot/certification**", (r) => {
      const body = Date.now() - opened < 700 ? NO_GO_CERT : GO_CERT;
      return r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("boot-verdict")).toHaveText("ADEPT UI SETUP REQUIRED", { timeout: 10_000 });
    await expect(page.getByTestId("boot-ready")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("startup-systems-gauge")).toHaveCount(0);
    expect(startCalls).toBe(0);
  });

  test("optional provider unavailable still reaches GO", async ({ page }) => {
    await page.route("**/api/healthz", (r) => r.fulfill({ status: 200, body: "ok" }));
    await page.route("**/api/runtime-manager/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(ALL_ONLINE) }));
    await page.route("**/api/setup/status", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ components: [], firstRunSetupComplete: true }) }));
    await mockBoot(page, OPTIONAL_CERT);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("boot-ready")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("boot-optional")).toContainText("No hosted image provider is configured.");
    await expect(page.getByTestId("startup-systems-gauge")).toHaveCount(0);
  });
});
