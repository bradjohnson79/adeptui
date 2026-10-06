/**
 * Owner lock: Korri Anadriya Front + fal Vision lock + Qwen angles.
 * Generate/Approve Side, 3/4, Back is authorized. Do not regenerate Front.
 */
import { expect, test } from "@playwright/test";
import { creatorUiBase, studioApiBase } from "../setup/ownerProjectGuard";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const CHARACTER_ID = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
const FRONT_ASSET_ID = "0c7d967f-eb3b-4003-a4d6-a4a562a38ee0";

test.setTimeout(120_000);

test.describe("Anadriya Character Angles persist", () => {
  test("Generate available; angles persist; no Create Back View; no upload", async ({ page, request }) => {
    const api = studioApiBase();
    const ui = creatorUiBase();
    const serverErrors: string[] = [];
    page.on("response", (res) => {
      if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    });

    const status = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    expect(status.ok(), await status.text()).toBeTruthy();
    const body = (await status.json()) as {
      visualLock?: { status?: string; provider?: string };
      engine?: { available?: boolean; status?: string };
      views?: { front?: { assetId?: string; approved?: boolean } };
      multiView?: {
        angles?: Record<string, { assetId?: string; approved?: boolean; status?: string }>;
      };
      sheetGate?: { ready?: boolean };
    };
    expect(body.views?.front?.assetId).toBe(FRONT_ASSET_ID);
    expect(body.views?.front?.approved).toBeTruthy();
    expect(body.visualLock?.status).toBe("ok");
    expect(body.visualLock?.provider).toBe("fal");
    expect(body.engine?.available).toBeTruthy();

    await page.goto(`${ui}/project/${PROJECT_ID}?workspace=characters&characterId=${CHARACTER_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Create Back View")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-card-side").locator("input[type=file]")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-card-three_quarter").locator("input[type=file]")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-card-back").locator("input[type=file]")).toHaveCount(0);

    const angles = body.multiView?.angles || {};
    const allApproved = ["side", "three_quarter", "back"].every(
      (name) => angles[name]?.approved && angles[name]?.assetId,
    );
    if (allApproved) {
      await expect(page.getByTestId("cc-v2-img-side")).toBeVisible();
      await expect(page.getByTestId("cc-v2-img-three_quarter")).toBeVisible();
      await expect(page.getByTestId("cc-v2-img-back")).toBeVisible();
      await expect(page.getByTestId("cc-v2-approve-side")).toBeDisabled();
      await expect(page.getByTestId("cc-v2-compose-sheet")).toBeEnabled();
    } else {
      await expect(page.getByTestId("cc-v2-generate-multiview")).toBeEnabled();
    }

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    const reloaded = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    const reloadBody = (await reloaded.json()) as {
      visualLock?: { status?: string };
      multiView?: { angles?: Record<string, { assetId?: string; approved?: boolean }> };
      sheetGate?: { ready?: boolean };
    };
    expect(reloadBody.visualLock?.status).toBe("ok");
    if (allApproved) {
      expect(reloadBody.multiView?.angles?.side?.approved).toBeTruthy();
      expect(reloadBody.multiView?.angles?.three_quarter?.approved).toBeTruthy();
      expect(reloadBody.multiView?.angles?.back?.approved).toBeTruthy();
      expect(reloadBody.sheetGate?.ready).toBeTruthy();
      await expect(page.getByTestId("cc-v2-img-side")).toBeVisible();
      await expect(page.getByTestId("cc-v2-compose-sheet")).toBeEnabled();
    }
    await expect(page.getByText("Create Back View")).toHaveCount(0);
    expect(serverErrors, serverErrors.join("\n")).toEqual([]);
  });
});
