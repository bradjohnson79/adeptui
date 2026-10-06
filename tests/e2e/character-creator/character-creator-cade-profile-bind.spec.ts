import { expect, test, type APIRequestContext } from "@playwright/test";
import { openCoDirectorContentTab, openCoDirectorFullScreen } from "../codirector/helpers/audit";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const CADE_SCENES_ID = "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const CADE_NAME = "Cade O'Connor";
const FOREIGN_GLOBAL_ID = "c557e79f-2b43-43b4-8fc3-2f965cd2df43";

function cadeProjectId(): string {
  return process.env.ADEPT_CADE_PROJECT_ID || CADE_SCENES_ID;
}

async function listCharacters(request: APIRequestContext, projectId: string) {
  const api = studioApiBase();
  const listed = await request.get(`${api}/api/projects/${projectId}/characters`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  return (await listed.json()) as {
    items?: Array<{ id: string; name: string; project_id?: string; is_global?: boolean }>;
  };
}

function ownedCade(items: Array<{ id: string; name: string; project_id?: string }> | undefined, projectId: string) {
  return (items || []).find((row) => row.name === CADE_NAME && row.project_id === projectId);
}

test.describe("Character Creator Cade profile bind", () => {
  test("create/reload binds the local Cade profile and keeps foreign Globals read-only", async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);
    const projectId = cadeProjectId();
    assertNotOwnerWriteTarget(projectId);
    const api = studioApiBase();
    const before = await listCharacters(request, projectId);
    expect((before.items || []).some((row) => row.id === FOREIGN_GLOBAL_ID && row.is_global)).toBeTruthy();
    let characterId = ownedCade(before.items, projectId)?.id || "";

    await openCoDirectorFullScreen(page, projectId);
    await openCoDirectorContentTab(page, "characters");
    await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-compact-create")).toBeVisible();

    if (!characterId) {
      const selected = await page.getByTestId("character-compact-saved-select").inputValue();
      expect(selected).not.toBe(FOREIGN_GLOBAL_ID);
      await page.getByTestId("character-compact-create").click();
      await expect(page.getByTestId("character-field-name")).toBeVisible({ timeout: 20_000 });
      await page.getByTestId("character-field-name").fill(CADE_NAME);
      await page.getByTestId("character-field-profile").fill(
        "Adult man, dark hair, determined face, cinematic portrait lighting. Local Cade Scenes character.",
      );
      await page.getByTestId("character-save").click();
      await expect(page.getByTestId("character-core-notice")).toContainText(/saved/i, { timeout: 20_000 });
      const afterCreate = await listCharacters(request, projectId);
      characterId = ownedCade(afterCreate.items, projectId)?.id || "";
      expect(characterId, "Create Character must persist a local Cade profile").toBeTruthy();
    } else {
      await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    }

    const profile = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}`);
    expect(profile.ok(), await profile.text()).toBeTruthy();
    const profileBody = (await profile.json()) as { id?: string; project_id?: string; name?: string };
    expect(profileBody.id).toBe(characterId);
    expect(profileBody.project_id).toBe(projectId);
    expect(profileBody.name).toBe(CADE_NAME);

    const v2 = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    expect(v2.ok(), await v2.text()).toBeTruthy();
    const v2Body = (await v2.json()) as { characterId?: string; name?: string };
    expect(v2Body.characterId).toBe(characterId);

    const foreignV2 = await request.get(`${api}/api/projects/${projectId}/characters/${FOREIGN_GLOBAL_ID}/cc-v2`);
    expect(foreignV2.status()).toBe(403);
    const foreignDetail = (await foreignV2.json()) as { detail?: { code?: string; message?: string } };
    expect(foreignDetail.detail?.code).toBe("OWNER_REQUIRED");
    expect(foreignDetail.detail?.message || "").not.toMatch(/Profile not found/i);

    const foreignPatch = await request.patch(
      `${api}/api/projects/${projectId}/characters/${FOREIGN_GLOBAL_ID}`,
      { data: { name: "Should Not Rename" } },
    );
    expect(foreignPatch.status()).toBe(403);

    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("character-field-name")).toHaveValue(CADE_NAME);
    await expect(page.getByTestId("character-core-error")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible();
    await expect(page.getByTestId("cc-v2-studio")).not.toContainText("Character Profile not found");

    await page.reload();
    await expect(
      page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
    ).toBeVisible({ timeout: 45_000 });
    await openCoDirectorContentTab(page, "characters");
    await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-compact-saved-select")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    await expect(page.getByTestId("character-field-name")).toHaveValue(CADE_NAME, { timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible();

    await page.getByTestId("character-compact-saved-select").selectOption(FOREIGN_GLOBAL_ID);
    await expect(page.getByTestId("character-core-ownership")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("character-core-ownership")).toContainText(
      "Global characters can only be edited from the project that created them.",
    );
    await expect(page.getByTestId("cc-v2-ownership")).toBeVisible();
    await expect(page.getByTestId("cc-v2-studio")).toHaveCount(0);
    await expect(page.getByTestId("character-save")).toBeDisabled();
    await expect(page.getByTestId("character-create-local")).toBeVisible();
  });
});
