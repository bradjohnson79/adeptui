/**
 * Owner lock: Korri Anadriya project / Anadriya character.
 * Save Character persist + reload only. Never generate angles, approve/reject
 * angles, or Retry Co-Director Vision.
 */
import { expect, test } from "@playwright/test";
import { creatorUiBase, studioApiBase } from "../setup/ownerProjectGuard";

const PROJECT_ID = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const CHARACTER_ID = "4c1c0bc8-a771-4998-b652-5d549b2a2b8d";
const MARKER = " [save-e2e]";

test.setTimeout(180_000);

test.describe("Anadriya Save Character persist", () => {
  test("UI Save + reload keeps profile and reference; no angle generate", async ({ page, request }) => {
    const api = studioApiBase();
    const ui = creatorUiBase();
    const before = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`);
    expect(before.ok(), await before.text()).toBeTruthy();
    const original = (await before.json()) as { name?: string; description?: string };
    expect(original.name).toBe("Anadriya");
    const originalDescription = String(original.description || "");
    const edited = originalDescription.includes(MARKER)
      ? originalDescription
      : `${originalDescription}${MARKER}`;

    const patches: string[] = [];
    const forbidden: string[] = [];
    page.on("request", (req) => {
      const url = req.url();
      if (req.method() === "PATCH" && url.includes(`/characters/${CHARACTER_ID}`) && !url.includes("/views/") && !url.includes("/angles")) {
        patches.push(url);
      }
      if (
        /generateCharacterAngles|generate-multiview|retryCharacterVision|\/angles|\/multiview|retry-vision/i.test(url)
        && req.method() !== "GET"
      ) {
        forbidden.push(`${req.method()} ${url}`);
      }
    });

    try {
      await page.goto(`${ui}/project/${PROJECT_ID}?workspace=characters&characterId=${CHARACTER_ID}`, {
        waitUntil: "domcontentloaded",
      });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-field-name")).toHaveValue("Anadriya");
      await expect(page.getByTestId("character-reference-preview")).toBeVisible();

      const description = page.getByTestId("character-field-profile");
      await expect(description).toBeVisible();
      await description.fill(edited);
      await page.getByTestId("character-save").click();
      await expect(page.getByTestId("character-core-notice")).toContainText(/saved/i, { timeout: 15_000 });
      expect(patches.length).toBeGreaterThan(0);

      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-field-name")).toHaveValue("Anadriya");
      await expect(page.getByTestId("character-field-profile")).toHaveValue(edited);
      await expect(page.getByTestId("character-reference-preview")).toBeVisible();
      expect(forbidden).toEqual([]);
    } finally {
      const restore = await request.patch(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`, {
        data: { name: "Anadriya", description: originalDescription },
      });
      expect(restore.ok(), await restore.text()).toBeTruthy();
    }
  });

  test("API-direct save persists without generating angles", async ({ request }) => {
    const api = studioApiBase();
    const before = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`);
    expect(before.ok(), await before.text()).toBeTruthy();
    const original = (await before.json()) as { description?: string; name?: string };
    const token = `api-save-${Date.now()}`;
    const patched = await request.patch(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`, {
      data: {
        name: "Anadriya",
        description: `${String(original.description || "").replace(/\s*\[api-save-\d+\]\s*$/, "")} [${token}]`,
      },
    });
    expect(patched.ok(), await patched.text()).toBeTruthy();
    const after = await request.get(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`);
    expect(after.ok(), await after.text()).toBeTruthy();
    const body = (await after.json()) as { description?: string; name?: string };
    expect(body.name).toBe("Anadriya");
    expect(String(body.description || "")).toContain(token);
    const restore = await request.patch(`${api}/api/projects/${PROJECT_ID}/characters/${CHARACTER_ID}`, {
      data: { name: "Anadriya", description: original.description || "" },
    });
    expect(restore.ok(), await restore.text()).toBeTruthy();
  });
});
