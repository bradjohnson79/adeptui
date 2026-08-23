import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const betaBaseURL = "http://127.0.0.1:5173";
const betaApiBase = "http://127.0.0.1:8758";
const betaApiPort = "8758";

/** ADEPT_BETA_TARGET=1 or explicit 5173/8758 wiring → certify against live Vite + Studio API. Retired :8760 is not a creator UI. */
const betaTarget =
  process.env.ADEPT_BETA_TARGET === "1" ||
  process.env.ADEPT_BETA_TARGET === "true" ||
  process.env.ADEPT_BETA_TARGET === "TRUE" ||
  process.env.PLAYWRIGHT_BASE_URL === betaBaseURL ||
  process.env.STUDIO_API_BASE === betaApiBase ||
  process.env.STUDIO_API_PORT === betaApiPort;

const baseURL =
  process.env.PLAYWRIGHT_BASE_URL ||
  (betaTarget ? betaBaseURL : "http://127.0.0.1:5173");

if (betaTarget) {
  process.env.PLAYWRIGHT_BASE_URL = process.env.PLAYWRIGHT_BASE_URL || betaBaseURL;
  process.env.STUDIO_API_BASE = process.env.STUDIO_API_BASE || betaApiBase;
  process.env.STUDIO_API_PORT = process.env.STUDIO_API_PORT || betaApiPort;
  process.env.ADEPT_BETA_TARGET = "1";
}

const artifactDir = path.join("artifacts", "functional-audit");

export default defineConfig({
  // Root suite. Covers every suite under tests/e2e, including tests/e2e/m30a (fal.ai BYOK).
  // The M3.0a live-render checks inside that suite additionally require ADEPT_M30A_FAL_LIVE=1
  // and a real key, and skip themselves otherwise; the env passes through to the webServer
  // below. The workspace specs under studio-web/e2e run as a second project (see `projects`).
  //
  // Certification smoke against live Beta: `npm run test:e2e:beta` (ADEPT_BETA_TARGET=1).
  // Isolated fixture harness remains the default for pack/e2e-route specs.
  testDir: path.join("tests", "e2e"),
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 1,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    ["json", { outputFile: path.join(artifactDir, "playwright-results.json") }],
  ],
  outputDir: path.join(artifactDir, "test-output"),
  use: {
    extraHTTPHeaders:
      process.env.ADEPT_ALLOW_KORRI_MUTATION === "1"
        ? {}
        : { "X-Adept-Deny-Owner-Writes": "1" },
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
    ...devices["Desktop Chrome"],
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // studio-web/e2e sits outside the root testDir, so a default run used to skip the
      // M2.13 and M2.14 workspace smokes entirely. Both are flag-gated and self-skip when
      // their STUDIO_FEATURE_* flag is off, so including them here is safe by default and
      // becomes real coverage as soon as the flags are enabled in the E2E env.
      name: "workspaces",
      testDir: path.join("studio-web", "e2e"),
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  // Against live Beta we must NOT spawn scripts/e2e-start.mjs (different ports + STUDIO_E2E).
  ...(betaTarget
    ? {}
    : {
        webServer: {
          command: "node scripts/e2e-start.mjs",
          url: `${baseURL}/`,
          reuseExistingServer: !process.env.CI,
          timeout: 180_000,
          stdout: "pipe" as const,
          stderr: "pipe" as const,
        },
      }),
});
