/**
 * Timeline V2 layout geometry + theme regression. Schnick Coffee only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

const REQUIRED_LABELS = [
  "timeline-v2-label-batches",
  "timeline-v2-label-visual",
  "timeline-v2-label-timed-instructions",
  "timeline-v2-label-audio",
  "timeline-v2-label-sfx",
  "timeline-v2-label-lip-sync",
] as const;

async function waitApiReady(request: APIRequestContext) {
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
          return res.ok();
        } catch {
          return false;
        }
      },
      { timeout: 90_000 },
    )
    .toBeTruthy();
}

async function firstScene(request: APIRequestContext) {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/scenes`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const scenes = body.scenes || body.items || body || [];
  const scene = Array.isArray(scenes) ? scenes[0] : null;
  expect(scene?.id).toBeTruthy();
  return scene as { id: string };
}

async function openTimeline(page: Page, sceneId: string) {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
  await expect(page.locator(".timeline-v2")).toBeVisible();
  await expect(page.getByTestId("timeline-v2-label-batches")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("timeline-v2-label-visual")).toBeVisible({ timeout: 60_000 });
}

type LabelProbe = {
  testId: string;
  color: string;
  opacity: string;
  transform: string;
  filter: string;
  visibility: string;
  scopedVar: string;
  width: number;
  left: number;
  right: number;
  contentLeft: number;
};

async function probeLabels(page: Page): Promise<LabelProbe[]> {
  return page.evaluate((ids) => {
    const root = document.querySelector(".timeline-v2") as HTMLElement | null;
    const scopedVar = root ? getComputedStyle(root).getPropertyValue("--timeline-v2-track-label-color").trim() : "";
    return ids.map((testId) => {
      const el = document.querySelector(`[data-testid="${testId}"]`) as HTMLElement | null;
      if (!el) {
        return {
          testId,
          color: "",
          opacity: "",
          transform: "",
          filter: "",
          visibility: "",
          scopedVar,
          width: 0,
          left: 0,
          right: 0,
          contentLeft: 0,
        };
      }
      const style = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      const row = el.closest(".timeline-v2__track-row");
      const content = row?.querySelector(".timeline-v2__track-content") as HTMLElement | null;
      return {
        testId,
        color: style.color,
        opacity: style.opacity,
        transform: style.transform,
        filter: style.filter,
        visibility: style.visibility,
        scopedVar,
        width: Math.round(rect.width),
        left: rect.left,
        right: rect.right,
        contentLeft: content ? content.getBoundingClientRect().left : 0,
      };
    });
  }, [...REQUIRED_LABELS]);
}

function isScopedV2LabelColor(value: string) {
  const v = value.trim().toLowerCase();
  // Authored #e1e8f2 (opaque light rail text).
  return /225\s*,\s*232\s*,\s*242/.test(v) || /#e1e8f2/.test(v);
}

function assertReadableScoped(probes: LabelProbe[], theme: string) {
  for (const probe of probes) {
    expect(probe.color, `${probe.testId} missing in ${theme}`).toBeTruthy();
    expect(probe.opacity, `${probe.testId} opacity ${theme}`).toBe("1");
    expect(probe.transform, `${probe.testId} transform ${theme}`).toBe("none");
    expect(probe.filter === "none" || probe.filter === "", `${probe.testId} filter ${theme}`).toBeTruthy();
    expect(probe.visibility, `${probe.testId} visibility ${theme}`).toBe("visible");
    expect(
      isScopedV2LabelColor(probe.scopedVar) || isScopedV2LabelColor(probe.color),
      `scoped var missing in ${theme}: ${probe.scopedVar} color=${probe.color}`,
    ).toBeTruthy();
    expect(
      isScopedV2LabelColor(probe.color),
      `${probe.testId} must use scoped V2 color in ${theme}, got ${probe.color}`,
    ).toBeTruthy();
    expect(probe.color, `${probe.testId} must not use aurora-day near-black token in ${theme}`).not.toMatch(/18,\s*31,\s*45/);
    expect(probe.width, `${probe.testId} label width ${theme}`).toBeGreaterThanOrEqual(120);
    expect(probe.width, `${probe.testId} label width ${theme}`).toBeLessThanOrEqual(150);
    if (probe.contentLeft) {
      expect(probe.contentLeft, `${probe.testId} content overlap ${theme}`).toBeGreaterThanOrEqual(probe.right - 2);
    }
  }
}

test.describe("Timeline V2 layout", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("geometry, no Expand, labels readable in default and aurora-day", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id);

    await expect(page.getByTestId("workspace-expand")).toHaveCount(0);
    await expect(page.getByTestId("workspace-fullscreen-controls")).toHaveCount(1);
    await expect(page.getByTestId("timeline-drawer-left-toggle")).toBeVisible();
    await expect(page.getByTestId("timeline-drawer-right-toggle")).toBeVisible();
    await expect(page.getByTestId("timeline-focus-workspace")).toBeVisible();
    await expect(page.getByTestId("timeline-splitter-left")).toBeVisible();
    await expect(page.getByTestId("timeline-splitter-right")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-inspector")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-codirector")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-hotkeys")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-timed-instructions")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-audio")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-sfx")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-lip-sync")).toBeVisible({ timeout: 30_000 });

    const geometry = await page.evaluate(() => {
      const left = document.querySelector(".timeline-v2__left")?.getBoundingClientRect();
      const main = document.querySelector(".timeline-v2__main")?.getBoundingClientRect();
      const right = document.querySelector(".timeline-v2__right")?.getBoundingClientRect();
      const preview = document.querySelector('[data-testid="timeline-focus-viewer"]')?.getBoundingClientRect();
      return {
        leftRight: left?.right || 0,
        mainLeft: main?.left || 0,
        mainRight: main?.right || 0,
        rightLeft: right?.left || 0,
        previewWidth: preview?.width || 0,
        mainWidth: main?.width || 0,
      };
    });
    expect(geometry.mainLeft).toBeGreaterThanOrEqual(geometry.leftRight - 2);
    expect(geometry.rightLeft).toBeGreaterThanOrEqual(geometry.mainRight - 2);
    expect(geometry.mainWidth).toBeGreaterThanOrEqual(500);
    expect(geometry.previewWidth).toBeGreaterThanOrEqual(240);

    const defaultProbes = await probeLabels(page);
    assertReadableScoped(defaultProbes, "default");

    const overlay = await page.evaluate(() => {
      const label = document.querySelector('[data-testid="timeline-v2-label-batches"]');
      const gutter = document.querySelector(".timeline-v2__playhead-gutter");
      const rail = document.querySelector(".timeline-v2__playhead-rail");
      return {
        labelZ: label ? getComputedStyle(label).zIndex : "",
        labelColor: label ? getComputedStyle(label).color : "",
        gutterBg: gutter ? getComputedStyle(gutter).backgroundColor : "",
        railZ: rail ? getComputedStyle(rail).zIndex : "",
      };
    });
    expect(overlay.gutterBg, "playhead gutter must not paint an opaque plate over labels").toMatch(/rgba\(0,\s*0,\s*0,\s*0\)|transparent/);
    expect(Number(overlay.labelZ), "labels must stack above the playhead rail").toBeGreaterThan(Number(overlay.railZ));
    expect(overlay.labelColor).toMatch(/225,\s*232,\s*242|#e1e8f2/i);

    await page.evaluate(() => document.documentElement.setAttribute("data-theme", "aurora-day"));
    const dayProbes = await probeLabels(page);
    assertReadableScoped(dayProbes, "aurora-day");

    const left = page.getByTestId("timeline-splitter-left");
    const box = await left.boundingBox();
    expect(box).toBeTruthy();
    const before = await page.locator(".timeline-v2__body").evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    await page.mouse.move(box!.x + box!.width / 2, box!.y + 40);
    await page.mouse.down();
    await page.mouse.move(box!.x + 70, box!.y + 40);
    await page.mouse.up();
    const afterDrag = await page.locator(".timeline-v2__body").evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(afterDrag).not.toEqual(before);
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
    const afterReload = await page.locator(".timeline-v2__body").evaluate((el) => getComputedStyle(el).gridTemplateColumns);
    expect(afterReload).toEqual(afterDrag);
  });

  test("retractable drawers persist, overlay, and do not pan Preview", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id);
    await page.getByTestId("timeline-reset-layout").click();
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-left-placement", "push");
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-right-placement", "push");

    const preview = page.getByTestId("timeline-focus-viewer");
    const tracks = page.locator(".timeline-v2__tracks");
    const inspectorPanel = page.getByTestId("timeline-right-panel-inspector");
    const library = page.locator(".timeline-v2__dock--library");
    const scenesDock = page.locator(".timeline-v2__dock--scenes");
    const refsDock = page.locator(".timeline-v2__dock--references");

    const previewWidthOpen = await preview.evaluate((el) => el.getBoundingClientRect().width);
    await page.evaluate(() => {
      const inspector = document.querySelector('[data-testid="timeline-inspector"]') as HTMLElement | null;
      if (inspector) inspector.dataset.keepAlive = "drawer";
    });

    const storedOpen = await page.evaluate(() => {
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      return raw ? (JSON.parse(raw) as { leftWidth: number; rightWidth: number }) : { leftWidth: 0, rightWidth: 0 };
    });

    await page.getByTestId("timeline-drawer-right-toggle").click();
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-right-placement", "closed");
    const previewWidthClosed = await preview.evaluate((el) => el.getBoundingClientRect().width);
    expect(previewWidthClosed).toBeGreaterThan(previewWidthOpen + 40);
    const storedClosed = await page.evaluate(() => {
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      return raw ? (JSON.parse(raw) as { rightWidth: number; rightDrawerOpen: boolean }) : { rightWidth: 0, rightDrawerOpen: true };
    });
    expect(storedClosed.rightDrawerOpen).toBe(false);
    expect(storedClosed.rightWidth).toBe(storedOpen.rightWidth);

    await page.getByTestId("timeline-drawer-right-toggle").click();
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-right-placement", "push");
    await expect(page.getByTestId("timeline-inspector")).toHaveAttribute("data-keep-alive", "drawer");
    await expect(page.getByTestId("timeline-tab-inspector")).toBeVisible();

    const previewTop = await preview.evaluate((el) => el.getBoundingClientRect().top);
    const tracksTop = await tracks.evaluate((el) => el.getBoundingClientRect().top);
    await inspectorPanel.evaluate((el) => {
      el.scrollTop = 240;
    });
    await expect.poll(async () => inspectorPanel.evaluate((el) => el.scrollTop)).toBeGreaterThan(20);
    expect(Math.abs((await preview.evaluate((el) => el.getBoundingClientRect().top)) - previewTop)).toBeLessThan(2);
    expect(Math.abs((await tracks.evaluate((el) => el.getBoundingClientRect().top)) - tracksTop)).toBeLessThan(2);

    await page.getByTestId("timeline-tab-hotkeys").click();
    const hotkeysPanel = page.getByTestId("timeline-right-panel-hotkeys");
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
    const previewTopHotkeys = await preview.evaluate((el) => el.getBoundingClientRect().top);
    await hotkeysPanel.evaluate((el) => {
      el.scrollTop = 180;
    });
    await expect.poll(async () => hotkeysPanel.evaluate((el) => el.scrollTop)).toBeGreaterThan(10);
    expect(Math.abs((await preview.evaluate((el) => el.getBoundingClientRect().top)) - previewTopHotkeys)).toBeLessThan(2);

    await page.getByTestId("timeline-tab-inspector").click();
    const scenesTop = await scenesDock.evaluate((el) => el.getBoundingClientRect().top);
    const refsVisible = await refsDock.evaluate((el) => el.getBoundingClientRect().height > 8);
    expect(refsVisible).toBeTruthy();
    await library.evaluate((el) => {
      el.scrollTop = 160;
    });
    await expect(scenesDock).toBeVisible();
    await expect(refsDock).toBeVisible();
    expect(Math.abs((await scenesDock.evaluate((el) => el.getBoundingClientRect().top)) - scenesTop)).toBeLessThan(8);

    await page.getByTestId("timeline-drawer-left-toggle").click();
    await page.getByTestId("timeline-drawer-left-toggle").click();
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-left-placement", "push");

    await page.setViewportSize({ width: 1100, height: 900 });
    await expect
      .poll(async () => page.locator(".timeline-v2__body").getAttribute("data-right-placement"), { timeout: 10_000 })
      .toBe("overlay");
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-left-placement", "push");
    const overlayGeometry = await page.evaluate(() => {
      const main = document.querySelector(".timeline-v2__main")?.getBoundingClientRect();
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      const layout = raw ? JSON.parse(raw) : {};
      return {
        mainWidth: main?.width || 0,
        leftWidth: layout.leftWidth,
        rightWidth: layout.rightWidth,
      };
    });
    expect(overlayGeometry.mainWidth).toBeGreaterThanOrEqual(500);
    expect(overlayGeometry.leftWidth).toBe(storedOpen.leftWidth);
    expect(overlayGeometry.rightWidth).toBe(storedOpen.rightWidth);

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByTestId("timeline-focus-workspace").click();
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-left-placement", "closed");
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-right-placement", "closed");
    await expect(page.getByTestId("workspace-fullscreen-controls").locator("button").first()).toHaveAttribute("aria-pressed", "false");
    expect(await page.evaluate(() => document.fullscreenElement)).toBeNull();

    await page.getByTestId("timeline-reset-layout").click();
    const reset = await page.evaluate(() => {
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      return raw ? JSON.parse(raw) : {};
    });
    expect(reset.leftDrawerOpen).toBe(true);
    expect(reset.rightDrawerOpen).toBe(true);
    expect(reset.leftWidth).toBe(280);
    expect(reset.rightWidth).toBe(320);
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-left-placement", "push");
    await expect(page.locator(".timeline-v2__body")).toHaveAttribute("data-right-placement", "push");

    await expect(page.locator(".scene-block").first()).toBeVisible();
    await page.locator(".scene-block").first().click();
    await expect(page.getByTestId("asset-library-list")).toBeVisible();
    const libraryItem = page.locator("[data-testid^='asset-library-item-']").first();
    if (await libraryItem.count()) {
      await libraryItem.click();
      const addRef = page.locator("[data-testid^='asset-add-reference-']").first();
      await expect(addRef).toBeVisible();
    }
    await page.getByTestId("timeline-tab-inspector").click();
    await expect(page.getByTestId("timeline-inspector")).toBeVisible();
    await page.getByTestId("timeline-tab-codirector").click();
    await expect(page.getByTestId("timeline-codirector-rail")).toBeVisible();
    await page.getByTestId("timeline-tab-hotkeys").click();
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
  });
});
