import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, createTempProject, deleteProject, waitForAppReady } from "../helpers/app";
import {
  captureHandoffSnapshot,
  createProjectViaHomeUi,
  deleteDisposableProjects,
  expectHandoffUnchanged,
  MANUAL_HANDOFF_ID,
  monitorProjectCreatePosts,
  openCoDirectorFullScreen,
} from "./helpers/autonomousCert";

type ProposalSummary = {
  id: string;
  status: string;
  title?: string;
};

type ErsSheet = {
  sheetId: string;
  status: string;
  spatialMap?: { mapId?: string | null; northLockDirection?: string | null; warnings: string[] } | null;
  directionalViews: Array<{
    direction: "north" | "east" | "south" | "west";
    approvedAssetId?: string | null;
    status: string;
  }>;
  continuity: {
    status: string;
    summary: string;
    note?: string | null;
    preservedDirections: string[];
    findings: Array<{ code: string; title: string; message: string }>;
  };
  composition: {
    continuitySummary: string;
    lastRenderedAt?: string | null;
  };
  exports: Array<{
    exportKind: "png" | "pdf" | "offline_html";
    status: string;
    assetId?: string | null;
    filePath?: string | null;
    archiveName?: string | null;
    message: string;
  }>;
};

type SpatialMapDocument = {
  id: string;
  title: string;
  warnings: string[];
};

type ProjectJob = {
  id: string;
  status: string;
  stage?: string | null;
  message?: string | null;
  params_json?: string | null;
};

const PROJECT_PREFIX = "HELIOS-ERS-CERT";
const ISO_PREFIX = "HELIOS-ERS-ISO";
const DIRECTIONS = ["north", "east", "south", "west"] as const;
type Direction = (typeof DIRECTIONS)[number];

function logStep(step: string) {
  console.log(`[ERS CERT] ${step}`);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function createToolProposal(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  toolId: string,
  args: Record<string, unknown>,
) {
  const requestId = `ers-cert-${toolId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const res = await fetch(`${API}/api/codirector/projects/${projectId}/tools/proposals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      toolId,
      arguments: args,
      requestId,
      createdBy: "user",
    }),
  });
  const response = {
    ok: res.ok,
    status: res.status,
    text: await res.text(),
  };
  expect(response.ok, response.text).toBeTruthy();
  return JSON.parse(response.text) as { id: string; title?: string; status?: string };
}

async function listProposals(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/proposals`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.proposals || []) as ProposalSummary[];
}

async function getProposalStatus(request: APIRequestContext, projectId: string, proposalId: string) {
  const proposals = await listProposals(request, projectId);
  const proposal = proposals.find((entry) => entry.id === proposalId);
  expect(proposal, `Proposal ${proposalId} not found.`).toBeTruthy();
  return proposal!.status;
}

async function approveProposalByApi(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  proposalId: string,
) {
  const res = await fetch(`${API}/api/codirector/projects/${projectId}/proposals/${proposalId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decidedBy: "user" }),
  });
  const response = {
    ok: res.ok,
    status: res.status,
    text: await res.text(),
  };
  expect(response.ok, response.text).toBeTruthy();
  await expect
    .poll(async () => getProposalStatus(request, projectId, proposalId), { timeout: 30_000 })
    .toBe("completed");
}

async function approveProposalFromUi(
  page: Page,
  request: APIRequestContext,
  projectId: string,
  proposalId: string,
) {
  await page.getByTestId("codirector-content-tab-approvals").click();
  let card = page.getByTestId("codirector-approvals-panel").getByTestId(`codirector-proposal-card-${proposalId}`);
  if (!(await card.isVisible().catch(() => false))) {
    await page.reload();
    await expect(page.getByTestId("codirector-composer-input")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("codirector-content-tab-approvals").click();
    card = page.getByTestId("codirector-approvals-panel").getByTestId(`codirector-proposal-card-${proposalId}`);
  }
  await expect(card).toBeVisible({ timeout: 30_000 });
  await card.getByRole("button", { name: "Approve" }).click();
  await expect
    .poll(async () => getProposalStatus(request, projectId, proposalId), { timeout: 30_000 })
    .toBe("completed");
}

async function getSheet(request: APIRequestContext, projectId: string, sheetId: string) {
  const res = await request.get(`${API}/api/environment-reference-sheets/projects/${projectId}/${sheetId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { sheet: ErsSheet }).sheet;
}

async function listSheets(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/environment-reference-sheets/projects/${projectId}`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { sheets: Array<{ sheetId: string; name: string }> }).sheets;
}

async function listMaps(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/spatial-map/projects/${projectId}/maps`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return ((await res.json()) as { documents: SpatialMapDocument[] }).documents;
}

async function getErsToolAvailability(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/codirector/projects/${projectId}/tools/availability`);
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return (body.availability || []) as Array<{
    toolId: string;
    available: boolean;
    capabilityStatus: string;
    reason?: string | null;
  }>;
}

async function listJobs(request: APIRequestContext, projectId: string) {
  const res = await request.get(`${API}/api/projects/${projectId}/jobs`);
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as ProjectJob[];
}

function parseJobParams(job: ProjectJob) {
  if (!job.params_json) return null;
  try {
    return JSON.parse(job.params_json) as {
      output_asset_id?: string;
      imageIntent?: { purpose?: string };
      purpose?: string;
    };
  } catch {
    return null;
  }
}

function directionFromJob(job: ProjectJob): Direction | null {
  const params = parseJobParams(job);
  const purpose = String(params?.imageIntent?.purpose || params?.purpose || "");
  const match = purpose.match(/ers-(north|east|south|west)-view/);
  return (match?.[1] as Direction | undefined) || null;
}

function directionAssetMapFromJobs(jobs: ProjectJob[]) {
  const assets: Partial<Record<Direction, string>> = {};
  for (const job of jobs) {
    if (job.status !== "done") continue;
    const direction = directionFromJob(job);
    const assetId = parseJobParams(job)?.output_asset_id;
    if (!direction || !assetId || assets[direction]) continue;
    assets[direction] = assetId;
  }
  return assets;
}

async function waitForDirectionalAssetIds(request: APIRequestContext, projectId: string) {
  await expect
    .poll(async () => Object.keys(directionAssetMapFromJobs(await listJobs(request, projectId))).sort(), {
      timeout: 15 * 60_000,
      intervals: [2_000, 5_000, 10_000],
    })
    .toEqual([...DIRECTIONS].sort());

  const assets = directionAssetMapFromJobs(await listJobs(request, projectId));
  return assets as Record<Direction, string>;
}

async function settleProjectJobsForCleanup(request: APIRequestContext, projectId: string) {
  const terminal = new Set(["done", "failed", "cancelled", "cancel_failed_runtime_active"]);
  const jobs = await listJobs(request, projectId);
  for (const job of jobs) {
    if (terminal.has(job.status)) continue;
    const res = await request.post(`${API}/api/jobs/${job.id}/cancel`);
    if (!res.ok() && ![404, 409].includes(res.status())) {
      expect(res.ok(), await res.text()).toBeTruthy();
    }
  }

  await expect
    .poll(async () => {
      const next = await listJobs(request, projectId);
      return next.every((job) => terminal.has(job.status));
    }, { timeout: 3 * 60_000, intervals: [2_000, 5_000] })
    .toBeTruthy();

  await sleep(1_000);
}

async function openErsPlansPanel(page: Page) {
  await page.getByTestId("codirector-content-tab-plans").click();
  const panel = page.getByTestId("codirector-ers-panel").or(page.getByTestId("codirector-ers-empty")).first();
  await expect(panel).toBeVisible({ timeout: 30_000 });
  return panel;
}

test.describe.serial("@critical codirector ers autonomous certification", () => {
  test.beforeEach(async ({ request }) => {
    await waitForAppReady(request);
  });

  test("ERS panel stays review-only until a canonical sheet exists", async ({ page, request }) => {
    const project = await createTempProject(request, `ERS Panel ${Date.now()}`);
    try {
      await openCoDirectorFullScreen(page, project.id);
      await openErsPlansPanel(page);
      await expect(page.getByText(/Ask Co-Director to create an Environment Reference Sheet/i)).toBeVisible();
      await expect(page.getByRole("button", { name: /create environment reference sheet/i })).toHaveCount(0);
    } finally {
      await deleteProject(request, project.id);
    }
  });

  test("Helios Research Atrium disposable-project certification covers creation repair review export and cleanup", async ({
    page,
    request,
  }) => {
    test.slow();
    test.setTimeout(20 * 60_000);

    const createdProjectIds: string[] = [];
    const projectName = `${PROJECT_PREFIX}-${Date.now()}`;
    const isoProjectName = `${ISO_PREFIX}-${Date.now()}`;
    const handoffBefore = await captureHandoffSnapshot(request);

    try {
      await page.setViewportSize({ width: 1440, height: 900 });

      const createMonitor = monitorProjectCreatePosts(page);
      let projectId = "";
      try {
        projectId = await createProjectViaHomeUi(page, request, projectName);
      } finally {
        expect(createMonitor.getCount()).toBe(1);
        createMonitor.dispose();
      }
      createdProjectIds.push(projectId);
      logStep(`created project ${projectId}`);

      await openCoDirectorFullScreen(page, projectId);
      logStep("opened Co-Director");

      // Scenario A-B: disposable project + review-only ERS empty state
      await openErsPlansPanel(page);
      await expect(page.getByTestId("codirector-ers-empty")).toContainText(/canonical ERS exists/i);
      logStep("verified ERS empty state");

      const sceneIdRes = await request.get(`${API}/api/projects/${projectId}`);
      expect(sceneIdRes.ok(), await sceneIdRes.text()).toBeTruthy();
      const sceneId = ((await sceneIdRes.json()) as { scenes: Array<{ id: string }> }).scenes[0]?.id;
      expect(sceneId).toBeTruthy();

      // Scenario C: creator-approved Co-Director spatial map creation
      const createMapWithPromptProposal = await createToolProposal(page, request, projectId, "spatial.create_map", {
        title: "Helios Research Atrium Map",
        sceneId,
        masterEnvironmentPrompt: "Glass-roofed research atrium with layered gardens and cool daylight.",
      });
      await approveProposalFromUi(page, request, projectId, createMapWithPromptProposal.id);
      logStep("approved spatial map creation");

      let maps = await listMaps(request, projectId);
      const map = maps.find((entry) => entry.title === "Helios Research Atrium Map") || maps[0];
      expect(map?.id).toBeTruthy();
      expect(map?.warnings || []).toContain("No camera has been placed yet.");

      // Scenario D: repair Spatial Map warnings honestly before certifying continuity
      const createCameraProposal = await createToolProposal(page, request, projectId, "spatial.create_camera", {
        documentId: map.id,
        label: "North Lock Camera",
        x: 0,
        y: 1.6,
        z: -4,
        yawDegrees: 0,
        pitchDegrees: 0,
        lensMm: 24,
        hero: true,
        lockedFor360: true,
      });
      await approveProposalFromUi(page, request, projectId, createCameraProposal.id);
      logStep("approved spatial camera repair");

      maps = await listMaps(request, projectId);
      const repairedMap = maps.find((entry) => entry.id === map.id);
      expect(repairedMap?.warnings || []).toEqual([]);

      // Scenario E: canonical ERS creation via Co-Director proposal/approval
      const createSheetProposal = await createToolProposal(page, request, projectId, "ers.create_sheet", {
        name: "Helios Research Atrium",
        description:
          "Glass-roofed atrium with hanging gardens, reflective stone, cool daylight, and quiet research balconies.",
        sceneId,
        creatorNotes: "Keep the environment calm, precise, and stable across all four directions.",
      });
      await approveProposalFromUi(page, request, projectId, createSheetProposal.id);
      logStep("approved ERS draft creation");

      const sheets = await listSheets(request, projectId);
      expect(sheets).toHaveLength(1);
      const sheetId = sheets[0]!.sheetId;
      let sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.status).toBe("draft");

      await openErsPlansPanel(page);
      const ersPanel = page.getByTestId("codirector-ers-panel");
      await expect(ersPanel).toContainText("Helios Research Atrium");

      // Scenario F: attach the map and prove north lock + four-direction skeleton
      const attachMapProposal = await createToolProposal(page, request, projectId, "ers.attach_spatial_map", {
        sheetId,
        spatialMapId: map.id,
      });
      await approveProposalFromUi(page, request, projectId, attachMapProposal.id);
      logStep("attached spatial map to ERS");

      sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.spatialMap?.mapId).toBe(map.id);
      expect(sheet.spatialMap?.northLockDirection).toBe("north");
      expect(sheet.directionalViews.map((view) => view.direction)).toEqual(["north", "east", "south", "west"]);
      expect(sheet.continuity.status).toBe("warning");

      await openErsPlansPanel(page);
      await expect(ersPanel).toContainText(/North lock:\s*north/i);

      // Scenario G: generation route is callable and queues real directional jobs
      const availability = await getErsToolAvailability(request, projectId);
      const directionalGeneration = availability.find((entry) => entry.toolId === "ers.generate_directional_views");
      expect(directionalGeneration).toBeTruthy();
      expect(directionalGeneration?.available).toBeTruthy();
      expect(directionalGeneration?.capabilityStatus).toBe("locally_verified");

      const generateDirectionsProposal = await createToolProposal(page, request, projectId, "ers.generate_directional_views", {
        sheetId,
        qualityProfile: "cinematic",
        deploymentPreference: "best-match",
      });
      await approveProposalByApi(page, request, projectId, generateDirectionsProposal.id);
      logStep("queued real directional generation");

      sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.directionalViews.every((view) => view.status === "queued")).toBeTruthy();
      const generationJobs = await listJobs(request, projectId);
      expect(generationJobs.filter((job) => directionFromJob(job)).length).toBeGreaterThanOrEqual(8);

      const directionalAssets = await waitForDirectionalAssetIds(request, projectId);
      logStep("received generated directional assets");

      // Scenario H: use generated project-owned keepers for continuity review
      const approveNorthProposal = await createToolProposal(page, request, projectId, "ers.approve_direction", {
        sheetId,
        direction: "north",
        assetId: directionalAssets.north,
      });
      await approveProposalFromUi(page, request, projectId, approveNorthProposal.id);

      const validateAfterNorthProposal = await createToolProposal(page, request, projectId, "ers.validate_continuity", {
        sheetId,
      });
      await approveProposalFromUi(page, request, projectId, validateAfterNorthProposal.id);
      logStep("approved north keeper and warning-state validation");

      sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.continuity.status).toBe("warning");
      expect(sheet.continuity.preservedDirections).toEqual(["north"]);
      expect(sheet.continuity.note || "").toMatch(/metadata-based/i);
      expect(sheet.continuity.findings.map((finding) => finding.code)).toEqual(
        expect.arrayContaining(["direction_unapproved"]),
      );

      // Scenario I-J: repair remaining directions while preserving approved work
      for (const [direction, assetId] of [
        ["east", directionalAssets.east],
        ["south", directionalAssets.south],
        ["west", directionalAssets.west],
      ] as const) {
        const proposal = await createToolProposal(page, request, projectId, "ers.approve_direction", {
          sheetId,
          direction,
          assetId,
        });
        await approveProposalByApi(page, request, projectId, proposal.id);
      }
      logStep("approved east south west keepers");

      const validateFinalProposal = await createToolProposal(page, request, projectId, "ers.validate_continuity", {
        sheetId,
      });
      await approveProposalByApi(page, request, projectId, validateFinalProposal.id);
      logStep("validated full continuity");

      sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.continuity.status).toBe("ready");
      expect(sheet.continuity.preservedDirections).toEqual(["north", "east", "south", "west"]);
      expect(sheet.continuity.findings).toEqual([]);

      await openErsPlansPanel(page);
      await ersPanel.getByRole("button", { name: "Views" }).click();
      await expect(ersPanel).toContainText(/NORTH/i);
      await expect(ersPanel).toContainText(/EAST/i);
      await expect(ersPanel).toContainText(/SOUTH/i);
      await expect(ersPanel).toContainText(/WEST/i);

      // Scenario K: compose + export
      const composeProposal = await createToolProposal(page, request, projectId, "ers.compose_sheet", { sheetId });
      await approveProposalByApi(page, request, projectId, composeProposal.id);
      logStep("composed ERS sheet");

      sheet = await getSheet(request, projectId, sheetId);
      expect(sheet.composition.lastRenderedAt).toBeTruthy();
      expect(sheet.composition.continuitySummary).toMatch(/North, East, South, West/i);

      for (const exportKind of ["png", "pdf", "offline_html"] as const) {
        const proposal = await createToolProposal(page, request, projectId, "ers.export_sheet", {
          sheetId,
          exportKind,
        });
        await approveProposalByApi(page, request, projectId, proposal.id);
        logStep(`exported ${exportKind}`);
      }

      sheet = await getSheet(request, projectId, sheetId);
      const exportKinds = sheet.exports.map((entry) => entry.exportKind).sort();
      expect(exportKinds).toEqual(["offline_html", "pdf", "png"]);
      for (const entry of sheet.exports) {
        expect(entry.status).toBe("created");
        expect(entry.assetId).toBeTruthy();
        expect(entry.filePath).toBeTruthy();
      }

      await openErsPlansPanel(page);
      await ersPanel.getByRole("button", { name: "Exports" }).click();
      await expect(ersPanel).toContainText(/png/i);
      await expect(ersPanel).toContainText(/pdf/i);
      await expect(ersPanel).toContainText(/offline_html/i);
      await expect(ersPanel).toContainText(/review-only/i);

      // Scenario L: project isolation
      const isolated = await createTempProject(request, isoProjectName);
      createdProjectIds.push(isolated.id);
      logStep(`created isolation project ${isolated.id}`);
      const isolatedSheets = await listSheets(request, isolated.id);
      expect(isolatedSheets).toEqual([]);
      const isolatedMaps = await listMaps(request, isolated.id);
      expect(isolatedMaps).toEqual([]);

      const projectRes = await request.get(`${API}/api/projects/${projectId}`);
      expect(projectRes.ok(), await projectRes.text()).toBeTruthy();
      const projectBody = (await projectRes.json()) as { assets: Array<{ id: string }> };
      expect(projectBody.assets.length).toBeGreaterThanOrEqual(7);
      const exportAssetIds = new Set(sheet.exports.map((entry) => entry.assetId).filter(Boolean));
      expect(projectBody.assets.some((asset) => exportAssetIds.has(asset.id))).toBeTruthy();
    } finally {
      const handoffAfter = await captureHandoffSnapshot(request);
      expectHandoffUnchanged(handoffBefore, handoffAfter);
      for (const id of createdProjectIds) {
        if (!id || id === MANUAL_HANDOFF_ID) continue;
        await settleProjectJobsForCleanup(request, id);
      }
      await deleteDisposableProjects(request, createdProjectIds);
      for (const id of createdProjectIds) {
        if (!id || id === MANUAL_HANDOFF_ID) continue;
        const res = await request.get(`${API}/api/projects/${id}`);
        expect(res.status(), await res.text()).toBe(404);
      }
    }
  });
});
