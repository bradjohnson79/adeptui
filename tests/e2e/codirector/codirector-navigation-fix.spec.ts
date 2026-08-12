/**
 * Co-Director Navigation Fix Certification — Spatial Map + Scene Creator tabs.
 *
 * Verifies the fix for the defect where Spatial Map and Scene Creator tabs were
 * visible but inert (clicking them silently reverted to Wiki due to
 * `normalizeContentTab` not recognizing `spatial_map` / `scene_creator`).
 *
 * Reuses existing helpers (Law #17 — reuse before rebuild):
 *   - tests/e2e/helpers/app.ts (createTempProject, deleteProject, waitForAppReady, API)
 *   - tests/e2e/codirector/helpers/audit.ts (openCoDirectorFullScreen, TINY_PNG)
 *
 * Test plan:
 *   A — Spatial Map: click tab -> panel renders, project context preserved
 *   B — Scene Creator: click tab -> panel renders, project context preserved
 *   C — Tab availability: neither tab is disabled / aria-disabled
 *   D — Regression: Wiki, Script Writer, Character Creator, Spatial Map, Scene Creator, Library all navigate
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_PREFIX = "NAV-FIX-CERT";

/** Dismiss the first-run onboarding if present. */
async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(300);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if (await btn.isVisible().catch(() => false)) {
        const disabled = await btn.isDisabled().catch(() => false);
        if (!disabled) {
          await btn.click({ force: true }).catch(() => undefined);
          await page.waitForTimeout(800);
          break;
        }
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

/** Cancel any in-flight Co-Director generation so it cannot intercept tab clicks. */
async function cancelInFlightGeneration(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const stopBtn = page.getByRole("button", { name: /Stop generating/i }).first();
    if (!(await stopBtn.isVisible().catch(() => false))) return;
    await stopBtn.click({ force: true }).catch(() => undefined);
    await page.waitForTimeout(800);
  }
}

/** Click a content tab and wait for its container or inner panel to become visible. */
async function clickTabAndWait(page: Page, tabId: string, panelTestIds: string[]): Promise<void> {
  await dismissOnboarding(page);
  await cancelInFlightGeneration(page);
  const tab = page.getByTestId(`codirector-content-tab-${tabId}`);
  await expect(tab).toBeVisible({ timeout: 30_000 });
  // Retry the click — onboarding dismissal can trigger a generation that intercepts.
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    for (const testId of panelTestIds) {
      if (await page.getByTestId(testId).first().isVisible().catch(() => false)) return;
    }
    await cancelInFlightGeneration(page);
    await page.waitForTimeout(1000);
  }
  // Final assertion for clear error reporting.
  const firstPanel = page.getByTestId(panelTestIds[0]).first();
  await expect(firstPanel).toBeVisible({ timeout: 45_000 });
}

test.describe.serial("@critical Co-Director navigation fix — Spatial Map + Scene Creator", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("A — Spatial Map tab is clickable and loads SpatialMapPanel", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-spatial-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await clickTabAndWait(page, "spatial_map", [
        "codirector-content-spatial-map",
        "spatial-map-panel",
        "spatial-map-error",
        "spatial-map-loading",
      ]);
      // Tab must be selected (aria-selected=true), not reverted to Wiki.
      const spatialTab = page.getByTestId("codirector-content-tab-spatial_map");
      await expect(spatialTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });
      // Project context preserved — project name visible in the Co-Director header.
      await expect(page.getByTestId("codirector-header-project")).toContainText(project.name, { timeout: 15_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("B — Scene Creator tab is clickable and loads SceneCreatorPanel", async ({ page, request }) => {
    test.setTimeout(180_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-scene-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await clickTabAndWait(page, "scene_creator", [
        "codirector-content-scene-creator",
        "scene-creator-panel",
        "scene-creator-empty-no-ers",
        "scene-creator-loading",
      ]);
      // Tab must be selected (aria-selected=true), not reverted to Wiki.
      const sceneTab = page.getByTestId("codirector-content-tab-scene_creator");
      await expect(sceneTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });
      // Project context preserved.
      await expect(page.getByTestId("codirector-header-project")).toContainText(project.name, { timeout: 15_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("C — Tab availability: Spatial Map and Scene Creator are not disabled", async ({ page, request }) => {
    test.setTimeout(120_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-avail-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);
      await dismissOnboarding(page);
      await cancelInFlightGeneration(page);

      const spatialTab = page.getByTestId("codirector-content-tab-spatial_map");
      const sceneTab = page.getByTestId("codirector-content-tab-scene_creator");

      await expect(spatialTab).toBeVisible({ timeout: 30_000 });
      await expect(sceneTab).toBeVisible({ timeout: 30_000 });

      // Neither tab should be disabled.
      await expect(spatialTab).not.toHaveAttribute("disabled", /.*/);
      await expect(sceneTab).not.toHaveAttribute("disabled", /.*/);
      await expect(spatialTab).not.toHaveAttribute("aria-disabled", "true");
      await expect(sceneTab).not.toHaveAttribute("aria-disabled", "true");
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });

  test("D — Regression: all primary tabs navigate correctly", async ({ page, request }) => {
    test.setTimeout(240_000);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-regress-${Date.now()}`);
    const observer = new AuditObserver(page, test.info);
    observer.attach();
    try {
      await page.setViewportSize({ width: 1440, height: 900 });
      await openCoDirectorFullScreen(page, project.id);

      // Wiki
      await clickTabAndWait(page, "wiki", ["codirector-content-wiki"]);
      const wikiTab = page.getByTestId("codirector-content-tab-wiki");
      await expect(wikiTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });

      // Script Writer
      await clickTabAndWait(page, "scriptwriter", ["codirector-content-scriptwriter"]);
      const swTab = page.getByTestId("codirector-content-tab-scriptwriter");
      await expect(swTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });

      // Character Creator
      await clickTabAndWait(page, "characters", ["codirector-content-characters"]);
      const ccTab = page.getByTestId("codirector-content-tab-characters");
      await expect(ccTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });

      // Spatial Map
      await clickTabAndWait(page, "spatial_map", [
        "codirector-content-spatial-map",
        "spatial-map-panel",
        "spatial-map-error",
        "spatial-map-loading",
      ]);
      const smTab = page.getByTestId("codirector-content-tab-spatial_map");
      await expect(smTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });

      // Scene Creator
      await clickTabAndWait(page, "scene_creator", [
        "codirector-content-scene-creator",
        "scene-creator-panel",
        "scene-creator-empty-no-ers",
        "scene-creator-loading",
      ]);
      const scTab = page.getByTestId("codirector-content-tab-scene_creator");
      await expect(scTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });

      // Library
      await clickTabAndWait(page, "library", ["codirector-content-library"]);
      const libTab = page.getByTestId("codirector-content-tab-library");
      await expect(libTab).toHaveAttribute("aria-selected", "true", { timeout: 10_000 });
    } finally {
      observer.flush();
      await deleteProject(request, project.id);
    }
  });
});
