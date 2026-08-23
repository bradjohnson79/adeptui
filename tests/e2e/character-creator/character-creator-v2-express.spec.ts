import { expect, test, type APIRequestContext } from "@playwright/test";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const CERT_PROJECT_ID = "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";

function certProjectId(): string {
  return process.env.ADEPT_CERT_PROJECT_ID || process.env.ADEPT_PROJECT_ID || CERT_PROJECT_ID;
}

async function ensureMiraVale(request: APIRequestContext): Promise<{ projectId: string; characterId: string }> {
  const api = studioApiBase();
  const projectId = certProjectId();
  assertNotOwnerWriteTarget(projectId);
  const listed = await request.get(`${api}/api/projects/${projectId}/characters`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const body = (await listed.json()) as { items?: { id: string; name: string }[] };
  const found = (body.items || []).find((row) => row.name === "Mira Vale");
  if (found) {
    assertNotOwnerWriteTarget(projectId, found.id);
    return { projectId, characterId: found.id };
  }
  const created = await request.post(`${api}/api/projects/${projectId}/characters`, {
    data: {
      name: "Mira Vale",
      description: "Certification character for Character Creator V2. Not Schnick or Korri.",
      gender_presentation: "woman",
      visual_style: "cinematic",
    },
  });
  expect(created.ok(), await created.text()).toBeTruthy();
  const row = (await created.json()) as { id?: string };
  const characterId = String(row.id || "");
  assertNotOwnerWriteTarget(projectId, characterId);
  return { projectId, characterId };
}

test.describe("Character Creator V2 Express", () => {
  test("Express exposes Front/Back and no Close-up", async ({ page, request }) => {
    test.setTimeout(90_000);
    const { projectId, characterId } = await ensureMiraVale(request);
    await openCoDirectorFullScreen(page, projectId);
    await page.getByTestId("codirector-content-tab-characters").click();
    await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    const studio = page.getByTestId("cc-v2-studio");
    await expect(studio).toBeVisible({ timeout: 20_000 });
    await expect(studio).toHaveAttribute("data-mode", "express");
    await expect(page.getByTestId("cc-v2-card-front")).toBeVisible();
    await expect(page.getByTestId("cc-v2-card-back")).toBeVisible();
    await expect(page.getByTestId("cc-v2-card-closeup")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-compose-sheet")).toBeVisible();
    await expect(page.getByTestId("cc-v2-compose-sheet")).toBeDisabled();
  });
});
