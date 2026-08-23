/**
 * Image Generator Library references + accordion UX.
 * Schnick Coffee only — never POST /api/projects.
 */
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = process.env.ADEPT_WEB_URL || process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.ADEPT_API_URL || process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT =
  process.env.ADEPT_SCHNICK_PROJECT_ID ||
  process.env.ADEPT_PROJECT_ID ||
  "2347bf46-3762-4763-86c5-4a6032522278";
const ARTIFACTS = path.resolve("artifacts/image-generator-refs");

const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
);

function ensureDir(dir: string) {
  fs.mkdirSync(dir, { recursive: true });
}

test.describe("Image Generator library references + accordion UX", () => {
  test("upload, add reference, accordions, compile assetIds, reload", async ({ page, request }) => {
    ensureDir(ARTIFACTS);
    const lib = await request.get(`${API}/api/projects/${PROJECT}/library`);
    expect(lib.ok()).toBeTruthy();
    const items = ((await lib.json()).items || []).filter((item: { kind?: string; mime_type?: string }) => {
      const hay = `${item.kind || ""} ${item.mime_type || ""}`.toLowerCase();
      return hay.includes("image") || hay.includes("environment");
    });
    expect(items.length).toBeGreaterThan(2);
    const pick = items.slice(0, 3) as Array<{ id: string }>;

    await page.goto(`${WEB}/project/${PROJECT}?workspace=imagegen`);
    await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({
      timeout: 60_000,
    });
    const plan = page.getByTestId("cis-accordion-image-plan");
    if (!(await plan.evaluate((el) => (el as HTMLDetailsElement).open))) {
      await plan.locator("summary").click();
    }

    const category = page.getByTestId("cis-category");
    const options = await category.locator("option").allTextContents();
    expect(options).not.toContain("Storyboard");
    expect(options).toContain("General");
    await expect(page.getByTestId("cis-color-grade")).toBeVisible();
    await expect(page.getByRole("button", { name: /Open Storyboard/i })).toBeVisible();

    const refs = page.getByTestId("cis-accordion-references");
    if (!(await refs.evaluate((el) => (el as HTMLDetailsElement).open))) {
      await refs.locator("summary").click();
    }
    await expect(page.getByTestId("cis-reference-browser")).toBeVisible();
    await expect(page.getByTestId("cis-upload-library")).toBeVisible();

    const uploadPath = path.join(ARTIFACTS, "upload-cert.png");
    fs.writeFileSync(uploadPath, TINY_PNG);
    await page.getByTestId("cis-upload-library-input").setInputFiles(uploadPath);
    await expect(page.getByText(/Image added to the project Library/i)).toBeVisible({ timeout: 30_000 });

    for (const asset of pick) {
      await page.getByTestId(`cis-ref-card-${asset.id}`).click();
    }
    await expect(page.getByTestId("cis-ref-selected-count")).toContainText("3 selected");
    await page.getByTestId("cis-add-reference").click();
    await expect(page.getByTestId("cis-active-ref-count")).toContainText("3 active");
    for (const asset of pick) {
      await expect(page.getByTestId(`cis-active-ref-${asset.id}`)).toBeVisible();
    }

    const removeId = pick[2].id;
    await page.getByTestId(`cis-remove-ref-${removeId}`).click();
    await expect(page.getByTestId("cis-active-ref-count")).toContainText("2 active");
    const stillThere = await request.get(`${API}/api/assets/${removeId}/file`);
    expect(stillThere.status()).toBeLessThan(400);

    const scroller = page.getByTestId("cis-ref-scroller");
    await expect(scroller).toBeVisible();
    const box = await scroller.evaluate((el) => ({
      clientHeight: (el as HTMLElement).clientHeight,
      scrollHeight: (el as HTMLElement).scrollHeight,
    }));
    expect(box.clientHeight).toBeLessThanOrEqual(box.scrollHeight);
    if (box.scrollHeight > box.clientHeight + 8) {
      await scroller.evaluate((el) => {
        (el as HTMLElement).scrollTop = (el as HTMLElement).scrollHeight;
      });
    }

    await refs.locator("summary").click();
    await expect(page.getByTestId("cis-reference-browser")).toBeHidden();
    await page.getByTestId("cis-accordion-camera").locator("summary").click();
    await page.getByTestId("cis-accordion-camera").locator("summary").click();
    const hosted = page.getByTestId("cis-accordion-hosted-api");
    if (await hosted.count()) {
      if (!(await hosted.evaluate((el) => (el as HTMLDetailsElement).open))) await hosted.locator("summary").click();
      await expect(page.getByTestId("cis-hosted-api-card")).toBeVisible();
      await expect(page.getByText("Generation Source")).toBeVisible();
    }
    const pi = page.getByTestId("cis-accordion-prompt-intelligence");
    if (!(await pi.evaluate((el) => (el as HTMLDetailsElement).open))) await pi.locator("summary").click();
    await expect(page.getByTestId("prompt-intelligence-strategy-mode-recommend")).toBeVisible();
    await expect(page.getByTestId("prompt-intelligence-preview")).toBeVisible();

    const remaining = pick.slice(0, 2).map((a) => a.id);
    const preview = await request.post(
      `${API}/api/image-studio/projects/${PROJECT}/cinematic/compile-preview`,
      {
        data: {
          prompt: "Korri tastes Schnick Coffee",
          projectId: PROJECT,
          referenceAssetIds: remaining,
          controls: { category: "general", colorGradePreset: "natural", aspectRatio: "16:9", shotIntent: "medium" },
        },
      }
    );
    expect(preview.ok()).toBeTruthy();
    const body = await preview.json();
    const ids = body.imageProductBody?.referenceAssetIds || [];
    const intentIds = body.imageProductBody?.creativeContext?.reference_image_ids || [];
    expect(ids).toEqual(expect.arrayContaining(remaining));
    expect(intentIds).toEqual(expect.arrayContaining(remaining));
    expect(body.imageProductBody?.taskType).toBe("IMAGE_I2I");
    fs.writeFileSync(path.join(ARTIFACTS, "compile-preview-refs.json"), JSON.stringify(body, null, 2));

    await page.screenshot({ path: path.join(ARTIFACTS, "imagegen-refs-accordion.png"), fullPage: true });
    await page.reload();
    await expect(page.getByRole("heading", { name: /Cinematic Image Generator/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("cis-accordion-image-plan")).toBeVisible();
    await expect(page.getByTestId("cis-color-grade")).toBeVisible();
    const after = await request.get(`${API}/api/projects/${PROJECT}/library`);
    const afterItems = ((await after.json()).items || []) as Array<{ id: string; filename?: string; tag?: string }>;
    const uploaded = afterItems.some(
      (item) => item.filename === "upload-cert.png" || (item.tag || "").includes("upload-cert")
    );
    expect(uploaded).toBeTruthy();
  });
});
