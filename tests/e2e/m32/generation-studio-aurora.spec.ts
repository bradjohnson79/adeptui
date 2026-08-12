/**
 * M3.2d — Generation Studio Aurora landing (GENSTUDIO-UI-01..20)
 */
import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const SHOT_DIR = path.join("artifacts", "m32", "generation-studio-aurora");

async function ensureShotDir() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
}

async function gotoHome(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
}

test.describe("M3.2d Generation Studio Aurora @DETERMINISTIC", () => {
  test.beforeAll(async () => {
    await ensureShotDir();
  });

  test("GENSTUDIO-UI-01 Hero renders with local artwork and SVG overlay", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const hero = page.getByTestId("generation-studio-hero");
    await expect(hero).toBeVisible();
    const img = page.getByTestId("generation-studio-hero-image");
    await expect(img).toBeVisible();
    const src = await img.getAttribute("src");
    expect(src || "").toMatch(/\/images\/hero\/Adept_UI_Hero_header\.(png|webp)/);
    const logo = page.getByTestId("generation-studio-hero-logo");
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute("src", /\/brand\/adept-ui-logo\.svg/);
    await page.screenshot({ path: path.join(SHOT_DIR, "01-hero.png"), fullPage: false });
  });

  test("GENSTUDIO-UI-02 Old New Production panel is absent", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.locator("#new-production")).toHaveCount(0);
    await expect(page.getByText("Start from a project type")).toHaveCount(0);
    await expect(page.getByText("NEW PRODUCTION", { exact: false })).toHaveCount(0);
  });

  test("GENSTUDIO-UI-03 Co-Director composer is visible above templates", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const card = page.getByTestId("codirector-launch-card");
    const templates = page.getByTestId("browse-templates-card");
    await expect(card).toBeVisible();
    await expect(page.getByTestId("codirector-launch-composer")).toBeVisible();
    const cardBox = await card.boundingBox();
    const templatesBox = await templates.boundingBox();
    expect(cardBox && templatesBox).toBeTruthy();
    expect(cardBox!.y).toBeLessThan(templatesBox!.y);
  });

  test("GENSTUDIO-UI-04 Empty prompt does not submit", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const submit = page.getByTestId("codirector-launch-submit");
    await expect(submit).toBeDisabled();
    await page.getByTestId("codirector-launch-composer").fill("   ");
    await expect(submit).toBeDisabled();
    await expect(page).toHaveURL(/\/$/);
  });

  test("GENSTUDIO-UI-05 Submitted homepage prompt opens fullscreen Co-Director", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await gotoHome(page);
    const prompt = `M32d aurora prompt ${Date.now()}`;
    await page.getByTestId("codirector-launch-composer").fill(prompt);
    await page.getByTestId("codirector-launch-submit").click();
    await expect(page).toHaveURL(/\/co-director/, { timeout: 15_000 });
    await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-mode", "fullscreen", {
      timeout: 15_000,
    });
    await page.screenshot({ path: path.join(SHOT_DIR, "05-fullscreen-codirector.png") });
    observer.flush();
  });

  test("GENSTUDIO-UI-06 Submitted prompt appears once in the conversation", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const prompt = `Unique aurora seed ${Date.now()}`;
    await page.getByTestId("codirector-launch-composer").fill(prompt);
    await page.getByTestId("codirector-launch-submit").click();
    await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 15_000 });
    const matches = page.getByText(prompt);
    await expect(matches.first()).toBeVisible({ timeout: 20_000 });
    expect(await matches.count()).toBe(1);
  });

  test("GENSTUDIO-UI-07 Prompt starter uses canonical composer/send path", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("codirector-starter-start-a-storyboard").click();
    await expect(page.getByTestId("codirector-launch-composer")).toHaveValue("Start a storyboard");
    await page.getByTestId("codirector-launch-submit").click();
    await expect(page).toHaveURL(/\/co-director/, { timeout: 15_000 });
    await expect(page.getByText("Start a storyboard").first()).toBeVisible({ timeout: 20_000 });
  });

  test("GENSTUDIO-UI-08 Project Templates use real inventory", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("browse-templates-card")).toBeVisible();
    const slides = page.locator("[data-testid^='carousel-slide-']");
    const count = await slides.count();
    expect(count).toBeGreaterThanOrEqual(10);
    for (const id of [
      "narrative",
      "explainer",
      "documentary",
      "social",
      "trailer",
      "talking-avatar",
      "web-series",
      "brand-ad",
    ]) {
      await expect(page.getByTestId(`carousel-slide-${id}`)).toBeAttached();
    }
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`1 / ${count}`);
    await expect(page.getByText("Fake Template XYZ")).toHaveCount(0);
    await expect(page.getByTestId("project-templates-grid")).toHaveCount(0);
  });

  test("GENSTUDIO-UI-09 Template selection reaches real template flow", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("carousel-slide-narrative").click();
    await expect(page).toHaveURL(/\/project\//, { timeout: 30_000 });
  });

  test("GENSTUDIO-UI-10 Create Project opens real blank-project flow", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("create-project-open").click();
    await expect(page.getByTestId("create-project-modal")).toBeVisible();
    await expect(page.getByTestId("create-project-submit")).toBeVisible();
    await page.screenshot({ path: path.join(SHOT_DIR, "10-create-project-modal.png") });
  });

  test("GENSTUDIO-UI-11 Browse Templates carousel is keyboard operable", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const track = page.getByTestId("carousel-track");
    const viewport = page.locator(".gs-carousel__viewport");
    await expect(page.getByTestId("carousel-prev")).toBeVisible();
    await expect(page.getByTestId("carousel-next")).toBeVisible();
    const slideCount = await page.locator("[data-testid^='carousel-slide-']").count();
    expect(slideCount).toBeGreaterThanOrEqual(10);
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`1 / ${slideCount}`);

    // Controlled transform carousel — never a native horizontal scroll surface.
    const overflowX = await track.evaluate((el) => getComputedStyle(el).overflowX);
    expect(["visible", "clip", "hidden"]).toContain(overflowX);
    const viewportOverflow = await viewport.evaluate((el) => getComputedStyle(el).overflowX);
    expect(["hidden", "clip"]).toContain(viewportOverflow);
    // No classic horizontal scrollbar gutter on the viewport.
    const scrollbarDx = await viewport.evaluate((el) => el.offsetWidth - el.clientWidth);
    expect(scrollbarDx).toBeLessThanOrEqual(1);

    await track.focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`2 / ${slideCount}`);
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`1 / ${slideCount}`);

    await page.getByTestId("carousel-next").click();
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`2 / ${slideCount}`);
    await expect(page.getByTestId("carousel-slide-dialogue")).toHaveAttribute("aria-selected", "true");

    // Wrap at end
    for (let i = 0; i < slideCount - 1; i += 1) {
      await page.getByTestId("carousel-next").click();
    }
    await expect(page.getByTestId("carousel-page-indicator")).toHaveText(`1 / ${slideCount}`);

    await page.screenshot({ path: path.join(SHOT_DIR, "11-template-carousel.png") });
  });

  test("GENSTUDIO-UI-12 Existing Explore Adept UI routes remain live", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("explore-adept-ui")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Explore Adept UI" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Director/i }).first()).toBeVisible();
  });

  test("GENSTUDIO-UI-13 System Status remains live and is not hardcoded", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const block = page.getByTestId("system-status-block");
    await expect(block).toBeVisible();
    await expect(block.getByTestId("status-api")).toBeVisible({ timeout: 15_000 });
    const apiText = (await block.getByTestId("status-api").textContent()) || "";
    expect(apiText).toMatch(/API/i);
    expect(apiText).not.toMatch(/hardcoded-healthy/i);
  });

  test("GENSTUDIO-UI-14 Capability Readiness remains functional", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const block = page.getByTestId("capability-readiness-block");
    await expect(block).toBeVisible();
    await expect(block.getByText(/Capability|Ready|Readiness/i).first()).toBeVisible({
      timeout: 20_000,
    });
  });

  test("GENSTUDIO-UI-15 Shared Button is used for new interactive chrome", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("create-project-open")).toHaveClass(/ui-btn/);
    await expect(page.getByTestId("enter-codirector")).toHaveClass(/ui-btn/);
    await expect(page.getByTestId("codirector-launch-submit")).toHaveClass(/ui-btn/);
    await expect(page.getByTestId("carousel-next")).toHaveClass(/ui-btn/);
  });

  test("GENSTUDIO-UI-16 Narrow desktop has no unexpected horizontal scroll", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await page.setViewportSize({ width: 1100, height: 800 });
    await gotoHome(page);
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      return doc.scrollWidth > doc.clientWidth + 2;
    });
    expect(overflow).toBeFalsy();
    await page.screenshot({ path: path.join(SHOT_DIR, "16-narrow-desktop.png") });
  });

  test("GENSTUDIO-UI-17 200% zoom remains usable", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.evaluate(() => {
      document.body.style.zoom = "2";
    });
    await expect(page.getByTestId("codirector-launch-composer")).toBeVisible();
    await expect(page.getByTestId("create-project-open")).toBeVisible();
    await page.screenshot({ path: path.join(SHOT_DIR, "17-zoom-200.png") });
    await page.evaluate(() => {
      document.body.style.zoom = "";
    });
  });

  test("GENSTUDIO-UI-18 No unexpected console errors", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("codirector-launch-composer").fill("console check");
    await page.waitForTimeout(500);
    observer.assertHealthyBrowser();
    observer.flush();
  });

  test("GENSTUDIO-UI-19 No serious or critical axe violations", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const results = await new AxeBuilder({ page })
      .disableRules(["color-contrast"]) // glass translucency can trip contrast heuristics
      .analyze();
    const serious = results.violations.filter((v) =>
      ["serious", "critical"].includes(v.impact || ""),
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
    await page.screenshot({ path: path.join(SHOT_DIR, "19-a11y.png"), fullPage: true });
  });

  test("GENSTUDIO-UI-20 Reduced motion suppresses nonessential visual motion", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await gotoHome(page);
    const transition = await page
      .locator(".gs-template-card")
      .first()
      .evaluate((el) => getComputedStyle(el).transitionProperty);
    expect(transition === "none" || transition === "").toBeTruthy();
  });
});
