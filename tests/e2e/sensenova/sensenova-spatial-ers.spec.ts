/**
 * SenseNova U1.5 Spatial Map → ERS — Lab Observatory only.
 * Never Schnick Coffee. Never mutate Venture production assets.
 * Not Ready / missing Atlas must skip live generate — never silent-pass.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const LAB = "SenseNova Integration Lab";
const MAP_TITLE = "Observatory Control Room";
const EVIDENCE = path.resolve(__dirname, "..", "..", "..", "docs", "release-gate", "sensenova-u15", "evidence");
const FORBIDDEN = "2347bf46-3762-4763-86c5-4a6032522278";

test.setTimeout(40 * 60 * 1000);

async function ensureLabProject(request: APIRequestContext): Promise<string> {
  const listed = await request.get(`${API}/api/projects`);
  expect(listed.ok()).toBeTruthy();
  const body = await listed.json();
  const rows = Array.isArray(body) ? body : body.projects || body.items || [];
  const existing = rows.find((row: { name?: string; id?: string }) => String(row.name || "") === LAB);
  if (existing?.id) {
    expect(String(existing.id)).not.toBe(FORBIDDEN);
    return String(existing.id);
  }
  const created = await request.post(`${API}/api/projects`, { data: { name: LAB } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const proj = await created.json();
  const id = String(proj.id || proj.projectId);
  expect(id).not.toBe(FORBIDDEN);
  return id;
}

async function ensureObservatory(
  request: APIRequestContext,
  projectId: string,
): Promise<{ mapId: string; atlasId: string }> {
  const listed = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps`);
  expect(listed.ok(), await listed.text()).toBeTruthy();
  const docs = ((await listed.json()).documents || []) as Array<{
    id: string;
    title?: string;
    cameras?: unknown[];
    backgroundAssetId?: string;
  }>;
  let map = docs.find((row) => String(row.title || "") === MAP_TITLE);
  if (!map) {
    const created = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps`, {
      data: {
        title: MAP_TITLE,
        widthMeters: 16,
        depthMeters: 12,
        metersPerCell: 1,
        sceneDescription:
          "Observatory Control Room. Curved observation window forward, holographic table center, left console bank, rear door, right equipment rack. Not Venture corridor.",
        masterEnvironmentPrompt:
          "Observatory Control Room with a curved observation window, holographic table, left console bank, rear door, and right equipment rack.",
      },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    map = (await created.json()).document;
  }
  const mapId = String(map?.id || "");
  const current = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
  const doc = (await current.json()).document as {
    cameras?: Array<{ id: string }>;
    backgroundAssetId?: string;
  };
  if (!(doc.cameras || []).length) {
    const camA = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/cameras`, {
      data: { label: "Hero Window", x: 0, y: 1.6, z: 6, heightMeters: 1.6, orientation: "N", hero: true },
    });
    expect(camA.ok(), await camA.text()).toBeTruthy();
    const camB = await request.post(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}/cameras`, {
      data: { label: "Console Bank", x: -4, y: 1.6, z: 1, heightMeters: 1.6, orientation: "E" },
    });
    expect(camB.ok(), await camB.text()).toBeTruthy();
  }
  const refreshed = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
  const latest = (await refreshed.json()).document as { backgroundAssetId?: string };
  if (!latest.backgroundAssetId) {
    const atlasPath = path.join(EVIDENCE, "observatory-atlas.png");
    if (fs.existsSync(atlasPath)) {
      const uploaded = await request.post(`${API}/api/projects/${projectId}/assets`, {
        multipart: {
          file: {
            name: "observatory-atlas.png",
            mimeType: "image/png",
            buffer: fs.readFileSync(atlasPath),
          },
          tag: "atlas_shot",
          kind: "image",
        },
      });
      expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
      const asset = await uploaded.json();
      const patch = await request.patch(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`, {
        data: {
          backgroundAssetId: asset.id,
          originalEnvironmentReferenceAssetId: asset.id,
        },
      });
      expect(patch.ok(), await patch.text()).toBeTruthy();
    }
  }
  const after = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps/${mapId}`);
  const afterDoc = after.ok() ? ((await after.json()).document || {}) : {};
  return { mapId, atlasId: String(afterDoc.backgroundAssetId || "") };
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

async function openLabSpatialMap(page: Page, projectId: string) {
  await page.goto(`${UI}/co-director?projectId=${encodeURIComponent(projectId)}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 45_000 });
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("ers-generator-select")).first();
    if (await panel.isVisible().catch(() => false)) break;
    await page.waitForTimeout(700);
  }
  const mapCard = page.getByText(MAP_TITLE, { exact: false }).first();
  if (await mapCard.isVisible().catch(() => false)) {
    await mapCard.click().catch(() => undefined);
  }
}

test.describe("SenseNova Spatial Map ERS", () => {
  test("SenseNova is selectable and default stays Qwen", async ({ page, request }) => {
    const projectId = await ensureLabProject(request);
    expect(projectId).not.toBe(FORBIDDEN);
    await ensureObservatory(request, projectId);
    await openLabSpatialMap(page, projectId);
    const select = page.getByTestId("ers-generator-select");
    await expect(select).toBeVisible({ timeout: 45_000 });
    await expect(select.locator('option[value="sensenova"]')).toHaveCount(1, { timeout: 45_000 });
    await expect(select).toHaveValue("qwen2512");
    const labels = await select.locator("option").allTextContents();
    expect(labels.some((label) => /SenseNova U1\.5/i.test(label))).toBeTruthy();
    await select.selectOption("sensenova");
    await expect(select).toHaveValue("sensenova");
    await shot(page, "ers-sensenova-selected.png");
  });

  test("live native ERS generate only when Ready and Atlas exists", async ({ page, request }) => {
    const projectId = await ensureLabProject(request);
    const observatory = await ensureObservatory(request, projectId);
    await openLabSpatialMap(page, projectId);
    const select = page.getByTestId("ers-generator-select");
    await expect(select).toBeVisible({ timeout: 45_000 });
    await expect(select.locator('option[value="sensenova"]')).toHaveCount(1, { timeout: 45_000 });
    const atlasId = observatory.atlasId;
    await select.selectOption("sensenova");
    const option = await select.locator("option:checked").textContent();
    const generate = page.getByRole("button", { name: /Generate Environment Reference Sheet/i }).first();
    const blocked =
      /not ready/i.test(option || "") ||
      !atlasId ||
      (await generate.isDisabled().catch(() => true));
    if (blocked) {
      await shot(page, "ers-sensenova-not-ready.png");
      test.skip(true, "SenseNova ERS Not Ready or Atlas missing — live generate blocked");
    }
    await generate.click();
    await shot(page, "ers-sensenova-generating.png");
    await expect
      .poll(
        async () => {
          const lib = await request.get(`${API}/api/projects/${projectId}/library?limit=200`);
          if (!lib.ok()) return 0;
          const body = await lib.json();
          const items = body.items || body.assets || [];
          return items.filter((item: { tag?: string; filename?: string; prompt?: string }) =>
            /environment.reference|ers|sensenova/i.test(
              `${item.tag || ""} ${item.filename || ""} ${item.prompt || ""}`,
            ),
          ).length;
        },
        { timeout: 35 * 60 * 1000 },
      )
      .toBeGreaterThan(0);
    await shot(page, "ers-sensenova-native-sheet.png");
  });
});
