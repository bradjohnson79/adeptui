import { test, expect } from "@playwright/test";

/**
 * M41 4.1A — Video Runtime diagnostics + gate surfaces.
 * Does not run live Comfy generation.
 */

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8756";
const WEB = process.env.STUDIO_WEB_BASE || "http://127.0.0.1:5173";

test.describe("M41 4.1A Video Runtime", () => {
  test("diagnostics API returns structured payload", async ({ request }) => {
    const res = await request.get(`${API}/api/video-runtime/diagnostics`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("comfyui");
    expect(body).toHaveProperty("modelInventory");
    expect(body).toHaveProperty("queue");
    expect(body).toHaveProperty("health");
  });

  test("compatibility catalog includes WAN and deferred upscale", async ({ request }) => {
    const res = await request.get(`${API}/api/video-runtime/compatibility`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const keys = (body.entries || []).map((e: { workflowKey: string }) => e.workflowKey);
    expect(keys).toContain("wan.first_last_frame");
    expect(keys).toContain("video.upscale");
  });

  test("wave6 gate endpoint responds", async ({ request }) => {
    const res = await request.get(`${API}/api/video-runtime/gate`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body).toHaveProperty("wave6MediaExecutionUnlocked");
    expect(body).toHaveProperty("message");
  });

  test("diagnostics page renders", async ({ page }) => {
    await page.goto(`${WEB}/diagnostics/video-runtime`);
    await expect(page.getByTestId("video-runtime-diagnostics")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Video Runtime" })).toBeVisible();
  });
});
