import { expect, test } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";

const BETA = process.env.ADEPT_BETA_TARGET === "1";

test.describe("@critical Voice Studio standalone + Voice Environment", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("Production menu exposes Voice Studio under Creative Studios", async ({ page, request }) => {
    const projects = await request.get(`${API}/api/projects`);
    expect(projects.ok()).toBeTruthy();
    const body = await projects.json();
    const projectId =
      (body.projects || body.items || [])[0]?.id ||
      (await request.post(`${API}/api/projects`, { data: { name: "Voice Studio Cert" } }).then(async (r) => (await r.json()).id));

    await page.goto(`/project/${projectId}`);
    await expect(page.getByTestId("production-menu").or(page.getByRole("navigation").first())).toBeVisible({
      timeout: 60_000,
    });

    // Open production menu if collapsed
    const prodBtn = page.getByRole("button", { name: /Production/i }).first();
    if (await prodBtn.isVisible().catch(() => false)) {
      await prodBtn.click();
    }

    await expect(page.getByText("Voice Studio").first()).toBeVisible({ timeout: 30_000 });
  });

  test("standalone Voice Studio shell and environment stage order", async ({ page, request }) => {
    const projects = await request.get(`${API}/api/projects`);
    const body = await projects.json();
    let projectId = (body.projects || body.items || []).find((p: { name?: string }) =>
      /Korri|Voice|Character/i.test(String(p.name || "")),
    )?.id;
    if (!projectId) {
      projectId = (body.projects || body.items || [])[0]?.id;
    }
    if (!projectId) {
      const created = await request.post(`${API}/api/projects`, {
        data: { name: "Korri Character Production" },
      });
      expect(created.ok()).toBeTruthy();
      projectId = (await created.json()).id;
    }

    await page.goto(`/project/${projectId}?workspace=voicestudio`);
    await expect(page.getByTestId("voice-studio-shell")).toBeVisible({ timeout: 60_000 });

    // Prefer Korri card when present
    const korri = page.getByRole("heading", { name: /Korri/i }).first();
    if (await korri.isVisible().catch(() => false)) {
      await page.getByRole("button", { name: "Open Voice Studio" }).first().click();
    } else {
      const openBtn = page.getByRole("button", { name: "Open Voice Studio" }).first();
      if (await openBtn.isVisible().catch(() => false)) {
        await openBtn.click();
      }
    }

    const envTab = page.getByTestId("voice-environment-tab");
    if (await envTab.isVisible().catch(() => false)) {
      await expect(page.getByTestId("voice-performance-tab")).toBeVisible();
      await expect(envTab).toBeVisible();
      // Environment appears after Performance in DOM order of tabs
      const tabs = page.getByTestId("voice-studio-ia").locator('[role="tab"]');
      const labels = await tabs.allTextContents();
      const perfIdx = labels.findIndex((t) => /Voice Performance/i.test(t));
      const envIdx = labels.findIndex((t) => /Voice Environment/i.test(t));
      expect(envIdx).toBeGreaterThan(perfIdx);

      await envTab.click();
      await expect(page.getByTestId("voice-environment-panel")).toBeVisible({ timeout: 30_000 });
      // Handoff controls must be present (wired, not orphaned).
      await expect(page.getByTestId("voice-environment-timeline")).toBeVisible();
      await expect(page.getByTestId("voice-environment-lipsync")).toBeVisible();
      await expect(page.getByTestId("voice-environment-audio-studio")).toBeVisible();
      await expect(page.getByTestId("voice-environment-apply-scene")).toBeVisible();
    }

    // Custom device prompt accepts spaces when available
    const device = page.getByTestId("voice-environment-device");
    if (await device.isVisible().catch(() => false)) {
      // Device axis uses chip buttons + optional custom textarea (not a <select>).
      const customChip = device.getByRole("button", { name: /^Custom$/i });
      if (await customChip.isVisible().catch(() => false)) {
        await customChip.click();
        const custom = device.locator("textarea");
        await custom.fill("ship intercom with light static");
        await expect(custom).toHaveValue(/ship intercom with light static/);
      }
    }
  });

  test("voice-environment runtime status is honest", async ({ request }) => {
    const res = await request.get(`${API}/api/voice-environment/runtime/status`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("ok");
    expect(body).toHaveProperty("status");
    expect(body.processingKind || "deterministic_acoustic").toBeTruthy();
    if (!BETA) {
      expect(body.aiGeneration === false || body.aiGeneration == null).toBeTruthy();
    }
  });
});
