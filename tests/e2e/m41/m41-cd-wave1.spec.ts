import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

/**
 * M41 Wave 1 UI / persistence coverage.
 * Full IDs in titles: M41-CD-04, M41-CD-08, M41-CD-11, M41-CD-12.
 */
test.describe("@m41 @codirector wave1", () => {
  test("M41-CD-04 Project context persists across navigation", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-04 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-runtime-chip")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);

      await page.goto("/");
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-no-project-banner")).toHaveCount(0);
      const chip = page.getByTestId("codirector-runtime-chip");
      await expect(chip).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-08 Refresh restores the active session", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-08 ${Date.now()}`);
    try {
      const save = await request.post(`${API}/api/codirector/conversations/${project.id}`, {
        data: {
          messages: [
            { role: "user", content: "M41-CD-08 persist me", created_at: new Date().toISOString() },
            { role: "assistant", content: "restored", created_at: new Date().toISOString() },
          ],
          model: "mock-model",
          provider_id: "mock",
        },
      });
      expect(save.ok()).toBeTruthy();

      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByText("M41-CD-08 persist me")).toBeVisible({ timeout: 30_000 });

      await page.reload();
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByText("M41-CD-08 persist me")).toBeVisible({ timeout: 30_000 });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-11 Project context does not leak across projects (UI)", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const a = await createTempProject(request, `M41-CD-11-A ${Date.now()}`);
    const b = await createTempProject(request, `M41-CD-11-B ${Date.now()}`);
    try {
      await request.post(`${API}/api/codirector/conversations/${a.id}`, {
        data: {
          messages: [
            { role: "user", content: "secret-from-project-a-only", created_at: new Date().toISOString() },
            { role: "assistant", content: "ok", created_at: new Date().toISOString() },
          ],
          model: "mock-model",
          provider_id: "mock",
        },
      });

      await page.goto(`/co-director?projectId=${encodeURIComponent(a.id)}`);
      await expect(page.getByText("secret-from-project-a-only")).toBeVisible({ timeout: 30_000 });

      await page.goto(`/co-director?projectId=${encodeURIComponent(b.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByText("secret-from-project-a-only")).toHaveCount(0);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, a.id);
      await deleteProject(request, b.id);
      observer.flush();
    }
  });

  test("M41-CD-12 Beta restart restores valid session state (no silent bind)", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-12 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });

      // Simulate restart without route project: must NOT silently restore production permissions.
      await page.goto("/co-director");
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-no-project-banner")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("codirector-select-project")).toBeVisible();
      // Resume is suggestion-only and must be an explicit click — presence is OK.
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-03 / M41-CD-05 No-project banner and limited mode", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await page.goto("/co-director");
    await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("codirector-no-project-banner")).toBeVisible();
    await expect(page.getByTestId("codirector-runtime-chip")).toBeVisible();
    const state = await page.getByTestId("codirector-shell").getAttribute("data-runtime-state");
    expect(state).toBeTruthy();
    observer.assertHealthyBrowser();
    observer.flush();
  });
});
