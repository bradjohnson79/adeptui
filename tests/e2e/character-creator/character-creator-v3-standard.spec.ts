import { expect, test } from "@playwright/test";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const CERT_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";

function certProjectId(): string {
  return process.env.ADEPT_CERT_PROJECT_ID || process.env.ADEPT_PROJECT_ID || CERT_PROJECT_ID;
}

test.describe("Character Creator V3 Standard chrome", () => {
  test("Close-up remains optional; Wonder3D is not a generator", async ({ page, request }) => {
    const api = studioApiBase();
    const projectId = certProjectId();
    assertNotOwnerWriteTarget(projectId);
    const listed = await request.get(`${api}/api/projects/${projectId}/characters`);
    expect(listed.ok(), await listed.text()).toBeTruthy();
    const body = (await listed.json()) as { items?: { id: string; name: string }[] };
    const found = (body.items || []).find((row) => row.name === "Mira Vale");
    if (!found) {
      test.skip(true, "Mira Vale cert character is not in the project yet.");
    }
    assertNotOwnerWriteTarget(projectId, found!.id);
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${found!.id}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-generate-back")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-generate-multiview")).toBeVisible();
    await expect(page.getByTestId("cc-v2-card-closeup")).toBeVisible();
    const select = page.getByTestId("cc-v2-generator-select");
    const options = await select.locator("option").allTextContents();
    expect(options.join(" ").toLowerCase()).not.toMatch(/wonder3d/);
    expect(options.join(" ").toLowerCase()).not.toMatch(/\bkrea 2\b/);
    await expect(page.getByTestId("cc-v2-generate-multiview")).toBeVisible();
  });
});
