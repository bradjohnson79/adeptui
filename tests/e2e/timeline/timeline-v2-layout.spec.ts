/**
 * Timeline V2 overlay-drawer geometry + theme regression. Schnick Coffee only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const STILLS_DIR = path.join("artifacts", "timeline-overlay-drawer");

const REQUIRED_LABELS = [
  "timeline-v2-label-batches",
  "timeline-v2-label-visual",
  "timeline-v2-label-timed-prompt",
  "timeline-v2-label-audio",
  "timeline-v2-label-sfx",
  "timeline-v2-label-lip-sync",
] as const;

type Box = { x: number; y: number; width: number; height: number };

type WorkspaceProbe = {
  workspace: Box;
  preview: Box;
  canvas: Box;
  playhead: Box;
};

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
  await expect(page.getByTestId("timeline-playhead")).toBeVisible({ timeout: 30_000 });
}

async function waitDrawerSettled(page: Page) {
  await page.waitForTimeout(240);
}

async function waitPlayheadStable(page: Page) {
  await expect(page.getByTestId("timeline-playhead")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: /Batch 1/ })).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(
      async () => {
        const samples: number[] = [];
        for (let i = 0; i < 4; i += 1) {
          samples.push(await page.getByTestId("timeline-playhead").evaluate((el) => el.getBoundingClientRect().x));
          if (i < 3) await page.waitForTimeout(140);
        }
        return Math.max(...samples) - Math.min(...samples);
      },
      { timeout: 15_000 },
    )
    .toBeLessThanOrEqual(1);
}

async function clickDrawerHandle(page: Page, testId: "timeline-drawer-left-toggle" | "timeline-drawer-right-toggle") {
  const handle = page.getByTestId(testId);
  const box = await handle.boundingBox();
  expect(box).toBeTruthy();
  await handle.click({ position: { x: Math.max(2, box!.width / 2), y: 16 } });
}

function assertBoxClose(before: Box, after: Box, label: string) {
  expect(Math.abs(after.x - before.x), `${label} x`).toBeLessThanOrEqual(1);
  expect(Math.abs(after.y - before.y), `${label} y`).toBeLessThanOrEqual(1);
  expect(Math.abs(after.width - before.width), `${label} width`).toBeLessThanOrEqual(1);
  expect(Math.abs(after.height - before.height), `${label} height`).toBeLessThanOrEqual(1);
}

function assertWorkspaceInvariant(before: WorkspaceProbe, after: WorkspaceProbe, label: string) {
  assertBoxClose(before.workspace, after.workspace, `${label} workspace`);
  assertBoxClose(before.preview, after.preview, `${label} preview`);
  assertBoxClose(before.canvas, after.canvas, `${label} timeline canvas`);
  assertBoxClose(before.playhead, after.playhead, `${label} playhead`);
}

async function measureWorkspace(page: Page): Promise<WorkspaceProbe> {
  return page.evaluate(() => {
    const box = (el: Element | null): Box => {
      if (!el) return { x: 0, y: 0, width: 0, height: 0 };
      const r = el.getBoundingClientRect();
      return { x: r.x, y: r.y, width: r.width, height: r.height };
    };
    return {
      workspace: box(document.querySelector('[data-testid="timeline-v2-workspace"]')),
      preview: box(document.querySelector('[data-testid="timeline-focus-viewer"]')),
      canvas: box(document.querySelector(".timeline-v2__tracks")),
      playhead: box(document.querySelector('[data-testid="timeline-playhead"]')),
    };
  });
}

async function drawerTransform(page: Page, testId: string) {
  return page.getByTestId(testId).evaluate((el) => {
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return {
      transform: style.transform,
      transition: style.transition,
      width: rect.width,
      tx: (() => {
        const m = style.transform.match(/matrix\(([^)]+)\)/);
        if (!m) return style.transform === "none" ? 0 : Number.NaN;
        return Number(m[1].split(",")[4]);
      })(),
    };
  });
}

function isOpenTransform(transform: string, tx: number) {
  return transform === "none" || transform === "matrix(1, 0, 0, 1, 0, 0)" || Math.abs(tx) <= 1;
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
    await page.getByTestId("timeline-reset-layout").click();
    await waitDrawerSettled(page);

    await expect(page.getByTestId("workspace-expand")).toHaveCount(0);
    await expect(page.getByTestId("workspace-fullscreen-controls")).toHaveCount(1);
    await expect(page.getByTestId("timeline-drawer-left-toggle")).toBeVisible();
    await expect(page.getByTestId("timeline-drawer-right-toggle")).toBeVisible();
    await expect(page.getByTestId("timeline-focus-workspace")).toBeVisible();
    await expect(page.getByTestId("timeline-splitter-left")).toHaveCount(1);
    await expect(page.getByTestId("timeline-splitter-right")).toHaveCount(1);
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-inspector")).toHaveCount(1);
    await expect(page.getByTestId("timeline-tab-codirector")).toHaveCount(1);
    await expect(page.getByTestId("timeline-tab-hotkeys")).toHaveCount(1);
    await expect(page.getByTestId("timeline-v2-label-timed-prompt")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-audio")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-sfx")).toBeVisible();
    await expect(page.getByTestId("timeline-v2-label-lip-sync")).toBeVisible({ timeout: 30_000 });

    const geometry = await page.evaluate(() => {
      const body = document.querySelector(".timeline-v2__body")?.getBoundingClientRect();
      const workspace = document.querySelector('[data-testid="timeline-v2-workspace"]')?.getBoundingClientRect();
      const preview = document.querySelector('[data-testid="timeline-focus-viewer"]')?.getBoundingClientRect();
      return {
        bodyX: body?.x || 0,
        bodyWidth: body?.width || 0,
        workspaceX: workspace?.x || 0,
        workspaceWidth: workspace?.width || 0,
        previewWidth: preview?.width || 0,
      };
    });
    expect(Math.abs(geometry.workspaceX - geometry.bodyX)).toBeLessThanOrEqual(1);
    expect(Math.abs(geometry.workspaceWidth - geometry.bodyWidth)).toBeLessThanOrEqual(1);
    expect(geometry.workspaceWidth).toBeGreaterThanOrEqual(500);
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
  });

  test("overlay drawers leave center, preview, timeline, and playhead literally invariant", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id);
    await page.getByTestId("timeline-reset-layout").click();
    await waitDrawerSettled(page);
    await waitPlayheadStable(page);
    await expect(page.getByTestId("timeline-drawer-left-toggle")).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("timeline-drawer-right-toggle")).toHaveAttribute("aria-expanded", "false");

    await mkdir(STILLS_DIR, { recursive: true });
    await page.screenshot({ path: path.join(STILLS_DIR, "both-closed.png"), fullPage: false });

    const closed = await measureWorkspace(page);
    expect(closed.workspace.width).toBeGreaterThan(500);
    expect(closed.playhead.width).toBeGreaterThan(0);

    const closedLeft = await drawerTransform(page, "timeline-drawer-left");
    const closedRight = await drawerTransform(page, "timeline-drawer-right");
    expect(closedLeft.tx, "closed left must sit off-canvas").toBeLessThan(-closedLeft.width + 2);
    expect(closedRight.tx, "closed right must sit off-canvas").toBeGreaterThan(closedRight.width - 2);
    expect(closedLeft.transition.toLowerCase()).toMatch(/transform/);
    expect(closedRight.transition.toLowerCase()).toMatch(/transform/);

    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await waitDrawerSettled(page);
    await expect(page.getByTestId("timeline-drawer-left-toggle")).toHaveAttribute("aria-expanded", "true");
    const leftOpen = await measureWorkspace(page);
    assertWorkspaceInvariant(closed, leftOpen, "left open");
    const leftOpenTx = await drawerTransform(page, "timeline-drawer-left");
    expect(isOpenTransform(leftOpenTx.transform, leftOpenTx.tx)).toBeTruthy();
    await page.screenshot({ path: path.join(STILLS_DIR, "left-open.png"), fullPage: false });

    await clickDrawerHandle(page, "timeline-drawer-right-toggle");
    await waitDrawerSettled(page);
    const bothOpen = await measureWorkspace(page);
    assertWorkspaceInvariant(closed, bothOpen, "both open");
    await page.screenshot({ path: path.join(STILLS_DIR, "both-open.png"), fullPage: false });

    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await waitDrawerSettled(page);
    const rightOnly = await measureWorkspace(page);
    assertWorkspaceInvariant(closed, rightOnly, "right open");
    await page.screenshot({ path: path.join(STILLS_DIR, "right-open.png"), fullPage: false });

    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await waitDrawerSettled(page);

    expect(await page.getByTestId("timeline-drawer-left").count()).toBe(1);
    expect(await page.getByTestId("timeline-drawer-right").count()).toBe(1);
    expect(await page.getByTestId("timeline-inspector").count()).toBe(1);
    expect(await page.getByTestId("asset-library-list").count()).toBe(1);
    expect(await page.getByTestId("timeline-hotkeys-pane").count()).toBe(1);

    const containment = await page.evaluate(() => {
      const left = document.querySelector('[data-testid="timeline-drawer-left"]')?.getBoundingClientRect();
      const right = document.querySelector('[data-testid="timeline-drawer-right"]')?.getBoundingClientRect();
      const scenes = document.querySelector(".timeline-v2__dock--scenes")?.getBoundingClientRect();
      const library = document.querySelector(".timeline-v2__dock--library")?.getBoundingClientRect();
      const refs = document.querySelector(".timeline-v2__dock--references")?.getBoundingClientRect();
      const inspector = document.querySelector('[data-testid="timeline-inspector"]')?.getBoundingClientRect();
      const tabs = document.querySelector(".timeline-v2__tabs")?.getBoundingClientRect();
      const inside = (inner?: DOMRect, outer?: DOMRect) =>
        Boolean(
          inner &&
            outer &&
            inner.left >= outer.left - 2 &&
            inner.right <= outer.right + 2 &&
            inner.top >= outer.top - 2 &&
            inner.bottom <= outer.bottom + 2,
        );
      return {
        scenesInLeft: inside(scenes, left),
        libraryInLeft: inside(library, left),
        refsInLeft: inside(refs, left),
        inspectorInRight: inside(inspector, right),
        tabsInRight: inside(tabs, right),
      };
    });
    expect(containment.scenesInLeft).toBeTruthy();
    expect(containment.libraryInLeft).toBeTruthy();
    expect(containment.refsInLeft).toBeTruthy();
    expect(containment.inspectorInRight).toBeTruthy();
    expect(containment.tabsInRight).toBeTruthy();

    await page.getByTestId("timeline-focus-workspace").click();
    await waitDrawerSettled(page);
    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await waitDrawerSettled(page);
    await expect.poll(async () => {
      const raw = await page.evaluate(() => localStorage.getItem("adept_timeline_workspace_layout_v1"));
      return raw ? (JSON.parse(raw) as { leftWidth: number }).leftWidth : 0;
    }).toBe(280);

    const beforeResize = await measureWorkspace(page);
    const splitter = page.getByTestId("timeline-splitter-left");
    const box = await splitter.boundingBox();
    expect(box).toBeTruthy();
    await page.mouse.move(box!.x + box!.width / 2, box!.y + 40);
    await page.mouse.down();
    await page.mouse.move(box!.x + 60, box!.y + 40);
    const midResize = await measureWorkspace(page);
    assertWorkspaceInvariant(beforeResize, midResize, "during left resize");
    await page.mouse.move(box!.x + 120, box!.y + 40);
    await page.mouse.up();
    await waitDrawerSettled(page);
    const afterResize = await measureWorkspace(page);
    assertWorkspaceInvariant(beforeResize, afterResize, "after left 280-to-400 resize");
    const resized = await page.evaluate(() => {
      const root = document.querySelector(".timeline-v2") as HTMLElement | null;
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      const layout = raw ? JSON.parse(raw) : {};
      return {
        css: root ? getComputedStyle(root).getPropertyValue("--timeline-left-width").trim() : "",
        leftWidth: layout.leftWidth as number,
      };
    });
    expect(resized.leftWidth).toBeGreaterThanOrEqual(390);
    expect(resized.leftWidth).toBeLessThanOrEqual(410);
    expect(resized.css).toBe(`${resized.leftWidth}px`);

    const preview = page.getByTestId("timeline-focus-viewer");
    const tracks = page.locator(".timeline-v2__tracks");
    const previewTop = await preview.evaluate((el) => el.getBoundingClientRect().top);
    const tracksTop = await tracks.evaluate((el) => el.getBoundingClientRect().top);
    const libraryList = page.getByTestId("asset-library-list");
    await libraryList.evaluate((el) => {
      el.scrollTop = 160;
    });
    await expect.poll(async () => libraryList.evaluate((el) => el.scrollTop)).toBeGreaterThan(10);
    expect(Math.abs((await preview.evaluate((el) => el.getBoundingClientRect().top)) - previewTop)).toBeLessThanOrEqual(1);
    expect(Math.abs((await tracks.evaluate((el) => el.getBoundingClientRect().top)) - tracksTop)).toBeLessThanOrEqual(1);

    await clickDrawerHandle(page, "timeline-drawer-right-toggle");
    await waitDrawerSettled(page);
    const inspectorPanel = page.getByTestId("timeline-right-panel-inspector");
    await inspectorPanel.evaluate((el) => {
      el.scrollTop = 240;
    });
    await expect.poll(async () => inspectorPanel.evaluate((el) => el.scrollTop)).toBeGreaterThan(20);
    expect(Math.abs((await preview.evaluate((el) => el.getBoundingClientRect().top)) - previewTop)).toBeLessThanOrEqual(1);
    expect(Math.abs((await tracks.evaluate((el) => el.getBoundingClientRect().top)) - tracksTop)).toBeLessThanOrEqual(1);

    await page.locator(".timeline-v2__dock--library button", { hasText: "video" }).click();
    await expect(page.locator(".timeline-v2__dock--library button.primary", { hasText: "video" })).toBeVisible();
    const libraryScroll = await libraryList.evaluate((el) => el.scrollTop);
    await page.getByTestId("timeline-tab-hotkeys").click();
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await clickDrawerHandle(page, "timeline-drawer-right-toggle");
    await waitDrawerSettled(page);
    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await clickDrawerHandle(page, "timeline-drawer-right-toggle");
    await waitDrawerSettled(page);
    await expect(page.locator(".timeline-v2__dock--library button.primary", { hasText: "video" })).toBeVisible();
    expect(await libraryList.evaluate((el) => el.scrollTop)).toBe(libraryScroll);
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
    await expect(page.getByTestId("timeline-tab-hotkeys")).toHaveClass(/primary/);

    await page.setViewportSize({ width: 1100, height: 900 });
    await waitDrawerSettled(page);
    const narrow = await measureWorkspace(page);
    expect(narrow.workspace.width).toBeGreaterThan(500);
    await page.screenshot({ path: path.join(STILLS_DIR, "narrow-both-open.png"), fullPage: false });
    await page.setViewportSize({ width: 1440, height: 900 });
    await waitDrawerSettled(page);
    const restored = await measureWorkspace(page);

    await page.getByTestId("timeline-focus-workspace").click();
    await waitDrawerSettled(page);
    await expect(page.getByTestId("timeline-drawer-left-toggle")).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("timeline-drawer-right-toggle")).toHaveAttribute("aria-expanded", "false");
    await expect(page.getByTestId("workspace-fullscreen-controls").locator("button").first()).toHaveAttribute("aria-pressed", "false");
    expect(await page.evaluate(() => document.fullscreenElement)).toBeNull();
    const afterFocus = await measureWorkspace(page);
    assertWorkspaceInvariant(restored, afterFocus, "focus timeline");

    await page.getByTestId("timeline-reset-layout").click();
    await waitDrawerSettled(page);
    const reset = await page.evaluate(() => {
      const raw = localStorage.getItem("adept_timeline_workspace_layout_v1");
      return raw ? JSON.parse(raw) : {};
    });
    expect(reset.leftDrawerOpen).toBe(false);
    expect(reset.rightDrawerOpen).toBe(false);
    expect(reset.leftWidth).toBe(280);
    expect(reset.rightWidth).toBe(320);

    await clickDrawerHandle(page, "timeline-drawer-left-toggle");
    await waitDrawerSettled(page);
    await expect(page.locator(".scene-block").first()).toBeVisible();
    await page.locator(".scene-block").first().evaluate((el: HTMLElement) => el.click());
    await expect(page.getByTestId("asset-library-list")).toHaveCount(1);
    const smokeLibrary = page.getByTestId("asset-library-list");
    const libraryUsable = await smokeLibrary.evaluate((el) => {
      const rect = el.getBoundingClientRect();
      return rect.height > 8 && rect.width > 8;
    });
    if (libraryUsable) {
      const libraryItem = page.locator("[data-testid^='asset-library-item-']").first();
      if (await libraryItem.count()) {
        await libraryItem.evaluate((el: HTMLElement) => el.click());
        const addRef = page.locator("[data-testid^='asset-add-reference-']").first();
        await expect(addRef).toBeAttached();
      }
    }
    await clickDrawerHandle(page, "timeline-drawer-right-toggle");
    await waitDrawerSettled(page);
    await page.getByTestId("timeline-tab-inspector").click();
    await expect(page.getByTestId("timeline-inspector")).toBeVisible();
    await page.getByTestId("timeline-tab-codirector").click();
    await expect(page.getByTestId("timeline-codirector-rail")).toBeVisible();
    await page.getByTestId("timeline-tab-hotkeys").click();
    await expect(page.getByTestId("timeline-hotkeys-pane")).toBeVisible();
  });
});
