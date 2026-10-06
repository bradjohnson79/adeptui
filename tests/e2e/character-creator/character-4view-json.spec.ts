/**
 * Character Creator 4-view + JSON — Schnick Coffee only.
 * UI clicks on a disposable engineering character. Korri is read-only.
 * Never POST /api/projects. Never approve Korri.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5173";
const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = "2347bf46-3762-4763-86c5-4a6032522278";
const KORRI_ID = "c49371ed-ba6b-4c16-ba98-a8b28b72118b";
const EVIDENCE = path.resolve(
  process.cwd(),
  "docs",
  "release-gate",
  "character-creator-4view-json",
  "evidence",
);

test.setTimeout(240 * 60 * 1000);

const consoleErrors: string[] = [];
const networkFailures: string[] = [];

async function openCharacter(page: Page, characterId: string) {
  await page.goto(`${BASE}/project/${PROJECT_ID}?workspace=characters&characterId=${characterId}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
}

async function shot(page: Page, name: string) {
  fs.mkdirSync(EVIDENCE, { recursive: true });
  await page.screenshot({ path: path.join(EVIDENCE, name), fullPage: true });
}

async function createDisposable(request: APIRequestContext) {
  const reuse = String(process.env.ADEPT_CC_DISPOSABLE_ID || "").trim();
  if (reuse) {
    const res = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${reuse}`);
    expect(res.ok(), await res.text()).toBeTruthy();
    const body = await res.json();
    return { id: reuse, name: String(body.name || body.displayName || "CC 4View") };
  }
  const name = `CC 4View ${Date.now()}`;
  const res = await request.post(`${API}/api/projects/${PROJECT_ID}/characters`, {
    data: {
      name,
      description: "Disposable Character Creator 4-view fixture. Safe to delete.",
      visual_description: "Adult woman, dark hair, warm skin, practical jacket, cinematic anime.",
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  return { id: String(body.id || body.characterId), name };
}

async function apiOk(request: APIRequestContext, path: string) {
  try {
    return (await request.get(`${API}${path}`)).ok();
  } catch {
    return false;
  }
}

async function waitForDraftSheet(request: APIRequestContext, characterId: string) {
  let sheetAssetId = "";
  await expect
    .poll(
      async () => {
        try {
          const res = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${characterId}/visual-sheet`);
          if (!res.ok()) return "";
          const body = await res.json();
          const pack = body.pack || body;
          const cand = (pack.candidates || [])[0] || {};
          if (String(pack.status || "").toUpperCase() === "FAILED" && !cand.sheetAssetId) {
            throw new Error(String(cand.error || pack.error || "Character sheet generation failed"));
          }
          const views = cand.viewJobs || [];
          const fourDone =
            views.length === 4 &&
            views.every((view: { status?: string }) => String(view.status || "").toLowerCase() === "done");
          sheetAssetId = fourDone ? String(cand.sheetAssetId || "") : "";
          return sheetAssetId;
        } catch (err) {
          const msg = String(err || "");
          if (/ECONNREFUSED|ECONNRESET|socket hang up|fetch failed/i.test(msg)) return "";
          throw err;
        }
      },
      { timeout: 120 * 60 * 1000 },
    )
    .not.toEqual("");
  return sheetAssetId;
}

async function writeGpuEvidence(request: APIRequestContext, characterId: string, name: string) {
  const sheetRes = await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${characterId}/visual-sheet`);
  const pack = sheetRes.ok() ? await sheetRes.json() : { error: await sheetRes.text() };
  const viewJobs = (((pack.pack || pack).candidates || [])[0] || {}).viewJobs || [];
  const jobs = [];
  for (const view of viewJobs) {
    const jobId = String(view.jobId || view.job_id || "");
    if (!jobId) continue;
    const jobRes = await request.get(`${API}/api/jobs/${jobId}`);
    jobs.push(jobRes.ok() ? await jobRes.json() : { jobId, error: await jobRes.text() });
  }
  const comfy = await request.get(`${API}/api/comfy/health`);
  fs.mkdirSync(EVIDENCE, { recursive: true });
  fs.writeFileSync(
    path.join(EVIDENCE, name),
    JSON.stringify(
      {
        capturedAt: new Date().toISOString(),
        characterId,
        pack,
        jobs,
        comfy: comfy.ok() ? await comfy.json() : { error: await comfy.text() },
      },
      null,
      2,
    ),
    "utf8",
  );
}

test.describe("Character Creator 4-view + JSON", () => {
  test.beforeEach(async ({ page }) => {
    consoleErrors.length = 0;
    networkFailures.length = 0;
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(String(err)));
    page.on("response", (res) => {
      const status = res.status();
      const url = res.url();
      if ((status === 422 || status >= 500) && url.includes("/api/")) {
        networkFailures.push(`${status} ${url}`);
      }
    });
  });

  test("Korri inspect is read-only and API-only approve is refused", async ({ page, request }) => {
    await expect.poll(async () => apiOk(request, "/api/health"), { timeout: 90_000 }).toBeTruthy();
    const crs = await (await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/crs`)).json();
    expect(String(crs.approved_reference_asset_id || "")).toBeTruthy();
    const blocked = await request.post(
      `${API}/api/projects/${PROJECT_ID}/characters/${KORRI_ID}/approve-candidate`,
      { data: { assetId: crs.approved_reference_asset_id, ownerConfirmed: false } },
    );
    expect(blocked.status()).toBe(403);
    const detail = await blocked.json();
    expect(detail.detail?.code || detail.code).toBe("PRODUCTION_CANON_PROTECTED");

    await openCharacter(page, KORRI_ID);
    await expect(page.getByTestId("character-active-crs")).toBeVisible();
    await expect(page.getByTestId("character-active-crs-status")).toContainText(/Approved/i);
    await expect(page.getByTestId("character-active-crs-approve")).toHaveCount(0);
    await shot(page, "pw-korri-readonly.png");
  });

  test("disposable Generate Preview Reject then Generate Approve JSON reload", async ({ page, request }) => {
    await expect.poll(async () => apiOk(request, "/api/health"), { timeout: 90_000 }).toBeTruthy();
    const created = await createDisposable(request);
    try {
      await openCharacter(page, created.id);
      const existing = await (
        await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`)
      ).json();
      const existingPack = existing.pack || existing;
      const existingSheet = String((existingPack.candidates || [])[0]?.sheetAssetId || "");
      const generate = page.getByTestId("character-generate");
      if (!existingSheet) {
        await expect(generate).toBeEnabled({ timeout: 30_000 });
        await generate.click();
        await shot(page, "pw-disposable-generate-1.png");
      }
      const firstDraftId = existingSheet || (await waitForDraftSheet(request, created.id));
      await writeGpuEvidence(request, created.id, "gpu-four-view-draft-1.json");
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-active-crs-status")).toContainText(/Draft/i);
      await page.getByTestId("character-active-crs-preview").click();
      await shot(page, "pw-disposable-preview-draft.png");
      await page.keyboard.press("Escape");

      await page.getByTestId("character-active-crs-reject").click();
      await page.getByTestId("character-reject-crs-dialog").getByRole("button", { name: "Reject" }).click();
      await expect(page.getByTestId("character-active-crs-empty")).toBeVisible({ timeout: 20_000 });
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-core")).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("character-active-crs-empty")).toBeVisible();
      const afterReject = await (
        await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/visual-sheet`)
      ).json();
      const rejectPack = afterReject.pack || afterReject;
      const rejectIds = (rejectPack.candidates || []).map((c: { sheetAssetId?: string; assetId?: string }) =>
        String(c.sheetAssetId || c.assetId || ""),
      );
      expect(rejectIds).not.toContain(firstDraftId);
      const library = await (await request.get(`${API}/api/projects/${PROJECT_ID}/library?limit=200`)).json();
      const libraryIds = (library.items || []).map((item: { id?: string; assetId?: string }) =>
        String(item.id || item.assetId || ""),
      );
      expect(libraryIds).not.toContain(firstDraftId);
      await shot(page, "pw-disposable-rejected.png");

      await page.getByTestId("character-generate").click();
      const approvedDraftId = await waitForDraftSheet(request, created.id);
      await writeGpuEvidence(request, created.id, "gpu-four-view-draft-2.json");
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-active-crs-status")).toContainText(/Draft/i);
      await page.getByTestId("character-active-crs-approve").click();
      await page.getByTestId("character-approve-crs-dialog").getByRole("button", { name: "Approve" }).click();
      await expect(page.getByTestId("character-active-crs-status")).toContainText(/Approved/i, { timeout: 30_000 });
      const json = await (
        await request.get(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}/character-json`)
      ).json();
      expect(json.crsRevision).toBeGreaterThanOrEqual(1);
      expect(json.approvedSheetAssetId).toBe(approvedDraftId);
      expect(json.views.front).toBeTruthy();
      expect(json.views.closeup.label).toMatch(/Close-Up/i);
      await page.reload({ waitUntil: "domcontentloaded" });
      await expect(page.getByTestId("character-active-crs-status")).toContainText(/Approved/i);
      await shot(page, "pw-disposable-approved.png");

      const ask = page.getByTestId("character-ask-codirector-crs");
      if (await ask.isVisible().catch(() => false)) {
        await ask.click();
      } else {
        await page.goto(`${BASE}/co-director?projectId=${PROJECT_ID}`, { waitUntil: "domcontentloaded" });
      }
      await expect(
        page.getByTestId("codirector-composer").or(page.getByTestId("codirector-shell")).or(page.getByPlaceholder("Ask Co-Director...")),
      ).toBeVisible({ timeout: 30_000 });
      await shot(page, "pw-disposable-codirector.png");

      const unexplained = networkFailures.filter((row) => !/dismiss/i.test(row));
      fs.mkdirSync(EVIDENCE, { recursive: true });
      fs.writeFileSync(
        path.join(EVIDENCE, "pw-console-network.json"),
        JSON.stringify({ consoleErrors, networkFailures, unexplained, characterId: created.id }, null, 2),
        "utf8",
      );
      expect(unexplained, unexplained.join("\n")).toEqual([]);
    } finally {
      await request.delete(`${API}/api/projects/${PROJECT_ID}/characters/${created.id}`).catch(() => undefined);
    }
  });
});
