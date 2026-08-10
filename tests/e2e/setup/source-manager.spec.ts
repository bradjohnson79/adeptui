import { test, expect } from "@playwright/test";
import { API, resetLiveBetaTestSurface, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const BETA_TARGET = process.env.ADEPT_BETA_TARGET === "1";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});
test.afterEach(async ({ page, request }) => {
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical @isolated source manager", () => {
  test("Source Manager route opens with provider cards", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();

    if (!BETA_TARGET) {
      await request.post(`${API}/api/e2e/cli-mock`, {
        data: {
          github: {
            status: "Ready",
            cli_detected: true,
            executable_path: "C:\\\\mock\\\\gh.exe",
            executable_name: "gh",
            version: "2.40.0",
            authenticated: true,
            account_name: "e2e-user",
            token_available: true,
            message: "GitHub CLI is ready and authenticated.",
          },
          huggingface: {
            status: "Installed but not authenticated",
            cli_detected: true,
            executable_path: "C:\\\\mock\\\\hf.exe",
            executable_name: "hf",
            version: "0.20.0",
            authenticated: false,
            account_name: null,
            token_available: false,
            message: "The CLI is installed, but this source may require you to sign in.",
          },
        },
      });
    }

    try {
      const overview = await request.get(`${API}/api/source-manager/overview`);
      expect(overview.ok()).toBeTruthy();
      const body = await overview.json();
      expect(body.schemaVersion).toBeGreaterThanOrEqual(3);
      expect(Array.isArray(body.providers)).toBeTruthy();
      expect(body.providers.some((p: { id: string }) => p.id === "github_cli")).toBeTruthy();

      await page.goto("/source-manager");
      await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByRole("heading", { name: "Source Manager" })).toBeVisible();
      await expect(page.getByTestId("source-manager-providers")).toBeVisible();
      await expect(page.getByTestId("source-provider-github_cli")).toBeVisible();
      await expect(page.getByTestId("source-provider-huggingface_cli")).toBeVisible();
      await expect(page.getByTestId("source-provider-direct_http")).toBeVisible();
      await expect(page.getByTestId("download-source-github")).toBeVisible();
      await expect(page.getByTestId("download-source-huggingface")).toBeVisible();
      await expect(page.getByTestId("source-manager-deferred")).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      if (!BETA_TARGET) {
        await request.post(`${API}/api/e2e/cli-mock`, { data: { clear: true } });
      }
      observer.flush();
    }
  });
});
