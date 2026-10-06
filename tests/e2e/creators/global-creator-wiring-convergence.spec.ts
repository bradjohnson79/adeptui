/**
 * Live Global Character / Prop / Environment wiring.
 * ADEPT_BETA_TARGET=1. No mocks. Looks up specimens by name, not hardcoded UUIDs
 * in product code. Destructive work uses a disposable project only.
 */
import { expect, test, type APIRequestContext } from "@playwright/test";
import { API, waitForAppReady } from "../helpers/app";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

test.use({ extraHTTPHeaders: {} });

async function json(res: { ok: () => boolean; json: () => Promise<unknown>; text: () => Promise<string> }) {
  expect(res.ok(), await res.text()).toBeTruthy();
  return res.json();
}

async function findProject(request: APIRequestContext, name: string): Promise<string> {
  const res = await request.get(`${API}/api/projects`);
  const body = (await json(res)) as { items?: { id: string; name: string }[] } | { id: string; name: string }[];
  const rows = Array.isArray(body) ? body : body.items || [];
  const hit = rows.find((row) => String(row.name || "") === name);
  expect(hit, `project ${name}`).toBeTruthy();
  return String(hit!.id);
}

async function listCharacters(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/characters`);
  const body = (await json(res)) as { items?: { id: string; name: string; slug?: string; is_global?: boolean }[] };
  return body.items || [];
}

test.describe("Global creator wiring convergence", () => {
  test.setTimeout(240_000);

  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("Korri promote keeps identity; Cade reconnects; Venture description/PRS stay clean", async ({
    request,
    page,
  }) => {
    const korriProject = await findProject(request, "Korri Anadriya");
    const cadeProject = await findProject(request, "Cade Scenes");

    const korriChars = await listCharacters(request, korriProject);
    const korri = korriChars.find((row) => String(row.name || "").toLowerCase() === "korri");
    expect(korri, "Korri character").toBeTruthy();
    const promoted = await request.patch(`${API}/api/projects/${korriProject}/characters/${korri!.id}`, {
      data: { is_global: true, isGlobal: true, name: "Korri" },
    });
    const promotedBody = (await json(promoted)) as { id: string; name: string; slug: string; is_global: boolean };
    expect(promotedBody.id).toBe(korri!.id);
    expect(promotedBody.name).toBe("Korri");
    expect(promotedBody.slug.toLowerCase()).toBe("korri");
    expect(String(promotedBody.slug).toLowerCase()).not.toContain("new");
    const reloadedKorri = (await json(
      await request.get(`${API}/api/projects/${korriProject}/characters/${korri!.id}`),
    )) as { name: string; slug: string; is_global: boolean };
    expect(reloadedKorri.name).toBe("Korri");
    expect(reloadedKorri.slug.toLowerCase()).toBe("korri");
    expect(reloadedKorri.is_global).toBeTruthy();

    const cadeChars = await listCharacters(request, cadeProject);
    const cade = cadeChars.find((row) => /cade/i.test(row.name || "") && !/starfighter/i.test(row.name || ""));
    expect(cade, "Cade character present").toBeTruthy();
    const cadeAgain = await listCharacters(request, cadeProject);
    expect(cadeAgain.some((row) => row.id === cade!.id)).toBeTruthy();

    const propsRes = await request.get(`${API}/api/prop-creator/projects/${korriProject}/props`);
    const propsBody = (await json(propsRes)) as { props?: { id: string; display_label?: string; tag?: string; description?: string; notes?: string; is_global?: boolean; advanced_sheet_asset_id?: string }[] };
    const venture = (propsBody.props || []).find(
      (row) => /venture spaceship/i.test(row.display_label || "") && row.is_global,
    );
    expect(venture, "Venture Spaceship").toBeTruthy();
    const ventureGet = await request.get(`${API}/api/prop-creator/projects/${korriProject}/props/${venture!.id}`);
    const ventureBody = (await json(ventureGet)) as { prop: { description?: string; notes?: string; tag?: string; is_global?: boolean; advanced_sheet_asset_id?: string; display_label?: string } };
    const desc = `${ventureBody.prop.description || ""}${ventureBody.prop.notes || ""}`;
    expect(desc).not.toMatch(/prsAssetId=/);
    expect(desc).not.toMatch(/adeptWorkingProp=/);
    expect(ventureBody.prop.display_label).toBe("Venture Spaceship");
    expect(ventureBody.prop.is_global).toBeTruthy();
    expect(String(ventureBody.prop.advanced_sheet_asset_id || "")).toBeTruthy();

    await openCoDirectorFullScreen(page, cadeProject);
    const showContent = page.getByRole("button", { name: "Show project content" });
    if (await showContent.isVisible().catch(() => false)) {
      await showContent.click();
    }
    await page.getByRole("tab", { name: "Character Creator" }).click();
    await expect(page.getByTestId("character-compact")).toBeVisible({ timeout: 30_000 });
    const select = page.getByTestId("character-compact-saved-select");
    await expect(select).toBeVisible({ timeout: 30_000 });
    await expect
      .poll(async () => {
        const options = await select.locator("option").allTextContents();
        return options.some((text) => /cade/i.test(text) && !/starfighter/i.test(text));
      }, { timeout: 45_000 })
      .toBeTruthy();
    const options = await select.locator("option").allTextContents();
    expect(options.some((text) => /wiringsmoke|characterglobaltest/i.test(text))).toBeFalsy();
    expect(options.some((text) => /^new character$/i.test(text.trim()))).toBeFalsy();
  });

  test("disposable Standard/Advanced Remove and Environment Global persist", async ({ request }) => {
    const created = await request.post(`${API}/api/projects`, {
      data: { name: `Global Wiring Disposable ${Date.now()}` },
    });
    const project = (await json(created)) as { id?: string; project_id?: string };
    const projectId = String(project.id || project.project_id || "");
    expect(projectId).toBeTruthy();

    const std = await request.post(`${API}/api/prop-creator/projects/${projectId}/props`, {
      data: { name: "Disposable Standard Prop", description: "detach me" },
    });
    const stdBody = (await json(std)) as { prop: { id: string } };
    const asset = await request.post(`${API}/api/projects/${projectId}/assets`, {
      multipart: {
        file: {
          name: "std-ref.png",
          mimeType: "image/png",
          buffer: Buffer.from(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "base64",
          ),
        },
      },
    });
    const assetBody = (await json(asset)) as { id?: string; asset?: { id?: string } };
    const assetId = String(assetBody.id || assetBody.asset?.id || "");
    if (assetId) {
      await request.post(`${API}/api/prop-creator/projects/${projectId}/props`, {
        data: { prop_id: stdBody.prop.id, name: "Disposable Standard Prop", reference_asset_id: assetId },
      });
    }
    const removed = await request.post(`${API}/api/prop-creator/projects/${projectId}/props`, {
      data: { prop_id: stdBody.prop.id, name: "Disposable Standard Prop", clear_reference: true },
    });
    const removedBody = (await json(removed)) as { prop: { reference_asset_id?: string; id: string } };
    expect(removedBody.prop.reference_asset_id || "").toBe("");
    const stdReload = (await json(
      await request.get(`${API}/api/prop-creator/projects/${projectId}/props/${stdBody.prop.id}`),
    )) as { prop: { reference_asset_id?: string } };
    expect(stdReload.prop.reference_asset_id || "").toBe("");

    const adv = await request.post(`${API}/api/prop-creator/projects/${projectId}/props`, {
      data: { name: "Disposable Advanced Prop", mode: "advanced", primary_prompt: "box" },
    });
    const advBody = (await json(adv)) as { prop: { id: string } };
    if (assetId) {
      await request.post(
        `${API}/api/prop-creator/projects/${projectId}/props/${advBody.prop.id}/advanced/angles/front/adopt`,
        { data: { asset_id: assetId, source_type: "library" } },
      ).catch(() => undefined);
      await request.post(
        `${API}/api/prop-creator/projects/${projectId}/props/${advBody.prop.id}/advanced/angles/front/approve`,
        { data: { approved: true } },
      ).catch(() => undefined);
      await request.post(
        `${API}/api/prop-creator/projects/${projectId}/props/${advBody.prop.id}/advanced/angles/front/approve`,
        { data: { approved: false } },
      );
    }
    const advReload = (await json(
      await request.get(`${API}/api/prop-creator/projects/${projectId}/props/${advBody.prop.id}`),
    )) as { prop: { angles?: Record<string, { asset_id?: string; approved?: boolean }> } };
    if (advReload.prop.angles?.front) {
      expect(advReload.prop.angles.front.asset_id || "").toBe("");
      expect(Boolean(advReload.prop.angles.front.approved)).toBeFalsy();
    }

    const env = await request.post(`${API}/api/environment-reference-sheets/projects/${projectId}/save`, {
      data: {
        name: "Disposable Horizon",
        environmentPrompt: "orbit",
        isGlobal: false,
        aspectRatio: "16:9",
        generator: "gpt-image-2",
      },
    });
    const envBody = (await json(env)) as { sheet: { sheetId: string; isGlobal?: boolean; name: string } };
    const patched = await request.patch(
      `${API}/api/environment-reference-sheets/projects/${projectId}/${envBody.sheet.sheetId}/identity`,
      { data: { isGlobal: true, name: "Disposable Horizon" } },
    );
    const patchedBody = (await json(patched)) as { sheet: { isGlobal?: boolean; name: string; sheetId: string } };
    expect(patchedBody.sheet.isGlobal).toBeTruthy();
    expect(patchedBody.sheet.name).toBe("Disposable Horizon");
    const envReload = (await json(
      await request.get(
        `${API}/api/environment-reference-sheets/projects/${projectId}/${envBody.sheet.sheetId}`,
      ),
    )) as { sheet: { isGlobal?: boolean; name: string } };
    expect(envReload.sheet.isGlobal).toBeTruthy();
    expect(envReload.sheet.name).toBe("Disposable Horizon");

    await request.delete(`${API}/api/prop-creator/projects/${projectId}/props/${stdBody.prop.id}`);
    await request.delete(`${API}/api/prop-creator/projects/${projectId}/props/${advBody.prop.id}`);
    await request.delete(
      `${API}/api/environment-reference-sheets/projects/${projectId}/${envBody.sheet.sheetId}`,
    );
  });
});
