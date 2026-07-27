import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const artifactDir = path.join("artifacts", "functional-audit");

export default defineConfig({
  // Root suite. Covers every suite under tests/e2e, including tests/e2e/m30a (fal.ai BYOK).
  // The M3.0a live-render checks inside that suite additionally require ADEPT_M30A_FAL_LIVE=1
  // and a real key, and skip themselves otherwise; the env passes through to the webServer
  // below. The workspace specs under studio-web/e2e run as a second project (see `projects`).
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
  webServer: {
    command: "node scripts/e2e-start.mjs",
    url: `${baseURL}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
