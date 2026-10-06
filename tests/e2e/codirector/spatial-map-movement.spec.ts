/**
 * Spatial Map M1–M5 restoration + GPT Image 2 ERS default.
 * Named cert project only. Never writes the production Atlas map.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API } from "../helpers/app";
import { openCoDirectorFullScreen } from "./helpers/audit";

const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2bc632b8-b329-4d3b-bc40-b68dc41b6bb1";
const PRODUCTION_MAP = "e6f64c3b-2533-4549-a476-bf0dcb90d298";
const PRODUCTION_ATLAS = "9f7d4571-9444-41fa-b4c2-29c27919736a";
const ERS_MAP = "d7c721c3-9377-4eca-bea7-3c2be2e5e5fc";
const ERS_EXECUTION = "0e86ed60-fbb9-4677-93ac-bec2fe66b458";

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

async function openSpatialMap(page: Page) {
  await openCoDirectorFullScreen(page, PROJECT_ID);
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

async function selectMap(page: Page, mapId: string) {
  const selector = page.getByTestId("spatial-map-selector");
  if (await selector.isVisible().catch(() => false)) {
    await page.locator("#spatial-map-select").selectOption(mapId);
    await page.waitForTimeout(600);
  }
}

async function restoreProduction(request: APIRequestContext) {
  try {
    await request.patch(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP}`, {
      data: { notes: `restore-production ${Date.now()}` },
    });
  } catch {
    // API recycle mid-test must not hide the real assertion.
  }
}

test.describe("Spatial Map movement restoration + GPT ERS default", () => {
  test.afterEach(async ({ request }) => {
    await restoreProduction(request);
    const atlas = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${PRODUCTION_MAP}`);
    if (atlas.ok()) {
      const body = await atlas.json();
      expect(body.document?.backgroundAssetId || body.backgroundAssetId).toBe(PRODUCTION_ATLAS);
    }
  });

  test("accordion, slot Move persist, CD meters, GPT-only ERS", async ({ page, request }) => {
    const mapRes = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    expect(mapRes.ok(), "ERS Production Cert map must exist").toBeTruthy();
    const before = await mapRes.json();
    expect(before.document?.id || before.id).toBe(ERS_MAP);
    expect(ERS_MAP).not.toBe(PRODUCTION_MAP);

    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    await expect(page.getByTestId("spatial-map-movements")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("spatial-map-add-movement")).toBeVisible();

    const add = page.getByTestId("spatial-map-add-movement");
    if (await add.isEnabled()) {
      await add.click();
      await expect(page.getByTestId("spatial-map-movement-2")).toBeVisible({ timeout: 15_000 });
    }
    await expect(page.getByTestId("spatial-map-movement-1")).toBeVisible();
    await page.getByTestId("spatial-map-movement-1").locator("button").first().click();
    await expect(page.getByTestId("spatial-map-movement-1")).toContainText(/Active/i);

    const moveBtn = page.getByTestId("character-move-0");
    if (await moveBtn.isVisible().catch(() => false)) {
      await moveBtn.click();
      await expect(page.getByTestId("placement-mode-banner")).toBeVisible();
      const cell = page.locator('[data-testid^="cell-circle-"]').first();
      if (await cell.isVisible().catch(() => false)) {
        await cell.click({ force: true });
        await expect(page.getByTestId("placement-mode-banner")).toHaveCount(0, { timeout: 15_000 });
      } else {
        await page.getByTestId("placement-mode-cancel").click();
      }
    }

    const docAfterMove = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    const movedBody = await docAfterMove.json();
    const liveChar = (movedBody.document?.characters || [])[0];
    expect(movedBody.document?.movementSegments?.length || 0).toBeGreaterThanOrEqual(1);

    if (liveChar?.id) {
      const proposal = await request.post(`${API}/api/codirector/projects/${PROJECT_ID}/tools/proposals`, {
        data: {
          toolId: "spatial.move_placement",
          arguments: {
            documentId: ERS_MAP,
            targetType: "character",
            targetId: liveChar.id,
            metersNorth: 1,
          },
        },
      });
      expect(proposal.ok(), await proposal.text()).toBeTruthy();
      const proposed = await proposal.json();
      const proposalId = proposed.id || proposed.proposal?.id;
      const approved = await request.post(
        `${API}/api/codirector/projects/${PROJECT_ID}/proposals/${proposalId}/approve`,
        { data: {} },
      );
      expect(approved.ok(), await approved.text()).toBeTruthy();
    }

    await page.reload();
    await openSpatialMap(page);
    await selectMap(page, ERS_MAP);
    await expect(page.getByTestId("spatial-map-movements")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("spatial-map-movement-1")).toBeVisible();
    await expect(page.getByTestId("character-move-0").or(page.getByTestId("spatial-map-add-movement"))).toBeVisible();

    const reloaded = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps/${ERS_MAP}`);
    const reloadedBody = await reloaded.json();
    expect(reloadedBody.document?.id).toBe(ERS_MAP);
    expect(reloadedBody.document?.movementSegments?.length || 0).toBeGreaterThanOrEqual(1);

    const ersSelect = page.getByTestId("ers-generator-select");
    if (await ersSelect.isVisible().catch(() => false)) {
      await expect(ersSelect).toHaveValue("gpt-image-2");
      const optionValues = await ersSelect.locator("option").evaluateAll((opts) =>
        opts.map((o) => (o as HTMLOptionElement).value),
      );
      expect(optionValues).toEqual(["gpt-image-2"]);
    }

    const exec = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions/${ERS_EXECUTION}`);
    if (exec.ok()) {
      const body = await exec.json();
      const payload = JSON.stringify(body);
      expect(payload).not.toMatch(/qwen2512\.ref/);
      expect(String(body.plan_data?.ers_pipeline || "")).toBe("components");
      const jobIds = (body.child_jobs || []).map((row: { job_id?: string }) => row.job_id).filter(Boolean);
      expect(jobIds.length).toBeGreaterThan(0);
      for (const jobId of jobIds) {
        const jobRes = await request.get(`${API}/api/jobs/${jobId}`);
        expect(jobRes.ok(), `job ${jobId}`).toBeTruthy();
        const job = await jobRes.json();
        let history: Record<string, unknown> = {};
        if (job.history_json && typeof job.history_json === "object") history = job.history_json;
        else if (typeof job.history_json === "string") {
          try {
            history = JSON.parse(job.history_json);
          } catch {
            history = {};
          }
        }
        const provenance = (history.provenance || {}) as Record<string, unknown>;
        const workflow = String(job.comfy_prompt_id || provenance.workflow || "").toLowerCase();
        expect(workflow).toContain("gpt-image-2-image-to-image");
        expect(workflow).not.toMatch(/qwen2512/);
      }
    }
  });
});
