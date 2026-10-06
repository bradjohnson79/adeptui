/**
 * Workflow coverage wiring — Image / Prop / Brand / PoseCraft / Voice / Avatar honesty.
 * Schnick Coffee only. Does not create a new project.
 * Run with PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 so config does not flip to retired :8760.
 */
import { expect, test, type Page } from "@playwright/test";

const WEB = process.env.ADEPT_WEB_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.ADEPT_API_URL || process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT =
  process.env.ADEPT_SCHNICK_PROJECT_ID ||
  process.env.ADEPT_PROJECT_ID ||
  "2347bf46-3762-4763-86c5-4a6032522278";

type FailedRequest = { url: string; status: number; method: string };

function attachCoverageCapture(page: Page): { consoleErrors: string[]; failed: FailedRequest[] } {
  const consoleErrors: string[] = [];
  const failed: FailedRequest[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("response", (res) => {
    const status = res.status();
    if (status >= 400) {
      failed.push({ url: res.url(), status, method: res.request().method() });
    }
  });
  page.on("requestfailed", (req) => {
    failed.push({ url: req.url(), status: 0, method: req.method() });
  });
  return { consoleErrors, failed };
}

function requiredCoverageFailures(failed: FailedRequest[]): FailedRequest[] {
  return failed.filter((item) => {
    const url = item.url;
    if (!/127\.0\.0\.1:(8758|5173)/.test(url)) return false;
    if (item.status === 500 && url.includes("/api/")) return true;
    if (item.status !== 404) return false;
    return (
      /\/api\/health(?:\?|$)/.test(url) ||
      /\/api\/projects\/[^/?]+\/library(?:\?|$)/.test(url) ||
      /\/api\/image-product\/compile(?:\?|$)/.test(url) ||
      /\/api\/image-studio\/.*compile-preview/.test(url)
    );
  });
}

function assertNoRequiredCoverageFailures(failed: FailedRequest[]) {
  const bad = requiredCoverageFailures(failed);
  expect(bad, `required coverage request failed: ${JSON.stringify(bad)}`).toEqual([]);
}

test.describe("Workflow coverage wiring", () => {
  test("CIS compile-preview with refs stamps IMAGE_I2I and pins zimage I2I on compile", async ({ request }) => {
    const lib = await request.get(`${API}/api/projects/${PROJECT}/library`);
    expect(lib.ok(), `library ${lib.status()}`).toBeTruthy();
    const items = ((await lib.json()).items || []).filter((item: { kind?: string }) =>
      String(item.kind || "").toLowerCase().includes("image"),
    );
    test.skip(!items.length, "No library image to use as a reference");
    const refId = items[0].id as string;

    const preview = await request.post(`${API}/api/image-studio/projects/${PROJECT}/cinematic/compile-preview`, {
      data: {
        prompt: "Korri holds the coffee cup in soft window light",
        projectId: PROJECT,
        modelFamilyPreference: "zimage",
        referenceAssetIds: [refId],
        controls: { category: "general", aspectRatio: "16:9", shotIntent: "medium" },
      },
    });
    expect(preview.ok(), `compile-preview ${preview.status()}`).toBeTruthy();
    const body = await preview.json();
    expect(body.imageProductBody?.taskType).toBe("IMAGE_I2I");
    expect(body.imageProductBody?.referenceAssetIds).toContain(refId);

    const compiled = await request.post(`${API}/api/image-product/compile`, {
      data: {
        projectId: PROJECT,
        prompt: "Korri holds the coffee cup in soft window light",
        purpose: "general",
        modelFamilyPreference: "zimage",
        lockModelFamily: true,
        taskType: "IMAGE_I2I",
        referenceAssetIds: [refId],
      },
    });
    expect(compiled.ok(), `compile ${compiled.status()}`).toBeTruthy();
    const out = await compiled.json();
    const key = out.imageRuntime?.workflowKey || out.contract?.workflowKey;
    expect(key).toBe("zimage.ref_edit");
    expect(out.imageIntent?.sourceAssetId || out.imageIntent?.source_asset_id).toBe(refId);
  });

  test("Brand Studio is retired from Adept UI v1.1", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), `health ${health.status()}`).toBeTruthy();
    const catalog = await (await request.get(`${API}/api/generation-tools/catalog`)).json();
    const ids = (catalog.tools as { id: string }[]).map((tool) => tool.id);
    expect(ids).not.toContain("brand.studio");
    const capture = attachCoverageCapture(page);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=brandstudio`);
    await expect(page).not.toHaveURL(/workspace=brandstudio/, { timeout: 45_000 });
    await expect(page.getByTestId("brand-studio")).toHaveCount(0);
    assertNoRequiredCoverageFailures(capture.failed);
  });

  test("PoseCraft Send to Image Gen is consumed by CIS as a reference", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), `health ${health.status()}`).toBeTruthy();
    const lib = await request.get(`${API}/api/projects/${PROJECT}/library`);
    expect(lib.ok(), `library ${lib.status()}`).toBeTruthy();
    const items = ((await lib.json()).items || []).filter((item: { kind?: string }) =>
      String(item.kind || "").toLowerCase().includes("image"),
    );
    test.skip(!items.length, "No library image for PoseCraft handoff");
    const assetId = items[0].id as string;
    const capture = attachCoverageCapture(page);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await page.evaluate(
      ({ projectId, assetId: id }) => {
        sessionStorage.setItem(
          `adept.posecraft.handoff.${projectId}`,
          JSON.stringify({
            snapshotId: "playwright-snap",
            imageAssetId: id,
            honestyLabel: "PoseCraft Snapshot — Visual Staging Reference",
            at: Date.now(),
          }),
        );
      },
      { projectId: PROJECT, assetId },
    );
    await page.reload();
    await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/PoseCraft Snapshot/i)).toBeVisible({ timeout: 15_000 });
    assertNoRequiredCoverageFailures(capture.failed);
  });

  test("Avatar Plan Sections is separate from Generate Video", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), `health ${health.status()}`).toBeTruthy();
    const capture = attachCoverageCapture(page);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=avatar`);
    const workspace = page.getByTestId("avatar-studio-workspace");
    const needsCharacter = page.getByTestId("avatar-requires-character");
    await expect(workspace.or(needsCharacter)).toBeVisible({ timeout: 45_000 });
    if (await needsCharacter.count()) {
      const picker = page.getByTestId("avatar-character-select");
      if (await picker.count()) {
        const options = picker.locator("option");
        if ((await options.count()) > 1) {
          await picker.selectOption({ index: 1 });
        }
      }
    }
    const plan = page.getByTestId("avatar-plan-button");
    const generate = page.getByTestId("avatar-generate-button");
    await expect(plan).toBeVisible({ timeout: 20_000 });
    await expect(generate).toBeVisible();
    await expect(plan).toHaveText(/Plan Sections/i);
    await expect(generate).toHaveText(/Generate Video/i);
    await expect(generate).toBeDisabled();
    assertNoRequiredCoverageFailures(capture.failed);
  });

  test("Voice Identity shows Clone and Upload routes", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), `health ${health.status()}`).toBeTruthy();
    const capture = attachCoverageCapture(page);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=voicestudio`);
    await expect(page.getByTestId("voice-studio-shell")).toBeVisible({ timeout: 45_000 });
    const identityPanel = page.getByTestId("voice-identity-panel");
    if ((await identityPanel.count()) === 0) {
      const korriCard = page.locator("article").filter({ hasText: "Korri" }).first();
      const openKorri = korriCard.getByRole("button", { name: "Open Voice Studio" });
      if (await openKorri.count()) {
        await openKorri.click();
      } else {
        await page.getByRole("button", { name: "Open Voice Studio" }).first().click();
      }
    }
    await expect(page.getByTestId("voice-identity-panel")).toBeVisible({ timeout: 20_000 });
    const identityTab = page.getByTestId("voice-identity-tab");
    if (await identityTab.count()) {
      await identityTab.click();
    }
    const clone = page.getByTestId("vs-method-clone");
    await expect(clone).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("vs-method-upload")).toBeVisible();
    await clone.click();
    await expect(page.getByTestId("vs-clone-file")).toBeVisible();
    await expect(page.getByTestId("vs-clone-consent")).toBeVisible();
    await page.getByTestId("vs-method-upload").click();
    await expect(page.getByTestId("vs-upload-file")).toBeVisible();
    await expect(page.getByTestId("vs-upload-consent")).toBeVisible();
    assertNoRequiredCoverageFailures(capture.failed);
  });

  test("Audio Studio stays on isolated workers and shows Setup when not ready", async ({ page, request }) => {
    const health = await request.get(`${API}/api/health`);
    expect(health.ok(), `health ${health.status()}`).toBeTruthy();
    const capture = attachCoverageCapture(page);
    await page.goto(`${WEB}/project/${PROJECT}?workspace=audio`);
    await expect(page.getByTestId("audio-studio-workspace")).toBeVisible({ timeout: 45_000 });
    const comfyProbe = capture.failed.filter((item) => /:8188\//.test(item.url));
    expect(comfyProbe, `Audio must not hit Comfy: ${JSON.stringify(comfyProbe)}`).toEqual([]);
    assertNoRequiredCoverageFailures(capture.failed);
  });
});
