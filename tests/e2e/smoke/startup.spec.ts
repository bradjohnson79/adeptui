import { test, expect } from "@playwright/test";
import { waitForAppReady, countApiCalls, API } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

test.describe("@critical @isolated startup", () => {
  test("app shell renders with healthy API and no render-phase warnings", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);

    await page.goto("/");
    await expect(page.locator("body")).toBeVisible();
    await expect(page.getByRole("button", { name: "Create New Project" })).toBeVisible({
      timeout: 30_000,
    });

    const health = await request.get(`${API}/api/health`);
    expect(health.ok()).toBeTruthy();

    // Poll flood check: health should not be requested dozens of times in a short window.
    const calls = await countApiCalls(page, "/api/health", 4000);
    expect(calls).toBeLessThan(8);

    await observer.snapshot("startup");
    observer.assertHealthyBrowser();
    observer.flush();
  });
});
