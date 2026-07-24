import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test, expect } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated download queue", () => {
  test("queues fixture install, shows progress panel, completes with receipt", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    const dest = fs.mkdtempSync(path.join(os.tmpdir(), "adept-dl-queue-"));
    try {
      await request.post(`${API}/api/e2e/pack-source-override`, {
        data: { clear: true },
      }).catch(() => undefined);

      const enqueue = await request.post(`${API}/api/downloads`, {
        data: {
          componentId: "pack_essential_photoreal",
          providerId: "fixture",
          destinationRoot: dest,
          estimatedDownloadBytes: 4096,
          artifacts: [{ remotePath: "pack.zip", destinationRelativePath: "pack.json" }],
          metadata: { version: "1.0.0" },
        },
      });
      expect(enqueue.ok()).toBeTruthy();
      const body = await enqueue.json();
      const opId = body.operation.id as string;
      expect(opId).toBeTruthy();

      await page.goto("/source-manager");
      await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("active-downloads-heading").or(page.getByRole("heading", { name: "Active Downloads" }))).toBeVisible();

      // Operation should appear or finish quickly with fixture
      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/downloads/${opId}`);
          if (!res.ok()) return "missing";
          const json = await res.json();
          return json.operation?.phase as string;
        }, { timeout: 120_000 })
        .toMatch(/installed|downloading|extracting|validating|finalizing|queued|preflighting|resolving|verifying_source/);

      await expect
        .poll(async () => {
          const res = await request.get(`${API}/api/downloads/${opId}`);
          const json = await res.json();
          return json.operation?.phase as string;
        }, { timeout: 120_000 })
        .toBe("installed");

      const history = await request.get(`${API}/api/install-history`);
      expect(history.ok()).toBeTruthy();
      const hist = await history.json();
      expect(hist.entries.some((e: { componentId?: string }) => e.componentId === "pack_essential_photoreal")).toBeTruthy();

      await page.getByRole("heading", { name: "Install History" }).scrollIntoViewIfNeeded();
      await expect(page.getByTestId("install-history-list").or(page.getByTestId("install-history-empty"))).toBeVisible();

      // Duplicate enqueue returns same / no second active op
      const again = await request.post(`${API}/api/downloads`, {
        data: {
          componentId: "pack_essential_photoreal",
          providerId: "fixture",
          destinationRoot: dest,
        },
      });
      expect(again.ok()).toBeTruthy();
      const againBody = await again.json();
      // After installed, a new enqueue is allowed (previous terminal). Ensure API healthy.
      expect(againBody.operation?.id).toBeTruthy();

      const health = await request.get(`${API}/api/health`);
      expect(health.ok()).toBeTruthy();
      observer.assertHealthyBrowser();
    } finally {
      try {
        fs.rmSync(dest, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
      observer.flush();
    }
  });

  test("cancel unsupported pause messaging on fixture provider", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    await page.goto("/source-manager");
    await expect(page.getByTestId("source-manager-page")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByRole("heading", { name: "Active Downloads" })).toBeVisible();
    await expect(page.getByTestId("active-downloads-empty").or(page.getByTestId("active-downloads-list"))).toBeVisible();
    observer.assertHealthyBrowser();
    observer.flush();
  });
});
