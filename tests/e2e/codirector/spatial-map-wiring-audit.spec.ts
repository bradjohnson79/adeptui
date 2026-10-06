/**
 * Surgical Spatial Map wiring audit — Korri Anadriya only.
 * Does not remake Character Creator views. Does not start Comfy.
 * Captures the live Generate path and records the actual provider (fal vs Kie vs local).
 */
import { expect, test, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const ENV_DESC = "a silver underground research corridor with an elevator at the south end";

test.setTimeout(4 * 60 * 1000);

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

async function openSpatialMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

test.describe("Spatial Map wiring audit — Express GPT Image 2", () => {
  test("Express controls are wired; Generate is not fal.ai GPT Image 2", async ({ page, request }) => {
    await expect.poll(async () => (await request.get(`${API}/api/healthz`)).ok(), { timeout: 60_000 }).toBeTruthy();

    const mapsBefore = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
    expect(mapsBefore.ok(), await mapsBefore.text()).toBeTruthy();
    const mapsBody = (await mapsBefore.json()) as { documents?: Array<{ id?: string; backgroundAssetId?: string }> };
    expect(mapsBody.documents || []).toHaveLength(0);

    const providers = await request.get(`${API}/api/image-studio/providers?includeUnready=true`);
    const providerBody = providers.ok() ? ((await providers.json()) as { providers?: Array<Record<string, unknown>> }) : { providers: [] };
    const gptRows = (providerBody.providers || []).filter((row) =>
      /gpt-image-2|gpt_image_2/i.test(JSON.stringify(row)),
    );
    const falGpt = gptRows.filter((row) => /fal/i.test(JSON.stringify(row)));
    test.info().annotations.push({
      type: "audit",
      description: `GPT provider rows=${gptRows.length} fal-tagged=${falGpt.length} sample=${JSON.stringify(gptRows[0] || {})}`,
    });

    await openSpatialMap(page);

    const form = page.getByTestId("spatial-map-express-form");
    await expect(form).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("spatial-map-atlas-engine")).toContainText("GPT Image 2");
    await expect(page.getByTestId("scene-description-input")).toBeVisible();
    await expect(page.getByTestId("spatial-map-select-library")).toBeEnabled();
    await expect(page.getByTestId("spatial-map-upload-reference")).toBeEnabled();
    await expect(page.getByTestId("spatial-map-generate")).toBeDisabled();
    await expect(page.getByTestId("spatial-map-generate-reason")).toBeVisible();
    await expect(page.getByTestId("spatial-map-reference-file")).toHaveCount(0);

    await page.getByTestId("spatial-map-select-library").click();
    const picker = page.locator(".spatial-map__picker").first();
    await expect(picker).toBeVisible({ timeout: 15_000 });
    const pickerClose = picker.locator(".spatial-map__picker-close").first();
    if (await pickerClose.isVisible().catch(() => false)) {
      await pickerClose.click();
    } else {
      await page.keyboard.press("Escape");
    }
    await expect(picker).toBeHidden({ timeout: 10_000 });

    const hiddenFiles = page.locator('input[type="file"][accept="image/*"]');
    expect(await hiddenFiles.count()).toBeGreaterThan(0);

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
    await expect(page.getByTestId("spatial-map-generate")).toBeEnabled();

    const waitExec = page.waitForResponse(
      (res) => res.url().includes("/executions") && res.request().method() === "POST" && !res.url().includes("/cancel"),
      { timeout: 30_000 },
    );
    await page.getByTestId("spatial-map-generate").click();
    const execRes = await waitExec;
    const execJson = (await execRes.json().catch(() => ({}))) as {
      execution_id?: string;
      executionId?: string;
      child_jobs?: Array<{ job_id?: string }>;
      status?: string;
      error?: string;
    };
    expect(execRes.status(), JSON.stringify(execJson)).toBeLessThan(500);
    expect(executions.length).toBeGreaterThan(0);
    const posted = executions[executions.length - 1];
    const ctx = (posted.context || {}) as Record<string, unknown>;
    expect(String(posted.capability || "")).toBe("atlas.generate");
    expect(String(ctx.hostedModelId || ctx.hosted_model_id)).toBe("gpt-image-2-kie");
    expect(String(ctx.generationMethod || ctx.generation_method)).toBe("api");
    expect(JSON.stringify(ctx)).not.toMatch(/fal-ai|fal\.ai/i);

    const executionId = String(execJson.execution_id || execJson.executionId || "");
    test.info().annotations.push({
      type: "audit",
      description: `execution POST status=${execRes.status()} id=${executionId} body=${JSON.stringify(execJson).slice(0, 1200)}`,
    });

    let jobId = String(execJson.child_jobs?.[0]?.job_id || "");
    if (!jobId && executionId) {
      const fetched = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}`);
      if (fetched.ok()) {
        const pack = (await fetched.json()) as { child_jobs?: Array<{ job_id?: string }>; childJobs?: Array<{ job_id?: string }> };
        jobId = String(pack.child_jobs?.[0]?.job_id || pack.childJobs?.[0]?.job_id || "");
      }
    }

    let jobLeak = "";
    if (jobId) {
      const jobRes = await request.get(`${API}/api/jobs/${jobId}`);
      jobLeak = await jobRes.text();
      test.info().annotations.push({ type: "audit", description: `job ${jobId} ${jobRes.status()} ${jobLeak.slice(0, 1600)}` });
    }

    if (executionId) {
      await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/executions/${executionId}/cancel`).catch(() => undefined);
    }

    expect.soft(jobLeak, "queued job must not be local Z-Image when UI says GPT Image 2").not.toMatch(/zimage\.txt2img/i);
    expect.soft(jobLeak, "GPT Image 2 Spatial Map is not a fal.ai job").not.toMatch(/fal-ai|fal\.ai/i);
    expect.soft(String(ctx.hostedModelId || ""), "UI/API request pins Kie, not fal").toBe("gpt-image-2-kie");

    await expect(page.getByTestId("spatial-map-express-form")).toBeVisible();
    await expect(page.getByTestId("cc-v2-studio")).toHaveCount(0);
  });
});
