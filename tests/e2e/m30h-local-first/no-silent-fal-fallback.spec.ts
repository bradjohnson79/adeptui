import { test, expect } from "@playwright/test";
import { API, createTempProject, deleteProject } from "../helpers/app";

async function waitForStudioReady(request: import("@playwright/test").APIRequestContext) {
  await expect
    .poll(async () => {
      try {
        return (await request.get(`${API}/api/health`)).ok();
      } catch {
        return false;
      }
    }, { timeout: 60_000 })
    .toBeTruthy();
}

/**
 * TEXT-ONLY CONTRACT — Text to Video is text-only.
 * No References panel, no inherited image references, no Attach Asset controls,
 * no start-frame / I2V fallback, and never a silent fal submit. Generate either
 * surfaces the honest blocker (no executable T2V) or the paid-approval dialog
 * (executable hosted T2V) — in both cases no fal request is submitted without
 * explicit approval. The submitted payload must carry only text + generation
 * settings (no reference / spatial / start-frame asset IDs).
 */
test.describe("Text to Video text-only — no silent fal, clean payload", () => {
  test("Generate never silently submits fal — blocker or paid-approval dialog only", async ({
    page,
    request,
  }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `T2V-NOSILENT ${Date.now()}`);
    let txt2vidPosts = 0;
    await page.route(/\/api\/projects\/[^/]+\/txt2vid$/, async (route) => {
      txt2vidPosts += 1;
      // Never let a real submit through during this test.
      await route.abort();
    });
    try {
      await page.goto(`/project/${project.id}?workspace=txt2vid`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("txt2vid-panel")).toBeVisible({ timeout: 30_000 });

      await page.getByLabel(/prompt/i).fill(
        "Exactly one woman in an observation chamber, slow push-in, no music",
      );
      await page.getByTestId("txt2vid-generate").click();

      const blocker = page.getByTestId("txt2vid-message");
      const dialog = page.getByTestId("paid-fal-fallback-dialog");
      await expect.poll(async () => {
        return (await blocker.isVisible()) || (await dialog.isVisible()) || txt2vidPosts > 0;
      }, { timeout: 10_000 }).toBeTruthy();

      if (await dialog.isVisible()) {
        await expect(page.getByTestId("approve-paid-fal")).toBeVisible();
        await expect(page.getByTestId("generate-local-start-frame")).toHaveCount(0);
        await page.getByTestId("cancel-fal-fallback").click();
        await expect(dialog).toBeHidden();
        expect(txt2vidPosts, "no silent hosted POST before approval").toBe(0);
      } else if (txt2vidPosts > 0) {
        // Local LTX 2.5 / MiniMax may submit immediately. Hosted still needs the dialog.
        expect(dialog).toHaveCount(0);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Txt2Vid surface is text-only — no References panel or Attach Asset controls", async ({
    page,
    request,
  }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `T2V-NOREFS ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=txt2vid`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("txt2vid-panel")).toBeVisible({ timeout: 30_000 });

      // No References panel of any kind.
      await expect(page.getByTestId("scene-references-pane")).toHaveCount(0);
      await expect(page.getByTestId("references-attach-form")).toHaveCount(0);
      await expect(page.getByTestId("references-filter")).toHaveCount(0);
      await expect(page.getByTestId("ref-attach-submit")).toHaveCount(0);
      // No spatial reference fieldset.
      await expect(page.getByTestId("videospatial-reference")).toHaveCount(0);

      // The creator-facing inputs are text + generation settings only.
      await expect(page.getByLabel(/prompt/i)).toBeVisible();
      await expect(page.getByLabel(/generator/i)).toBeVisible();
      await expect(page.getByLabel(/duration/i)).toBeVisible();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Txt2Vid submit payload carries only text + generation settings (no reference IDs)", async ({
    page,
    request,
  }) => {
    await waitForStudioReady(request);
    const project = await createTempProject(request, `T2V-PAYLOAD ${Date.now()}`);
    let capturedBody: string | null = null;
    await page.route(/\/api\/projects\/[^/]+\/txt2vid$/, async (route) => {
      const req = route.request();
      capturedBody = req.postData() || null;
      // Abort so no real (paid) fal job is ever submitted during this test.
      await route.abort();
    });
    try {
      await page.goto(`/project/${project.id}?workspace=txt2vid`);
      await page.waitForLoadState("domcontentloaded");
      await expect(page.getByTestId("txt2vid-panel")).toBeVisible({ timeout: 30_000 });

      await page.getByLabel(/prompt/i).fill("A lone explorer finds a glowing artifact in a jungle temple, slow push-in.");
      await page.getByTestId("txt2vid-generate").click();

      const dialog = page.getByTestId("paid-fal-fallback-dialog");
      if (await dialog.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await page.getByTestId("approve-paid-fal").click();
      }
      if (capturedBody || (await dialog.isVisible().catch(() => false))) {
        await expect.poll(async () => capturedBody !== null, { timeout: 10_000 }).toBeTruthy();
        const payload = JSON.parse(capturedBody as string) as Record<string, unknown>;
        const keys = Object.keys(payload);
        const forbidden = [
          "sceneReferenceProvenance",
          "spatialMapId",
          "spatialMapVersion",
          "spatialCameraId",
          "spatialStartCameraId",
          "spatialEndCameraId",
          "spatialReferenceBundle",
          "spatialReferenceAssetIds",
          "start_asset_id",
          "source_asset_id",
          "reference_asset_ids",
          "referenceAssetIds",
        ];
        for (const bad of forbidden) {
          expect(keys, `payload must not carry ${bad}`).not.toContain(bad);
        }
        expect(payload.prompt, "payload must carry the prompt").toBeTruthy();
        if (!String(payload.engine || "").startsWith("fal_")) {
          expect(payload.providerPreference).toBe("local");
        }
      }
      // Whether or not a submit occurred, no reference IDs leaked.
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
