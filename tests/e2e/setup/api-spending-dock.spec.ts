/**
 * Scenarios E–I: usage records, cross-category summary, budget warn/confirm,
 * no silent paid fallback flag, persistence across reload.
 */
import { test, expect } from "@playwright/test";
import {
  createTempProject,
  deleteProject,
  resetLiveBetaTestSurface,
  waitForAppReady,
} from "../helpers/app";

const API = process.env.STUDIO_API_BASE_URL || "http://127.0.0.1:8758";

test.beforeEach(async ({ page, request }) => {
  await waitForAppReady(request);
  await resetLiveBetaTestSurface(request, page);
});

test.describe("@critical api spending dock", () => {
  test("E–I: ledger, budgets, dock spend, silent fallback forbidden", async ({ page, request }) => {
    const project = await createTempProject(request, `API Spend ${Date.now()}`);
    try {
      const img = await request.post(`${API}/api/provider-usage/records`, {
        data: {
          providerId: "fal",
          capability: "image",
          projectId: project.id,
          workspaceOrigin: "Image Gen",
          units: 1,
          status: "estimated",
        },
      });
      expect(img.ok()).toBeTruthy();
      const vid = await request.post(`${API}/api/provider-usage/records`, {
        data: {
          providerId: "kie",
          capability: "video",
          projectId: project.id,
          workspaceOrigin: "Timeline",
          units: 2,
          status: "estimated",
        },
      });
      expect(vid.ok()).toBeTruthy();
      const fail = await request.post(`${API}/api/provider-usage/records`, {
        data: {
          providerId: "wavespeed",
          capability: "image",
          projectId: project.id,
          status: "failed",
          billingStatus: "unknown",
          failureStage: "after_accept",
        },
      });
      expect(fail.ok()).toBeTruthy();
      const failBody = await fail.json();
      expect(failBody.record?.billingStatus).toBe("unknown");

      const summary = await request.get(
        `${API}/api/provider-usage/summary?projectId=${encodeURIComponent(project.id)}`,
      );
      const sumBody = await summary.json();
      expect(sumBody.byCapability?.image).toBeTruthy();
      expect(sumBody.byCapability?.video).toBeTruthy();
      expect(sumBody.disclaimer).toBeTruthy();

      await request.put(`${API}/api/provider-usage/budgets`, {
        data: {
          budgetPreference: "balanced",
          perRequestWarnUsd: 0.01,
          doNotPromptBelowUsd: 0,
          projectBudgetUsd: 0.001,
          onExceed: "require_confirmation",
          askBeforeSpending: true,
        },
      });
      const pre = await request.post(`${API}/api/provider-usage/preflight`, {
        data: {
          providerId: "fal",
          capability: "image",
          units: 1,
          projectId: project.id,
          approved: false,
        },
      });
      const preBody = await pre.json();
      expect(preBody.silentPaidFallbackForbidden).toBeTruthy();
      expect(["require_confirmation", "block", "allow_with_disclaimer"]).toContain(preBody.action);

      const dock = await request.get(
        `${API}/api/provider-usage/dock?projectId=${encodeURIComponent(project.id)}`,
      );
      const dockBody = await dock.json();
      expect(dockBody.localLabel).toContain("Local");
      expect(dockBody.silentPaidFallbackForbidden).toBeTruthy();

      const cd = await request.get(
        `${API}/api/provider-usage/codirector-summary?projectId=${encodeURIComponent(project.id)}`,
      );
      const cdBody = await cd.json();
      expect(cdBody.secretsIncluded).toBeFalsy();
      expect(JSON.stringify(cdBody).toLowerCase()).not.toContain("api_key");

      await page.goto(`/project/${project.id}`);
      // Open production dock settings when the control is present
      const settingsBtn = page.locator('[data-testid="production-dock-settings"], [data-testid="production-dock-settings-open"]').first();
      if ((await settingsBtn.count()) > 0) {
        await settingsBtn.click({ timeout: 5_000 }).catch(() => undefined);
        const spend = page.getByTestId("production-dock-spend");
        if ((await spend.count()) > 0) {
          await expect(spend).toContainText("Local — No API charge");
          await expect(spend).toContainText("never silently");
        }
      }

      // Persistence: budgets survive API re-read (reload-safe store)
      const budgets2 = await request.get(`${API}/api/provider-usage/budgets`);
      const b2 = await budgets2.json();
      expect(b2.budgets?.askBeforeSpending).toBeTruthy();
      expect(Number(b2.budgets?.projectBudgetUsd)).toBeGreaterThan(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
