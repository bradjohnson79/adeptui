/**
 * Empty camera Enabled creates C3/C4 at any time. Existing ERS must not block.
 * Named Jacob project only. Never POSTs ers.generate.
 */
import { expect, test, type Page } from "@playwright/test";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const MAP_ID = "477b450c-734d-49ae-a40a-51402e0a832f";

test.setTimeout(3 * 60 * 1000);

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) return;
    const skip = region.getByRole("button", { name: /Skip for now/i }).first();
    if (await skip.isVisible().catch(() => false)) {
      await skip.click({ force: true }).catch(() => undefined);
      await page.waitForTimeout(400);
    } else {
      break;
    }
  }
}

async function openObservatoryMap(page: Page) {
  await page.goto(`${UI}/co-director?projectId=${encodeURIComponent(PROJECT_ID)}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(
    page.getByTestId("codirector-fullscreen-shell").or(page.getByTestId("codirector-workspace")).first(),
  ).toBeVisible({ timeout: 45_000 });
  await dismissOnboarding(page);
  const showContent = page.getByRole("button", { name: "Show project content" });
  if (await showContent.isVisible().catch(() => false)) {
    await showContent.click({ force: true }).catch(() => undefined);
  }
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 45_000 });
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    if (await page.getByTestId("spatial-map-panel").isVisible().catch(() => false)) break;
    await page.waitForTimeout(700);
  }
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
  const select = page.locator("#spatial-map-select");
  if ((await select.count()) > 0) {
    await select.selectOption(MAP_ID);
    await expect(select).toHaveValue(MAP_ID, { timeout: 15_000 });
  }
}

async function emptyCameraSlot(page: Page): Promise<number> {
  for (const index of [2, 3, 1, 0]) {
    if (await page.getByTestId(`camera-add-${index}`).isVisible().catch(() => false)) {
      return index;
    }
  }
  await page.getByTestId("camera-remove-2").click();
  await expect(page.getByTestId("camera-add-2")).toBeVisible({ timeout: 20_000 });
  return 2;
}

test.describe("Spatial Map camera add anytime", () => {
  test.describe.configure({ retries: 0 });

  test("empty Enabled creates a camera while ERS is complete", async ({ page }) => {
    const forbidden: string[] = [];
    page.on("request", (req) => {
      if (
        req.method() === "POST" &&
        /\/executions\/?$/.test(req.url()) &&
        String(req.postData() || "").includes("ers.generate")
      ) {
        forbidden.push(req.url());
      }
    });

    await openObservatoryMap(page);
    await expect(page.getByTestId("ers-generation-monitor")).toBeVisible({ timeout: 45_000 });

    const slot = await emptyCameraSlot(page);
    const toggle = page.getByTestId(`camera-online-${slot}`);
    await expect(toggle).toBeEnabled();
    await expect(toggle).not.toHaveClass(/is-disabled/);

    const createPost = page.waitForRequest(
      (req) =>
        (req.method() === "POST" || req.method() === "PATCH") &&
        /\/cameras(\/|$)/.test(req.url()),
      { timeout: 20_000 },
    );
    await toggle.click();
    await createPost;
    await expect(page.getByTestId(`camera-add-${slot}`)).toHaveCount(0, { timeout: 20_000 });
    await expect(page.getByTestId(`camera-lens-${slot}`)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`slot-active-badge-camera-${slot}`)).toBeVisible({ timeout: 15_000 });
    await expect(toggle).toHaveAttribute("aria-checked", "true");
    await expect(page.getByTestId("spatial-map-save-state-ers-row")).toContainText(/Unsaved changes/i, {
      timeout: 15_000,
    });
    await expect(page.getByTestId("ers-regenerate")).toBeVisible();
    expect(forbidden, "ERS generate must not fire from adding a camera").toEqual([]);
  });
});
