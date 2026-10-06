/**
 * Owner lock: Korri Anadriya Front → Co-Director Vision (fal.ai).
 * Retry Vision on the current Front is authorized. Do not generate angles
 * or regenerate Front in this spec.
 */
import { expect, test } from "@playwright/test";
import { creatorUiBase, studioApiBase } from "../setup/ownerProjectGuard";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const CHARACTER_ID = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
const FRONT_ASSET_ID = "0c7d967f-eb3b-4003-a4d6-a4a562a38ee0";
const WRONG_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";

test.setTimeout(180_000);

test.describe("Anadriya Front Co-Director Vision", () => {
  test("fal Vision lock persists; Generate stays gated; wrong project rejected", async ({ page, request }) => {
    const api = studioApiBase();
    const ui = creatorUiBase();
    const serverErrors: string[] = [];
    const angleWrites: string[] = [];

    page.on("response", (res) => {
      if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    });
    page.on("request", (req) => {
      const url = req.url();
      if (
        req.method() !== "GET" &&
        /generateCharacterAngles|generate-multiview|\/angles|\/multiview/i.test(url) &&
        !/retry-vision/i.test(url)
      ) {
        angleWrites.push(`${req.method()} ${url}`);
      }
    });

    const scoped = await request.get(`${api}/api/projects/${PROJECT_ID}/assets/${FRONT_ASSET_ID}/file`);
    expect(scoped.status(), await scoped.text()).toBe(200);
    const unscoped = await request.get(`${api}/api/assets/${FRONT_ASSET_ID}/file`);
    expect(unscoped.status()).toBe(403);
    const wrong = await request.get(
      `${api}/api/projects/${WRONG_PROJECT_ID}/assets/${FRONT_ASSET_ID}/file`,
    );
    expect(wrong.status()).toBe(403);

    await page.goto(`${ui}/project/${PROJECT_ID}?workspace=characters&characterId=${CHARACTER_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("cc-v2-img-front")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Create Back View")).toHaveCount(0);

    const before = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    expect(before.ok(), await before.text()).toBeTruthy();
    const beforeBody = (await before.json()) as {
      views?: { front?: { assetId?: string; approved?: boolean } };
    };
    expect(beforeBody.views?.front?.assetId).toBe(FRONT_ASSET_ID);
    expect(beforeBody.views?.front?.approved).toBeTruthy();

    const retry = page.getByTestId("cc-v2-retry-vision");
    if (await retry.count()) {
      const waitRetry = page.waitForResponse(
        (res) => res.url().includes("/canon/retry-vision") && res.request().method() === "POST",
        { timeout: 120_000 },
      );
      await retry.click();
      expect((await waitRetry).status()).toBeLessThan(500);
    }

    const after = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    expect(after.ok(), await after.text()).toBeTruthy();
    const afterBody = (await after.json()) as {
      visualLock?: { status?: string; facts?: Record<string, unknown>; provider?: string; model?: string };
      engine?: { available?: boolean };
    };
    expect(afterBody.visualLock?.status).toBe("ok");
    expect(afterBody.visualLock?.provider).toBe("fal");
    expect(String(afterBody.visualLock?.model || "")).toContain("gemini");
    expect(Object.keys(afterBody.visualLock?.facts || {}).length).toBeGreaterThan(0);
    await expect(page.getByTestId("cc-v2-vision-failed")).toHaveCount(0);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    const reloaded = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    const reloadBody = (await reloaded.json()) as { visualLock?: { status?: string; provider?: string } };
    expect(reloadBody.visualLock?.status).toBe("ok");
    expect(reloadBody.visualLock?.provider).toBe("fal");
    await expect(page.getByTestId("cc-v2-vision-failed")).toHaveCount(0);
    await expect(page.getByText("Create Back View")).toHaveCount(0);
    if (afterBody.engine?.available !== true) {
      await expect(page.getByTestId("cc-v2-generate-multiview")).toBeDisabled();
    }
    expect(angleWrites).toEqual([]);
    expect(serverErrors, serverErrors.join("\n")).toEqual([]);
  });
});
