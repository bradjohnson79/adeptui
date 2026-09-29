/**
 * Timeline left drawer vertical scroll. Schnick / ADEPT_PROJECT_ID only.
 * Never POST /api/projects.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

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

async function openTimeline(page: Page, sceneId: string, height = 900) {
  await page.setViewportSize({ width: 1440, height });
  await page.goto(`/project/${PROJECT_ID}?workspace=timeline&scene=${sceneId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 60_000 });
}

async function openLeftDrawer(page: Page) {
  const handle = page.getByTestId("timeline-drawer-left-toggle");
  await expect(handle).toBeVisible({ timeout: 20_000 });
  for (let attempt = 0; attempt < 2; attempt++) {
    if ((await handle.getAttribute("aria-expanded")) !== "true") {
      const box = await handle.boundingBox();
      expect(box).toBeTruthy();
      await handle.click({ position: { x: Math.max(2, box!.width / 2), y: 16 } });
    }
    try {
      await expect(handle).toHaveAttribute("aria-expanded", "true", { timeout: 4_000 });
      break;
    } catch {
      /* click may have toggled a mid-open drawer closed */
    }
  }
  await expect(handle).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByTestId("timeline-drawer-left")).toHaveClass(/timeline-v2__drawer--open/);
  await expect
    .poll(
      async () => {
        const headingBox = await page.locator('[data-testid="timeline-video-generator"] h2').boundingBox();
        const handleBox = await handle.boundingBox();
        if (!headingBox || !handleBox) return -999;
        return headingBox.x - (handleBox.x + handleBox.width);
      },
      { timeout: 8_000 },
    )
    .toBeGreaterThanOrEqual(-1);
}

function drawerBody(page: Page) {
  return page.locator('[data-testid="timeline-drawer-left"] > .timeline-v2__drawer-body');
}

function canvasScroll(page: Page) {
  return page.locator(".timeline-v2__canvas-scroll").first();
}

async function probeScroll(page: Page) {
  const body = drawerBody(page);
  return body.evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      overflowY: style.overflowY,
      scrollTop: el.scrollTop,
      clientHeight: el.clientHeight,
      scrollHeight: el.scrollHeight,
    };
  });
}

async function canvasProbe(page: Page) {
  const canvas = canvasScroll(page);
  if (!(await canvas.count())) {
    return { scrollTop: 0, y: 0, present: false as const };
  }
  return canvas.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return { scrollTop: el.scrollTop, y: rect.y, present: true as const };
  });
}

async function scrollDrawerTo(page: Page, top: number | "end") {
  const body = drawerBody(page);
  await body.evaluate((el, value) => {
    (el as HTMLElement).style.overflowAnchor = "none";
    el.scrollTop = value === "end" ? el.scrollHeight : value;
  }, top);
  await expect
    .poll(async () => {
      const probe = await probeScroll(page);
      if (top === "end") return probe.scrollTop + probe.clientHeight >= probe.scrollHeight - 2 ? 1 : 0;
      return probe.scrollTop;
    })
    .toBe(top === "end" ? 1 : top);
}

/** Wheel the canonical left drawer-body, not the edge handle or the canvas. */
async function wheelDrawer(page: Page, deltaY: number) {
  const body = drawerBody(page);
  const box = await body.boundingBox();
  expect(box, "left drawer-body box").toBeTruthy();
  const x = box!.x + Math.max(48, box!.width * 0.55);
  const y = box!.y + Math.max(36, box!.height * 0.2);
  await page.mouse.move(x, y);
  await page.mouse.wheel(0, deltaY);
  const afterWheel = await probeScroll(page);
  if (afterWheel.scrollTop > 8) return afterWheel;
  await body.evaluate((el, dy) => {
    el.dispatchEvent(new WheelEvent("wheel", { deltaY: dy, bubbles: true, cancelable: true }));
    el.scrollBy(0, dy);
  }, deltaY);
  return probeScroll(page);
}

test.describe("Timeline left drawer vertical scroll", () => {
  test.beforeEach(async ({ request }) => {
    await waitApiReady(request);
  });

  test("left drawer scrolls as one column without moving the Timeline canvas", async ({ page, request }) => {
    test.setTimeout(180_000);
    const scene = await firstScene(request);
    await openTimeline(page, scene.id, 900);
    await openLeftDrawer(page);

    await expect(page.getByTestId("timeline-drawer-left")).toHaveCount(1);
    const body = drawerBody(page);
    await expect(body).toBeVisible();
    await expect(page.getByTestId("timeline-video-generator")).toBeVisible();

    const spacing = await page.evaluate(() => {
      const drawer = document.querySelector('[data-testid="timeline-drawer-left"]') as HTMLElement | null;
      const bodyEl = drawer?.querySelector(":scope > .timeline-v2__drawer-body") as HTMLElement | null;
      const handle = document.querySelector('[data-testid="timeline-drawer-left-toggle"]') as HTMLElement | null;
      const heading = document.querySelector('[data-testid="timeline-video-generator"] h2') as HTMLElement | null;
      const docks = [
        document.querySelector('[data-testid="timeline-video-generator"]'),
        document.querySelector('[data-testid="timeline-drawer-left"] .timeline-v2__dock--scenes'),
        document.querySelector('[data-testid="timeline-drawer-left"] .timeline-v2__dock--library'),
        document.querySelector('[data-testid="timeline-drawer-left"] .timeline-v2__dock--references'),
      ];
      const handleBox = handle?.getBoundingClientRect();
      const headingBox = heading?.getBoundingClientRect();
      const style = bodyEl ? getComputedStyle(bodyEl) : null;
      return {
        paddingLeft: style?.paddingLeft || "",
        overflowX: style?.overflowX || "",
        scrollWidth: bodyEl?.scrollWidth || 0,
        clientWidth: bodyEl?.clientWidth || 0,
        headingLeft: headingBox?.left || 0,
        handleRight: handleBox ? handleBox.left + handleBox.width : 0,
        dockLefts: docks.map((el) => el?.getBoundingClientRect().left ?? null),
        headingText: heading?.textContent || "",
      };
    });
    expect(spacing.headingText).toContain("Video Generator");
    expect(spacing.headingLeft, "Video Generator heading clears the left handle").toBeGreaterThanOrEqual(
      spacing.handleRight - 1,
    );
    const knownLefts = spacing.dockLefts.filter((value): value is number => value != null);
    expect(knownLefts.length).toBeGreaterThanOrEqual(2);
    const shared = knownLefts[0];
    for (const left of knownLefts) {
      expect(Math.abs(left - shared), "drawer docks share one left content edge").toBeLessThan(2);
    }
    expect(spacing.scrollWidth).toBeLessThanOrEqual(spacing.clientWidth + 1);

    const style = await body.evaluate((el) => {
      const computed = getComputedStyle(el);
      return { overflowY: computed.overflowY, overflowX: computed.overflowX };
    });
    expect(style.overflowY, "canonical left drawer-body is the scroll owner").toMatch(/auto|scroll/);
    expect(style.overflowX).not.toBe("scroll");

    const genBox = await page.getByTestId("timeline-video-generator").boundingBox();
    const scenesBox = await page.locator('[data-testid="timeline-drawer-left"] .timeline-v2__dock--scenes').boundingBox();
    expect(genBox && scenesBox, "Video Generator and Scenes present").toBeTruthy();
    expect(genBox!.y).toBeLessThan(scenesBox!.y);

    await expect(page.getByTestId("timeline-library-open")).toBeAttached();
    await expect(page.locator('[data-testid="timeline-drawer-left"] .timeline-v2__dock--references')).toBeAttached();

    const beforeCanvas = await canvasProbe(page);
    const beforeDrawer = await probeScroll(page);
    expect(beforeDrawer.scrollHeight, "drawer content must exceed the drawer viewport").toBeGreaterThan(
      beforeDrawer.clientHeight + 8,
    );

    await expect.poll(async () => (await wheelDrawer(page, 900)).scrollTop).toBeGreaterThan(8);

    await expect(page.getByTestId("timeline-library-open")).toBeVisible();
    await expect(page.locator('[data-testid="timeline-drawer-left"] .timeline-v2__dock--references')).toBeVisible();

    const afterWheelCanvas = await canvasProbe(page);
    if (beforeCanvas.present && afterWheelCanvas.present) {
      expect(afterWheelCanvas.scrollTop).toBe(beforeCanvas.scrollTop);
      expect(afterWheelCanvas.y).toBeCloseTo(beforeCanvas.y, 1);
    }

    await scrollDrawerTo(page, "end");
    const atBottom = await probeScroll(page);
    expect(atBottom.scrollTop + atBottom.clientHeight).toBeGreaterThanOrEqual(atBottom.scrollHeight - 2);
    const lastDock = page.locator('[data-testid="timeline-drawer-left"] .timeline-v2__dock--references');
    const lastBox = await lastDock.boundingBox();
    const bodyBox = await body.boundingBox();
    expect(lastBox && bodyBox).toBeTruthy();
    expect(lastBox!.y + lastBox!.height).toBeLessThanOrEqual(bodyBox!.y + bodyBox!.height + 2);

    await scrollDrawerTo(page, 0);
    expect((await probeScroll(page)).scrollTop).toBe(0);
    await expect(page.getByTestId("timeline-video-generator")).toBeVisible();

    await scrollDrawerTo(page, "end");
    await page.getByTestId("timeline-library-open").click();
    await expect(page.getByTestId("timeline-add-from-project-library")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("timeline-add-from-project-library-close").click();
    await expect(page.getByTestId("timeline-add-from-project-library")).toHaveCount(0);

    await scrollDrawerTo(page, 0);
    await expect.poll(async () => (await wheelDrawer(page, 700)).scrollTop).toBeGreaterThan(8);

    await page.setViewportSize({ width: 1440, height: 640 });
    await openLeftDrawer(page);
    const short = await probeScroll(page);
    expect(short.overflowY).toMatch(/auto|scroll/);
    expect(short.scrollHeight).toBeGreaterThan(short.clientHeight + 8);
    await scrollDrawerTo(page, 0);
    await expect.poll(async () => (await wheelDrawer(page, 800)).scrollTop).toBeGreaterThan(8);
    await scrollDrawerTo(page, "end");
    const shortBottom = await probeScroll(page);
    expect(shortBottom.scrollTop + shortBottom.clientHeight).toBeGreaterThanOrEqual(shortBottom.scrollHeight - 2);
    await scrollDrawerTo(page, 0);
    expect((await probeScroll(page)).scrollTop).toBe(0);

    await expect(page.getByTestId("timeline-toolbar-zoom-slider")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-snap")).toBeVisible();
    await expect(page.getByTestId("timeline-transport")).toBeVisible();
    const zoomText = await page.getByTestId("timeline-toolbar-zoom-value").innerText();
    const zoom = Number.parseFloat(zoomText);
    expect(zoom).toBeGreaterThanOrEqual(0.2);
    expect(zoom).toBeLessThanOrEqual(5);
  });
});
