/**
 * Live Express API-only GPT Image 2 certification.
 * Named cert project only. Uses/creates "API-Only GPT Image 2 Cert" map.
 * Never writes the production Supplementary View Assist Cert background.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const PRODUCTION_MAP_ID = "e6f64c3b-2533-4549-a476-bf0dcb90d298";
const PRODUCTION_ATLAS_ID = "9f7d4571-9444-41fa-b4c2-29c27919736a";
const HISTORICAL_LOCAL_CERT_ID = "a6176a4c-c25c-48c2-9077-ee8932ec4ced";
const CERT_MAP_TITLE = "API-Only GPT Image 2 Cert";
const STYLE_REFERENCE_ID = "7780805f-7c6d-4e1b-a746-f53dc998f706";
const CORRIDOR =
  "Long silver metallic corridor with an elevator door at the end of the corridor. " +
  "Around the middle area of the corridor is a door to the Combat chamber on the right side. " +
  "Yellow strip against the wall leading to the Combat Chamber.";

test.setTimeout(12 * 60 * 1000);

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
      await page.waitForTimeout(400);
    } else {
      break;
    }
  }
}

async function listMaps(request: APIRequestContext) {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()).documents as Array<{
    id: string;
    title?: string;
    backgroundAssetId?: string | null;
    geometrySource?: string;
    updatedAt?: string;
    characters?: unknown[];
    props?: unknown[];
    cameras?: unknown[];
  }>;
}

async function restoreProductionDefault(request: APIRequestContext) {
  const touch = await request.patch(
    `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP_ID}`,
    { data: { notes: "API-only cert isolation restore" } },
  );
  expect(touch.ok()).toBeTruthy();
}

async function makeCertMostRecent(request: APIRequestContext, certId: string) {
  const touch = await request.patch(
    `${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${certId}`,
    { data: { notes: `API-only cert active ${Date.now()}` } },
  );
  expect(touch.ok()).toBeTruthy();
}

async function ensureCertMap(request: APIRequestContext) {
  const docs = await listMaps(request);
  const production = docs.find((d) => d.id === PRODUCTION_MAP_ID);
  expect(production?.backgroundAssetId).toBe(PRODUCTION_ATLAS_ID);
  let cert = docs.find((d) => d.title === CERT_MAP_TITLE);
  if (!cert) {
    const created = await request.post(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`, {
      data: { title: CERT_MAP_TITLE, notes: "API-only GPT Image 2 certification map." },
    });
    expect(created.ok()).toBeTruthy();
    cert = (await created.json()).document;
  }
  expect(cert?.id).toBeTruthy();
  expect(cert?.id).not.toBe(PRODUCTION_MAP_ID);
  expect(cert?.id).not.toBe(HISTORICAL_LOCAL_CERT_ID);
  return { certId: String(cert!.id), docs };
}

async function openCertSpatialMap(page: Page, request: APIRequestContext, certId: string) {
  await makeCertMostRecent(request, certId);
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  await page.getByTestId("codirector-content-tab-spatial_map").click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

test.describe("API-only GPT Image 2 live Express", () => {
  test("UI chrome is GPT-only and description-only is ready when configured", async ({
    page,
    request,
  }) => {
    const { certId } = await ensureCertMap(request);
    await openCertSpatialMap(page, request, certId);
    await expect(page.getByTestId("spatial-map-mode-toggle")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);
    const form = page.getByTestId("spatial-map-express-form");
    if (await form.isVisible().catch(() => false)) {
      await expect(
        page.getByTestId("spatial-map-atlas-engine").or(page.getByTestId("spatial-map-gpt-required")),
      ).toBeVisible();
      await expect(form).not.toContainText(/FLUX|ControlNet|MoGe|VGGT/i);
      await expect(form).not.toContainText(/Qwen Image|qwen2512/i);
      await page.screenshot({
        path: "docs/release-gate/spatial-map/evidence/api-only/express-form.png",
        fullPage: true,
      });
      await page.getByTestId("scene-description-input").fill(CORRIDOR);
      if (await page.getByTestId("spatial-map-gpt-required").isVisible().catch(() => false)) {
        await expect(page.getByTestId("spatial-map-generate")).toBeDisabled();
      } else {
        await expect(page.getByTestId("spatial-map-atlas-engine")).toContainText("GPT Image 2");
        await expect(page.getByTestId("spatial-map-generate")).toBeEnabled();
      }
    } else {
      await expect(page.getByTestId("atlas-regenerate-btn")).toBeVisible();
      await expect(page.getByTestId("spatial-map-panel")).not.toContainText(/FLUX|MoGe|VGGT/i);
    }
  });

  test("Generate stays on GPT Image 2 I2I and never writes production Atlas", async ({
    page,
    request,
  }) => {
    const { certId } = await ensureCertMap(request);
    const executions: Array<Record<string, unknown>> = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && req.url().includes("/executions")) {
        try {
          executions.push(req.postDataJSON() as Record<string, unknown>);
        } catch {
          /* ignore */
        }
      }
    });
    await openCertSpatialMap(page, request, certId);
    const form = page.getByTestId("spatial-map-express-form");
    const regenerate = page.getByTestId("atlas-regenerate-btn");
    if (await form.isVisible({ timeout: 15_000 }).catch(() => false)) {
      await expect
        .poll(async () => page.getByTestId("spatial-map-atlas-engine").isVisible().catch(() => false), {
          timeout: 45_000,
        })
        .toBeTruthy();
      await page.getByTestId("scene-description-input").fill(CORRIDOR);
      const refRes = await request.get(`${API}/api/assets/${STYLE_REFERENCE_ID}/file`);
      expect(refRes.ok()).toBeTruthy();
      const refBytes = Buffer.from(await refRes.body());
      expect(refBytes.length).toBeGreaterThan(1000);
      await page.getByTestId("spatial-map-reference-file").setInputFiles({
        name: "api-only-env-ref.png",
        mimeType: "image/png",
        buffer: refBytes,
      });
      await expect(page.getByTestId("spatial-map-selected-reference")).toBeVisible({ timeout: 20_000 });
      const generate = page.getByTestId("spatial-map-generate");
      await expect(generate).toBeEnabled();
      await generate.click();
    } else if (await regenerate.isVisible().catch(() => false)) {
      await regenerate.click();
    } else {
      throw new Error("Neither Express Generate nor Generate New was available on the cert map.");
    }
    await expect.poll(() => executions.length, { timeout: 20_000 }).toBeGreaterThan(0);
    const ctx = (executions[executions.length - 1].context || {}) as Record<string, unknown>;
    expect(String(ctx.generationMethod || ctx.generation_method)).toBe("api");
    expect(String(ctx.hostedModelId || ctx.hosted_model_id)).toBe("gpt-image-2-kie");
    expect(String(ctx.source || "")).toBe("api");
    expect(JSON.stringify(ctx)).not.toMatch(/qwen2512|flux\.txt2img|moge|vggt|controlnet/i);
    expect(String(ctx.generation_route || ctx.generationRoute)).toMatch(/designed/);
    expect(String(ctx.hostedModelId || ctx.hosted_model_id)).not.toBe("");
    expect(STYLE_REFERENCE_ID).not.toBe(PRODUCTION_ATLAS_ID);
    await expect(
      page.getByTestId("atlas-generation-progress").or(page.getByRole("progressbar")).first(),
    ).toBeVisible({ timeout: 20_000 });

    await expect
      .poll(
        async () => {
          const production = (await listMaps(request)).find((d) => d.id === PRODUCTION_MAP_ID);
          return production?.backgroundAssetId;
        },
        { timeout: 180_000 },
      )
      .toBe(PRODUCTION_ATLAS_ID);
    await expect
      .poll(
        async () => {
          const cert = (await listMaps(request)).find((d) => d.id === certId);
          return Boolean(cert?.backgroundAssetId);
        },
        { timeout: 480_000 },
      )
      .toBeTruthy();
    const cert = (await listMaps(request)).find((d) => d.id === certId);
    expect(cert?.geometrySource).toBe("designed");
    expect(cert?.id).not.toBe(PRODUCTION_MAP_ID);
    expect(cert?.id).not.toBe(HISTORICAL_LOCAL_CERT_ID);
    await restoreProductionDefault(request);
  });

  test("workspace Save/reload and production isolation stay intact", async ({ page, request }) => {
    const { certId } = await ensureCertMap(request);
    await openCertSpatialMap(page, request, certId);
    const maps = await listMaps(request);
    const cert = maps.find((d) => d.id === certId);
    expect(cert?.id).not.toBe(PRODUCTION_MAP_ID);
    if (cert?.backgroundAssetId) {
      expect(cert.geometrySource).toBe("designed");
    }
    await page.reload();
    await dismissOnboarding(page);
    await page.getByTestId("codirector-content-tab-spatial_map").click({ force: true });
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    const after = await listMaps(request);
    const certAfter = after.find((d) => d.id === certId);
    if (cert?.backgroundAssetId) {
      expect(certAfter?.backgroundAssetId).toBe(cert.backgroundAssetId);
    }
    const production = after.find((d) => d.id === PRODUCTION_MAP_ID);
    expect(production?.backgroundAssetId).toBe(PRODUCTION_ATLAS_ID);
    await restoreProductionDefault(request);
  });
});
