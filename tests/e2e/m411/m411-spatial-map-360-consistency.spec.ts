import { expect, test } from "@playwright/test";
import { createTempProject, deleteProject, waitForAppReady, API } from "../helpers/app";

async function waitForSpatialStack(request: Parameters<typeof waitForAppReady>[0]) {
  // Prefer the full E2E harness readiness path. Fall back to beta-local health when
  // `/api/e2e/status` is intentionally disabled (STUDIO_E2E=0).
  try {
    await waitForAppReady(request);
    return;
  } catch {
    await expect
      .poll(
        async () => {
          try {
            const res = await request.get(`${API}/api/health`);
            return res.ok();
          } catch {
            return false;
          }
        },
        { timeout: 120_000 }
      )
      .toBeTruthy();
  }
}

test.describe("M4.11 Spatial Map 360 consistency", () => {
  test("creator flow covers limits, 360 plan, scene assignment, and image studio selection", async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000);
    await waitForSpatialStack(request);
    const project = await createTempProject(request, `M411 Spatial Consistency ${Date.now()}`);

    const sceneRes = await request.post(`${API}/api/projects/${project.id}/scenes`, {
      data: { name: "M411 Spatial Scene" },
    });
    expect(sceneRes.ok()).toBeTruthy();
    const sceneId = String((await sceneRes.json()).id);

    try {
      await page.goto(`/project/${project.id}?workspace=spatial`);
      await expect(page.getByTestId("spatial-map-studio")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("spatial-canvas")).toBeVisible({ timeout: 30_000 });

      const canvas = page.getByTestId("spatial-canvas");

      await page.getByTestId("spatial-add-character").click();
      for (const position of [
        { x: 120, y: 120 },
        { x: 250, y: 180 },
        { x: 420, y: 260 },
        { x: 620, y: 320 },
      ]) {
        await canvas.click({ position });
      }
      await expect(page.getByTestId("spatial-character-limit")).toContainText("4 / 4 characters");
      await expect(page.getByTestId("spatial-add-character")).toBeDisabled();

      await page.getByTestId("spatial-add-prop").click();
      for (const position of [
        { x: 160, y: 420 },
        { x: 320, y: 450 },
        { x: 520, y: 470 },
        { x: 720, y: 500 },
      ]) {
        await canvas.click({ position });
      }
      await expect(page.getByTestId("spatial-prop-limit")).toContainText("4 / 4 props");
      await expect(page.getByTestId("spatial-add-prop")).toBeDisabled();

      await page.getByTestId("spatial-add-camera").click();
      await canvas.click({ position: { x: 500, y: 90 } });
      await expect(page.getByText("1 / 8 cameras")).toBeVisible();

      await page.getByTestId("spatial-360-tab").click();
      await page.getByTestId("spatial-generate-360").click();
      await expect(page.locator(".spatial-propose")).toContainText("master environment", {
        ignoreCase: true,
      });
      await expect(page.locator(".spatial-propose")).toContainText("0°");

      await page.getByRole("button", { name: "Export", exact: true }).click();
      const assignSceneResponse = page.waitForResponse(
        (response) =>
          response.url().includes("/assign-scene") && response.request().method() === "POST"
      );
      await page.getByTestId("spatial-assign-scene").click();
      expect((await assignSceneResponse).ok()).toBeTruthy();

      await page.goto(`/project/${project.id}?workspace=imagegen`);
      await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({
        timeout: 30_000,
      });
      const select = page.getByTestId("image-spatial-reference-select");
      await expect(select).toBeVisible();
      await expect
        .poll(async () => {
          const options = await select.locator("option").evaluateAll((items) =>
            items.map((option) => ({
              value: (option as HTMLOptionElement).value,
              label: option.textContent || "",
            }))
          );
          return options.some(
            (option) => option.value && option.label.includes("4 chars") && option.label.includes("4 props")
          );
        })
        .toBe(true);
      const spatialOptions = await select.locator("option").evaluateAll((options) =>
        options.map((option) => ({
          value: (option as HTMLOptionElement).value,
          label: option.textContent || "",
        }))
      );
      const spatialMapOption = spatialOptions.find(
        (option) => option.value && option.label.includes("4 chars") && option.label.includes("4 props")
      );
      expect(spatialMapOption?.value).toBeTruthy();
      await select.selectOption(spatialMapOption!.value);
      const spatialSummary = page.getByTestId("image-spatial-reference");
      await expect(spatialSummary).toContainText("Characters:");
      await expect(spatialSummary).toContainText("Character 1");
      await expect(spatialSummary).toContainText("Props:");
      await expect(spatialSummary).toContainText("Prop 1");
      await expect(page.getByTestId("image-spatial-reference-camera-select")).toBeVisible();

      // Fifth character must be blocked via API as well.
      const maps = await request.get(`${API}/api/spatial-map/projects/${project.id}/maps`);
      expect(maps.ok()).toBeTruthy();
      const documents = (await maps.json()).documents as Array<{ id: string; characters: unknown[] }>;
      const documentId = documents[0]?.id;
      expect(documentId).toBeTruthy();
      const over = await request.post(
        `${API}/api/spatial-map/projects/${project.id}/maps/${documentId}/characters`,
        { data: { characterId: "blocked", label: "Character 5", x: 0, z: 0 } }
      );
      expect(over.status()).toBe(409);
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
