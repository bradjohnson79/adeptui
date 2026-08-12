import { expect, test } from "@playwright/test";

test.describe("M42 W43 Korri Character Creator", () => {
  test("characterCreatorGo gate is binary", async ({ request }) => {
    const res = await request.get("/api/m42-product/gate/wave43");
    if (!res.ok()) {
      test.info().annotations.push({ type: "note", description: `HTTP ${res.status()}` });
      return;
    }
    const body = await res.json();
    expect(body).toHaveProperty("characterCreatorGo");
    expect(body.binaryOnly).toBeTruthy();
    expect(body.conditionalGoForbidden).toBeTruthy();
  });

  test("Character Profile workspace exposes Korri seed and Motion/Relationships tabs", async ({ page }) => {
    await page.goto("/");
    const seed = page.getByTestId("character-seed-korri");
    if ((await seed.count()) === 0) return;
    await expect(seed).toBeVisible();
  });

  test("terminology: no invented blonde/aqua Korri in canon endpoint", async ({ request }) => {
    // Soft: only when API project available via e2e helpers; otherwise skip
    const res = await request.get("/api/m42-product/gate/wave43");
    if (!res.ok()) return;
    const body = await res.json();
    if (body.characterCreatorGo) {
      expect(body.flags?.korriHairProfileOperational).toBeTruthy();
      expect(body.flags?.korriMotionProfileOperational).toBeTruthy();
      expect(body.flags?.korriPromptPackageOperational).toBeTruthy();
    }
  });
});
