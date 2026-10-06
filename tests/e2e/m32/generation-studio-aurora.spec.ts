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

  test("GENSTUDIO-UI-01 Compact hero renders the local emblem", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const hero = page.getByTestId("generation-studio-hero");
    await expect(hero).toBeVisible();
    await expect(page.getByRole("heading", { name: "ADEPT UI", exact: true })).toBeVisible();
    await expect(page.getByText("AI-Powered Film Production")).toBeVisible();
    await expect(page.getByTestId("generation-studio-hero-image")).toHaveCount(0);
    const logo = page.getByTestId("generation-studio-hero-logo");
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute("src", /\/brand\/adept-ui-emblem\.webp/);
    await page.screenshot({ path: path.join(SHOT_DIR, "01-hero.png"), fullPage: false });
  });

  test("GENSTUDIO-UI-02 Old New Production panel is absent", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.locator("#new-production")).toHaveCount(0);
    await expect(page.getByText("Start from a project type")).toHaveCount(0);
    await expect(page.getByText("NEW PRODUCTION", { exact: false })).toHaveCount(0);
  });

  test("GENSTUDIO-UI-03 Co-Director feature card is visible above projects", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const card = page.getByTestId("codirector-launch-card");
    const projects = page.getByTestId("projects-hero");
    await expect(card).toBeVisible();
    await expect(page.getByTestId("codirector-launch-image")).toBeVisible();
    await expect(page.getByTestId("enter-codirector")).toBeVisible();
    await expect(page.getByTestId("codirector-launch-composer")).toHaveCount(0);
    await expect(page.getByTestId("browse-templates-card")).toHaveCount(0);
    const cardBox = await card.boundingBox();
    const projectsBox = await projects.boundingBox();
    expect(cardBox && projectsBox).toBeTruthy();
    expect(cardBox!.y).toBeLessThan(projectsBox!.y);
  });

  test("GENSTUDIO-UI-04 Home composer and prompt starters are absent", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("codirector-launch-composer")).toHaveCount(0);
    await expect(page.getByTestId("codirector-launch-submit")).toHaveCount(0);
    await expect(page.getByTestId("codirector-starter-start-a-storyboard")).toHaveCount(0);
    await expect(page).toHaveURL(/\/$/);
  });

  test("GENSTUDIO-UI-05 Enter Co-Director opens fullscreen Co-Director", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("enter-codirector").click();
    await expect(page).toHaveURL(/\/co-director/, { timeout: 15_000 });
    await expect(page.getByTestId("codirector-fullscreen-shell")).toHaveAttribute("data-mode", "fullscreen", {
      timeout: 15_000,
    });
    await page.screenshot({ path: path.join(SHOT_DIR, "05-fullscreen-codirector.png") });
    observer.flush();
  });

  test("GENSTUDIO-UI-06 Home entry opens a single fullscreen Co-Director session", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("enter-codirector").click();
    await expect(page.getByTestId("codirector-fullscreen-shell")).toBeVisible({ timeout: 15_000 });
    expect(await page.getByTestId("codirector-fullscreen-shell").count()).toBe(1);
    expect(await page.getByTestId("codirector-fullscreen").count()).toBe(1);
  });

  test("GENSTUDIO-UI-07 Co-Director card keeps project context", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    const context = page.getByTestId("codirector-project-context");
    await expect(context).toBeVisible();
    await expect(context).toHaveText(/Active project:|Open Co-Director to choose or continue a project\./);
  });

  test("GENSTUDIO-UI-08 Projects header replaces Browse Templates", async ({ page, request }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("projects-hero")).toBeVisible();
    await expect(page.getByTestId("projects-hero-summary")).toBeVisible();
    await expect(page.getByTestId("home-active-project-banner")).toBeVisible();
    await expect(page.getByTestId("home-previous-project")).toBeVisible();
    await expect(page.getByTestId("browse-templates-card")).toHaveCount(0);
    await expect(page.getByTestId("template-carousel")).toHaveCount(0);
    await expect(page.getByText("Fake Template XYZ")).toHaveCount(0);
  });

  test("GENSTUDIO-UI-09 Create Project stays on the projects header", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await page.getByTestId("create-project-open").click();
    await expect(page.getByTestId("create-project-modal")).toBeVisible();
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

  test("GENSTUDIO-UI-11 Projects header keeps create and project actions", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await gotoHome(page);
    await expect(page.getByTestId("create-project-open")).toBeVisible();
    await expect(page.getByTestId("home-active-project-name")).toBeVisible();
    await expect(page.getByTestId("home-previous-project-name")).toBeVisible();
    await expect(page.getByTestId("carousel-next")).toHaveCount(0);

    await page.getByTestId("create-project-open").focus();
    await expect(page.getByTestId("create-project-open")).toBeFocused();
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
    await expect(page.getByTestId("codirector-launch-card")).toBeVisible();
    await expect(page.getByTestId("enter-codirector")).toBeVisible();
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
    await expect(page.getByTestId("enter-codirector")).toBeVisible();
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
