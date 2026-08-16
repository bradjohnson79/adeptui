/**
 * Hosted grounding smoke. Never POST /api/projects. Never :8760.
 * Browser: adeptui.vercel.app. API: api-beta.adeptui.org (not localhost :8758).
 */
import { expect, test, type APIRequestContext } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "https://adeptui.vercel.app";
const API = process.env.STUDIO_API_BASE || "https://api-beta.adeptui.org";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";
const SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2";
const SHOT_ID = "88539183-6fd2-495a-aa48-e406a3653cd5";
const KORRI_CAST = "b6ab91dd-9d0a-4e4b-98b4-b26d268950dc";
const KNOWN_JOB = "6b86b9f2-5ec1-4d2a-be6a-e677711021f4";
const CAM = "1a8198ec-8c40-4608-9b9f-0d4544aabe5c";
const SC_URL = `${BASE}/project/${PROJECT_ID}?workspace=scenecreator`;

test.describe("Scene Creator hosted grounding smoke", () => {
  test("uses hosted API hostname, not localhost", () => {
    expect(API).toContain("api-beta.adeptui.org");
    expect(API).not.toContain("127.0.0.1");
    expect(API).not.toContain(":8758");
    expect(BASE).toContain("adeptui.vercel.app");
  });

  test("CD hydrate advisory, Qwen refused, Korri packet, panes, reload", async ({ request, page }) => {
    const health = await request.get(`${API}/api/health`, { timeout: 20_000 });
    expect(health.ok(), `hosted API health ${API} ${health.status()}`).toBeTruthy();

    const handoff = await request.post(`${API}/api/scene-creator/projects/${PROJECT_ID}/production-handoff`, {
      data: { scene_id: SCENE_ID },
    });
    expect(handoff.ok(), await handoff.text()).toBeTruthy();
    const a = await handoff.json();

    const ws = await request.get(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/workspace?scene_id=${a.sceneId}&sheet_id=${a.sheetId}&spatial_profile_id=${a.handoffId}&shot_id=${SHOT_ID}`,
    );
    expect(ws.ok()).toBeTruthy();
    const workspace = await ws.json();
    expect(workspace.production_context?.loaded).toBe(true);
    expect(workspace.production_readiness?.status).toBe("advisory");
    expect(workspace.production_readiness?.ticks?.character).toBe("ok");
    expect(workspace.production_readiness?.ticks?.prop).toBe("warn");
    expect(workspace.production_readiness?.ticks?.environment).toBe("warn");

    const qwen = await request.post(
      `${API}/api/scene-creator/projects/${PROJECT_ID}/scenes/${SCENE_ID}/cinematographer/preview`,
      {
        data: {
          camera_id: CAM,
          shot_id: SHOT_ID,
          local_enabled: true,
          api_enabled: false,
          local_family: "qwen2512",
        },
        failOnStatusCode: false,
      },
    );
    expect(qwen.status(), await qwen.text()).toBe(400);
    const qwenBody = await qwen.text();
    expect(qwenBody.toLowerCase()).toContain("z-image");
    expect(qwenBody.toLowerCase()).not.toContain("qwen2512.txt2img");

    const known = await request.get(`${API}/api/jobs/${KNOWN_JOB}`);
    expect(known.ok()).toBeTruthy();
    const job = await known.json();
    const pj = typeof job.params_json === "string" ? JSON.parse(job.params_json) : job.params_json || {};
    const ii = pj.imageIntent || {};
    const pkt = (pj.creativeContext || {}).referencePacket || {};
    expect(pj.purpose).toBe("scene_shot_preview");
    expect((pj.imageRuntime || {}).workflowKey).toBe("zimage.ref_edit");
    expect(ii.sourceAssetId || pj.source_asset_id).toBe(KORRI_CAST);
    expect(ii.referenceIds).toEqual([KORRI_CAST]);
    expect(pkt.consumedAssetIds).toEqual([KORRI_CAST]);
    expect(pkt.props?.[0]?.consumption).toBe("semantic_only");
    expect(pkt.environment?.consumption).toBe("semantic_only");

    await page.setViewportSize({ width: 1440, height: 900 });
    const dest = `${SC_URL}&scene_id=${a.sceneId}&sheet_id=${a.sheetId}&shot_id=${SHOT_ID}&spatialProfileId=${a.handoffId}`;
    await page.goto(dest, { waitUntil: "domcontentloaded" });
    const standard = page.getByTestId("scene-creator-standard");
    const offline = page.getByText("Studio API Offline", { exact: false });
    await expect.poll(async () => {
      if (await offline.isVisible().catch(() => false)) return "offline";
      if (await standard.isVisible().catch(() => false)) return "ready";
      return "wait";
    }, { timeout: 90_000 }).not.toBe("wait");
    expect(await offline.isVisible().catch(() => false), "hosted UI must reach api-beta.adeptui.org").toBeFalsy();

    await expect(page.getByTestId("scene-creator-cd-caption")).toHaveText("✓ Co-Director production data loaded", {
      timeout: 60_000,
    });
    const integrity = page.getByTestId("scene-creator-integrity-caption");
    await expect(integrity).toBeVisible({ timeout: 15_000 });
    await expect(integrity).not.toHaveText(/Production integrity verified/);
    await expect(page.getByTestId("scene-creator-ref-ticks")).toContainText("Character");
    await expect(page.getByTestId("scene-creator-splitter-left")).toBeVisible();
    await expect(page.getByTestId("scene-creator-reset-layout")).toBeVisible();
    await expect(page.getByTestId("cine-preview")).toBeVisible();
    await expect(page.getByTestId("scene-creator-generate")).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("scene-creator-cd-caption")).toHaveText("✓ Co-Director production data loaded", {
      timeout: 60_000,
    });
    await expect(page.getByTestId("scene-creator-integrity-caption")).not.toHaveText(/Production integrity verified/);
  });
});
