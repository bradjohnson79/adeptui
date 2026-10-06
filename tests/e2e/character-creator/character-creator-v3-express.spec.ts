import { expect, test, type APIRequestContext } from "@playwright/test";
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
      description: "Certification character for Character Creator V3. Not Schnick or Korri.",
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

test.describe("Character Creator V3 Express chrome", () => {
  test("Front-only generator; Character Angles is not a generator option", async ({ page, request }) => {
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("cc-v2-generate-front")).toBeVisible();
    await expect(page.getByTestId("cc-v2-generate-back")).toHaveCount(0);
    await expect(page.getByTestId("cc-v2-generate-multiview")).toBeVisible();
    await expect(page.getByTestId("cc-v2-generate-back")).toHaveCount(0);
    const select = page.getByTestId("cc-v2-generator-select");
    await expect(select).toBeVisible();
    const options = await select.locator("option").allTextContents();
    expect(options.join(" ").toLowerCase()).not.toMatch(/wonder3d/);
    expect(options.join(" ").toLowerCase()).not.toMatch(/\bkrea 2\b/);

    const backRes = await request.post(
      `${api}/api/projects/${projectId}/characters/${characterId}/views/back/generate`,
      { data: {} },
    );
    expect(backRes.status()).toBe(409);
    const backBody = (await backRes.json()) as { detail?: { code?: string } };
    expect(backBody.detail?.code || (backBody as { code?: string }).code).toBe("BACK_RETIRED");

    const mvRes = await request.post(
      `${api}/api/projects/${projectId}/characters/${characterId}/multiview/generate`,
      { data: {} },
    );
    expect(mvRes.status()).toBe(409);
    const mvBody = (await mvRes.json()) as { detail?: { code?: string } };
    const code = mvBody.detail?.code || (mvBody as { code?: string }).code;
    expect([
      "FRONT_LOCK_REQUIRED",
      "MODEL_MISSING",
      "RUNTIME_NOT_READY",
      "GPU_NOT_READY",
      "JOB_ACTIVE",
      "ANGLES_APPROVED",
    ]).toContain(code);
  });
});
