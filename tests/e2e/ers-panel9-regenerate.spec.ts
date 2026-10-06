/**
 * Owner E2E: Observatory ERS Panel 9 compositor + Spatial Map Regenerate.
 * Named Jacob project only. Full paid ers.generate is in-scope.
 */
import { expect, test, type Page } from "@playwright/test";
import { spawnSync } from "node:child_process";
import path from "node:path";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "0ffe56e2-0d58-4926-91bf-0f947898d02e";
const MAP_ID = "477b450c-734d-49ae-a40a-51402e0a832f";
const ORIGINAL_COLLAGE = "32cfec5b-5110-43bc-bd0f-96e089f287d0";
const PYTHON = path.resolve("studio-api", ".venv", "Scripts", "python.exe");

test.setTimeout(40 * 60 * 1000);

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

function assertPanel9Geometry(compositeAssetId: string) {
  const script = `
from io import BytesIO
import urllib.request
from PIL import Image
api = ${JSON.stringify(API)}
orig_id = ${JSON.stringify(ORIGINAL_COLLAGE)}
comp_id = ${JSON.stringify(compositeAssetId)}
box = (1048, 496, 1660, 632)
def load(aid):
    url = f"{api}/api/assets/{aid}/file"
    with urllib.request.urlopen(url) as res:
        return Image.open(BytesIO(res.read())).convert("RGB")
orig = load(orig_id)
out = load(comp_id)
assert out.size == orig.size == (1672, 941), (out.size, orig.size)
x0, y0, x1, y1 = box
for sample in ((10, 10), (x0 - 1, y0), (x0, y0 - 1), (x1, y0 + 4), (800, 200)):
    assert out.getpixel(sample) == orig.getpixel(sample), sample
mid = out.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
orig_mid = orig.getpixel(((x0 + x1) // 2, (y0 + y1) // 2))
assert mid != (20, 24, 30), mid
assert mid != orig_mid, (mid, orig_mid)
print("PANEL9_OK", out.size, mid)
`;
  const result = spawnSync(PYTHON, ["-c", script], { encoding: "utf8" });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  expect(result.stdout).toContain("PANEL9_OK");
}

test.describe("ERS Panel 9 + Spatial Map Regenerate", () => {
  test.describe.configure({ retries: 0 });

  test("stale saved map Regenerates a full ers.generate and cover-fits Panel 9", async ({ page }) => {
    await openObservatoryMap(page);
    const monitor = page.getByTestId("ers-generation-monitor");
    await expect(monitor).toBeVisible({ timeout: 45_000 });
    const stale = page.getByTestId("ers-stale-banner");
    const staleVisible = await stale.isVisible().catch(() => false);
    if (staleVisible) {
      await expect(stale).toContainText(/out of date/i);
    }

    const regenerate = page.getByTestId("ers-regenerate");
    await expect(regenerate).toBeVisible({ timeout: 20_000 });

    const execPost = page.waitForRequest(
      (req) =>
        req.method() === "POST" &&
        /\/api\/codirector\/projects\/[^/]+\/executions\/?$/.test(req.url()) &&
        String(req.postData() || "").includes("ers.generate"),
      { timeout: 45_000 },
    );
    await regenerate.scrollIntoViewIfNeeded();
    await regenerate.click();
    const posted = await execPost;
    const body = posted.postDataJSON() as { capability?: string; context?: Record<string, unknown> };
    expect(body.capability).toBe("ers.generate");
    expect(body.context?.retry_component || "").toBe("");
    expect(body.context?.retryComponent || "").toBe("");

    await expect(monitor).toHaveAttribute("data-phase", /queued|generating/, { timeout: 20_000 });
    await expect(page.getByTestId("ers-generation-progress")).toBeVisible({ timeout: 20_000 });

    await expect(monitor).toHaveAttribute("data-phase", "complete", { timeout: 38 * 60 * 1000 });
    await expect(page.getByTestId("ers-stale-banner")).toHaveCount(0);

    const img = monitor.locator("img.spatial-map__ers-live-img");
    await expect(img).toBeVisible();
    const src = (await img.getAttribute("src")) || "";
    const assetMatch = src.match(/assets\/([0-9a-f-]{36})/i);
    expect(assetMatch?.[1], src).toBeTruthy();
    assertPanel9Geometry(String(assetMatch?.[1]));

    await page.reload();
    await openObservatoryMap(page);
    await expect(page.getByTestId("ers-generation-monitor")).toHaveAttribute("data-phase", "complete", {
      timeout: 45_000,
    });
    await expect(page.getByTestId("ers-stale-banner")).toHaveCount(0);
    const reloaded = page.locator("img.spatial-map__ers-live-img");
    await expect(reloaded).toBeVisible({ timeout: 20_000 });
    const reloadedSrc = (await reloaded.getAttribute("src")) || "";
    const reloadedId = reloadedSrc.match(/assets\/([0-9a-f-]{36})/i)?.[1];
    expect(reloadedId).toBe(assetMatch?.[1]);
    assertPanel9Geometry(String(reloadedId));
  });
});
