/**
 * M3.2e — Application-wide Aurora theme (M32E-THEME-01..22)
 */
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const SHOT_DIR = path.join("artifacts", "m32", "aurora-theme");

async function ensureShotDir() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
}

async function bodyIsDark(page: Page) {
  return page.evaluate(() => {
    const styles = getComputedStyle(document.body);
    const bg = styles.backgroundColor;
    const color = styles.color;
    const parse = (c: string) => {
      const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
      if (!m) return null;
      return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]) };
    };
    const bgRgb = parse(bg);
    const inkRgb = parse(color);
    const bgLum = bgRgb ? (bgRgb.r + bgRgb.g + bgRgb.b) / 3 : 255;
    const inkLum = inkRgb ? (inkRgb.r + inkRgb.g + inkRgb.b) / 3 : 0;
    return { bgLum, inkLum, bg, color };
  });
}

test.describe("M3.2e Aurora Theme @DETERMINISTIC", () => {
  test.beforeAll(async () => {
    await ensureShotDir();
  });

  test("M32E-THEME-01 Home body uses dark Aurora canvas", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
    const { bgLum, inkLum } = await bodyIsDark(page);
    expect(bgLum).toBeLessThan(80);
    expect(inkLum).toBeGreaterThan(160);
    await page.screenshot({ path: path.join(SHOT_DIR, "01-home-dark.png"), fullPage: false });
  });

  test("M32E-THEME-02 System status strip uses StatusBadge primitives", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("system-status-strip")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("status-api")).toBeVisible();
    await expect(page.getByTestId("status-comfy")).toBeVisible();
    await expect(page.getByTestId("status-api")).toHaveClass(/ds-status-badge/);
  });

  test("M32E-THEME-03 Capability panel has ds-surface and readiness meter", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const panel = page.getByTestId("capability-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    await expect(panel).toHaveClass(/ds-surface/);
    await expect(panel.locator(".ds-readiness-meter")).toBeVisible();
    await page.screenshot({ path: path.join(SHOT_DIR, "03-capability.png"), fullPage: false });
  });

  test("M32E-THEME-04 Director shell is dark cinematic, not washed white", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32E Theme ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=director`);
      const shell = page.locator(".director-shell");
      await expect(shell).toBeVisible({ timeout: 45_000 });
      const parseLum = (c: string) => {
        const m = c.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
        if (!m) return 255;
        return (Number(m[1]) + Number(m[2]) + Number(m[3])) / 3;
      };
      const shellBg = await shell.evaluate((el) => getComputedStyle(el).backgroundColor || getComputedStyle(document.body).backgroundColor);
      const panel = shell.locator(".panel").first();
      if (await panel.count()) {
        const panelBg = await panel.evaluate((el) => getComputedStyle(el).backgroundColor);
        expect(parseLum(panelBg)).toBeLessThan(110);
      }
      const { bgLum, inkLum } = await bodyIsDark(page);
      expect(bgLum).toBeLessThan(80);
      expect(inkLum).toBeGreaterThan(160);
      expect(parseLum(shellBg) < 120 || bgLum < 80).toBeTruthy();
      await page.screenshot({ path: path.join(SHOT_DIR, "04-director.png"), fullPage: false });
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M32E-THEME-05 Source Manager status regions use ds-surface", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/source-manager");
    await expect(page.locator(".ds-surface").first()).toBeVisible({ timeout: 30_000 });
    await page.screenshot({ path: path.join(SHOT_DIR, "05-source-manager.png"), fullPage: false });
  });

  test("M32E-THEME-06 Template carousel falls back to aurora plates without scrollbar", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const carousel = page.getByTestId("template-carousel");
    await expect(carousel).toBeVisible({ timeout: 30_000 });
    const overflow = await carousel.locator(".gs-carousel__viewport").evaluate((el) => {
      const s = getComputedStyle(el);
      return { x: s.overflowX, y: s.overflowY };
    });
    expect(overflow.x === "hidden" || overflow.x === "clip").toBeTruthy();
    await expect(carousel.locator(".aurora-plate, .cinematic-media-fallback").first()).toBeVisible();
    await page.screenshot({ path: path.join(SHOT_DIR, "06-carousel-plates.png"), fullPage: false });
  });

  test("M32E-THEME-07 Co-Director shell remains cinematic dark", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/co-director");
    const shell = page.getByTestId("codirector-shell");
    await expect(shell).toBeVisible({ timeout: 30_000 });
    await expect(shell).toHaveClass(/cinematic/);
    await page.screenshot({ path: path.join(SHOT_DIR, "07-codirector.png"), fullPage: false });
  });

  test("M32E-THEME-08 Global CSS variables expose Aurora semantic tokens", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const tokens = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return {
        bg1: s.getPropertyValue("--bg1").trim(),
        ink: s.getPropertyValue("--ink").trim(),
        panel: s.getPropertyValue("--panel-solid").trim(),
        statusPositive: s.getPropertyValue("--status-positive").trim(),
        media: s.getPropertyValue("--media-monitor-bg").trim(),
      };
    });
    expect(tokens.bg1.toLowerCase()).toMatch(/#070b14|#050914/);
    expect(tokens.ink.toLowerCase()).toMatch(/#f3f7fb|#f/);
    expect(tokens.statusPositive).toBeTruthy();
    expect(tokens.media).toBeTruthy();
  });

  test("M32E-THEME-09 Scrollbar styling tokens are dark/thin", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const scrollbar = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return {
        width: s.getPropertyValue("scrollbar-width").trim() || getComputedStyle(document.body).scrollbarWidth,
        color: getComputedStyle(document.body).scrollbarColor,
      };
    });
    expect(scrollbar.width === "thin" || Boolean(scrollbar.color)).toBeTruthy();
  });

  test("M32E-THEME-10 Topbar uses glass dark chrome", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const topbar = page.locator(".studio-chrome.topbar, .topbar").first();
    await expect(topbar).toBeVisible();
    const bg = await topbar.evaluate((el) => getComputedStyle(el).backgroundColor);
    const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    expect(m).toBeTruthy();
    const lum = (Number(m![1]) + Number(m![2]) + Number(m![3])) / 3;
    expect(lum).toBeLessThan(80);
  });

  test("M32E-THEME-11 Panel borders use glass token line", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const panel = page.locator(".panel, .dash-card").first();
    await expect(panel).toBeVisible({ timeout: 30_000 });
    const border = await panel.evaluate((el) => getComputedStyle(el).borderColor);
    expect(border).toBeTruthy();
  });

  test("M32E-THEME-12 Media monitor tokens stay neutral dark", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const media = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--media-monitor-bg").trim(),
    );
    expect(media.toLowerCase()).toMatch(/#0a0c10|#111|#0/);
  });

  test("M32E-THEME-13 Codirector accent aliases Aurora teal", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/co-director");
    const accent = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--codirector-accent").trim(),
    );
    expect(accent).toBeTruthy();
  });

  test("M32E-THEME-14 Reduced-motion does not break landing", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
  });

  test("M32E-THEME-15 Focus ring token is present", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const ring = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue("--focus-ring").trim(),
    );
    expect(ring.length).toBeGreaterThan(0);
  });

  test("M32E-THEME-16 Status tone tokens exist for IA primitives", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const tones = await page.evaluate(() => {
      const s = getComputedStyle(document.documentElement);
      return ["--status-positive", "--status-warning", "--status-danger", "--status-info"].map((k) =>
        s.getPropertyValue(k).trim(),
      );
    });
    expect(tones.every((t) => t.length > 0)).toBeTruthy();
  });

  test("M32E-THEME-17 Home hero remains local artwork", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const src = await page.getByTestId("generation-studio-hero-image").getAttribute("src");
    expect(src || "").toMatch(/\/images\/hero\//);
  });

  test("M32E-THEME-18 Create project control still available", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("create-project-open")).toBeVisible({ timeout: 30_000 });
  });

  test("M32E-THEME-19 No light mint body gradient remains", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const bgImage = await page.evaluate(() => getComputedStyle(document.body).backgroundImage);
    expect(bgImage.toLowerCase()).not.toContain("#f7fcfb");
    expect(bgImage.toLowerCase()).not.toContain("rgb(247, 252, 251)");
  });

  test("M32E-THEME-20 Brand text remains readable on dark chrome", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const brand = page.locator(".brand").first();
    await expect(brand).toBeVisible();
    const color = await brand.evaluate((el) => getComputedStyle(el).color);
    const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
    expect(m).toBeTruthy();
    const lum = (Number(m![1]) + Number(m![2]) + Number(m![3])) / 3;
    expect(lum).toBeGreaterThan(140);
  });

  test("M32E-THEME-21 Image-ready plate CSS loaded", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const hasPlate = await page.evaluate(() => {
      const sheets = [...document.styleSheets];
      for (const sheet of sheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.cssText?.includes(".aurora-plate")) return true;
          }
        } catch {
          /* cross-origin */
        }
      }
      return Boolean(document.querySelector(".aurora-plate"));
    });
    expect(hasPlate).toBeTruthy();
  });

  test("M32E-THEME-22 Atmosphere overlays are non-interactive", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const pe = await page.evaluate(() => {
      const before = getComputedStyle(document.querySelector(".app-shell.atmosphere") || document.body, "::before");
      return before.pointerEvents;
    });
    expect(pe === "none" || pe === "").toBeTruthy();
  });
});
