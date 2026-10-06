import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { createTempProject, deleteProject, waitForAppReady, API } from "../helpers/app";
import { openCoDirectorFullScreen, TINY_PNG, uploadProjectAsset } from "./helpers/audit";

const PROJECT_PREFIX = "SUPP-VIEW-CERT";
const LIVE_CERT = path.join(
  process.cwd(),
  "docs",
  "release-gate",
  "spatial-map",
  "evidence",
  "supplementary_views",
  "live_cert.json",
);

async function openSpatialMapTab(page: Page) {
  const tab = page.getByTestId("codirector-content-tab-spatial_map");
  await expect(tab).toBeVisible({ timeout: 30_000 });
  await tab.click({ force: true });
  await expect(page.getByTestId("spatial-map-panel")).toBeVisible({ timeout: 45_000 });
}

test.describe.serial("Qwen supplementary environment views", () => {
  let projectId = "";

  test.afterAll(async ({ request }) => {
    if (projectId) await deleteProject(request, projectId);
  });

  test("Improve Spatial Understanding panel keeps observed master authority", async ({ page, request }) => {
    test.setTimeout(180_000);
    await waitForAppReady(request);
    const project = await createTempProject(request, `${PROJECT_PREFIX}-${Date.now()}`);
    projectId = project.id;
    const uploaded = await uploadProjectAsset(request, project.id, {
      name: "master.png",
      mimeType: "image/png",
      kind: "image",
      buffer: TINY_PNG,
      tag: "location_master",
    });
    const masterId = uploaded.id;
    const mapRes = await request.post(`${API}/api/spatial-map/projects/${project.id}/maps`, {
      data: {
        title: "Supplementary Cert",
        backgroundAssetId: masterId,
        originalEnvironmentReferenceAssetId: masterId,
        masterEnvironmentPrompt: "metallic corridor with elevators and repeating arches",
      },
    });
    expect(mapRes.ok(), await mapRes.text()).toBeTruthy();
    const mapId = (await mapRes.json()).document.id as string;

    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") pageErrors.push(msg.text());
    });
    const failed: string[] = [];
    page.on("response", (res) => {
      if (res.status() >= 500) failed.push(`${res.status()} ${res.url()}`);
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, project.id);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("supplementary-views-panel")).toBeVisible();
    await expect(page.getByText("Improve Spatial Understanding")).toBeVisible();
    await expect(page.getByTestId("generate-additional-views")).toBeVisible();
    await expect(page.getByTestId("master-reference-card")).toBeVisible();
    await expect(page.getByText("Observed reference")).toBeVisible();

    const analyze = await request.post(
      `${API}/api/spatial-map/projects/${project.id}/maps/${mapId}/supplementary-views/analyze`,
    );
    expect(analyze.ok(), await analyze.text()).toBeTruthy();
    expect((await analyze.json()).cameraRole).toBeTruthy();

    const state = await request.get(
      `${API}/api/spatial-map/projects/${project.id}/maps/${mapId}/supplementary-views`,
    );
    expect(state.ok()).toBeTruthy();
    const body = await state.json();
    expect(body.master.evidenceClass).toBe("OBSERVED");
    expect(body.observedAssetIds).toEqual([masterId]);
    expect(body.notGeometryEvidence).toBeTruthy();

    await page.reload();
    await openSpatialMapTab(page);
    await expect(page.getByTestId("supplementary-views-panel")).toBeVisible();
    await expect(page.getByTestId("master-reference-card")).toBeVisible();

    const noise = /Download the React DevTools|favicon|fonts\.gstatic|fonts\.googleapis|ERR_FAILED|x-adept-deny-owner-writes/i;
    expect(failed.filter((u) => !/favicon|fonts\.gstatic|fonts\.googleapis/i.test(u))).toEqual([]);
    expect(pageErrors.filter((line) => !noise.test(line))).toEqual([]);
  });

  test("live sequential A/B stays inferred after reload", async ({ page, request }) => {
    test.setTimeout(180_000);
    let live: {
      ok?: boolean;
      projectId?: string;
      mapId?: string;
      masterAssetId?: string;
      viewA?: { assetId?: string; evidenceClass?: string; status?: string };
      viewB?: { assetId?: string; evidenceClass?: string; status?: string };
    };
    try {
      live = JSON.parse(readFileSync(LIVE_CERT, "utf8"));
    } catch {
      test.skip(true, "live_cert.json is not available yet");
      return;
    }
    if (!live.projectId || !live.mapId) {
      test.skip(true, "live sequential Qwen A/B has not completed");
      return;
    }

    await waitForAppReady(request);
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") pageErrors.push(msg.text());
    });
    const failed: string[] = [];
    page.on("response", (res) => {
      if (res.status() >= 500) failed.push(`${res.status()} ${res.url()}`);
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await openCoDirectorFullScreen(page, live.projectId);
    await openSpatialMapTab(page);
    await expect(page.getByTestId("supplementary-views-panel")).toBeVisible();
    await expect(page.getByTestId("supplementary-view-a-inferred")).toBeVisible();
    if (live.viewB?.assetId || live.live?.viewB?.assetId) {
      await expect(page.getByTestId("supplementary-view-b-inferred")).toBeVisible();
    }
    await expect(page.getByTestId("spatial-confidence-summary")).toBeVisible();

    const state = await request.get(
      `${API}/api/spatial-map/projects/${live.projectId}/maps/${live.mapId}/supplementary-views`,
    );
    expect(state.ok()).toBeTruthy();
    const body = await state.json();
    expect(body.master.evidenceClass).toBe("OBSERVED");
    expect(body.observedAssetIds).toEqual([live.masterAssetId]);
    expect(body.state.viewA.evidenceClass).toBe("INFERRED");
    if (body.state.viewB?.assetId) {
      expect(body.state.viewB.evidenceClass).toBe("INFERRED");
      expect(body.observedAssetIds).not.toContain(body.state.viewB.assetId);
    }
    expect(body.observedAssetIds).not.toContain(body.state.viewA.assetId);

    await page.reload();
    await openSpatialMapTab(page);
    await expect(page.getByTestId("supplementary-view-a-inferred")).toBeVisible();
    await expect(page.getByText("Accepted for Spatial Reasoning").first()).toBeVisible();

    const noise = /Download the React DevTools|favicon|fonts\.gstatic|fonts\.googleapis|ERR_FAILED|x-adept-deny-owner-writes/i;
    expect(failed.filter((u) => !/favicon|fonts\.gstatic|fonts\.googleapis/i.test(u))).toEqual([]);
    expect(pageErrors.filter((line) => !noise.test(line))).toEqual([]);
  });
});
