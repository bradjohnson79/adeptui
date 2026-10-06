/**
 * Owner lock: Korri Anadriya approved Front + Side + 3/4 + Back.
 * Save and Create Character Sheet is authorized. Do not remake views.
 */
import { expect, test } from "@playwright/test";
import { creatorUiBase, studioApiBase } from "../setup/ownerProjectGuard";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const CHARACTER_ID = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
const FRONT_ASSET_ID = "0c7d967f-eb3b-4003-a4d6-a4a562a38ee0";

test.setTimeout(180_000);

test.describe("Anadriya local Character Sheet compose", () => {
  test("product button stitches locally; CRS and @Anadriya persist", async ({ page, request }) => {
    const api = studioApiBase();
    const ui = creatorUiBase();
    const serverErrors: string[] = [];
    const providerHits: string[] = [];

    page.on("response", (res) => {
      if (res.status() >= 500) serverErrors.push(`${res.status()} ${res.url()}`);
    });
    page.on("request", (req) => {
      const url = req.url();
      if (/any-llm\/vision|fal\.ai|kie\.ai|retry-vision|retry-revision-2/i.test(url)) {
        providerHits.push(`${req.method()} ${url}`);
      }
    });

    const before = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    expect(before.ok(), await before.text()).toBeTruthy();
    const beforeBody = (await before.json()) as {
      views?: { front?: { assetId?: string; approved?: boolean } };
      visualLock?: { status?: string };
      multiView?: { angles?: Record<string, { assetId?: string; approved?: boolean }> };
      sheetGate?: { ready?: boolean };
    };
    expect(beforeBody.views?.front?.assetId).toBe(FRONT_ASSET_ID);
    expect(beforeBody.views?.front?.approved).toBeTruthy();
    expect(beforeBody.visualLock?.status).toBe("ok");
    expect(beforeBody.sheetGate?.ready).toBeTruthy();
    for (const name of ["side", "three_quarter", "back"] as const) {
      expect(beforeBody.multiView?.angles?.[name]?.approved).toBeTruthy();
      expect(beforeBody.multiView?.angles?.[name]?.assetId).toBeTruthy();
    }

    await page.goto(`${ui}/project/${PROJECT_ID}?workspace=characters&characterId=${CHARACTER_ID}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Create Back View")).toHaveCount(0);
    const anglesStage = page.getByTestId("cc-v2-angles-stage");
    await expect(anglesStage).toBeVisible();
    await expect(anglesStage).toHaveText("Side, 3/4, and Back are ready.");
    await expect(anglesStage).not.toContainText(/object_info|WinError|urlopen|Comfy/i);
    const compose = page.getByTestId("cc-v2-compose-sheet");
    await expect(compose).toBeEnabled();

    const waitCompose = page.waitForResponse(
      (res) => res.url().includes("/sheet/compose") && res.request().method() === "POST",
      { timeout: 120_000 },
    );
    await compose.click();
    const composeRes = await waitCompose;
    expect(composeRes.status(), await composeRes.text()).toBe(200);
    const composeBody = (await composeRes.json()) as { sheetAssetId?: string; sheet?: { assetId?: string } };
    const sheetId = String(composeBody.sheetAssetId || composeBody.sheet?.assetId || "");
    expect(sheetId).toBeTruthy();

    await expect(page.getByTestId("cc-v2-img-sheet")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-regen-sheet")).toBeVisible();
    await expect(page.getByTestId("cc-v2-progress-sheet")).toContainText("Character Sheet Ready");
    await expect(page.getByTestId("cc-v2-progress-sheet")).toContainText("100%");
    expect(providerHits, providerHits.join("\n")).toEqual([]);
    expect(serverErrors, serverErrors.join("\n")).toEqual([]);

    const again = page.waitForResponse(
      (res) => res.url().includes("/sheet/compose") && res.request().method() === "POST",
      { timeout: 60_000 },
    );
    await compose.click();
    const againRes = await again;
    expect(againRes.status()).toBe(200);
    const againBody = (await againRes.json()) as { sheetAssetId?: string };
    expect(String(againBody.sheetAssetId || "")).toBe(sheetId);

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("cc-v2-img-sheet")).toBeVisible();
    await expect(page.getByTestId("cc-v2-regen-sheet")).toBeVisible();
    await expect(page.getByTestId("cc-v2-angles-stage")).toHaveText("Side, 3/4, and Back are ready.");

    const waitRegen = page.waitForResponse(
      (res) => res.url().includes("/sheet/compose") && res.request().method() === "POST",
      { timeout: 120_000 },
    );
    await page.getByTestId("cc-v2-regen-sheet").click();
    const regenRes = await waitRegen;
    expect(regenRes.status(), await regenRes.text()).toBe(200);
    const regenBody = (await regenRes.json()) as { sheetAssetId?: string };
    const regenId = String(regenBody.sheetAssetId || "");
    expect(regenId).toBeTruthy();
    expect(regenId).not.toBe(sheetId);
    await expect(page.getByTestId("cc-v2-img-sheet")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-progress-sheet")).toContainText("100%");

    const reloaded = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/cc-v2`);
    const reloadBody = (await reloaded.json()) as {
      sheetAssetId?: string;
      atTag?: string;
      visualLock?: { status?: string };
    };
    expect(reloadBody.sheetAssetId).toBe(regenId);
    expect(reloadBody.atTag).toBe("@Anadriya");
    expect(reloadBody.visualLock?.status).toBe("ok");

    const crs = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}/crs`);
    expect(crs.ok(), await crs.text()).toBeTruthy();
    const crsBody = (await crs.json()) as {
      tag?: string;
      approved_reference_asset_id?: string;
      approvedSheetAssetId?: string;
    };
    const crsSheet = String(crsBody.approved_reference_asset_id || crsBody.approvedSheetAssetId || "");
    expect(crsSheet).toBe(regenId);
    expect(String(crsBody.tag || "")).toMatch(/@Anadriya/i);
    expect(providerHits, providerHits.join("\n")).toEqual([]);
    expect(serverErrors, serverErrors.join("\n")).toEqual([]);
  });
});
