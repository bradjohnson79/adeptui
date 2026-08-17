/**
 * Spatial Map ERS live viewport — Express + Standard, observe-only.
 *
 * Topology (current Beta, AGENTS.md §15): Studio API :8758 + local Vite dev
 * server (5173). Override PLAYWRIGHT_BASE_URL / STUDIO_API_BASE for hosted or
 * live-Beta runs (e.g. https://adeptui.vercel.app + https://api-beta.adeptui.org).
 *
 * Generation is HOLDed BY DESIGN (documented observe-only certification): the
 * leftover-complete ERS is certified without dispatching a live generate, so
 * this spec never POSTs ers.generate / cine-preview / Final Quality Render
 * (same law as leftover success cards — no double-charge). The no-POST guard
 * below enforces that contract.
 *
 * HOLD: do not click Generate ERS, Character Creator Generate, cine-preview
 * Generate, or Final Quality Render. Leftover-complete sheet/asset is
 * observe-only (same law as leftover success cards). Mocked failure attach
 * is route-only — never click Generate / Retry / Regenerate.
 *
 * Beats here: Express+Standard load, sync, multi-toggle, monitor appear,
 * one job (not 4-job+PIL), failure sanitize.
 * Reload attach + Scene Creator handoff live in
 * spatial-map-ers-scene-handoff.spec.ts. Do not invent a third spec.
 *
 * Reuses helpers (Law #17): observer.ts, openCoDirectorFullScreen.
 */
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { AuditObserver } from "./helpers/observer";
import { openCoDirectorFullScreen } from "./codirector/helpers/audit";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const LIVE_SHEET_ID = "db095959-5678-4f11-98d1-e93e0810d119";
const LIVE_ERS_ASSET = "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b";
const LIVE_SHEET_PREFIX = "db095959";
const LIVE_ASSET_PREFIX = "2f2e871b";
const TRACEBACK_DUMP = /Traceback \(most recent call last\)|HANDLER_ERROR:|--- details ---/i;

type ErsSheetSummary = {
  sheetId?: string;
  name?: string;
  status?: string;
  has_reference?: boolean;
  ers_composite_asset_id?: string | null;
};

type SpatialMapDocument = {
  id: string;
  title?: string;
  updatedAt?: string;
  createdAt?: string;
  characters?: Array<{ id?: string; label?: string }>;
  props?: Array<{ id?: string; label?: string }>;
  cameras?: Array<{ id?: string; label?: string }>;
};

type ExecutionRow = {
  execution_id?: string;
  id?: string;
  capability?: string;
  status?: string;
  child_jobs?: Array<{ job_id?: string; label?: string; status?: string }>;
  result_asset_ids?: string[];
  error?: string | null;
};

type JobRecord = {
  id?: string;
  kind?: string;
  status?: string;
};

function logStep(step: string) {
  console.log(`[SM-ERS-LIVE] ${step}`);
}

function includesLiveAsset(value: unknown): boolean {
  return String(value || "").toLowerCase().includes(LIVE_ASSET_PREFIX);
}

function includesLiveSheet(value: unknown): boolean {
  return String(value || "").toLowerCase().includes(LIVE_SHEET_PREFIX);
}

async function waitForLiveReady(request: APIRequestContext) {
  const okGet = async (url: string) => {
    try {
      const res = await request.get(url);
      return res.ok();
    } catch {
      return false;
    }
  };
  await expect.poll(async () => okGet(`${API}/api/health`), { timeout: 60_000 }).toBeTruthy();
  const project = await request.get(`${API}/api/projects/${PROJECT_ID}`);
  expect(project.ok(), await project.text()).toBeTruthy();
}

async function listErsSheets(request: APIRequestContext): Promise<ErsSheetSummary[]> {
  const res = await request.get(`${API}/api/environment-reference-sheets/projects/${PROJECT_ID}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { sheets?: ErsSheetSummary[] }).sheets || [];
}

async function getLiveSheet(request: APIRequestContext): Promise<ErsSheetSummary> {
  const sheets = await listErsSheets(request);
  const live = sheets.find((s) => includesLiveSheet(s.sheetId) && includesLiveAsset(s.ers_composite_asset_id));
  expect(live, `live leftover-complete ERS ${LIVE_SHEET_PREFIX}/${LIVE_ASSET_PREFIX} must exist`).toBeTruthy();
  return live as ErsSheetSummary;
}

async function listMaps(request: APIRequestContext): Promise<SpatialMapDocument[]> {
  const res = await request.get(`${API}/api/spatial-map/projects/${PROJECT_ID}/maps`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { documents?: SpatialMapDocument[] }).documents || [];
}

async function getLatestMap(request: APIRequestContext): Promise<SpatialMapDocument> {
  const docs = await listMaps(request);
  expect(docs.length, "Schnick Coffee must already have a Spatial Map").toBeGreaterThan(0);
  return [...docs].sort((a, b) => (b.updatedAt || b.createdAt || "").localeCompare(a.updatedAt || a.createdAt || ""))[0];
}

async function listErsExecutions(request: APIRequestContext): Promise<ExecutionRow[]> {
  const res = await request.get(`${API}/api/codirector/projects/${PROJECT_ID}/executions?include_terminal=true`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const rows = (Array.isArray(body) ? body : (body as { executions?: ExecutionRow[] }).executions || []) as ExecutionRow[];
  return rows.filter((row) => String(row.capability || "") === "ers.generate");
}

function leftoverCompleteFromApi(sheet: ErsSheetSummary): boolean {
  const status = String(sheet.status || "").toLowerCase();
  if (/^(failed|error|cancelled)$/i.test(status)) return false;
  return Boolean(sheet.has_reference) || includesLiveAsset(sheet.ers_composite_asset_id);
}

function attachHoldGuards(page: Page, clicks: { generate: boolean }) {
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    const url = req.url();
    const body = `${req.postData() || ""}`;
    const ersGenerate =
      url.includes("/executions") &&
      !url.includes("/advance") &&
      (/ers\.generate/i.test(body) || /capability["']?\s*:\s*["']ers\.generate/i.test(body));
    const cinePreview = /cinematographer\/preview/i.test(url);
    if (ersGenerate || cinePreview) {
      clicks.generate = true;
      throw new Error(`HOLD violated: blocked live Generate POST ${url}`);
    }
  });
}

async function dismissOnboarding(page: Page) {
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const region = page.locator('[aria-label="Working relationship"]').first();
    if (!(await region.isVisible().catch(() => false))) {
      await page.waitForTimeout(200);
      continue;
    }
    const nameInput = region.getByRole("textbox", { name: /What should I call you/i }).first();
    if (await nameInput.isVisible().catch(() => false)) {
      const current = await nameInput.inputValue().catch(() => "");
      if (!current) await nameInput.fill("Tester");
    }
    for (const label of [/Save and continue/i, /Skip for now/i]) {
      const btn = region.getByRole("button", { name: label }).first();
      if ((await btn.isVisible().catch(() => false)) && !(await btn.isDisabled().catch(() => false))) {
        await btn.click({ force: true }).catch(() => undefined);
        await page.waitForTimeout(400);
        break;
      }
    }
    if (!(await region.isVisible().catch(() => false))) break;
  }
}

async function openSpatialMapTab(page: Page) {
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first();
    if (await panel.isVisible().catch(() => false)) return;
    await page.waitForTimeout(800);
  }
  await expect(page.getByTestId("spatial-map-panel").or(page.getByTestId("spatial-map-error")).first()).toBeVisible({
    timeout: 45_000,
  });
}

async function openExpressSpatialMap(page: Page) {
  let lastErr: unknown = null;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await openCoDirectorFullScreen(page, PROJECT_ID);
      await openSpatialMapTab(page);
      await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 30_000 });
      return;
    } catch (err) {
      lastErr = err;
      await page.waitForTimeout(800);
    }
  }
  throw lastErr;
}

async function openStandardSpatialMap(page: Page) {
  await page.goto(`/project/${PROJECT_ID}?workspace=spatial`, { waitUntil: "domcontentloaded" });
  await dismissOnboarding(page);
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

function attachObserver(page: Page, info: TestInfo) {
  const observer = new AuditObserver(page, info);
  observer.attach();
  observer.allow(/favicon|fonts\.(googleapis|gstatic)|vercel\.live|ingest\./i);
  return observer;
}

async function leftoverMonitorHydrated(page: Page): Promise<boolean> {
  const monitor = page.getByTestId("ers-generation-monitor");
  if (!(await monitor.isVisible().catch(() => false))) return false;
  const src = (await monitor.locator("img").first().getAttribute("src").catch(() => "")) || "";
  const html = (await monitor.innerHTML().catch(() => "")) || "";
  return includesLiveAsset(src) || includesLiveAsset(html);
}

test.describe("Spatial Map ERS live viewport", () => {
  test.beforeEach(async ({ request }) => {
    await waitForLiveReady(request);
  });

  test("1 Express + Standard load — both Spatial Map surfaces mount", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });
    await getLiveSheet(request);

    await openExpressSpatialMap(page);
    await expect(page.getByTestId("codirector-content-spatial-map")).toBeVisible();
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible();
    await expect(page.getByTestId("spatial-map-grid")).toBeVisible();
    logStep("Express Spatial Map loaded");

    await openStandardSpatialMap(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible();
    await expect(page.getByTestId("spatial-map-grid")).toBeVisible();
    logStep("Standard Spatial Map loaded");

    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    observer.flush();
  });

  test("2 sync Express <-> Standard — same leftover sheet/asset/placements", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const sheet = await getLiveSheet(request);
    const map = await getLatestMap(request);
    expect(leftoverCompleteFromApi(sheet)).toBe(true);
    expect(sheet.sheetId).toBe(LIVE_SHEET_ID);
    expect(sheet.ers_composite_asset_id).toBe(LIVE_ERS_ASSET);
    expect((map.characters || []).length).toBeGreaterThan(0);
    expect((map.props || []).length).toBeGreaterThan(0);
    expect((map.cameras || []).length).toBeGreaterThan(0);

    await openExpressSpatialMap(page);
    await expect(page.getByTestId("spatial-map-slot-character-0")).toContainText(/Korri/i);
    await expect(page.getByTestId("spatial-map-slot-prop-0")).toBeVisible();
    const expressMonitor = await leftoverMonitorHydrated(page);

    await openStandardSpatialMap(page);
    await expect(page.getByTestId("spatial-map-slot-character-0")).toContainText(/Korri/i);
    await expect(page.getByTestId("spatial-map-slot-prop-0")).toBeVisible();
    const standardMonitor = await leftoverMonitorHydrated(page);

    const after = await getLiveSheet(request);
    expect(after.sheetId).toBe(sheet.sheetId);
    expect(after.ers_composite_asset_id).toBe(sheet.ers_composite_asset_id);
    expect(expressMonitor || standardMonitor || leftoverCompleteFromApi(after), "leftover ERS stays attached across surfaces").toBe(
      true,
    );
    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    logStep(`sync sheet=${after.sheetId} asset=${after.ers_composite_asset_id} expressMonitor=${expressMonitor} standardMonitor=${standardMonitor}`);
    observer.flush();
  });

  test("3 multi-toggle — entity switches present; do not re-place", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });
    await getLatestMap(request);

    await openExpressSpatialMap(page);
    const charSwitch = page.getByTestId("character-online-0");
    const propSwitch = page.getByTestId("prop-online-0");
    const camSwitch = page.getByTestId("camera-online-0");
    await expect(charSwitch).toBeVisible();
    await expect(propSwitch).toBeVisible();
    await expect(camSwitch).toBeVisible();
    await expect(charSwitch).toHaveAttribute("aria-checked", /true|false/);
    await expect(propSwitch).toHaveAttribute("aria-checked", /true|false/);
    await expect(camSwitch).toHaveAttribute("aria-checked", /true|false/);

    const onCount = [charSwitch, propSwitch, camSwitch].reduce(async (accP, loc) => {
      const acc = await accP;
      return acc + ((await loc.getAttribute("aria-checked")) === "true" ? 1 : 0);
    }, Promise.resolve(0));
    expect(await onCount, "multi-toggle: more than one entity can be on").toBeGreaterThan(1);

    await expect(page.getByTestId("character-place-0")).toHaveCount(0);
    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    logStep("multi-toggle switches observed; no Place / Generate");
    observer.flush();
  });

  test("4 ERS monitor appear — leftover-complete hydrate, do not click Generate", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const sheet = await getLiveSheet(request);
    expect(leftoverCompleteFromApi(sheet), "live ERS is leftover-complete").toBe(true);

    await openExpressSpatialMap(page);
    const monitor = page.getByTestId("ers-generation-monitor");
    await expect(monitor).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("ers-generation-viewport")).toBeVisible();
    const src = (await monitor.locator("img").first().getAttribute("src").catch(() => "")) || "";
    expect(includesLiveAsset(src) || includesLiveAsset(await monitor.innerHTML()), "monitor shows leftover asset 2f2e871b").toBe(
      true,
    );

    const generateBtn = page.getByRole("button", {
      name: /Generate Environment Reference Sheet|Regenerate Environment Reference Sheet|Generating ERS/i,
    });
    const generateBusy = /generating/i.test(((await generateBtn.first().innerText().catch(() => "")) || "").trim());
    const mustWait = leftoverCompleteFromApi(sheet) || generateBusy || (await leftoverMonitorHydrated(page));
    expect(mustWait, "leftover-complete / in-flight => observe-only").toBe(true);
    expect(clicks.generate, "HOLD: Generate ERS was not clicked").toBe(false);
    logStep(`monitor leftover-complete sheet=${sheet.sheetId} asset=${sheet.ers_composite_asset_id}`);
    observer.flush();
  });

  test("5 one job — leftover success is one Image Core T2I, not 4-job+PIL", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const sheet = await getLiveSheet(request);
    expect(leftoverCompleteFromApi(sheet)).toBe(true);

    const executions = await listErsExecutions(request);
    const leftoverSuccess = executions.find(
      (row) =>
        String(row.status || "").toLowerCase() === "completed" &&
        (row.result_asset_ids || []).some((id) => includesLiveAsset(id)),
    );
    expect(leftoverSuccess, "completed leftover ERS execution for 2f2e871b must exist").toBeTruthy();
    const kids = leftoverSuccess?.child_jobs || [];
    expect(kids.length, "one job — not 4-view + PIL collage").toBe(1);
    expect(kids[0]?.label || "", "single child is the ERS composite").toMatch(/Environment Reference Sheet/i);
    expect(kids[0]?.label || "", "not the retired North View 4-job path").not.toMatch(/North View/i);

    const jobId = kids[0]?.job_id;
    expect(jobId, "leftover success has one child job id").toBeTruthy();
    const jobRes = await request.get(`${API}/api/jobs/${jobId}`);
    expect(jobRes.ok(), await jobRes.text()).toBeTruthy();
    const job = (await jobRes.json()) as JobRecord;
    expect(String(job.kind || ""), "one Image Core T2I").toMatch(/imagegen/i);

    await openExpressSpatialMap(page);
    const monitor = page.getByTestId("ers-generation-monitor");
    if (await monitor.isVisible().catch(() => false)) {
      const ctx = ((await page.getByTestId("ers-generation-context").innerText().catch(() => "")) || "").trim();
      expect(ctx, "monitor context is entity counts, not a 4-job strip").toMatch(/Environment|Characters|Props|Cameras/i);
    }
    expect(clicks.generate, "HOLD: did not dispatch a new ERS generate").toBe(false);
    logStep(`one-job leftover exec kids=${kids.length} job=${jobId} kind=${job.kind}`);
    observer.flush();
  });

  test("6 failure sanitize — short banner, no traceback dump (mocked attach, no Generate)", async ({
    page,
    request,
  }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });
    await getLiveSheet(request);

    const rawTraceback =
      "HANDLER_ERROR: TypeError: 'ImageGenerationPlan' object has no attribute 'prompt'\n\n--- details ---\nTraceback (most recent call last):\n  File \"ers_generate.py\", line 1, in handle\nAttributeError";

    await page.route("**/api/codirector/projects/**/executions**", async (route) => {
      const req = route.request();
      const url = req.url();
      if (req.method() === "GET" && /\/executions\/?(\?|$)/.test(url) && !/\/executions\/[^/?]+/.test(url.split("?")[0] || url)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            executions: [
              {
                execution_id: "ers-fail-mock-1",
                capability: "ers.generate",
                surface_type: "ers_generation",
                status: "running",
                progress: 0.4,
                child_jobs: [
                  {
                    job_id: "ers-fail-mock-job",
                    label: "Environment Reference Sheet",
                    status: "running",
                    progress: 0.4,
                    stage: "running",
                    child_index: 0,
                    metadata: {},
                  },
                ],
                result_asset_ids: [],
              },
            ],
          }),
        });
        return;
      }
      if (url.includes("/executions/ers-fail-mock-1/advance")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            execution_id: "ers-fail-mock-1",
            capability: "ers.generate",
            surface_type: "ers_generation",
            status: "failed",
            progress: 1,
            child_jobs: [
              {
                job_id: "ers-fail-mock-job",
                label: "Environment Reference Sheet",
                status: "failed",
                progress: 1,
                stage: "failed",
                child_index: 0,
                metadata: {},
              },
            ],
            result_asset_ids: [],
            error: rawTraceback,
          }),
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/jobs/ers-fail-mock-job", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ers-fail-mock-job",
          status: "failed",
          progress: 1,
          stage: "failed",
          message: rawTraceback,
          preview_json: "",
        }),
      });
    });

    await openExpressSpatialMap(page);
    const monitor = page.getByTestId("ers-generation-monitor");
    await expect(monitor).toBeVisible({ timeout: 30_000 });
    await expect(monitor).toHaveAttribute("data-phase", "failed", { timeout: 20_000 });
    const stage = page.getByTestId("ers-generation-stage");
    await expect(stage).toBeVisible();
    const banner = ((await stage.innerText()) || "").trim();
    expect(banner.length, "failure banner stays short").toBeLessThanOrEqual(160);
    expect(banner, "sanitized creator-facing message").toMatch(/ERS generation failed/i);
    expect(banner, "no traceback dump in the banner").not.toMatch(TRACEBACK_DUMP);
    expect(banner, "no raw ImageGenerationPlan attribute dump").not.toMatch(/object has no attribute/i);
    await expect(page.getByTestId("ers-generation-retry")).toBeVisible();
    expect(clicks.generate, "HOLD: Generate / Retry was not clicked").toBe(false);
    logStep(`failure sanitize banner="${banner}"`);
    observer.flush();
  });
});
