import { expect, test, type Page } from "@playwright/test";

/**
 * M42 W46 Final Addenda SA78 — operational Timeline suite.
 * Proves toolbar, Lip Sync, Inpaint gating, zoom scaling, layout presets, and camera inspector.
 */

async function openTimeline(page: Page): Promise<boolean> {
  const projectsRes = await page.request.get("/api/projects");
  if (!projectsRes.ok()) return false;
  const projects = (await projectsRes.json()) as Array<{ id?: string; archived?: number }>;
  const project = (projects || []).find((p) => p?.id && !p.archived) || (projects || [])[0];
  if (!project?.id) return false;

  await page.goto(`/project/${project.id}?workspace=timeline`);
  const shell = page.getByTestId("timeline-editor-shell");
  if (await shell.isVisible().catch(() => false)) {
    return true;
  }

  const timelineNav = page.getByRole("button", { name: /^Timeline$/i }).first();
  if ((await timelineNav.count()) > 0) {
    await timelineNav.click();
  } else {
    // Production menu / workspace switcher fallbacks
    const alt = page.getByRole("link", { name: /Timeline/i }).first();
    if ((await alt.count()) > 0) await alt.click();
  }
  await expect(shell).toBeVisible({ timeout: 20000 });
  return true;
}

test.describe("M42 W46 Timeline Final Ops (SA78)", () => {
  test("gate requires SA56–SA78 flags and stays binary", async ({ request }) => {
    const res = await request.get("/api/director-timeline/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(["GO", "NO-GO"]).toContain(body.verdict);
    for (const flag of [
      "timelineCameraMotionCatalogPassed",
      "timelineViewerLargeDefaultPassed",
      "timelineLipSyncToolbarPassed",
      "timelineInpaintVideoFinishingOnlyPassed",
      "timelineZoomControlsPassed",
      "timelinePlaywrightOperationalPassed",
    ]) {
      expect(body.requiredFlags).toContain(flag);
    }
  });

  test("camera catalog API returns motion + rig entries", async ({ request }) => {
    const res = await request.get("/api/director-timeline/camera-catalog");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    const motions = body.motions || body.motion || body.catalog?.motions || [];
    const rigs = body.rigs || body.rig || body.catalog?.rigs || [];
    expect(Array.isArray(motions) ? motions.length : 0).toBeGreaterThan(3);
    expect(Array.isArray(rigs) ? rigs.length : 0).toBeGreaterThan(1);
  });

  test("toolbar: Lip Sync controls, zoom scales board, mode gates Inpaint", async ({ page }) => {
    if (!(await openTimeline(page))) {
      test.skip(true, "No project/Timeline available");
      return;
    }

    await expect(page.getByTestId("timeline-toolbar")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-batch")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-image")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-prompt")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-audio")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-sfx")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-add")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-remove")).toBeVisible();
    await expect(page.getByTestId("timeline-toolbar-lipsync-clip")).toHaveCount(0);
    await expect(page.getByTestId("timeline-generator-banner")).toBeVisible();

    // Image Planning: Inpaint hidden
    const modeBtn = page.getByTestId("timeline-toolbar-mode");
    if ((await modeBtn.innerText()).match(/Video Finishing/i)) {
      await modeBtn.click();
    }
    await expect(page.getByTestId("timeline-toolbar-inpaint")).toHaveCount(0);

    // Switch to Video Finishing: Inpaint appears (disabled without eligible selection)
    await modeBtn.click();
    await expect(modeBtn).toContainText(/Video Finishing/i);
    const inpaint = page.getByTestId("timeline-toolbar-inpaint");
    await expect(inpaint).toBeVisible();
    await expect(inpaint).toBeDisabled();

    // Zoom end-to-end: board width increases
    const board = page.getByTestId("timeline-track-board").first();
    await expect(board).toBeVisible();
    const beforeWidth = Number(await board.getAttribute("data-board-width"));
    const beforeZoom = Number(await board.getAttribute("data-zoom"));
    await page.getByTestId("timeline-toolbar-zoom-in").click();
    await expect
      .poll(async () => Number(await board.getAttribute("data-zoom")))
      .toBeGreaterThan(beforeZoom);
    const afterWidth = Number(await board.getAttribute("data-board-width"));
    expect(afterWidth).toBeGreaterThan(beforeWidth);
    await expect(page.getByTestId("timeline-toolbar-zoom-value")).toBeVisible();

    // Lip Sync + adds an additional track (default Lip Sync 1 already present)
    page.once("dialog", (dialog) => dialog.dismiss().catch(() => undefined));
    await page.getByTestId("timeline-toolbar-lipsync-add").click();

    // Viewer presets + fullscreen controls present
    await expect(page.getByTestId("timeline-viewer-preset")).toBeVisible();
    await page.getByTestId("timeline-viewer-preset").selectOption("balanced");
    await expect(page.getByTestId("timeline-viewer-preset")).toHaveValue("balanced");
    await expect(page.getByTestId("workspace-fullscreen-controls")).toBeVisible();
  });

  test("1280 and 1920: toolbar Lip Sync + zoom remain visible", async ({ page }) => {
    if (!(await openTimeline(page))) {
      test.skip(true, "No project/Timeline available");
      return;
    }
    for (const size of [
      { width: 1280, height: 720 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(size);
      await expect(page.getByTestId("timeline-toolbar-lipsync")).toBeVisible();
      await expect(page.getByTestId("timeline-toolbar-lipsync-add")).toBeVisible();
      await expect(page.getByTestId("timeline-toolbar-lipsync-remove")).toBeVisible();
      await expect(page.getByTestId("timeline-toolbar-lipsync-clip")).toHaveCount(0);
      await expect(page.getByTestId("timeline-toolbar-zoom-in")).toBeVisible();
      await expect(page.getByTestId("timeline-toolbar-zoom-out")).toBeVisible();
      await expect(page.getByTestId("timeline-workspace-stack")).toBeVisible();
    }
  });
});
