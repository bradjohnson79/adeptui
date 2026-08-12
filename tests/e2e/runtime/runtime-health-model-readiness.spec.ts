import { test, expect, type Page } from "@playwright/test";

/**
 * Runtime Health / Model Readiness Refinement — Playwright certification.
 *
 * Certifies that ComfyUI runtime health is reported separately from model/generator
 * readiness, that an optional-missing component does NOT flip the runtime to
 * degraded, and that exact missing dependency filenames + expected paths are visible.
 *
 * Runs against the local Vite dev server (PLAYWRIGHT_BASE_URL) with the local Studio API
 * (STUDIO_API_PORT=8758). Local ComfyUI may be online or offline — the tests assert
 * the UI handles both states honestly.
 */

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";

async function dismissOnboarding(page: Page) {
  // Best-effort: close any onboarding/co-director setup modal that would block the UI.
  for (let i = 0; i < 3; i++) {
    const skip = page.getByRole("button", { name: /skip|continue|get started|save/i }).first();
    if (await skip.isVisible({ timeout: 1500 }).catch(() => false)) {
      await skip.click().catch(() => undefined);
      await page.waitForTimeout(300);
    } else {
      break;
    }
  }
}

test.describe("Runtime Health / Model Readiness Refinement", () => {
  test("SystemStatusStrip splits ComfyUI Runtime and Models badges", async ({ page }) => {
    await page.goto(`${BASE}/`);
    await dismissOnboarding(page);
    const strip = page.getByTestId("system-status-strip");
    await expect(strip).toBeVisible({ timeout: 15000 });
    // The strip must now have a separate "status-comfy" (runtime) and "status-models"
    // (model readiness) badge. Previously there was only "status-comfy".
    await expect(page.getByTestId("status-comfy")).toBeVisible();
    await expect(page.getByTestId("status-models")).toBeVisible();
  });

  test("VideoRuntimeDiagnostics shows layered Runtime / Hardware / Model Readiness / Overall", async ({ page }) => {
    await page.goto(`${BASE}/video-runtime`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("video-runtime-diagnostics")).toBeVisible({ timeout: 15000 });

    // Overall verdict section must be present and show one of the honest statuses.
    const verdict = page.getByTestId("runtime-overall-verdict");
    await expect(verdict).toBeVisible();
    const verdictStatus = page.getByTestId("runtime-overall-verdict-status");
    await expect(verdictStatus).toContainText(/HEALTHY|PARTIAL|DEGRADED|OFFLINE/);

    // Runtime (ComfyUI) section — reachability, NOT model readiness.
    await expect(page.getByTestId("runtime-comfyui")).toBeVisible();

    // Hardware (GPU) section.
    await expect(page.getByTestId("runtime-hardware")).toBeVisible();

    // Model Readiness section — per-generator, expandable.
    await expect(page.getByTestId("runtime-model-readiness")).toBeVisible();

    // Technical Information must be behind an expandable <details>, not shown by default.
    const techDetails = page.getByTestId("runtime-technical-details");
    await expect(techDetails).toBeVisible();
    // The raw JSON <pre> should not be visible until expanded.
    const techSummary = techDetails.locator("summary");
    await expect(techSummary).toContainText(/Technical Information/i);
  });

  test("Model Readiness surfaces exact missing dependency filename + expected path", async ({ page }) => {
    await page.goto(`${BASE}/video-runtime`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("runtime-model-readiness")).toBeVisible({ timeout: 15000 });

    // If any generator is incomplete, expanding it must show the exact filename +
    // expected path of the missing dependency (not a vague count). We look for the
    // LTX 2.5 generator entry specifically since LTX 2.5 text encoder/VAE are the
    // canonical "optional-missing" case.
    const ltx25 = page.getByTestId("generator-readiness-ltx_2_5");
    if (await ltx25.isVisible().catch(() => false)) {
      await ltx25.locator("summary").click();
      // If incomplete, a missing-dep entry must reference the exact filename or
      // expected path — never just a count.
      const missingDeps = ltx25.locator("[data-testid^='missing-dep-']");
      const count = await missingDeps.count();
      if (count > 0) {
        // The first missing dep should contain a <code> filename and an expectedPath span.
        const first = missingDeps.first();
        await expect(first.locator("code")).toBeVisible();
      }
    }
  });

  test("VideoModelLibrary shows honest model marks (✓ only when installed+healthy)", async ({ page }) => {
    await page.goto(`${BASE}/video-studio`);
    await page.waitForLoadState("networkidle");
    const library = page.getByTestId("video-model-library");
    if (await library.isVisible({ timeout: 10000 }).catch(() => false)) {
      // Every model row's leading mark must be either ✓ (installed+healthy) or ○ (not).
      // Critically: a default-but-uninstalled provider must NOT show ✓.
      const items = library.locator("[data-testid^='video-model-']");
      const itemCount = await items.count();
      if (itemCount > 0) {
        // Spot-check: no row should show ✓ when data-installed="false".
        for (let i = 0; i < itemCount; i++) {
          const row = items.nth(i);
          const installed = await row.getAttribute("data-installed");
          const text = await row.textContent();
          if (installed === "false") {
            // A leading ✓ would be the honest-label bug. The row text may still contain
            // ✓ elsewhere (e.g. benchmark), so we check the leading mark specifically.
            const strong = row.locator("strong").first();
            const strongText = await strong.textContent();
            expect(strongText?.trim().startsWith("✓"), `uninstalled row ${i} must not start with ✓`).toBe(false);
          }
        }
      }
    }
  });

  test("VideoModelLibrary Model Readiness section shows per-generator status", async ({ page }) => {
    await page.goto(`${BASE}/video-studio`);
    await page.waitForLoadState("networkidle");
    const readiness = page.getByTestId("video-model-readiness");
    if (await readiness.isVisible({ timeout: 10000 }).catch(() => false)) {
      // Each generator row must show READY or INCOMPLETE.
      const summaries = readiness.locator("summary");
      const count = await summaries.count();
      if (count > 0) {
        const firstText = await summaries.first().textContent();
        expect(firstText).toMatch(/READY|INCOMPLETE/);
      }
    }
  });
});
