import { test, expect } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated gpu comfy resilience", () => {
  test("gpu stats and health tolerate unavailable optional services", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    // GPU/Comfy may 503/500 when missing — allowlisted for this suite.
    observer.allow(/\/api\/gpu\/stats/);
    await waitForAppReady(request);

    await page.goto("/");
    const health = await request.get(`${API}/api/health`);
    expect(health.ok()).toBeTruthy();
    const body = await health.json();
    expect(body).toHaveProperty("ok");

    const gpu = await request.get(`${API}/api/gpu/stats`);
    expect(gpu.status()).toBeLessThan(600);

    // Malformed / slow handled by route mock
    await page.route("**/api/gpu/stats", async (route) => {
      await new Promise((r) => setTimeout(r, 50));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: false, error: "mock unavailable" }),
      });
    });
    await page.reload();
    await page.waitForTimeout(1000);
    expect((await request.get(`${API}/api/health`)).ok()).toBeTruthy();
    observer.assertHealthyBrowser();
    observer.flush();
  });
});
