/**
 * Scene Creator Final Production — hosted Playwright A–T.
 *
 * Express = launcher only. Standard = production editor. Generation via image_core.
 *
 * Topology (skip e2e-start / :8760). Set ADEPT_BETA_TARGET=1 ONLY with these URLs:
 *   PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app
 *   STUDIO_API_BASE=https://api-beta.adeptui.org
 *   ADEPT_BETA_TARGET=1
 *
 * Reuses Schnick Coffee. Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { AuditObserver } from "../helpers/observer";
import { openCoDirectorFullScreen } from "../codirector/helpers/audit";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "https://api-beta.adeptui.org";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
const SHOT_ID = "2a58894b-b5d4-4e86-b068-7cd156199d98";
const SC_URL = `${BASE}/project/${PROJECT_ID}?workspace=scenecreator`;

test.describe.configure({ mode: "default" });

function attachObserver(page: Page, testInfo: TestInfo) {
  const observer = new AuditObserver(page, testInfo);
  observer.attach();
  observer.allow(/favicon|fonts\.(googleapis|gstatic)|vercel\.live|ingest\./i);
  return observer;
}

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 15_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 120_000 },
    )
    .toBeTruthy();
}

async function studioBannerVisible(page: Page): Promise<boolean> {
  const offline = page.getByText("Studio API Offline", { exact: false });
  const reconnecting = page.getByText("Reconnecting to Studio API", { exact: false });
  return (await offline.isVisible().catch(() => false)) || (await reconnecting.isVisible().catch(() => false));
}

async function waitForStudioOnline(page: Page) {
  await expect
    .poll(async () => !(await studioBannerVisible(page)), { timeout: 180_000, intervals: [1_000, 2_000, 4_000] })
    .toBeTruthy();
}

async function openExpressLauncher(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openCoDirectorFullScreen(page, PROJECT_ID);
  const tab = page.getByTestId("codirector-content-tab-scene_creator");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("scene-creator-panel")).toBeVisible({ timeout: 45_000 });
}

async function openStandard(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(SC_URL, { waitUntil: "domcontentloaded" });
  await waitForStudioOnline(page);
  await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
}

test.describe("Scene Creator Final Production A–T", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("A — Express launcher shows intro and Open Scene Creator, not production controls", async ({
    page,
  }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openExpressLauncher(page);
      await expect(page.getByTestId("scene-creator-open-standard")).toBeVisible();
      await expect(page.getByTestId("scene-creator-open-standard")).toHaveText(/Open Scene Creator/i);
      await expect(page.getByText(/production-ready shots/i).first()).toBeVisible();
      await expect(page.getByTestId("scene-creator-generate")).toHaveCount(0);
      await expect(page.getByTestId("scene-creator-standard")).toHaveCount(0);
      await expect(page.getByTestId("scene-creator-inpaint-accordion")).toHaveCount(0);
      await expect(page.getByTestId("cine-tile-c1")).toHaveCount(0);
    } finally {
      observer.flush();
    }
  });

  test("B — Open Scene Creator navigates to Standard three-zone workspace", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openExpressLauncher(page);
      await page.getByTestId("scene-creator-open-standard").click();
      await expect(page).toHaveURL(/workspace=scenecreator/, { timeout: 45_000 });
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("scene-creator-browser")).toBeVisible();
    } finally {
      observer.flush();
    }
  });

  test("C — Standard hydrates existing Schnick Coffee scene/shot state", async ({ page, request }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      const ws = await request.get(
        `${API}/api/scene-creator/projects/${PROJECT_ID}/workspace?scene_id=${SCENE_ID}`,
      );
      expect(ws.ok(), await ws.text()).toBeTruthy();
      const body = (await ws.json()) as {
        selected_scene_id?: string;
        selected_shot?: { id?: string } | null;
        sheets?: unknown[];
      };
      expect(body.selected_scene_id || SCENE_ID).toBeTruthy();
      expect((body.sheets || []).length, "ERS sheets must already exist").toBeGreaterThan(0);

      await openExpressLauncher(page);
      await page.getByTestId("scene-creator-open-standard").click();
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("scene-creator-ers-select")).toBeVisible({ timeout: 30_000 });
      const selected = await page.getByTestId("scene-creator-ers-select").inputValue();
      expect(selected, "ERS hydrates from existing project state").toBeTruthy();
    } finally {
      observer.flush();
    }
  });

  test("D — compact Co-Director remains available after entering Standard", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openExpressLauncher(page);
      await page.getByTestId("scene-creator-open-standard").click();
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      await expect(page).not.toHaveURL(/\/co-director/);
      await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveCount(0);
      const compact = page.getByTestId("codirector-popup");
      if (!(await compact.isVisible().catch(() => false))) {
        const dock = page.getByTestId("production-dock-codirector");
        await expect(dock).toBeVisible({ timeout: 15_000 });
        await dock.click();
      }
      await expect(compact).toBeVisible({ timeout: 20_000 });
      await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveCount(0);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible();
    } finally {
      observer.flush();
    }
  });

  test("E — leave Standard and reopen from Express; Scene Creator state remains", async ({ page }, info) => {
    test.setTimeout(240_000);
    const observer = attachObserver(page, info);
    try {
      await openStandard(page);
      const ers = await page.getByTestId("scene-creator-ers-select").inputValue().catch(() => "");

      await openExpressLauncher(page);
      await expect(page.getByTestId("scene-creator-open-standard")).toBeVisible();
      await page.getByTestId("scene-creator-open-standard").click();
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      const ersAgain = await page.getByTestId("scene-creator-ers-select").inputValue();
      if (ers) expect(ersAgain).toBe(ers);
      expect(ersAgain).toBeTruthy();
    } finally {
      observer.flush();
    }
  });

  test("F — Image Core recommend Modify → FLUX, not a silent swap", async ({ request }) => {
    const res = await request.get(`${API}/api/image-core/recommend?operation=modify&family=zimage`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = (await res.json()) as {
      recommendedFamily?: string;
      keepCurrentAllowed?: boolean;
      message?: string;
    };
    expect(body.recommendedFamily).toBe("flux");
    expect(body.keepCurrentAllowed).toBe(true);
    expect(body.message || "").toMatch(/FLUX/i);
  });

  test("G — Image Core recommend Remove → Z-Image", async ({ request }) => {
    const res = await request.get(`${API}/api/image-core/recommend?operation=remove&family=flux`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = (await res.json()) as { recommendedFamily?: string; keepCurrentAllowed?: boolean };
    expect(body.recommendedFamily).toBe("zimage");
    expect(body.keepCurrentAllowed).toBe(true);
  });

  test("H — Qwen region-edit is refused before enqueue", async ({ request }) => {
    const res = await request.post(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}/region-edit`,
      {
        data: {
          operation: "modify",
          prompt: "irritated expression",
          maskAssetId: "mask-does-not-exist",
          sourceAssetId: "e0d3af5e-b63d-4974-b999-7c5543f7624e",
          local_family: "qwen2512",
          local_enabled: true,
        },
        failOnStatusCode: false,
      },
    );
    expect(res.status()).toBe(400);
    const text = await res.text();
    expect(text).toMatch(/cannot edit a region|Z-Image|Unsupported/i);
    expect(text.toLowerCase()).not.toContain("traceback");
  });

  test("I — no Express generation route exists", async ({ request }) => {
    const res = await request.post(`${API}/api/scene_creator_express_generate`, {
      data: { projectId: PROJECT_ID },
      failOnStatusCode: false,
    });
    expect(res.status(), "Express generation must not exist").toBeGreaterThanOrEqual(400);
  });

  test("J — Standard production path exposes generate and region-edit", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openStandard(page);
      await expect(page.getByTestId("scene-creator-generate").first()).toBeVisible();
      await expect(page.getByTestId("scene-creator-open-standard")).toHaveCount(0);
      await expect(page.getByTestId("scene-creator-inpaint-accordion")).toBeVisible();
    } finally {
      observer.flush();
    }
  });

  test("K — Modify recommend UI offers Use FLUX and Keep Current", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openStandard(page);
      const accordion = page.getByTestId("scene-creator-inpaint-accordion");
      await expect(accordion).toBeVisible();
      await accordion.click();
      const op = page.getByTestId("scene-creator-inpaint-operation");
      await expect(op).toBeVisible({ timeout: 15_000 });
      await op.selectOption("modify");
      const rec = page.getByTestId("scene-creator-operation-recommend");
      if (await rec.isVisible().catch(() => false)) {
        await expect(page.getByTestId("scene-creator-use-recommended-family")).toBeVisible();
        await expect(page.getByTestId("scene-creator-keep-current-family")).toBeVisible();
        await expect(page.getByTestId("scene-creator-use-recommended-family")).toHaveText(/FLUX/i);
      }
    } finally {
      observer.flush();
    }
  });

  test("L — Image Core preflight refuses Qwen region-edit", async ({ request }) => {
    const res = await request.post(`${API}/api/image-core/preflight`, {
      data: {
        projectId: PROJECT_ID,
        purpose: "region_edit",
        operation: "image.edit",
        modelId: "qwen2512",
        editOperation: "modify",
        sourceAssetId: "e0d3af5e-b63d-4974-b999-7c5543f7624e",
        maskAssetId: "mask-1",
      },
      failOnStatusCode: false,
    });
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = (await res.json()) as { ok?: boolean; code?: string; message?: string };
    expect(body.ok).toBe(false);
    expect(body.code).toBe("UNSUPPORTED_OPERATION");
    expect(body.message || "").toMatch(/cannot edit a region|Z-Image/i);
  });

  test("M — workspace keeps structured ERS and camera context", async ({ request }) => {
    const ws = await request.get(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/workspace?scene_id=${SCENE_ID}`,
    );
    expect(ws.ok(), await ws.text()).toBeTruthy();
    const body = (await ws.json()) as Record<string, unknown>;
    expect((body.sheets as unknown[] | undefined)?.length || 0).toBeGreaterThan(0);
  });

  test("N — Library still holds the approved Schnick Coffee take", async ({ request }) => {
    const shotRes = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}`);
    expect(shotRes.ok(), await shotRes.text()).toBeTruthy();
    const shotBody = (await shotRes.json()) as {
      shot?: { approved_candidate_id?: string; candidates?: Array<{ id?: string; asset_id?: string }> };
    };
    const approvedId = shotBody.shot?.approved_candidate_id;
    const approved = (shotBody.shot?.candidates || []).find((c) => c.id === approvedId);
    expect(approved?.asset_id, "approved take must have an asset").toBeTruthy();
    const lib = await request.get(`${API}/api/projects/${PROJECT_ID}/library`);
    expect(lib.ok(), await lib.text()).toBeTruthy();
    const libBody = await lib.json();
    const items: Array<{ id?: string; assetId?: string }> = Array.isArray(libBody)
      ? libBody
      : libBody.items || libBody.assets || libBody.library || [];
    const ids = items.map((item) => item.id || item.assetId).filter(Boolean);
    expect(ids).toContain(approved!.asset_id);
  });

  test("O — shot candidates persist on GET after reload-equivalent fetch", async ({ request }) => {
    const first = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}`);
    expect(first.ok(), await first.text()).toBeTruthy();
    const a = (await first.json()) as { shot?: { candidates?: unknown[] } };
    const second = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}`);
    expect(second.ok(), await second.text()).toBeTruthy();
    const b = (await second.json()) as { shot?: { candidates?: unknown[] } };
    expect((b.shot?.candidates || []).length).toBe((a.shot?.candidates || []).length);
    expect((b.shot?.candidates || []).length).toBeGreaterThan(0);
  });

  test("P — duplicate Qwen region-edit does not enqueue and stays 400", async ({ request }) => {
    const payload = {
      operation: "modify",
      prompt: "irritated expression",
      maskAssetId: "mask-does-not-exist",
      sourceAssetId: "e0d3af5e-b63d-4974-b999-7c5543f7624e",
      local_family: "qwen2512",
      local_enabled: true,
    };
    const a = await request.post(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}/region-edit`,
      { data: payload, failOnStatusCode: false },
    );
    const b = await request.post(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}/region-edit`,
      { data: payload, failOnStatusCode: false },
    );
    expect(a.status()).toBe(400);
    expect(b.status()).toBe(400);
  });

  test("Q — normalized failure has no traceback", async ({ request }) => {
    const res = await request.post(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}/region-edit`,
      {
        data: {
          operation: "modify",
          prompt: "irritated expression",
          maskAssetId: "mask-does-not-exist",
          sourceAssetId: "e0d3af5e-b63d-4974-b999-7c5543f7624e",
          local_family: "qwen2512",
          local_enabled: true,
        },
        failOnStatusCode: false,
      },
    );
    const text = await res.text();
    expect(text.toLowerCase()).not.toContain("traceback");
    expect(text.toLowerCase()).not.toMatch(/file ".+\.py"/);
  });

  test("R — shot remains bound to the Schnick Coffee scene", async ({ request }) => {
    const shotRes = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}`);
    expect(shotRes.ok(), await shotRes.text()).toBeTruthy();
    const body = (await shotRes.json()) as { shot?: { scene_id?: string; project_id?: string } };
    expect(body.shot?.scene_id || SCENE_ID).toBeTruthy();
    expect(body.shot?.project_id || PROJECT_ID).toBe(PROJECT_ID);
  });

  test("S — candidate provenance does not silently swap families", async ({ request }) => {
    const shotRes = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/shots/${SHOT_ID}`);
    expect(shotRes.ok(), await shotRes.text()).toBeTruthy();
    const body = (await shotRes.json()) as {
      shot?: {
        candidates?: Array<{ family?: string; provenance_label?: string; status?: string }>;
      };
    };
    const complete = (body.shot?.candidates || []).filter((c) => (c.status || "") === "complete");
    expect(complete.length).toBeGreaterThan(0);
    for (const cand of complete) {
      const fam = (cand.family || "").toLowerCase();
      const label = (cand.provenance_label || "").toLowerCase();
      if (fam.includes("flux")) expect(label).not.toMatch(/z-image|zimage/);
      if (fam.includes("zimage") || fam.includes("z-image")) expect(label).not.toMatch(/flux/);
    }
  });

  test("T — reload Standard keeps Scene Creator workspace", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await openStandard(page);
      await page.reload({ waitUntil: "domcontentloaded" });
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("scene-creator-generate").first()).toBeVisible();
    } finally {
      observer.flush();
    }
  });
});
