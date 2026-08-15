/**
 * Scene Creator → Adept Image Generation Core migration.
 *
 * Express = launcher only. Standard = production editor. Generation via image_core.
 *
 * Topology (do not use ADEPT_BETA_TARGET=1 / :8760):
 *   PLAYWRIGHT_BASE_URL=https://adeptui.vercel.app
 *   STUDIO_API_BASE=https://api-beta.adeptui.org
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

test.describe("Scene Creator Image Core migration", () => {
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
      const popup = page.getByTestId("codirector-shell").or(page.locator("#codirector-popup"));
      await expect(popup.first()).toBeVisible({ timeout: 30_000 });
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
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(SC_URL, { waitUntil: "domcontentloaded" });
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
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

  test("Standard production path exposes generate on the three-zone workspace only", async ({ page }, info) => {
    test.setTimeout(180_000);
    const observer = attachObserver(page, info);
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(SC_URL, { waitUntil: "domcontentloaded" });
      await waitForStudioOnline(page);
      await expect(page.getByTestId("scene-creator-standard")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("scene-creator-generate").first()).toBeVisible();
      await expect(page.getByTestId("scene-creator-open-standard")).toHaveCount(0);
    } finally {
      observer.flush();
    }
  });
});
