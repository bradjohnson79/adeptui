import { test, expect, type APIRequestContext } from "@playwright/test";

/**
 * Focused M2.14 Playwright smoke (section 53).
 *
 * The workspace lives at `/co-director` (the app has no `/codirector` route), and the flag
 * that reveals it is OFF for the rest of the suite because it replaces the Co-Director
 * conversation surface. These tests switch it on for themselves through the E2E-only
 * control endpoint and hand it back afterwards, so both states are really covered.
 */

const API =
  process.env.STUDIO_API_BASE ||
  `http://127.0.0.1:${process.env.STUDIO_API_PORT || "8742"}`;

const FLAG = "codirector_unified_experience_v1";

/** The Playwright webServer is ready when Vite answers, which can be before the API is up. */
async function waitForApi(request: APIRequestContext) {
  const deadline = Date.now() + 60_000;
  let lastError = "never contacted";
  while (Date.now() < deadline) {
    try {
      const res = await request.get(`${API}/api/health`);
      if (res.ok()) return;
      lastError = `HTTP ${res.status()}`;
    } catch (error) {
      lastError = String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`API at ${API} never became ready: ${lastError}`);
}

async function setUnifiedFlag(request: APIRequestContext, enabled: boolean | null) {
  const res = await request.post(`${API}/api/e2e/feature-flags`, {
    data: { flags: { [FLAG]: enabled } },
  });
  if (!res.ok()) {
    test.skip(true, `E2E feature-flag control unavailable (${res.status()}); STUDIO_E2E off?`);
  }
  return res.json();
}

test.describe("M2.14 Unified Experience", () => {
  test.beforeEach(async ({ request }) => {
    await waitForApi(request);
  });

  test.afterAll(async ({ request }) => {
    await request.post(`${API}/api/e2e/feature-flags`, { data: { flags: { [FLAG]: false } } });
  });

  test("workspace is hidden when the flag is off", async ({ page, request }) => {
    await setUnifiedFlag(request, false);
    await page.goto("/co-director");
    await expect(page.getByTestId("m214-unified-workspace")).toHaveCount(0);
    // The ordinary conversation surface is what renders instead.
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 20_000 });
  });

  test("workspace renders three-pane shell when flag on", async ({ page, request }) => {
    const applied = await setUnifiedFlag(request, true);
    expect(applied.flags[FLAG]).toBe(true);

    await page.goto("/co-director");
    const ws = page.getByTestId("m214-unified-workspace");
    await expect(ws).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("m214-flag-badge")).toContainText("Flag:");
    await expect(page.getByTestId("m214-approval-center")).toBeVisible();
    await expect(page.getByTestId("m214-production-plan")).toBeVisible();
  });

  test("hitchhiker mocked media labeled", async ({ page, request }) => {
    await setUnifiedFlag(request, true);
    await page.goto("/co-director");
    const btn = page.getByTestId("m214-hitchhiker");
    await expect(btn).toBeVisible({ timeout: 20_000 });
    await btn.click();

    // The hitchhiker appends a card, so a workspace that already had one ends up with several
    // and a bare locator is a strict-mode violation. Every card must carry the label — one
    // unlabelled mock among many is exactly the dishonesty this case exists to catch. The
    // count is re-read on each poll because cards keep arriving while this runs.
    const cards = page.getByTestId("m214-media-image");
    const labelled = cards.filter({ hasText: "MOCKED" });
    await expect(async () => {
      const total = await cards.count();
      expect(total).toBeGreaterThan(0);
      expect(await labelled.count()).toBe(total);
    }).toPass({ timeout: 20_000 });
  });
});
