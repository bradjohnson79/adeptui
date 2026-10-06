import { test, expect } from "@playwright/test";
import {
  API,
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

test.describe("@critical setup wizard adept runtime service", () => {
  test("Setup Wizard configures Adept Runtime and does not own lifecycle", async ({ page, request }) => {
    const project = await createTempProject(request, `Runtime Service Setup ${Date.now()}`);
    const seen: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/runtime-manager/")) {
        seen.push(`${req.method()} ${new URL(req.url()).pathname}`);
      }
    });
    try {
      await openSetup(page, project.id);
      const section = page.getByTestId("adept-background-services");
      await expect(section).toBeVisible();
      await expect(page.getByTestId("adept-runtime-managed-state")).toHaveText("Adept Runtime — Managed Automatically");
      await expect(page.getByTestId("validate-runtime-configuration")).toBeVisible();
      await expect(page.getByTestId("enable-recommended-background-services")).toBeVisible();
      await expect(page.getByTestId("repair-background-services")).toBeVisible();
      await expect(page.getByTestId("start-background-services")).toHaveCount(0);
      await expect(page.getByTestId("stop-background-services")).toHaveCount(0);
      await expect(page.getByTestId("restart-studio-api")).toHaveCount(0);
      await expect(page.getByTestId("restart-comfy")).toHaveCount(0);

      const startWithWindows = page.getByLabel("Start automatically when Windows starts");
      if (await startWithWindows.count()) {
        await expect(startWithWindows).toBeVisible();
      }

      const enable = page.getByTestId("enable-recommended-background-services");
      if (await enable.isEnabled()) {
        await enable.click();
        await expect.poll(() => seen.some((row) => row.includes("enable-recommended"))).toBeTruthy();
        expect(seen.some((row) => row === "POST /api/runtime-manager/start")).toBeFalsy();
        expect(seen.some((row) => row === "POST /api/runtime-manager/restart-api")).toBeFalsy();
        expect(seen.some((row) => row === "POST /api/runtime-manager/restart-comfy")).toBeFalsy();
      }
      const taskState = page.getByTestId("background-services-task-state");
      await expect(taskState).toBeVisible();
      await expect(taskState).toHaveText(
        /Starts when you sign in\.|Not set to start when you sign in\.|Windows needs permission once/,
      );
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Validate Runtime Configuration checks paths only", async ({ page, request }) => {
    const probe = await request.get(`${API}/api/runtime-manager/validate-config`);
    if (!probe.ok()) {
      test.info().annotations.push({
        type: "note",
        description: `Live Studio API has not loaded GET /validate-config (${probe.status()}). Recycle API only; do not restart Comfy.`,
      });
      test.skip(true, "Stale Studio API process — validate-config route not loaded.");
    }
    const project = await createTempProject(request, `Runtime Config Validate ${Date.now()}`);
    const seen: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/runtime-manager/")) {
        seen.push(`${req.method()} ${new URL(req.url()).pathname}`);
      }
    });
    try {
      await openSetup(page, project.id);
      await page.getByTestId("validate-runtime-configuration").click();
      await expect.poll(() => seen.some((row) => row === "GET /api/runtime-manager/validate-config")).toBeTruthy();
      expect(seen.some((row) => row === "POST /api/runtime-manager/start")).toBeFalsy();
      expect(seen.some((row) => row === "POST /api/runtime-manager/stop")).toBeFalsy();
      expect(seen.some((row) => row === "POST /api/runtime-manager/restart-api")).toBeFalsy();
      expect(seen.some((row) => row === "POST /api/runtime-manager/restart-comfy")).toBeFalsy();
      await expect(page.getByTestId("runtime-config-validation-result")).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
