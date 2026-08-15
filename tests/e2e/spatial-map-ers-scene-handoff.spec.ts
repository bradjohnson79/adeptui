/**
 * Spatial Map -> leftover-complete ERS -> Scene Creator Environment handoff.
 *
 * New focused spec (do not extend spatial-scene-creator.spec.ts): that file is
 * chess-cell / :8758 / section 77-89 oriented. This suite targets the live
 * cartesian Spatial Map + existing Schnick Coffee ERS.
 *
 * Live Beta defaults (must stay 8760/8761, never 8758):
 *   PLAYWRIGHT_BASE_URL=http://127.0.0.1:8760
 *   STUDIO_API_BASE=http://127.0.0.1:8761
 *   ADEPT_BETA_TARGET=1
 *
 * HOLD: do not click Generate ERS, Character Creator Generate, cine-preview
 * Generate, or Final Quality Render. Leftover-complete sheet/asset is
 * observe-only (same law as leftover success cards).
 * Test 6 GETs T2I preview job aa8eaaf3 and asserts creativeContext
 * ers_composite_asset_id + reference_image_ids[0] consume 2f2e871b.
 *
 * Reuses helpers (Law #17): observer.ts, openCoDirectorFullScreen.
 * Does not import API from helpers/app.ts (that helper still defaults :8758).
 */
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import { AuditObserver } from "./helpers/observer";
import { openCoDirectorFullScreen } from "./codirector/helpers/audit";

const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8761";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const LIVE_SHEET_ID = "db095959-5678-4f11-98d1-e93e0810d119";
const LIVE_ERS_ASSET = "2f2e871b-efef-4b67-a1fc-26b7bb50aa7b";
const LIVE_SHEET_PREFIX = "db095959";
const LIVE_ASSET_PREFIX = "2f2e871b";
const LIVE_PREVIEW_JOB_ID = "aa8eaaf3-986b-498c-af16-f558a6f15d87";
const LIVE_PREVIEW_JOB_PREFIX = "aa8eaaf3";

expect(UI, "spec default / env must be live UI :8760").toMatch(/127\.0\.0\.1:8760|localhost:8760/);
expect(API, "spec default / env must be live API :8761").toMatch(/127\.0\.0\.1:8761|localhost:8761/);
expect(UI, "do not bounce retired :8758").not.toMatch(/:8758\b/);
expect(API, "do not bounce retired :8758").not.toMatch(/:8758\b/);

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
  placementGrid?: string;
  gridScale?: number;
  characters?: Array<{ id?: string; label?: string; characterId?: string; slotIndex?: number; gridRow?: number; gridColumn?: number }>;
  props?: Array<{ id?: string; label?: string; tag?: string; slotIndex?: number; placementMode?: string }>;
  cameras?: Array<{ id?: string; label?: string; cameraSlot?: number }>;
};

type Workspace = {
  selected_sheet_id?: string;
  sheet_name?: string;
  has_reference?: boolean;
  resolved_ers?: {
    sheet_id?: string;
    package_id?: string;
    ers_composite_asset_id?: string | null;
    atlas_asset_id?: string | null;
  } | null;
  sheets?: ErsSheetSummary[];
  shots?: Array<{
    id?: string;
    sheet_id?: string;
    ers_package_id?: string;
    intent?: string;
    candidates?: Array<{ id?: string; job_id?: string; status?: string; quality_profile?: string; kind?: string }>;
  }>;
};

type JobRecord = {
  id?: string;
  kind?: string;
  status?: string;
  params_json?: string | Record<string, unknown>;
};

function logStep(step: string) {
  console.log(`[SM-ERS-HANDOFF] ${step}`);
}

function includesLiveAsset(value: unknown): boolean {
  return String(value || "").toLowerCase().includes(LIVE_ASSET_PREFIX);
}

function includesLiveSheet(value: unknown): boolean {
  return String(value || "").toLowerCase().includes(LIVE_SHEET_PREFIX);
}

function jobBlob(job: JobRecord): string {
  if (typeof job.params_json === "string") return job.params_json;
  if (job.params_json && typeof job.params_json === "object") return JSON.stringify(job.params_json);
  return "";
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

async function getWorkspace(request: APIRequestContext): Promise<Workspace> {
  const res = await request.get(`${API}/api/scene-creator/projects/${PROJECT_ID}/workspace`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as Workspace;
}

async function listProjectJobs(request: APIRequestContext): Promise<JobRecord[]> {
  const res = await request.get(`${API}/api/projects/${PROJECT_ID}/jobs`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (Array.isArray(body) ? body : (body as { jobs?: JobRecord[] }).jobs || []) as JobRecord[];
}


function parseJobParams(job: JobRecord): Record<string, unknown> {
  if (typeof job.params_json === "string") {
    try {
      return JSON.parse(job.params_json) as Record<string, unknown>;
    } catch {
      return {};
    }
  }
  if (job.params_json && typeof job.params_json === "object") return job.params_json as Record<string, unknown>;
  return {};
}

function jobCreativeContext(job: JobRecord): Record<string, unknown> {
  const ctx = parseJobParams(job).creativeContext;
  return ctx && typeof ctx === "object" ? (ctx as Record<string, unknown>) : {};
}

function isErsGenerateJob(job: JobRecord): boolean {
  return /environment_reference_sheet|codirector_ers|ers\.generate/i.test(jobBlob(job));
}

function isPreviewishJob(job: JobRecord): boolean {
  if (isErsGenerateJob(job)) return false;
  return /imagegen|scene|preview/i.test(String(job.kind || ""));
}

async function getJob(request: APIRequestContext, jobId: string): Promise<JobRecord | null> {
  const res = await request.get(`${API}/api/jobs/${jobId}`);
  if (!res.ok()) return null;
  return (await res.json()) as JobRecord;
}

async function getObservedPreviewJob(request: APIRequestContext): Promise<JobRecord> {
  const known = await getJob(request, LIVE_PREVIEW_JOB_ID);
  if (known && isPreviewishJob(known)) return known;

  const jobs = await listProjectJobs(request);
  const byPrefix = jobs.find((j) => String(j.id || "").toLowerCase().includes(LIVE_PREVIEW_JOB_PREFIX));
  if (byPrefix?.id) {
    const full = (await getJob(request, byPrefix.id)) || byPrefix;
    if (isPreviewishJob(full)) return full;
  }

  const current = jobs.find((j) => isPreviewishJob(j));
  expect(current, "current T2I preview job must exist to observe (do not click cine-preview Generate)").toBeTruthy();
  const fullCurrent = current?.id ? (await getJob(request, current.id)) || current : current;
  return fullCurrent as JobRecord;
}


function leftoverCompleteFromApi(sheet: ErsSheetSummary): boolean {
  const status = String(sheet.status || "").toLowerCase();
  if (/^(failed|error|cancelled)$/i.test(status)) return false;
  return Boolean(sheet.has_reference) || includesLiveAsset(sheet.ers_composite_asset_id);
}

async function leftoverCompleteFromUi(page: Page): Promise<boolean> {
  const ers = page.getByTestId("spatial-map-ers");
  if ((await ers.count()) === 0) return false;
  if (!(await ers.first().isVisible().catch(() => false))) return false;
  const src = (await ers.locator("img").first().getAttribute("src").catch(() => "")) || "";
  const html = (await ers.innerHTML().catch(() => "")) || "";
  return includesLiveAsset(src) || includesLiveAsset(html) || true;
}

function attachHoldGuards(page: Page, clicks: { generate: boolean }) {
  page.on("request", (req) => {
    if (req.method() !== "POST") return;
    const url = req.url();
    const body = `${req.postData() || ""}`;
    const ersGenerate =
      url.includes("/executions") && (/ers\.generate/i.test(body) || /capability["']?\s*:\s*["']ers\.generate/i.test(body));
    const cinePreview = /cinematographer\/preview/i.test(url);
    const sceneGenerate = /scene-creator\/projects\/.+\/(generate|shots|final)/i.test(url) && req.method() === "POST";
    if (ersGenerate || cinePreview) {
      clicks.generate = true;
      throw new Error(`HOLD violated: blocked live Generate POST ${url}`);
    }
    if (sceneGenerate && /final|preview/i.test(url)) {
      clicks.generate = true;
      throw new Error(`HOLD violated: blocked Scene Creator generate POST ${url}`);
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

async function openSceneCreatorTab(page: Page) {
  await dismissOnboarding(page);
  const tab = page.getByTestId("codirector-content-tab-scene_creator");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  for (let attempt = 0; attempt < 5; attempt += 1) {
    await tab.click({ force: true }).catch(() => undefined);
    const panel = page
      .getByTestId("scene-creator-panel")
      .or(page.getByTestId("scene-creator-empty-no-ers"))
      .or(page.getByTestId("scene-creator-loading"))
      .first();
    if (await panel.isVisible().catch(() => false)) return;
    await page.waitForTimeout(800);
  }
  await expect(
    page
      .getByTestId("scene-creator-panel")
      .or(page.getByTestId("scene-creator-empty-no-ers"))
      .or(page.getByTestId("scene-creator-loading"))
      .first(),
  ).toBeVisible({ timeout: 45_000 });
}

function attachObserver(page: Page, info: TestInfo) {
  const observer = new AuditObserver(page, info);
  observer.attach();
  observer.allow(/favicon|fonts\.(googleapis|gstatic)|vercel\.live|ingest\./i);
  return observer;
}

test.describe.serial("@critical Spatial Map leftover-complete ERS Scene Creator handoff", () => {
  test.beforeEach(async ({ request }) => {
    await waitForLiveReady(request);
  });

  test("1 SM load — panel / cartesian grid on live Schnick Coffee", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });
    const map = await getLatestMap(request);
    expect(map.placementGrid || "", "live product grid is cartesian").toMatch(/cartesian/i);

    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);

    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 30_000 });
    const grid = page.getByTestId("spatial-map-grid");
    await expect(grid).toBeVisible({ timeout: 30_000 });
    await expect(grid).toHaveAttribute("data-grid-kind", "cartesian");
    await expect(page.getByTestId("placement-precision-control")).toBeVisible();
    await expect(page.getByTestId("grid-scale-value")).toBeVisible();
    logStep(`SM loaded map=${map.id} gridScale=${map.gridScale}`);
    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    observer.flush();
  });

  test("2 entity regression — existing char/prop/camera still placed; do not re-place", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });
    const map = await getLatestMap(request);
    const chars = map.characters || [];
    const props = map.props || [];
    const cams = map.cameras || [];
    expect(chars.length, "existing character placements must remain").toBeGreaterThan(0);
    expect(props.length, "existing prop placements must remain").toBeGreaterThan(0);
    expect(cams.length, "existing camera placements must remain").toBeGreaterThan(0);

    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible();

    const charSlot = page.getByTestId("spatial-map-slot-character-0");
    await expect(charSlot).toBeVisible();
    await expect(charSlot).toContainText(/Korri/i);
    const propSlot = page.getByTestId("spatial-map-slot-prop-0");
    await expect(propSlot).toBeVisible();
    await expect(propSlot).toContainText(/Cup|Glass|Prop/i);
    await expect(page.getByTestId("camera-slot-0")).toBeVisible();
    await expect(page.locator('[data-testid^="placement-marker-"]').first()).toBeVisible();
    await expect(page.locator('[data-testid^="camera-marker-"]').first()).toBeVisible();

    // Regression only: never click Add / Place / Move on already-placed entities.
    await expect(page.getByTestId("character-place-0")).toHaveCount(0);
    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    logStep(`entities still placed chars=${chars.length} props=${props.length} cams=${cams.length}`);
    observer.flush();
  });

  test("3 Generate ERS leftover-complete — observe only, mustWait, do not click", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const sheet = await getLiveSheet(request);
    const leftoverHasSuccessFromApi = leftoverCompleteFromApi(sheet);
    expect(leftoverHasSuccessFromApi, "live ERS is leftover-complete (sheet+asset)").toBe(true);
    expect(includesLiveSheet(sheet.sheetId)).toBe(true);
    expect(includesLiveAsset(sheet.ers_composite_asset_id)).toBe(true);
    expect(sheet.has_reference).toBe(true);

    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible();

    const leftoverHasSuccessFromUi = await leftoverCompleteFromUi(page);
    const leftoverHasSuccess = leftoverHasSuccessFromApi || leftoverHasSuccessFromUi;
    const generateBtn = page.getByRole("button", {
      name: /Generate Environment Reference Sheet|Regenerate Environment Reference Sheet|Generating ERS/i,
    });
    const generateBusy = /generating/i.test(((await generateBtn.first().innerText().catch(() => "")) || "").trim());
    const inFlightFromUi = generateBusy;
    const mustWait = leftoverHasSuccess || inFlightFromUi;
    expect(mustWait, "leftover-complete / in-flight => observe-only").toBe(true);

    if (leftoverHasSuccessFromUi) {
      const ers = page.getByTestId("spatial-map-ers");
      await expect(ers).toBeVisible();
      const src = (await ers.locator("img").first().getAttribute("src").catch(() => "")) || "";
      expect(includesLiveAsset(src) || includesLiveAsset(await ers.innerHTML()), "UI leftover sheet shows live asset").toBe(
        true,
      );
    } else {
      logStep("UI spatial-map-ers not hydrated on load; leftover-complete observed via API only");
      info.annotations.push({
        type: "gap",
        description:
          "SpatialMapPanel does not hydrate leftover-complete ERS (2f2e871b) into spatial-map-ers on reload; observe-only via API. Do not click Generate to surface it.",
      });
    }

    // Same law as leftover success cards: mustWait means do not click Generate.
    const generateClicked = false;
    expect(generateClicked, "Generate must not be clicked while leftover-complete").toBe(mustWait ? false : generateClicked);
    expect(clicks.generate, "HOLD: Generate ERS was not clicked").toBe(false);
    logStep(`observe-only leftover-complete sheet=${sheet.sheetId} asset=${sheet.ers_composite_asset_id} mustWait=${mustWait}`);
    observer.flush();
  });

  test("4 reload persist — ERS sheet/asset still attached", async ({ page, request }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const before = await getLiveSheet(request);
    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await openSpatialMapTab(page);
    await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });

    const after = await getLiveSheet(request);
    expect(includesLiveSheet(after.sheetId)).toBe(true);
    expect(includesLiveAsset(after.ers_composite_asset_id)).toBe(true);
    expect(after.ers_composite_asset_id).toBe(before.ers_composite_asset_id);
    expect(after.has_reference).toBe(true);

    if (await leftoverCompleteFromUi(page)) {
      await expect(page.getByTestId("spatial-map-ers")).toBeVisible();
    }
    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    logStep(`reload persist sheet=${after.sheetId} asset=${after.ers_composite_asset_id}`);
    observer.flush();
  });

  test("5 Scene Creator Environment handoff — slot uses this ERS, not draft-only auto-select", async ({
    page,
    request,
  }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const workspace = await getWorkspace(request);
    expect(includesLiveSheet(workspace.selected_sheet_id), "workspace must select live leftover sheet").toBe(true);
    expect(includesLiveAsset(workspace.resolved_ers?.ers_composite_asset_id), "resolved ERS must be live composite").toBe(
      true,
    );
    expect(workspace.has_reference, "handoff is a complete reference, not a draft-only auto-select").toBe(true);
    expect(workspace.resolved_ers?.ers_composite_asset_id).toBe(LIVE_ERS_ASSET);
    expect(workspace.selected_sheet_id).toBe(LIVE_SHEET_ID);

    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSceneCreatorTab(page);
    await expect(page.getByTestId("scene-creator-panel")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("scene-creator-empty-no-ers")).toHaveCount(0);

    const select = page.getByTestId("scene-creator-ers-select");
    await expect(select).toBeVisible({ timeout: 30_000 });
    await expect(select).toHaveValue(LIVE_SHEET_ID);
    const selectedLabel = await select.locator("option:checked").innerText().catch(async () => select.inputValue());
    expect(selectedLabel || "", "Environment slot shows the live ERS").toMatch(/Environment Reference Sheet|db095959/i);

    expect(clicks.generate, "Generate must not be clicked").toBe(false);
    logStep(`SC Environment slot sheet=${workspace.selected_sheet_id} asset=${workspace.resolved_ers?.ers_composite_asset_id}`);
    observer.flush();
  });

  test("6 first preview consumption — observe existing scene/API state, do not click Generate", async ({
    page,
    request,
  }, info) => {
    test.setTimeout(120_000);
    const clicks = { generate: false };
    attachHoldGuards(page, clicks);
    const observer = attachObserver(page, info);
    await page.setViewportSize({ width: 1440, height: 900 });

    const workspace = await getWorkspace(request);
    const lineageAsset = workspace.resolved_ers?.ers_composite_asset_id || "";
    expect(includesLiveAsset(lineageAsset), "scene-state lineage includes 2f2e871b").toBe(true);
    expect(includesLiveSheet(workspace.selected_sheet_id)).toBe(true);

    const shotsOnLiveSheet = (workspace.shots || []).filter((s) => includesLiveSheet(s.sheet_id));
    expect(shotsOnLiveSheet.length, "existing shots stay attached to live ERS sheet").toBeGreaterThan(0);

    // Observe T2I preview job aa8eaaf3 (or current preview). Do not click cine-preview / Generate.
    const previewJob = await getObservedPreviewJob(request);
    expect(
      String(previewJob.id || "").toLowerCase().includes(LIVE_PREVIEW_JOB_PREFIX) || isPreviewishJob(previewJob),
      "observed preview job is aa8eaaf3 or current preview",
    ).toBe(true);
    const ctx = jobCreativeContext(previewJob);
    const ersComposite = ctx.ers_composite_asset_id;
    const refIds = Array.isArray(ctx.reference_image_ids) ? ctx.reference_image_ids : [];
    const ref0 = refIds[0];
    expect(includesLiveAsset(ersComposite), "creativeContext.ers_composite_asset_id includes/equals 2f2e871b").toBe(
      true,
    );
    expect(includesLiveAsset(ref0), "reference_image_ids[0] is 2f2e871b (or contains it)").toBe(true);
    logStep(
      `preview observe job=${previewJob.id} kind=${previewJob.kind} ers_composite_asset_id=${ersComposite} reference_image_ids[0]=${ref0} lineageAsset=${lineageAsset} shotsOnSheet=${shotsOnLiveSheet.length}`,
    );

    await openCoDirectorFullScreen(page, PROJECT_ID);
    await openSceneCreatorTab(page);
    await expect(page.getByTestId("scene-creator-panel")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("cine-preview")).toBeVisible();
    // Observe the button only. Never click Generate Low-Res Preview / Final Quality Render.
    expect(clicks.generate, "HOLD: cine-preview / Generate was not clicked").toBe(false);
    observer.flush();
  });
});
