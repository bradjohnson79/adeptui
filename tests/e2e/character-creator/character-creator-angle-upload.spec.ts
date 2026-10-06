import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { openCoDirectorContentTab, openCoDirectorFullScreen } from "../codirector/helpers/audit";
import { assertNotOwnerWriteTarget, studioApiBase } from "../setup/ownerProjectGuard";

const CADE_SCENES_ID = "fb24ff0f-8772-4d50-a602-ac69d14b5a6b";
const CADE_NAME = "Cade O'Connor";

function cadeProjectId(): string {
  return process.env.ADEPT_CADE_PROJECT_ID || CADE_SCENES_ID;
}

async function listCharacters(request: APIRequestContext, projectId: string) {
  const listed = await request.get(`${studioApiBase()}/api/projects/${projectId}/characters`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  return (await listed.json()) as {
    items?: Array<{ id: string; name: string; project_id?: string }>;
  };
}

function pngBuffer(): Buffer {
  return Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAgElEQVR4nNXOQREAIAzAsFIJqEIcohGxB9coyNrnUiZxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEidxEufvwNQDmrMBZn4PthMAAAAASUVORK5CYII=",
    "base64",
  );
}

async function ccState(request: APIRequestContext, projectId: string, characterId: string) {
  const res = await request.get(
    `${studioApiBase()}/api/projects/${projectId}/characters/${characterId}/cc-v2`,
  );
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json() as Promise<{
    characterId?: string;
    multiView?: {
      angles?: Record<
        string,
        { assetId?: string; approved?: boolean; source?: string; assetUrl?: string | null }
      >;
    };
  }>;
}

async function openCade(page: Page, projectId: string, characterId: string) {
  await openCoDirectorFullScreen(page, projectId);
  await openCoDirectorContentTab(page, "characters");
  await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("character-compact-saved-select").selectOption(characterId);
  await expect(page.getByTestId("character-compact").getByTestId("cc-v2-studio")).toBeVisible({
    timeout: 20_000,
  });
}

test.describe("Character Creator uploaded angles", () => {
  test("Cade Side upload binds the same character and stays after reload", async ({ page, request }) => {
    test.setTimeout(180_000);
    const projectId = cadeProjectId();
    assertNotOwnerWriteTarget(projectId);
    const listed = await listCharacters(request, projectId);
    const cade = (listed.items || []).find((row) => row.name === CADE_NAME && row.project_id === projectId);
    expect(cade?.id, "Cade must already exist in Cade Scenes").toBeTruthy();
    const characterId = String(cade?.id);
    const before = await ccState(request, projectId, characterId);
    expect(before.characterId).toBe(characterId);

    await openCade(page, projectId, characterId);
    const studio = page.getByTestId("character-compact").getByTestId("cc-v2-studio");
    await expect(studio.getByTestId("cc-v2-generate-multiview")).toBeVisible();
    await expect(studio.getByTestId("cc-v2-upload-side")).toBeVisible();
    await expect(studio.getByTestId("cc-v2-upload-three_quarter")).toBeVisible();
    await expect(studio.getByTestId("cc-v2-upload-back")).toBeVisible();
    await expect(studio.getByText("They cannot be uploaded.")).toHaveCount(0);

    await studio.getByTestId("cc-v2-upload-input-side").setInputFiles({
      name: "cade-side-upload.png",
      mimeType: "image/png",
      buffer: pngBuffer(),
    });
    await expect(studio.getByTestId("cc-v2-img-side")).toBeVisible({ timeout: 30_000 });

    const afterUpload = await ccState(request, projectId, characterId);
    expect(afterUpload.characterId).toBe(characterId);
    const side = afterUpload.multiView?.angles?.side || {};
    expect(side.source).toBe("uploaded");
    expect(side.approved).toBeFalsy();
    expect(side.assetId).toBeTruthy();

    const approve = await request.post(
      `${studioApiBase()}/api/projects/${projectId}/characters/${characterId}/multiview/angles/side/approve`,
      { data: { approved: true } },
    );
    expect(approve.ok(), await approve.text()).toBeTruthy();

    await page.reload();
    await expect(
      page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
    ).toBeVisible({ timeout: 45_000 });
    await openCoDirectorContentTab(page, "characters");
    await expect(page.getByTestId("codirector-content-characters")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("character-compact-saved-select")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("character-compact-saved-select").selectOption(characterId);
    await expect(studio.getByTestId("cc-v2-img-side")).toBeVisible({ timeout: 20_000 });
    const afterReload = await ccState(request, projectId, characterId);
    expect(afterReload.multiView?.angles?.side?.approved).toBeTruthy();
    expect(afterReload.multiView?.angles?.side?.source).toBe("uploaded");
    expect(afterReload.characterId).toBe(characterId);
  });
});
