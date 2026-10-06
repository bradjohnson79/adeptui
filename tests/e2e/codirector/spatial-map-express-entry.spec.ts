/**
 * Co-Director Spatial Map Express entry: API-only GPT Image 2 form.
 * Named cert project only. Does not spawn projects.
 */
import { expect, test, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const ENV_DESC = "a silver underground research corridor with an elevator at the south end";

test.setTimeout(6 * 60 * 1000);

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

async function openCoDirectorSpatialMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

test.describe("Co-Director Spatial Map Express entry", () => {
  test("Co-Director is Express API-only and Standard remains on the spatial workspace", async ({
    page,
    request,
  }) => {
    await expect.poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 }).toBeTruthy();
    await openCoDirectorSpatialMap(page);

    await expect(page.getByTestId("spatial-map-mode-toggle")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-mode-express")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-mode-standard")).toHaveCount(0);
    await expect(page.getByText("Improve Spatial Understanding")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);
    await expect(page.getByText("Generation Method", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Environment Type", { exact: true })).toHaveCount(0);

    const form = page.getByTestId("spatial-map-express-form");
    const atlas = page.getByTestId("active-atlas-panel");
    if (await form.isVisible().catch(() => false)) {
      await expect(page.getByText("Create Spatial Map with Co-Director")).toBeVisible();
      await expect(
        page.getByTestId("spatial-map-atlas-engine").or(page.getByTestId("spatial-map-gpt-required")),
      ).toBeVisible();
      await expect(page.getByTestId("scene-description-input")).toBeVisible();
      await expect(page.getByTestId("spatial-map-select-library")).toBeVisible();
      await expect(page.getByTestId("spatial-map-upload-reference")).toBeVisible();
      await expect(page.getByTestId("spatial-map-generate")).toBeVisible();
      await expect(page.getByText("Create Environment with Co-Director")).toHaveCount(0);
      await expect(page.getByText("Reconstruct from Location Image")).toHaveCount(0);
      await expect(page.getByText("Use Existing Atlas")).toHaveCount(0);
      await page.screenshot({
        path: "docs/release-gate/spatial-map/evidence/api-only/express-form.png",
        fullPage: true,
      });
    } else {
      await expect(atlas).toBeVisible();
      await expect(page.locator(".spatial-map__slot-group-title").getByText("Characters", { exact: true })).toBeVisible();
      await expect(page.locator(".spatial-map__slot-group-title").getByText("Props", { exact: true })).toBeVisible();
      await expect(page.locator(".spatial-map__slot-group-title").getByText("Cameras", { exact: true })).toBeVisible();
    }

    await page.goto(`/project/${PROJECT_ID}?tab=spatial`);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
    const standardChooser = page.getByTestId("spatial-map-start-chooser");
    if (await standardChooser.isVisible().catch(() => false)) {
      await expect(page.getByTestId("spatial-map-start-design")).toBeVisible();
      await expect(page.getByTestId("spatial-map-start-location")).toBeVisible();
      await expect(page.getByTestId("spatial-map-start-atlas")).toBeVisible();
    } else {
      await expect(page.getByTestId("active-atlas-panel")).toBeVisible();
    }
  });

  test("textarea, help tip, Atlas Engine, and Generate readiness", async ({ page }) => {
    await openCoDirectorSpatialMap(page);
    const form = page.getByTestId("spatial-map-express-form");
    if (!(await form.isVisible().catch(() => false))) {
      test.info().annotations.push({
        type: "note",
        description: "Existing Spatial Map present; empty-form controls skipped.",
      });
      return;
    }

    const help = page.getByTestId("scene-description-help").locator("button").first();
    await help.hover();
    await expect(page.locator(".help-tip-bubble").first()).toContainText("Describe the environment you want");
    await page.mouse.move(0, 0);
    await help.click();
    await expect(page.locator(".help-tip-bubble").first()).toContainText("rooms, corridors, doors");
    await help.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".help-tip-bubble").first()).toBeVisible();
    await page.keyboard.press("Escape");

    const textarea = page.getByTestId("scene-description-input");
    await textarea.fill(ENV_DESC);
    await expect(textarea).toHaveValue(ENV_DESC);

    await expect(page.getByTestId("spatial-map-generation-method")).toHaveCount(0);
    await expect(page.getByTestId("spatial-map-environment-type")).toHaveCount(0);

    if (await page.getByTestId("spatial-map-gpt-required").isVisible().catch(() => false)) {
      await expect(page.getByTestId("spatial-map-generate")).toBeDisabled();
      await expect(page.getByTestId("spatial-map-generate-reason")).toContainText("GPT Image 2");
      await expect(page.getByTestId("spatial-map-open-settings")).toBeVisible();
    } else {
      await expect(page.getByTestId("spatial-map-atlas-engine")).toContainText("GPT Image 2");
      await expect(page.getByTestId("spatial-map-generate")).toBeEnabled();
    }
  });

  test("Library, upload, remove/replace, and Generate request contract", async ({ page }) => {
    await openCoDirectorSpatialMap(page);
    const form = page.getByTestId("spatial-map-express-form");
    if (!(await form.isVisible().catch(() => false))) {
      test.info().annotations.push({
        type: "note",
        description: "Existing Spatial Map present; reference/generate skipped.",
      });
      return;
    }

    const executions: Array<Record<string, unknown>> = [];
    page.on("request", (req) => {
      if (req.method() === "POST" && /\/executions\/?$/.test(req.url())) {
        try {
          executions.push(req.postDataJSON() as Record<string, unknown>);
        } catch {
          /* ignore */
        }
      }
    });

    await page.getByTestId("scene-description-input").fill(ENV_DESC);
    await page.getByTestId("spatial-map-select-library").click();
    const picker = page.getByRole("dialog").or(page.locator(".spatial-map__picker, [data-testid='entity-picker']")).first();
    if (await picker.isVisible({ timeout: 8_000 }).catch(() => false)) {
      const firstImage = picker.locator("button, [role='option'], img").first();
      if (await firstImage.isVisible().catch(() => false)) {
        await firstImage.click();
        const confirm = picker.getByRole("button", { name: /confirm|use|select/i }).first();
        if (await confirm.isVisible().catch(() => false)) await confirm.click();
      } else {
        await page.keyboard.press("Escape");
      }
    }

    const fileInput = page.getByTestId("spatial-map-reference-file");
    await fileInput.setInputFiles({
      name: "express-ref.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
        "base64",
      ),
    });
    await expect(page.getByTestId("spatial-map-selected-reference")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("scene-description-input")).toHaveValue(ENV_DESC);

    await page.getByTestId("spatial-map-remove-reference").click();
    await expect(page.getByTestId("spatial-map-selected-reference")).toHaveCount(0);

    await fileInput.setInputFiles({
      name: "express-ref-2.png",
      mimeType: "image/png",
      buffer: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
        "base64",
      ),
    });
    await expect(page.getByTestId("spatial-map-selected-reference")).toBeVisible({ timeout: 20_000 });

    if (await page.getByTestId("spatial-map-generate").isEnabled()) {
      await page.getByTestId("spatial-map-generate").click();
      await expect.poll(() => executions.length, { timeout: 15_000 }).toBeGreaterThan(0);
      const body = executions[executions.length - 1];
      const ctx = (body.context || {}) as Record<string, unknown>;
      expect(String(ctx.generationMethod || ctx.generation_method)).toBe("api");
      expect(String(ctx.hostedModelId || ctx.hosted_model_id)).toBe("gpt-image-2-kie");
      expect(String(ctx.source || "")).toBe("api");
      expect(ctx.environmentType).toBeUndefined();
      expect(ctx.environment_type).toBeUndefined();
      expect(JSON.stringify(ctx)).not.toContain("environmentClass");
      expect(JSON.stringify(ctx)).not.toMatch(/qwen2512|flux\.txt2img|moge|vggt/i);
      expect(String(ctx.environmentDescription || ctx.scene_description || body.prompt)).toContain("silver underground");
      await expect(page.getByTestId("atlas-generation-monitor")).toBeVisible({ timeout: 15_000 });
    } else {
      await expect(page.getByTestId("spatial-map-gpt-required")).toBeVisible();
      const before = executions.length;
      await page.getByTestId("spatial-map-generate").click({ force: true }).catch(() => undefined);
      expect(executions.length).toBe(before);
    }
  });
});
