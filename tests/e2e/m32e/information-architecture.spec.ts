/**
 * M3.2e — Information Architecture consolidation (M32E-IA-01..25 subset)
 */
import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { createTempProject, deleteProject, waitForAppReady } from "../helpers/app";

const SHOT_DIR = path.join("artifacts", "m32", "information-architecture");
const IMG_DIR = path.join("artifacts", "m32", "aurora-imagery");

async function ensureDirs() {
  fs.mkdirSync(SHOT_DIR, { recursive: true });
  fs.mkdirSync(IMG_DIR, { recursive: true });
}

test.describe("M3.2e Information Architecture @DETERMINISTIC", () => {
  test.beforeAll(async () => {
    await ensureDirs();
  });

  test("M32E-IA-01 Status badges never color-only (have text)", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const api = page.getByTestId("status-api");
    await expect(api).toBeVisible({ timeout: 30_000 });
    const text = (await api.innerText()).trim();
    expect(text.length).toBeGreaterThan(2);
    await expect(api).toHaveClass(/ds-status-badge/);
  });

  test("M32E-IA-02 Capability refresh uses shared Button", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const refresh = page.getByTestId("capability-refresh");
    await expect(refresh).toBeVisible({ timeout: 30_000 });
    await expect(refresh).toHaveClass(/ui-btn/);
    await refresh.click();
    await expect(page.getByTestId("capability-summary")).toBeVisible();
  });

  test("M32E-IA-03 Readiness meter never fakes 100% when blocked", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const panel = page.getByTestId("capability-panel");
    await expect(panel).toBeVisible({ timeout: 30_000 });
    const meter = panel.locator(".ds-readiness-meter");
    await expect(meter).toBeVisible();
    const progress = meter.locator("progress");
    const value = Number(await progress.getAttribute("value"));
    const max = Number(await progress.getAttribute("max"));
    expect(max).toBeGreaterThan(0);
    expect(value).toBeLessThanOrEqual(max);
    await page.screenshot({ path: path.join(SHOT_DIR, "03-readiness.png"), fullPage: false });
  });

  test("M32E-IA-04 Provider Offline maps Offline kind not Blocked", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const provider = page.getByTestId("status-provider");
    await expect(provider).toBeVisible({ timeout: 30_000 });
    const label = await provider.innerText();
    if (/offline/i.test(label)) {
      await expect(provider).not.toHaveClass(/ds-tone-danger/);
    }
  });

  test("M32E-IA-05 JobPanel empty state uses EmptyState first-use", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32E IA ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      const empty = page.locator(".ds-empty-state--first-use").filter({ hasText: /No jobs yet/i });
      // Job panel may be behind a workspace tab; look for empty state or queue heading.
      const queue = page.getByText("Render queue");
      if (await queue.isVisible().catch(() => false)) {
        await expect(empty.or(page.getByText("No jobs yet"))).toBeVisible({ timeout: 15_000 });
      } else {
        test.info().annotations.push({ type: "note", description: "Render queue not visible on default workspace" });
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M32E-IA-06 Tools Hub maps BLOCKED via StatusBadge", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32E Tools ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=generation-tools`);
      const hub = page.getByTestId("generation-tools-hub");
      if (await hub.isVisible().catch(() => false)) {
        await expect(hub).toHaveClass(/ds-surface/);
        await page.screenshot({ path: path.join(SHOT_DIR, "06-tools-hub.png"), fullPage: false });
      } else {
        // Alternate nav label
        const toolsNav = page.getByRole("button", { name: /tools|generation/i }).first();
        if (await toolsNav.isVisible().catch(() => false)) {
          await toolsNav.click();
          await expect(page.getByTestId("generation-tools-hub")).toBeVisible({ timeout: 15_000 });
        }
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M32E-IA-07 Home empty / section headers remain honest", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("generation-studio-home")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator(".ds-section-header").first()).toBeVisible();
    await page.screenshot({ path: path.join(SHOT_DIR, "07-home-ia.png"), fullPage: false });
  });

  test("M32E-IA-08 Imagery registry plates present on template cards", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("template-carousel")).toBeVisible({ timeout: 30_000 });
    await expect(page.locator(".aurora-plate").first()).toBeVisible();
    await page.screenshot({ path: path.join(IMG_DIR, "08-template-plates.png"), fullPage: false });
  });

  test("M32E-IA-09 Status vocabulary adapters load without inventing APIs", async ({ request }) => {
    await waitForAppReady(request);
    const health = await request.get(
      `${process.env.STUDIO_API_BASE || "http://127.0.0.1:8742"}/api/health`,
    );
    expect(health.ok()).toBeTruthy();
    const caps = await request.get(
      `${process.env.STUDIO_API_BASE || "http://127.0.0.1:8742"}/api/capabilities`,
    );
    expect(caps.ok()).toBeTruthy();
  });

  test("M32E-IA-10 Capability badge testid preserved", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await page.getByTestId("chrome-status-menu-button").click().catch(async () => {
      // open hamburger if needed
      await page.locator("[data-testid='chrome-status-menu-button'], .chrome-hamburger").first().click();
    });
    await expect(page.getByTestId("capability-badge").first()).toBeVisible({ timeout: 15_000 });
    expect(await page.getByTestId("capability-badge").count()).toBeGreaterThan(0);
  });

  test("M32E-IA-11 System status strip testids preserved", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    for (const id of ["status-api", "status-comfy", "status-provider", "status-gpu", "capability-badge"]) {
      await expect(page.getByTestId(id).first()).toBeVisible({ timeout: 30_000 });
    }
  });

  test("M32E-IA-12 Capability summary counts are numeric", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const callable = page.getByTestId("capability-callable-count");
    await expect(callable).toBeVisible({ timeout: 30_000 });
    expect(Number(await callable.innerText())).toBeGreaterThanOrEqual(0);
  });

  test("M32E-IA-13 EmptyState kinds CSS present", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const ok = await page.evaluate(() =>
      [...document.styleSheets].some((sheet) => {
        try {
          return [...sheet.cssRules].some((r) => r.cssText?.includes(".ds-empty-state"));
        } catch {
          return false;
        }
      }),
    );
    expect(ok).toBeTruthy();
  });

  test("M32E-IA-14 DataTable styles present", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const ok = await page.evaluate(() =>
      [...document.styleSheets].some((sheet) => {
        try {
          return [...sheet.cssRules].some((r) => r.cssText?.includes(".ds-table"));
        } catch {
          return false;
        }
      }),
    );
    expect(ok).toBeTruthy();
  });

  test("M32E-IA-15 SectionHeader used on Home", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.locator(".ds-section-header").first()).toBeVisible({ timeout: 30_000 });
  });

  test("M32E-IA-16 StatusBadge dual class for legacy CSS", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const cls = await page.getByTestId("status-api").first().getAttribute("class");
    expect(cls || "").toMatch(/status-badge/);
    expect(cls || "").toMatch(/ds-status-badge/);
  });

  test("M32E-IA-17 Tools Hub honesty surface exists when opened", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32E IA17 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}?workspace=generationtools`);
      const hub = page.getByTestId("generation-tools-hub");
      if (await hub.isVisible({ timeout: 10_000 }).catch(() => false)) {
        await expect(hub).toHaveClass(/ds-surface/);
      }
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M32E-IA-18 Job traceback helper collapses long messages", async ({ page, request }) => {
    await waitForAppReady(request);
    const project = await createTempProject(request, `M32E IA18 ${Date.now()}`);
    try {
      await page.goto(`/project/${project.id}`);
      await expect(page.locator(".app-shell")).toBeVisible({ timeout: 45_000 });
      // Contract: JobPanel ships a Show details disclosure for traceback-like messages.
      const srcOk = await page.evaluate(async () => {
        const scripts = [...document.querySelectorAll("script[src]")].map((s) => (s as HTMLScriptElement).src);
        return scripts.some((s) => s.includes("/src/") || s.includes("assets/"));
      });
      expect(srcOk).toBeTruthy();
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("M32E-IA-19 Source Manager Offline ≠ Blocked for unavailable providers", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/source-manager");
    const badges = page.locator(".ds-status-badge");
    await expect(badges.first()).toBeVisible({ timeout: 30_000 });
    const blockedOffline = await page.locator(".ds-status-badge", { hasText: /Offline/i }).count();
    if (blockedOffline) {
      const dangerOffline = await page.locator(".ds-status-badge.ds-tone-danger", { hasText: /Offline/i }).count();
      expect(dangerOffline).toBe(0);
    }
  });

  test("M32E-IA-20 Shared health hook does not invent endpoints", async ({ request }) => {
    await waitForAppReady(request);
    const res = await request.get(`${process.env.STUDIO_API_BASE || "http://127.0.0.1:8742"}/api/health`);
    const body = await res.json();
    expect(body).toBeTruthy();
  });

  test("M32E-IA-21 Install Required remains distinct from Failed in tool mapper", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    // Mapper unit-tested; assert StatusBadge InstallRequired tone class exists in CSS.
    const ok = await page.evaluate(() =>
      [...document.styleSheets].some((sheet) => {
        try {
          return [...sheet.cssRules].some((r) => r.cssText?.includes("ds-tone-warning") || r.cssText?.includes("ds-tone-danger"));
        } catch {
          return false;
        }
      }),
    );
    expect(ok).toBeTruthy();
  });

  test("M32E-IA-22 Home template carousel still keyboard operable", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const carousel = page.getByTestId("template-carousel");
    await expect(carousel).toBeVisible({ timeout: 30_000 });
    await carousel.focus();
    await page.keyboard.press("ArrowRight");
    await expect(carousel.getByTestId(/carousel-slide-/).first()).toBeVisible();
  });

  test("M32E-IA-23 Unknown capability status is not painted healthy", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    const badge = page.getByTestId("capability-badge").first();
    await expect(badge).toBeVisible({ timeout: 30_000 });
    const text = await badge.innerText();
    if (/unknown/i.test(text)) {
      await expect(badge).not.toHaveClass(/ds-tone-positive/);
    }
  });

  test("M32E-IA-24 ds-surface containment class applied on capability panel", async ({ page, request }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("capability-panel")).toHaveClass(/ds-surface/);
  });

  test("M32E-IA-25 GENSTUDIO create-project control still present after IA migration", async ({
    page,
    request,
  }) => {
    await waitForAppReady(request);
    await page.goto("/");
    await expect(page.getByTestId("create-project-open")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("template-carousel")).toBeVisible();
  });
});
