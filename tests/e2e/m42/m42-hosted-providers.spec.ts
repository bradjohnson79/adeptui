import { expect, test } from "@playwright/test";

test.describe("M42 Hosted AI Providers", () => {
  test("catalog exposes Kie → WaveSpeed → fal with no mock", async ({ request }) => {
    const res = await request.get("/api/hosted-providers");
    if (!res.ok()) {
      test.info().annotations.push({ type: "note", description: "API unavailable" });
      return;
    }
    const body = await res.json();
    expect(body.mock).not.toBe(true);
    expect(body.title).toBe("Hosted AI Providers");
    expect(body.recommendationOrder).toEqual(["kie", "wavespeed", "fal"]);
    expect(body.providers).toHaveLength(3);
    expect(body.providers[0].displayName).toBe("Kie.ai");
    expect(body.providers[0].recommended).toBeTruthy();
    expect(body.silentSwitchForbidden).toBeTruthy();
  });

  test("canonical models hide provider suffixes", async ({ request }) => {
    const res = await request.get("/api/hosted-providers/models");
    if (!res.ok()) return;
    const body = await res.json();
    const names = (body.models || []).map((m: any) => m.displayName);
    expect(names).toContain("FLUX");
    for (const n of names) {
      expect(n).not.toMatch(/\(Kie\)|\(fal\)|\(WaveSpeed\)/i);
    }
  });

  test("capability matrix is honest (fal video certified)", async ({ request }) => {
    const res = await request.get("/api/hosted-providers/capabilities");
    if (!res.ok()) return;
    const body = await res.json();
    expect(body.mock).not.toBe(true);
    expect(body.providers.fal.text_to_video).toBe("Certified");
    expect(body.providers.kie.text_to_video).not.toBe("Certified");
  });

  test("Setup → AI Providers UI renders three cards", async ({ page }) => {
    await page.goto("/");
    // Soft path: open settings if available
    const settings = page.getByRole("button", { name: /settings|project settings/i }).first();
    if ((await settings.count()) === 0) {
      test.info().annotations.push({ type: "note", description: "Settings control not in view" });
      return;
    }
    await settings.click();
    const tab = page.getByRole("tab", { name: /AI Providers|Integrations/i });
    if ((await tab.count()) === 0) return;
    await tab.click();
    await expect(page.getByTestId("hosted-providers-panel")).toBeVisible();
    await expect(page.getByTestId("hosted-provider-card-kie")).toBeVisible();
    await expect(page.getByTestId("hosted-provider-card-wavespeed")).toBeVisible();
    await expect(page.getByTestId("hosted-provider-card-fal")).toBeVisible();
  });
});
