/**
 * M3.2c — Co-Director UI refinement (CODIRECTOR-UI-01..18)
 */
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const SHOT_DIR = path.join("artifacts", "m32", "codirector-ui");

async function openCoDirector(page: Page) {
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  if ((await fab.getAttribute("aria-expanded")) !== "true") {
    await fab.click();
  }
  await expect(page.getByTestId("codirector-popup")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 15_000 });
}

async function ensureShotDir() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
}

test.describe("M3.2 Co-Director UI @DETERMINISTIC", () => {
  test.beforeAll(async () => {
    await ensureShotDir();
  });

  test("CODIRECTOR-UI-01 compact popup opens chat-first without M2.14 grid", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 UI ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-mode", "popup");
      await expect(page.getByTestId("m214-unified-workspace")).toHaveCount(0);
      await expect(page.getByTestId("codirector-composer")).toBeVisible();
      await expect(page.getByTestId("codirector-header")).toBeVisible();
      await page.screenshot({
        path: path.join(SHOT_DIR, "01-compact-chat-first.png"),
        fullPage: false,
      });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("CODIRECTOR-UI-02 compact header controls do not overlap", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 overlap ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const header = page.getByTestId("codirector-header");
      const boxes = await header.locator("button").evaluateAll((btns) =>
        btns.map((b) => {
          const r = b.getBoundingClientRect();
          return { x: r.x, y: r.y, w: r.width, h: r.height, label: b.getAttribute("aria-label") };
        }),
      );
      for (let i = 0; i < boxes.length; i += 1) {
        for (let j = i + 1; j < boxes.length; j += 1) {
          const a = boxes[i];
          const b = boxes[j];
          const overlapX = a.x < b.x + b.w && a.x + a.w > b.x;
          const overlapY = a.y < b.y + b.h && a.y + a.h > b.y;
          expect(overlapX && overlapY, `${a.label} overlaps ${b.label}`).toBeFalsy();
        }
      }
      await page.screenshot({ path: path.join(SHOT_DIR, "02-header-no-overlap.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-03 drawer opens from hamburger", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 drawer ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await page.getByTestId("codirector-menu-button").click();
      await expect(page.getByTestId("codirector-nav-drawer")).toBeVisible();
      await expect(page.getByTestId("codirector-nav-chat")).toBeVisible();
      await page.screenshot({ path: path.join(SHOT_DIR, "03-nav-drawer.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-04 drawer Escape closes and restores focus", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 esc ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const menu = page.getByTestId("codirector-menu-button");
      await menu.click();
      await expect(page.getByTestId("codirector-nav-drawer")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("codirector-nav-drawer")).toHaveCount(0);
      await expect(page.getByTestId("codirector-popup")).toBeVisible();
      await expect(menu).toBeFocused();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-05 drawer backdrop closes", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 backdrop ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await page.getByTestId("codirector-menu-button").click();
      await expect(page.getByTestId("codirector-nav-drawer")).toBeVisible();
      // Panel occupies the left; click the right side of the full-bleed backdrop.
      await page.getByTestId("codirector-nav-drawer-backdrop").click({
        position: { x: 240, y: 40 },
        force: true,
      });
      await expect(page.getByTestId("codirector-nav-drawer")).toHaveCount(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-06 fullscreen two-pane Chat | Project Content", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 full ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await page.getByTestId("codirector-expand-button").click();
      await expect(page).toHaveURL(/\/co-director/);
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-mode", "fullscreen");
      await expect(page.getByTestId("codirector-workspace")).toBeVisible();
      await expect(page.getByTestId("codirector-project-content")).toBeVisible();
      await expect(page.getByLabel("Message Co-Director")).toBeVisible();
      await page.screenshot({ path: path.join(SHOT_DIR, "06-fullscreen-two-pane.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-07 composer always visible in compact", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 composer ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const composer = page.getByTestId("codirector-composer");
      await expect(composer).toBeVisible();
      const box = await composer.boundingBox();
      expect(box).toBeTruthy();
      expect(box!.height).toBeGreaterThan(40);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-08 long message does not break layout", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 long ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const long = "Scene treatment paragraph. ".repeat(40);
      await page.getByLabel("Message Co-Director").fill(long);
      const popup = page.getByTestId("codirector-popup");
      const scrollWidth = await popup.evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(scrollWidth).toBeLessThanOrEqual(8);
      await page.screenshot({ path: path.join(SHOT_DIR, "08-long-draft.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-09 production tab stages readable", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 stages ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${project.id}`);
      await expect(page.getByTestId("codirector-project-content")).toBeVisible({ timeout: 20_000 });
      await page.getByRole("tab", { name: /Production/i }).click();
      await expect(page.getByTestId("codirector-project-content")).toContainText(/Production|stage/i);
      await page.screenshot({ path: path.join(SHOT_DIR, "09-production-stages.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-10 approvals tab readable cards", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 approvals ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${project.id}`);
      await expect(page.getByTestId("codirector-project-content")).toBeVisible({ timeout: 20_000 });
      await page.getByRole("tab", { name: /Approvals/i }).click();
      await expect(page.getByTestId("codirector-approvals-panel")).toBeVisible();
      await page.screenshot({ path: path.join(SHOT_DIR, "10-approvals.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-11 icon buttons have accessible names", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 a11y icons ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      for (const name of [
        "Open Co-Director menu",
        "Co-Director more options",
        "Open full-screen Co-Director",
        "Close Co-Director",
        "Send message",
        "Attach files",
      ]) {
        await expect(page.getByRole("button", { name })).toBeVisible();
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-12 shared Button variants render non-transparent text", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 buttons ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const colors = await page.locator(".codirector-shell .ui-btn").evaluateAll((nodes) =>
        nodes.slice(0, 12).map((n) => {
          const s = getComputedStyle(n);
          return {
            text: s.color,
            opacity: s.opacity,
            name: n.getAttribute("aria-label") || n.textContent?.trim() || "btn",
          };
        }),
      );
      expect(colors.length).toBeGreaterThan(0);
      for (const c of colors) {
        expect(c.opacity, c.name).not.toBe("0");
        expect(c.text, c.name).not.toMatch(/rgba?\(0,\s*0,\s*0,\s*0\)|transparent/);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-13 200% zoom compact usable", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 zoom ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await page.evaluate(() => {
        document.documentElement.style.zoom = "2";
      });
      await openCoDirector(page);
      await expect(page.getByTestId("codirector-composer")).toBeVisible();
      await expect(page.getByTestId("codirector-menu-button")).toBeVisible();
      await page.screenshot({ path: path.join(SHOT_DIR, "13-zoom-200.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-14 narrow viewport chat + drawer", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 narrow ${Date.now()}`);
    try {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await expect(page.getByTestId("m214-unified-workspace")).toHaveCount(0);
      await page.getByTestId("codirector-menu-button").click();
      await expect(page.getByTestId("codirector-nav-drawer")).toBeVisible();
      await page.screenshot({ path: path.join(SHOT_DIR, "14-narrow-drawer.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-15 axe no critical/serious on open popup", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 axe ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await expect
        .poll(async () =>
          page.locator(".codirector-shell").evaluate((el) => getComputedStyle(el).backgroundColor),
        )
        .toBe("rgb(21, 26, 31)");
      const results = await new AxeBuilder({ page })
        .include('[data-testid="codirector-popup"]')
        .withTags(["wcag2a", "wcag2aa"])
        .analyze();
      const blockers = results.violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      );
      expect(blockers, JSON.stringify(blockers, null, 2)).toEqual([]);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-16 no unexpected horizontal scroll on popup", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 hscroll ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      const overflow = await page.getByTestId("codirector-popup").evaluate((el) => {
        return el.scrollWidth > el.clientWidth + 2;
      });
      expect(overflow).toBeFalsy();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-17 no console errors while opening compact + fullscreen", async ({
    page,
    request,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 console ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await page.getByTestId("codirector-expand-button").click();
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-mode", "fullscreen");
      const filtered = errors.filter(
        (e) =>
          !/favicon|Download the React DevTools|net::ERR_|Failed to load resource:.*404/i.test(e),
      );
      expect(filtered, filtered.join("\n")).toEqual([]);
      await page.screenshot({ path: path.join(SHOT_DIR, "17-fullscreen-stable.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("CODIRECTOR-UI-18 nav Project Content expands from compact", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32 nav content ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await openCoDirector(page);
      await page.getByTestId("codirector-menu-button").click();
      await page.getByTestId("codirector-nav-content").click();
      await expect(page).toHaveURL(/\/co-director/);
      await expect(page.getByTestId("codirector-project-content")).toBeVisible({ timeout: 20_000 });
      await page.screenshot({ path: path.join(SHOT_DIR, "18-nav-to-content.png") });
    } finally {
      await deleteProject(request, project.id);
    }
  });
});
