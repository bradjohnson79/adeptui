import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import { AuditObserver } from "../helpers/observer";

const ARTIFACT_DIR = path.join("artifacts", "m41", "wave2");

async function ensureArtifactDir() {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
}

async function openCompactCoDirector(page: Page, projectId: string) {
  await page.goto(`/project/${projectId}`);
  const fab = page.locator("button.codirector-fab");
  await expect(fab).toBeVisible({ timeout: 30_000 });
  if ((await fab.getAttribute("aria-expanded")) !== "true") {
    await fab.click();
  }
  await expect(page.getByTestId("codirector-popup")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-mode", "popup");
}

/**
 * M41 Wave 2 — Co-Director UI + approval honesty.
 * IDs: M41-CD-15 … M41-CD-34 (+ Wave 1 regression touches).
 */
test.describe("@m41 @codirector wave2", () => {
  test.beforeAll(async () => {
    await ensureArtifactDir();
  });

  test("M41-CD-15 Compact shell is uncluttered (no Stage/Specialist strips)", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-15 ${Date.now()}`);
    try {
      await openCompactCoDirector(page, project.id);
      await expect(page.getByTestId("codirector-stage-strip")).toHaveCount(0);
      await expect(page.getByTestId("codirector-specialist-strip")).toHaveCount(0);
      await expect(page.getByTestId("codirector-conversation")).toBeVisible();
      await expect(page.getByTestId("codirector-composer")).toBeVisible();
      await expect(page.getByTestId("codirector-header-project")).toBeVisible();
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "m41-cd-15-compact.png"), fullPage: false });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-16 / M41-CD-17 Header shows project + runtime chip honesty", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-16 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-header-project")).toBeVisible();
      await expect(page.getByTestId("codirector-runtime-chip")).toBeVisible();
      const chipText = (await page.getByTestId("codirector-runtime-chip").innerText()).trim();
      expect(chipText.toLowerCase()).not.toContain("mock ready");
      expect(chipText.length).toBeGreaterThan(0);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-18 / M41-CD-19 Fullscreen SplitPane + layout presets persist", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-19 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("ds-split-pane")).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId("codirector-layout-presets")).toBeVisible();

      await page.getByTestId("codirector-layout-chat-focus").click();
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-layout-preset", "chat-focus");
      await expect
        .poll(async () => page.getByTestId("ds-split-primary").evaluate((el) => el.getBoundingClientRect().width), {
          timeout: 5_000,
        })
        .toBeGreaterThan(500);
      const chatWidth = await page.getByTestId("ds-split-primary").evaluate((el) => el.getBoundingClientRect().width);

      await page.getByTestId("codirector-layout-project-focus").click();
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-layout-preset", "project-focus");
      await expect
        .poll(async () => page.getByTestId("ds-split-primary").evaluate((el) => el.getBoundingClientRect().width), {
          timeout: 5_000,
        })
        .toBeLessThan(chatWidth - 40);

      await page.getByTestId("codirector-layout-balanced").click();
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-layout-preset", "balanced");

      const stored = await page.evaluate(() => ({
        size: localStorage.getItem("adept_codirector_split_primary"),
        preset: localStorage.getItem("adept_codirector_split_preset"),
      }));
      expect(stored.preset).toBe("balanced");
      expect(Number(stored.size)).toBeGreaterThan(0);

      await page.reload();
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-layout-preset", "balanced");
      await expect(page.getByTestId("ds-split-pane")).toBeVisible();

      await page.screenshot({ path: path.join(ARTIFACT_DIR, "m41-cd-19-split-balanced.png"), fullPage: true });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-20 / M41-CD-21 Nav honesty — no Storyboards/Props/Exports mis-aliases", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-20 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await page.getByTestId("codirector-menu-button").click();
      await expect(page.getByTestId("codirector-nav-drawer")).toBeVisible();
      await expect(page.getByTestId("codirector-nav-scripts")).toBeVisible();
      await expect(page.getByTestId("codirector-nav-characters")).toBeVisible();
      await expect(page.getByTestId("codirector-nav-approvals")).toBeVisible();
      await expect(page.getByTestId("codirector-nav-storyboards")).toHaveCount(0);
      await expect(page.getByTestId("codirector-nav-props")).toHaveCount(0);
      await expect(page.getByTestId("codirector-nav-exports")).toHaveCount(0);
      // Wave 3: Jobs nav opens read-only retrieval (still no mutation controls).
      await expect(page.getByTestId("codirector-nav-jobs")).toBeEnabled();
      await page.keyboard.press("Escape");
      await expect(page.getByTestId("codirector-nav-drawer")).toHaveCount(0);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-22 / M41-CD-23 Approvals empty is honest (no sample seeds)", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-22 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await page.getByTestId("codirector-content-tab-approvals").click();
      await expect(page.getByTestId("codirector-approvals-empty")).toBeVisible({ timeout: 20_000 });
      await expect(page.getByText("No approvals are waiting.")).toBeVisible();
      await expect(page.getByText("Storyteller handoff")).toHaveCount(0);
      await expect(page.getByText("Mocked hitchhiker")).toHaveCount(0);
      await expect(page.getByText("media-1")).toHaveCount(0);
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "m41-cd-22-approvals-empty.png"), fullPage: true });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-24 / M41-CD-25 Progressive disclosure — plans empty quiet; production empty quiet", async ({
    page,
    request,
  }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-24 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await page.getByTestId("codirector-content-tab-plans").click();
      await expect(page.getByTestId("codirector-plans-empty")).toBeVisible();
      await page.getByTestId("codirector-content-tab-production").click();
      await expect(page.getByTestId("codirector-production-empty").or(page.getByTestId("codirector-stage-list"))).toBeVisible({
        timeout: 20_000,
      });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-26 / M41-CD-27 Compact widths 360–640 usable", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-26 ${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1280, height: 800 });
      await openCompactCoDirector(page, project.id);
      for (const width of [360, 420, 520, 640]) {
        await page.setViewportSize({ width, height: 800 });
        await expect(page.getByTestId("codirector-header")).toBeVisible();
        await expect(page.getByTestId("codirector-composer")).toBeVisible();
        const scrollWidth = await page
          .getByTestId("codirector-popup")
          .evaluate((el) => el.scrollWidth - el.clientWidth);
        expect(scrollWidth).toBeLessThanOrEqual(12);
      }
      await page.setViewportSize({ width: 360, height: 800 });
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "m41-cd-26-width-360.png") });
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-28 / M41-CD-29 Fullscreen responsive 1280 and 1920", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-28 ${Date.now()}`);
    try {
      for (const size of [
        { width: 1280, height: 720 },
        { width: 1920, height: 1080 },
      ]) {
        await page.setViewportSize(size);
        await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
        await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
        await expect(page.getByTestId("ds-split-pane")).toBeVisible();
        await page.screenshot({
          path: path.join(ARTIFACT_DIR, `m41-cd-28-${size.width}x${size.height}.png`),
          fullPage: true,
        });
      }
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-30 / M41-CD-31 No-project mode + draft project scope regression", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const a = await createTempProject(request, `M41-CD-30-A ${Date.now()}`);
    const b = await createTempProject(request, `M41-CD-30-B ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(a.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      const composer = page.locator("[data-testid='codirector-composer'] textarea").first();
      await expect(composer).toBeVisible({ timeout: 15_000 });
      await composer.fill("draft-only-for-project-a");
      await expect
        .poll(async () =>
          page.evaluate((pid) => localStorage.getItem(`adept_codirector_draft_${pid}`) || "", a.id),
        )
        .toContain("draft-only-for-project-a");

      await page.goto(`/co-director?projectId=${encodeURIComponent(b.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(composer).toBeVisible();
      await expect
        .poll(async () => composer.inputValue(), { timeout: 5_000 })
        .not.toContain("draft-only-for-project-a");

      await page.goto("/co-director");
      await expect(page.getByTestId("codirector-no-project-banner")).toBeVisible();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, a.id);
      await deleteProject(request, b.id);
      observer.flush();
    }
  });

  test("M41-CD-32 Options does not crush workspace", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-32 ${Date.now()}`);
    try {
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await page.getByTestId("codirector-overflow-button").click();
      const conv = page.getByTestId("codirector-conversation");
      await expect(conv).toBeVisible();
      const h = await conv.evaluate((el) => el.getBoundingClientRect().height);
      expect(h).toBeGreaterThan(80);
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });

  test("M41-CD-33 / M41-CD-34 Aurora cards + Wave 1 runtime chip still present", async ({ page, request }) => {
    const observer = new AuditObserver(page, test.info());
    observer.attach();
    await waitForAppReady(request);
    const project = await createTempProject(request, `M41-CD-33 ${Date.now()}`);
    try {
      await page.goto(`/co-director?projectId=${encodeURIComponent(project.id)}`);
      await expect(page.getByTestId("codirector-shell")).toBeVisible({ timeout: 45_000 });
      await expect(page.getByTestId("codirector-shell")).toHaveAttribute("data-runtime-state", /.+/);
      await page.getByTestId("codirector-content-tab-approvals").click();
      const empty = page.getByTestId("codirector-approvals-empty");
      await expect(empty).toBeVisible();
      const bg = await empty.evaluate((el) => getComputedStyle(el).backgroundColor);
      // Must not be a bright white sample card background
      expect(bg === "rgb(255, 255, 255)" || bg === "rgba(255, 255, 255, 1)").toBeFalsy();
      observer.assertHealthyBrowser();
    } finally {
      await deleteProject(request, project.id);
      observer.flush();
    }
  });
});
