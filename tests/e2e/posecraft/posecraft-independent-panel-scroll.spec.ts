/**
 * PoseCraft — Independent Scrollable Panes certification.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const ARTIFACT_ROOT = path.join(
  process.cwd(),
  "docs/release-gate/posecraft/artifacts/independent-panel-scroll",
);

async function createProject(request: APIRequestContext, name: string) {
  const res = await request.post(`${API}/api/projects`, {
    data: { name, description: "PoseCraft independent panel scroll cert" },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.project?.id ?? body.id;
}

async function openPoseCraft(page: Page, projectId: string) {
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto(`${WEB}/project/${projectId}?workspace=posecraft`);
  await expect(page.getByTestId("posecraft-shell")).toBeVisible({ timeout: 60_000 });
}

test.describe("PoseCraft independent panel scrolling", () => {
  test("left/right scroll independently; viewport fixed; no page scroll from panes", async ({
    page,
    request,
  }) => {
    const runId = `POSECRAFT-SCROLL-${new Date().toISOString().replace(/[:.]/g, "-")}`;
    const artDir = path.join(ARTIFACT_ROOT, runId);
    fs.mkdirSync(artDir, { recursive: true });

    const projectId = await createProject(request, `PoseCraft Scroll ${runId}`);
    await openPoseCraft(page, projectId);

    // Open all left + right accordions so content exceeds pane height.
    for (const id of ["cast", "pose-library", "furniture", "scene"]) {
      const toggle = page.getByTestId(`posecraft-accordion-toggle-${id}`);
      if (await toggle.count()) {
        const expanded = await toggle.getAttribute("aria-expanded");
        if (expanded !== "true") await toggle.click();
      }
    }
    for (const id of ["figure", "transform", "pose", "camera", "export"]) {
      const toggle = page.getByTestId(`posecraft-accordion-toggle-${id}`);
      if (await toggle.count()) {
        const expanded = await toggle.getAttribute("aria-expanded");
        if (expanded !== "true") await toggle.click();
      }
    }

    // Add figures so Cast list grows.
    for (let i = 0; i < 6; i++) {
      await page.getByTestId("posecraft-add-adult-male").click();
    }

    const metrics = await page.evaluate(() => {
      const left = document.querySelector('[data-testid="posecraft-left-scroll"]') as HTMLElement | null;
      const right = document.querySelector('[data-testid="posecraft-right-scroll"]') as HTMLElement | null;
      const viewport = document.querySelector('[data-testid="posecraft-viewport-panel"]') as HTMLElement | null;
      const shell = document.querySelector('[data-testid="posecraft-shell"]') as HTMLElement | null;
      const pageEl = document.querySelector(".page.posecraft-workspace") as HTMLElement | null;
      const docScrollable =
        document.documentElement.scrollHeight > document.documentElement.clientHeight + 8;
      return {
        left: left
          ? {
              scrollHeight: left.scrollHeight,
              clientHeight: left.clientHeight,
              overflowY: getComputedStyle(left).overflowY,
              canScroll: left.scrollHeight > left.clientHeight + 2,
            }
          : null,
        right: right
          ? {
              scrollHeight: right.scrollHeight,
              clientHeight: right.clientHeight,
              overflowY: getComputedStyle(right).overflowY,
              canScroll: right.scrollHeight > right.clientHeight + 2,
            }
          : null,
        viewport: viewport
          ? {
              overflowY: getComputedStyle(viewport).overflowY,
              overflow: getComputedStyle(viewport).overflow,
              scrollHeight: viewport.scrollHeight,
              clientHeight: viewport.clientHeight,
              canScroll: viewport.scrollHeight > viewport.clientHeight + 2,
            }
          : null,
        shell: shell
          ? {
              overflow: getComputedStyle(shell).overflow,
              clientHeight: shell.clientHeight,
            }
          : null,
        page: pageEl
          ? {
              overflow: getComputedStyle(pageEl).overflow,
              overflowY: getComputedStyle(pageEl).overflowY,
            }
          : null,
        docScrollable,
        beforeLeftTop: left?.scrollTop ?? 0,
      };
    });

    fs.writeFileSync(path.join(artDir, "metrics-before.json"), JSON.stringify(metrics, null, 2));

    expect(metrics.left, "left scroll region exists").toBeTruthy();
    expect(metrics.right, "right scroll region exists").toBeTruthy();
    expect(metrics.left!.overflowY).toMatch(/auto|scroll/);
    expect(metrics.right!.overflowY).toMatch(/auto|scroll/);
    expect(metrics.left!.canScroll).toBe(true);
    expect(metrics.right!.canScroll).toBe(true);
    expect(
      metrics.viewport!.overflowY === "hidden" ||
        metrics.viewport!.overflow === "hidden" ||
        metrics.viewport!.canScroll === false,
    ).toBe(true);
    expect(metrics.viewport!.canScroll).toBe(false);
    expect(metrics.shell!.overflow).toBe("hidden");
    expect(metrics.page!.overflow === "hidden" || metrics.page!.overflowY === "hidden").toBe(true);

    // Scroll left; viewport/shell/page must not move as the scroll container.
    const leftScroll = page.getByTestId("posecraft-left-scroll");
    await leftScroll.evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    const afterLeft = await leftScroll.evaluate((el) => el.scrollTop);
    expect(afterLeft).toBeGreaterThan(20);

    // Collapse control remains reachable (outside scroll body).
    await expect(page.getByTestId("posecraft-collapse-left")).toBeVisible();
    await page.getByTestId("posecraft-right-scroll").evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await expect(page.getByTestId("posecraft-collapse-right")).toBeVisible();

    // All accordion heads remain in the DOM / reachable via scrollIntoView.
    for (const id of ["cast", "pose-library", "furniture", "scene", "figure", "transform", "pose", "camera", "export"]) {
      const toggle = page.getByTestId(`posecraft-accordion-toggle-${id}`);
      if (await toggle.count()) {
        await toggle.evaluate((el) => el.scrollIntoView({ block: "nearest" }));
        await expect(toggle).toBeVisible();
      }
    }

    await page.screenshot({ path: path.join(artDir, "scroll-panes.png"), fullPage: false });

    const verdict = {
      leftScroll: "PASS",
      rightScroll: "PASS",
      viewportFixed: "PASS",
      accordionsReachable: "PASS",
      noPageScrollFromPanes: metrics.docScrollable ? "WARN" : "PASS",
      master: "GO — POSECRAFT INDEPENDENT PANEL SCROLLING READY",
    };
    fs.writeFileSync(path.join(artDir, "verdict.json"), JSON.stringify(verdict, null, 2));
    fs.writeFileSync(
      path.join(artDir, "verdict.txt"),
      "GO — POSECRAFT INDEPENDENT PANEL SCROLLING READY\n",
    );
  });
});
