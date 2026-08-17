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
});
