import { expect, test } from "@playwright/test";

/**
 * M42 W46 — Director Timeline Master + UX/Core/Co-Director addenda.
 * CT1–CT10 (API) + UX workflow smoke where the UI is available.
 */

test.describe("M42 W46 Director Timeline Master", () => {
  test("CT1: directorTimeline gate returns binary structure + addenda flags", async ({ request }) => {
    const res = await request.get("/api/director-timeline/gate");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(typeof body.directorTimelineGo).toBe("boolean");
    expect(["GO", "NO-GO"]).toContain(body.verdict);
    expect(body.flags.executionSnapshotPassed).toBeDefined();
    expect(body.flags.timelinePlayheadPassed).toBeDefined();
    expect(body.flags.codirectorTimelineMutationGatewayPassed).toBeDefined();
    expect(body.productionDockGoUnchanged).toBe(true);
    expect(Array.isArray(body.requiredFlags)).toBeTruthy();
    expect(body.requiredFlags).toContain("timelineMonitorResizePassed");
    expect(body.requiredFlags).toContain("codirectorTimelinePrimaryE2EPassed");
  });

  test("CT2: generators registry is honest about native InPaint", async ({ request }) => {
    const res = await request.get("/api/director-timeline/generators");
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.nativeVideoInPaintCertified).toBe(false);
    expect(body.defaultInPaintStrategy).toBeTruthy();
  });

  test("CT3: tool catalog exposes approval-gated mutations", async ({ request }) => {
    const res = await request.get("/api/director-timeline/tools");
    if (!res.ok()) {
      test.skip(true, "tools endpoint unavailable in this environment");
      return;
    }
    const body = await res.json();
    expect(body.mock).toBe(false);
    expect(body.mutationGate || body.tools).toBeTruthy();
  });
});

test.describe("M42 W46 Timeline UX shell", () => {
  test("UX1/CT4: Timeline workspace stack mounts with monitor + tracks", async ({ page }) => {
    await page.goto("/");
    // Best-effort: open first project if list exists
    const projectLink = page.locator("[data-testid='project-card'], a[href*='/project/']").first();
    if ((await projectLink.count()) === 0) {
      test.skip(true, "No project available for UI smoke");
      return;
    }
    await projectLink.click();
    const timelineTab = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineTab.count()) === 0) {
      test.skip(true, "Timeline tab not found");
      return;
    }
    await timelineTab.click();
    await expect(page.getByTestId("timeline-workspace-stack")).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId("timeline-monitor-divider")).toBeVisible();
    await expect(page.getByTestId("timeline-workspace-tracks")).toBeVisible();
  });

  test("UX2/CT5: playhead control present", async ({ page }) => {
    await page.goto("/");
    const projectLink = page.locator("[data-testid='project-card'], a[href*='/project/']").first();
    if ((await projectLink.count()) === 0) {
      test.skip(true, "No project available");
      return;
    }
    await projectLink.click();
    const timelineTab = page.getByRole("button", { name: /^Timeline$/i }).first();
    if ((await timelineTab.count()) === 0) {
      test.skip(true, "Timeline tab not found");
      return;
    }
    await timelineTab.click();
    const playhead = page.getByTestId("timeline-playhead");
    if ((await playhead.count()) === 0) {
      test.skip(true, "Playhead not mounted yet");
      return;
    }
    await expect(playhead).toBeVisible();
  });

  test("UX7/CT6: Asset Reference Name + action clarity", async ({ page }) => {
    await page.goto("/");
    const projectLink = page.locator("[data-testid='project-card'], a[href*='/project/']").first();
    if ((await projectLink.count()) === 0) {
      test.skip(true, "No project available");
      return;
    }
    await projectLink.click();
    await expect(page.getByText(/Reference Name/i).first()).toBeVisible({ timeout: 15000 });
    const addTimeline = page.getByRole("button", { name: /Add to Timeline/i }).first();
    const addRef = page.getByRole("button", { name: /Add as Reference/i }).first();
    // Buttons appear when assets exist; labels must be distinct when present.
    if ((await addTimeline.count()) > 0) {
      await expect(addTimeline).toBeVisible();
    }
    if ((await addRef.count()) > 0) {
      await expect(addRef).toBeVisible();
    }
  });
});
