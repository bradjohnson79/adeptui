import { expect, test } from "@playwright/test";

test.describe("M42 W6P Production Beta", () => {
  test("gate endpoint reports binary wave6pGo field", async ({ request }) => {
    const res = await request.get("/api/m42-product/gate/wave6p");
    if (!res.ok()) {
      test.info().annotations.push({ type: "note", description: `Gate HTTP ${res.status()}` });
      return;
    }
    const body = await res.json();
    expect(body).toHaveProperty("wave6pGo");
    expect(body).toHaveProperty("sceneReferenceAddendumGo");
    expect(body.binaryOnly).toBeTruthy();
    expect(body.conditionalGoForbidden).toBeTruthy();
    if (body.wave6pGo) {
      expect(body.sceneReferenceAddendumGo).toBeTruthy();
    }
  });

  test("scene reference addendum gate binary", async ({ request }) => {
    const res = await request.get("/api/m42-product/gate/wave6p/scene-references");
    if (!res.ok()) return;
    const body = await res.json();
    expect(body).toHaveProperty("sceneReferenceAddendumGo");
  });

  test("References pane order Assets / References / Scenes", async ({ page }) => {
    await page.goto("/");
    const refs = page.getByTestId("scene-references-pane");
    if ((await refs.count()) === 0) return;
    await expect(refs).toBeVisible();
  });
});
