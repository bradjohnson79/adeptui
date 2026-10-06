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
  return { projectId, characterId: String(row.id || "") };
}

test.describe("Character Creator V3 Character Angles live", () => {
  test("engine errors stay honest; generate is single-flight", async ({ page, request }) => {
    const { projectId, characterId } = await ensureMiraVale(request);
    const api = studioApiBase();
    const unexpected: string[] = [];
    page.on("pageerror", (err) => unexpected.push(`pageerror:${err.message}`));
    page.on("response", (res) => {
      const status = res.status();
      if (status >= 500) unexpected.push(`http:${status}:${res.url()}`);
    });

    const statusRes = await request.get(`${api}/api/projects/${projectId}/characters/${characterId}/cc-v2`);
    expect(statusRes.ok(), await statusRes.text()).toBeTruthy();
    const state = (await statusRes.json()) as {
      views?: { front?: { approved?: boolean } };
      visualLock?: { status?: string };
      multiviewEngine?: { available?: boolean; status?: string; creatorMessage?: string };
    };
    const engineReady = Boolean(state.multiviewEngine?.available && state.multiviewEngine?.status === "READY");
    const frontOk = Boolean(state.views?.front?.approved && state.visualLock?.status === "ok");
    const existingAngles = Boolean(
      (state as { multiView?: { angles?: Record<string, { assetId?: string | null }> } }).multiView?.angles?.side
        ?.assetId,
    );

    await page.goto(`/project/${projectId}?workspace=characters&characterId=${characterId}`, {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("cc-v2-studio")).toBeVisible({ timeout: 20_000 });
    const generate = page.getByTestId("cc-v2-generate-multiview");
    await expect(generate).toBeVisible();
    await expect(page.getByTestId("cc-v2-regen-side")).toBeVisible();
    await expect(page.getByTestId("cc-v2-reject-side")).toBeVisible();

    if (!engineReady || !frontOk) {
      await expect(generate).toBeDisabled();
      if (!engineReady && frontOk) {
        await expect(page.getByTestId("cc-v2-multiview-unavailable")).toBeVisible();
      }
      const mvRes = await request.post(
        `${api}/api/projects/${projectId}/characters/${characterId}/multiview/generate`,
        { data: {} },
      );
      expect(mvRes.status()).toBe(409);
      const mvBody = (await mvRes.json()) as { detail?: { code?: string } };
      const code = mvBody.detail?.code || (mvBody as { code?: string }).code;
      expect(["FRONT_LOCK_REQUIRED", "MODEL_MISSING", "RUNTIME_NOT_READY", "GPU_NOT_READY", "JOB_ACTIVE"]).toContain(
        code,
      );
      expect(unexpected, unexpected.join("\n")).toEqual([]);
      test.info().annotations.push({
        type: "blocker",
        description: engineReady
          ? "Front lock required before live Character Angles."
          : `Engine not READY: ${state.multiviewEngine?.status || "unknown"}`,
      });
      return;
    }

    await expect(page.getByTestId("cc-v2-angle-side")).toBeVisible();
    await expect(page.getByTestId("cc-v2-angle-three_quarter")).toBeVisible();
    await expect(page.getByTestId("cc-v2-angle-back")).toBeVisible();
    await expect(page.getByTestId("cc-v2-regen-side")).toBeVisible();
    await expect(page.getByTestId("cc-v2-reject-side")).toBeVisible();
    if (existingAngles) {
      await expect(page.getByTestId("cc-v2-angle-side").locator("img")).toBeVisible();
      expect(unexpected, unexpected.join("\n")).toEqual([]);
      return;
    }
    await expect(generate).toBeEnabled();
    await generate.click();
    await expect(generate).toBeDisabled();
    await expect(page.getByTestId("cc-v2-angle-side").locator("img")).toBeVisible({ timeout: 420_000 });
    expect(unexpected, unexpected.join("\n")).toEqual([]);
  });
});
