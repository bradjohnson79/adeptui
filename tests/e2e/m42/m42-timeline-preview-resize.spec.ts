import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

/**
 * Timeline Generator UX — remove redundant Lip Sync Clip button + Preview Monitor resize.
 */

const ARTIFACT_DIR = path.join("artifacts", "m42", "timeline-preview-resize");

async function openTimeline(page: Page): Promise<string | null> {
  const projectsRes = await page.request.get("/api/projects");
  if (!projectsRes.ok()) return null;
  const projects = (await projectsRes.json()) as Array<{ id?: string; archived?: number }>;
  const project = (projects || []).find((p) => p?.id && !p.archived) || (projects || [])[0];
  if (!project?.id) return null;

  await page.goto(`/project/${project.id}?workspace=timeline`);
  const shell = page.getByTestId("timeline-editor-shell");
  if (!(await shell.isVisible().catch(() => false))) {
    const timelineNav = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineNav.count()) > 0) {
      await timelineNav.click();
    } else {
      const alt = page.getByRole("link", { name: /Timeline/i }).first();
      if ((await alt.count()) > 0) await alt.click();
    }
  }
  await expect(shell).toBeVisible({ timeout: 20000 });
  return project.id;
}

async function monitorHeight(page: Page): Promise<number> {
  return page.getByTestId("timeline-workspace-monitor").evaluate((el) => el.getBoundingClientRect().height);
}

async function tracksHeight(page: Page): Promise<number> {
  return page.getByTestId("timeline-workspace-tracks").evaluate((el) => el.getBoundingClientRect().height);
}

test.describe("Timeline Generator Preview Resize UX", () => {
  test("Lip Sync Clip button removed; Preview Monitor resizes, scrolls, persists", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    const projectId = await openTimeline(page);
    if (!projectId) {
      test.skip(true, "No project/Timeline available");
      return;
    }

    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-add")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-remove")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-clip")).toHaveCount(0);
    await expect(page.getByText("+ Lip Sync Clip")).toHaveCount(0);

    const divider = page.getByTestId("timeline-monitor-divider");
    await expect(divider).toBeVisible();
    await expect(divider).toHaveAttribute("role", "separator");
    await expect(divider).toHaveAttribute("aria-orientation", "horizontal");

    const toolbar = page.getByTestId("timeline-toolbar");
    await expect(toolbar).toBeVisible();

    // Start from a compact baseline so enlargement headroom is available.
    await divider.focus();
    await page.keyboard.press("Home");
    const ariaMin = Number(await divider.getAttribute("aria-valuemin"));
    const ariaMax = Number(await divider.getAttribute("aria-valuemax"));
    expect(ariaMax).toBeGreaterThan(ariaMin + 100);
    await expect.poll(async () => monitorHeight(page)).toBeLessThanOrEqual(ariaMin + 8);

    const initialPreview = await monitorHeight(page);
    const initialTracks = await tracksHeight(page);
    expect(initialPreview).toBeGreaterThan(200);

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "01-default-preview.png"), fullPage: false });

    const box = await divider.boundingBox();
    expect(box).toBeTruthy();
    const startX = box!.x + box!.width / 2;
    const startY = box!.y + box!.height / 2;
    // Drag divider downward to enlarge the top Preview Monitor (natural top-pane math).
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY + 280, { steps: 20 });
    await page.mouse.up();

    await expect
      .poll(async () => monitorHeight(page))
      .toBeGreaterThan(initialPreview + 100);

    // Keyboard End expands to the current max — proves clamp + a11y path.
    await divider.focus();
    await page.keyboard.press("End");
    await expect
      .poll(async () => monitorHeight(page))
      .toBeGreaterThanOrEqual(ariaMax - 8);

    const expandedPreview = await monitorHeight(page);
    const compactedTracks = await tracksHeight(page);
    expect(compactedTracks).toBeLessThan(initialTracks);
    await expect(toolbar).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-zoom-in")).toBeVisible();

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "02-expanded-preview.png"), fullPage: false });

    const scroll = page.getByTestId("timeline-track-scroll");
    await expect(scroll).toBeVisible();
    const overflowY = await scroll.evaluate((el) => {
      const style = window.getComputedStyle(el);
      return {
        overflowY: style.overflowY,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      };
    });
    expect(["auto", "scroll", "overlay"]).toContain(overflowY.overflowY);
    if (overflowY.scrollHeight > overflowY.clientHeight + 4) {
      const before = await scroll.evaluate((el) => el.scrollTop);
      await scroll.evaluate((el) => {
        el.scrollTop = Math.min(el.scrollHeight, el.scrollTop + 80);
      });
      const after = await scroll.evaluate((el) => el.scrollTop);
      expect(after).toBeGreaterThan(before);
    }

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "03-compact-timeline-scroll.png"), fullPage: false });

    await expect(page.getByTestId("timeline-ruler")).toBeVisible();
    await page.getByTestId("timeline-ruler").click({ position: { x: 40, y: 8 } });
    await expect(page.getByTestId("timeline-playhead")).toBeVisible();

    const persistedHeight = expandedPreview;
    await page.reload();
    await expect(page.getByTestId("timeline-editor-shell")).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId("timeline-workspace-monitor")).toBeVisible();
    await expect
      .poll(async () => monitorHeight(page))
      .toBeGreaterThan(persistedHeight - 24);

    await page.screenshot({ path: path.join(ARTIFACT_DIR, "04-restored-after-reload.png"), fullPage: false });

    const beforeFullscreen = await monitorHeight(page);
    await page.getByTestId("workspace-fullscreen-toggle-timeline").click();
    await page.getByTestId("workspace-fullscreen-toggle-timeline").click();
    await expect(page.getByTestId("timeline-monitor-divider")).toBeVisible();
    await expect
      .poll(async () => monitorHeight(page))
      .toBeGreaterThan(beforeFullscreen - 24);

    await page.setViewportSize({ width: 1366, height: 768 });
    await expect(page.getByTestId("timeline-workspace-stack")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-workspace-tracks")).toBeVisible();
    const stackOverflow = await page.getByTestId("timeline-workspace-stack").evaluate((el) => {
      const parent = el.parentElement;
      return {
        stackHeight: el.getBoundingClientRect().height,
        parentHeight: parent?.getBoundingClientRect().height ?? 0,
        stackScroll: el.scrollHeight - el.clientHeight,
      };
    });
    expect(stackOverflow.stackHeight).toBeGreaterThan(300);
    expect(stackOverflow.stackScroll).toBeLessThan(40);

    // Keyboard clamp still works after viewport resize
    await divider.focus();
    await page.keyboard.press("Home");
    const minHeight = await monitorHeight(page);
    await page.keyboard.press("End");
    const maxHeight = await monitorHeight(page);
    expect(maxHeight).toBeGreaterThan(minHeight + 40);
  });
});
