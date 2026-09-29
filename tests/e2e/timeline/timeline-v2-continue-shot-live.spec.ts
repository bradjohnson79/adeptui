/**
 * Timeline V2 — UI-triggered MiniMax H3 Director Continue Shot live certification.
 *
 * Governing prompt Section 13 items 11-18. Certifies the full UI path:
 *   open Timeline -> model/aspect/1.2MP option -> change Megapixels to 0.4 ->
 *   continuation Timed Prompt -> click Continue Shot -> POST .../continue ->
 *   backend resolvedGeneration inherits 1728x736 (D2 preserve-on-continue) ->
 *   Comfy completes -> asset ingested -> shot has 3 segments -> preview 1728x736.
 *
 * Does NOT modify product code. Uses the existing disposable shot shot_ed8c484c22a3
 * (two completed segments; references @Renkoka / #Abode).
 *
 * Evidence JSON + screenshots -> theme_walk/timeline_v2_full_remediation (repo)
 * and mirrored to C:\\Users\\bradj\\theme_walk\\timeline_v2_full_remediation.
 *
 * Run:
 *   npx playwright test tests/e2e/timeline/timeline-v2-continue-shot-live.spec.ts \
 *     --project=chromium --reporter=list
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_PROJECT_ID || "bd6a5e6a-33c2-44a8-a115-8d37301d9d56";
const SCENE_ID = process.env.ADEPT_SCENE_ID || "95f7d229-ac2c-48c3-a704-2c17ec560e53";
const SHOT_ID = process.env.ADEPT_SHOT_ID || "shot_ed8c484c22a3";
const EXPECTED_MODEL_ID = "minimax-h3-i2v-local";
const EXPECTED_ASPECT = "21:9";
const EXPECTED_WIDTH = 1728;
const EXPECTED_HEIGHT = 736;
const POLL_BUDGET_MS = Number(process.env.ADEPT_UI_GENERATE_BUDGET_MS || 1800000); // 30 min
const EVIDENCE_DIR = process.env.ADEPT_EVIDENCE_DIR || path.join("theme_walk", "timeline_v2_full_remediation");
const MIRROR_DIR = process.env.ADEPT_EVIDENCE_MIRROR || "C:\\Users\\bradj\\theme_walk\\timeline_v2_full_remediation";

type Telemetry = {
  consoleErrors: Array<{ type: string; text: string }>;
  pageErrors: Array<{ message: string; stack?: string }>;
  badResponses: Array<{ status: number; method: string; url: string }>;
  requestFailures: Array<{ url: string; method: string; error: string }>;
};

function attachTelemetry(page: Page): Telemetry {
  const t: Telemetry = { consoleErrors: [], pageErrors: [], badResponses: [], requestFailures: [] };
  page.on("console", (msg) => { if (msg.type() === "error") t.consoleErrors.push({ type: "error", text: msg.text() }); });
  page.on("pageerror", (err) => t.pageErrors.push({ message: String((err && err.message) || err), stack: err && err.stack }));
  page.on("response", (res) => { if (res.status() >= 400) t.badResponses.push({ status: res.status(), method: res.request().method(), url: res.url() }); });
  page.on("requestfailed", (req) => t.requestFailures.push({ url: req.url(), method: req.method(), error: (req.failure() && req.failure().errorText) || "unknown" }));
  return t;
}

function writeEvidence(name: string, data: unknown): string {
  const json = JSON.stringify(data, null, 2);
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  const primary = path.join(EVIDENCE_DIR, name);
  writeFileSync(primary, json);
  try { mkdirSync(MIRROR_DIR, { recursive: true }); writeFileSync(path.join(MIRROR_DIR, name), json); }
  catch (error) { console.log("[evidence] mirror write skipped: " + String(error)); }
  return primary;
}

function writeShot(name: string, buffer: Buffer): string {
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  const primary = path.join(EVIDENCE_DIR, name);
  writeFileSync(primary, buffer);
  try { mkdirSync(MIRROR_DIR, { recursive: true }); writeFileSync(path.join(MIRROR_DIR, name), buffer); }
  catch (error) { console.log("[evidence] mirror screenshot skipped: " + String(error)); }
  return primary;
}

async function apiReady(request: APIRequestContext): Promise<boolean> {
  try { const res = await request.get(API + "/api/health", { timeout: 10000 }); return res.ok(); }
  catch { return false; }
}

async function readFilmSafe(request: APIRequestContext, projectId: string, sceneId: string) {
  const url = API + "/api/film-timeline/projects/" + encodeURIComponent(projectId) + "/scenes/" + encodeURIComponent(sceneId);
  for (let i = 0; i < 4; i += 1) {
    try {
      const res = await request.get(url, { timeout: 30000 });
      if (res.ok()) return (await res.json()) as { ok: boolean; film: any };
    } catch (error) { console.log("[readFilm] transient error: " + String(error)); }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  return null;
}

async function openTimeline(page: Page, url: string) {
  await page.setViewportSize({ width: 1600, height: 950 });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("film-timeline-inspector")).toBeVisible({ timeout: 60000 });
  await expect(page.getByTestId("film-timeline-monitor")).toBeVisible({ timeout: 60000 });
  await expect(page.getByTestId("film-timeline-model")).toBeVisible({ timeout: 30000 });
  await expect.poll(async () => page.getByTestId("film-timeline-model").locator("option").count(), { timeout: 30000 }).toBeGreaterThan(1);
}

async function readSelect(page: Page, testId: string) {
  return page.getByTestId(testId).evaluate((el) => {
    const select = el as HTMLSelectElement;
    const selected = select.options[select.selectedIndex];
    return {
      value: select.value,
      selectedText: (selected ? selected.textContent || "" : "").trim(),
      options: Array.from(select.options).map((o) => ({ value: o.value, text: (o.textContent || "").trim() })),
    };
  });
}

async function readReferenceChips(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-testid="film-reference-strip"] .film-reference-chip')).map((chip) => {
      const b = chip.querySelector("button");
      return (b ? b.textContent || "" : "").trim();
    }),
  );
}

async function readVideoTrackChips(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const track = Array.from(document.querySelectorAll(".film-timeline__track")).find((el) => {
      const s = el.querySelector("span");
      return (s ? s.textContent || "" : "").trim() === "Video";
    });
    if (!track) return [];
    return Array.from(track.querySelectorAll("button")).map((b) => (b.textContent || "").trim());
  });
}

async function readMonitorVideo(page: Page) {
  const video = page.getByTestId("film-timeline-monitor").locator("video");
  if (!(await video.count())) return { count: 0 } as any;
  return video.first().evaluate((el) => {
    const v = el as HTMLVideoElement;
    return { count: 1, src: v.getAttribute("src") || "", currentSrc: v.currentSrc || "", readyState: v.readyState, networkState: v.networkState, videoWidth: v.videoWidth, videoHeight: v.videoHeight, errorCode: v.error ? v.error.code : null, errorMessage: v.error ? v.error.message : null };
  });
}

function normalizeOptionText(text: string): string {
  return text.replace(/\u00d7/g, "x").replace(/\u00b7/g, "-").replace(/[\u2010-\u2015]/g, "-").replace(/\s+/g, " ").trim();
}

function segmentView(seg: any) {
  if (!seg) return null;
  const meta = seg.generationMetadata || {};
  return {
    id: seg.id,
    order: seg.order,
    status: seg.status,
    durationSec: seg.durationSec,
    assetId: seg.assetId || null,
    error: seg.error || null,
    legalCanvas: meta.legalCanvas || null,
    resolvedGeneration: meta.resolvedGeneration || null,
    h3Resolution: meta.h3Resolution || null,
    jobId: meta.jobId || null,
    queueJobId: meta.queueJobId || null,
    providerJobId: meta.providerJobId || null,
    strategy: meta.strategy || null,
  };
}

const TIMELINE_URL = "/project/" + PROJECT_ID + "?workspace=timeline&sceneId=" + SCENE_ID;

test.describe("Timeline V2 UI continue-shot live certification", () => {
  test.beforeEach(async ({ request }) => {
    await expect.poll(async () => apiReady(request), { timeout: 90000 }).toBeTruthy();
  });

  test("UI Continue Shot preserves 1728x736 and completes", async ({ page, request }) => {
    test.setTimeout(2400000); // 40 min
    const telemetry = attachTelemetry(page);
    const observed: Record<string, unknown> = {};
    const assertions: Array<{ n: number; name: string; pass: boolean; observed: unknown; detail?: string }> = [];
    const record = (n: number, name: string, pass: boolean, value: unknown, detail?: string) => {
      assertions.push({ n, name, pass, observed: value, detail });
      console.log("[ASSERT " + n + "] " + (pass ? "PASS" : "FAIL") + " - " + name + " :: " + JSON.stringify(value) + (detail ? " :: " + detail : ""));
    };
    const finish = (result: string) => {
      const passCount = assertions.filter((a) => a.pass).length;
      const failCount = assertions.length - passCount;
      const evidence = {
        generatedAt: new Date().toISOString(),
        result,
        url: TIMELINE_URL,
        projectId: PROJECT_ID,
        sceneId: SCENE_ID,
        shotId: SHOT_ID,
        pollBudgetMs: POLL_BUDGET_MS,
        passCount,
        failCount,
        assertions,
        observed,
        telemetry,
      };
      const p = writeEvidence("ui_cert_continue_shot_live.json", evidence);
      console.log("[evidence] wrote " + p);
      console.log("[SUMMARY] " + passCount + " passed, " + failCount + " failed, 0 skipped :: " + result);
      return { passCount, failCount };
    };

    // ---- preflight: capture shot BEFORE ----
    const filmBefore = await readFilmSafe(request, PROJECT_ID, SCENE_ID);
    expect(filmBefore, "film read failed before continue").toBeTruthy();
    const shotBefore = (filmBefore!.film.shots || []).find((s: any) => s.id === SHOT_ID);
    expect(shotBefore, "target shot present").toBeTruthy();
    observed.shotBefore = {
      id: shotBefore.id,
      status: shotBefore.status,
      durationSec: shotBefore.durationSec,
      references: ((shotBefore.state && shotBefore.state.references) || []).map((r: any) => r.tag),
      segments: (shotBefore.segments || []).map(segmentView),
      stitchAssetId: (shotBefore.state && shotBefore.state.stitchAssetId) || null,
      stateResolvedGeneration: (shotBefore.state && shotBefore.state.resolvedGeneration) || null,
    };
    const completedBefore = (shotBefore.segments || []).filter((s: any) => s.status === "completed" && s.assetId);
    record(0, "Disposable shot exists with 2 completed segments and refs @Renkoka/#Abode", completedBefore.length === 2 && observed.shotBefore.references.join(",") === "@Renkoka,#Abode", { completedBefore: completedBefore.length, references: observed.shotBefore.references });

    // ---- Step 1: open Timeline, verify model/aspect/1.2MP ----
    await openTimeline(page, TIMELINE_URL);
    observed.url = page.url();
    await page.waitForTimeout(1500);
    writeShot("c01_timeline_open.png", await page.screenshot({ fullPage: false }));

    await expect.poll(async () => (await readSelect(page, "film-timeline-model")).value, { timeout: 30000 }).toBe(EXPECTED_MODEL_ID);
    const modelSel = await readSelect(page, "film-timeline-model");
    observed.model = modelSel;
    record(1, "Model = MiniMax H3 Director - Local", modelSel.value === EXPECTED_MODEL_ID && /MiniMax H3 Director/.test(modelSel.selectedText) && /Local/.test(modelSel.selectedText), modelSel);

    const aspectSel = await readSelect(page, "timeline-scene-aspect");
    observed.aspect = aspectSel;
    record(2, "Picture Shape = 21:9", aspectSel.value === EXPECTED_ASPECT, aspectSel);

    const mpSel0 = await readSelect(page, "film-timeline-megapixels-select");
    const opt12 = mpSel0.options.find((o) => o.value === "1.2");
    const opt12Raw = opt12 ? opt12.text : "";
    const opt12Norm = normalizeOptionText(opt12Raw);
    observed.megapixelsInitial = mpSel0;
    observed.megapixels1_2Raw = opt12Raw;
    observed.megapixels1_2Normalized = opt12Norm;
    const noStale = !/1504/.test(opt12Raw) && !/832/.test(opt12Raw);
    record(3, "Megapixels 1.2 option text is '1.2 MP . 1728x736' (not 1504x832)", Boolean(opt12) && noStale && opt12Norm === "1.2 MP - 1728x736", { raw: opt12Raw, normalized: opt12Norm, containsStale1504x832: !noStale });

    const refChips = await readReferenceChips(page);
    observed.referenceChips = refChips;
    record(4, "Reference strip shows @Renkoka and #Abode", refChips.length === 2 && refChips[0] === "@Renkoka" && refChips[1] === "#Abode", refChips);

    // ---- Step 2: deliberate control changes ----
    const restoredMp = mpSel0.value;
    observed.megapixelsRestored = restoredMp;
    // Ensure a genuine change: first move to 1.2, then deliberately to 0.4.
    await page.getByTestId("film-timeline-megapixels-select").selectOption("1.2");
    await expect.poll(async () => (await readSelect(page, "film-timeline-megapixels-select")).value, { timeout: 15000 }).toBe("1.2");
    await page.getByTestId("film-timeline-megapixels-select").selectOption("0.4");
    const mpSel1 = await readSelect(page, "film-timeline-megapixels-select");
    observed.megapixelsAfterChange = mpSel1;
    observed.megapixelsAutoDimsCountWhenManual = await page.getByTestId("film-timeline-megapixels-auto-dims").count();
    record(5, "Megapixels deliberately changed to 0.4 MP (manual)", mpSel1.value === "0.4" && mpSel1.selectedText.indexOf("0.4 MP") >= 0, mpSel1);

    const continuationLine = "Continuation: Renkoka steps deeper into the Abode as the room light shifts warm, gentle handheld follow, cinematic anime feature quality. Audio: soft footsteps and room tone.";
    await page.getByTestId("film-timeline-prompt").fill(continuationLine);
    const promptNow = await page.getByTestId("film-timeline-prompt").inputValue();
    observed.continuationPrompt = promptNow;
    record(6, "Timed Prompt set to continuation line", promptNow === continuationLine, { length: promptNow.length });

    const durationSel = await readSelect(page, "film-timeline-duration");
    observed.duration = durationSel;
    const continueEnabled = await page.getByTestId("film-timeline-continue").isEnabled();
    observed.continueEnabled = continueEnabled;
    record(7, "Continue Shot enabled for shot with completed segment + prompt", continueEnabled, { duration: durationSel.value, durationText: durationSel.selectedText });
    writeShot("c02_configured_0p4mp.png", await page.screenshot({ fullPage: false }));

    // ---- Step 3: click Continue Shot, capture request + response ----
    const continueResponsePromise = page.waitForResponse(
      (res) => res.url().includes("/film-timeline/") && res.url().includes("/continue") && res.request().method() === "POST",
      { timeout: 90000 },
    );
    await page.getByTestId("film-timeline-continue").click();
    let continueReq: any = null;
    let continueRes: any = null;
    let continueHttpStatus = 0;
    let continueBody: any = null;
    try {
      continueRes = await continueResponsePromise;
      continueHttpStatus = continueRes.status();
      const rawReq = continueRes.request().postData() || "";
      try { continueReq = rawReq ? JSON.parse(rawReq) : null; } catch { continueReq = { raw: rawReq }; }
      try { continueBody = await continueRes.json(); } catch { continueBody = { raw: await continueRes.text().catch(() => "") }; }
    } catch (error) {
      observed.continueCaptureError = String(error);
    }
    observed.continueHttpStatus = continueHttpStatus;
    observed.continueRequest = continueReq;
    observed.continueResponse = continueBody;
    writeEvidence("continue_request_response.json", {
      generatedAt: new Date().toISOString(),
      url: TIMELINE_URL,
      request: { method: "POST", url: continueRes ? continueRes.url() : "(not captured)", body: continueReq },
      response: { status: continueHttpStatus, body: continueBody },
    });
    await page.waitForTimeout(2000);
    writeShot("c03_continue_clicked.png", await page.screenshot({ fullPage: false }));

    const continueOk = continueHttpStatus >= 200 && continueHttpStatus < 300 && Boolean(continueBody && continueBody.ok !== false);
    record(8, "POST .../continue accepted (2xx, ok)", continueOk, { status: continueHttpStatus, ok: continueBody && continueBody.ok, error: continueBody && continueBody.error, message: continueBody && continueBody.message });

    const newSegmentFromResponse = continueBody && continueBody.segment ? continueBody.segment : null;
    const newSegmentId = (newSegmentFromResponse && newSegmentFromResponse.id) || "";
    observed.newSegmentId = newSegmentId;
    observed.newSegmentFromResponse = segmentView(newSegmentFromResponse);
    const reqH3 = continueReq && continueReq.providerOptions && continueReq.providerOptions.h3Resolution;
    observed.continueRequestH3 = reqH3 || null;
    record(9, "Continue request carried the deliberate 0.4 MP control change", Boolean(reqH3) && reqH3.mode === "manual" && Number(reqH3.megapixels) === 0.4, reqH3 || null);

    const resolvedNew = newSegmentFromResponse && newSegmentFromResponse.generationMetadata ? newSegmentFromResponse.generationMetadata.resolvedGeneration : null;
    observed.continueResolvedGeneration = resolvedNew || null;
    const resolvedPass = Boolean(resolvedNew) && Number(resolvedNew.width) === EXPECTED_WIDTH && Number(resolvedNew.height) === EXPECTED_HEIGHT;
    const notSmall = !(Number(resolvedNew && resolvedNew.width) === 992 && Number(resolvedNew && resolvedNew.height) === 416);
    record(10, "D2 preserve-on-continue: NEW segment resolvedGeneration inherits 1728x736 (NOT 992x416)", resolvedPass && notSmall, resolvedNew || null);

    const comfyAccepted = continueOk && Boolean(newSegmentFromResponse) && Boolean(newSegmentFromResponse.generationMetadata && (newSegmentFromResponse.generationMetadata.queueJobId || newSegmentFromResponse.generationMetadata.jobId)) && ["queued", "generating", "completed"].indexOf(String(newSegmentFromResponse.status)) >= 0;
    record(11, "COMFY ACCEPTANCE: continue queued a live H3 job (jobId/queueJobId present)", comfyAccepted, { status: newSegmentFromResponse && newSegmentFromResponse.status, jobId: newSegmentFromResponse && newSegmentFromResponse.generationMetadata && newSegmentFromResponse.generationMetadata.jobId, queueJobId: newSegmentFromResponse && newSegmentFromResponse.generationMetadata && newSegmentFromResponse.generationMetadata.queueJobId });

    expect(newSegmentId, "continue must return the new segment id").toBeTruthy();

    // ---- Step 5: poll to terminal, waiting for COMPLETED ----
    const pollLog: Array<{ at: string; status: string; assetId: string | null }> = [];
    const deadline = Date.now() + POLL_BUDGET_MS;
    let finalSegment: any = null;
    let lastStatus = "";
    while (Date.now() < deadline) {
      let film: any = null;
      try {
        const syncRes = await request.post(API + "/api/film-timeline/projects/" + encodeURIComponent(PROJECT_ID) + "/scenes/" + encodeURIComponent(SCENE_ID) + "/shots/" + encodeURIComponent(SHOT_ID) + "/sync", { timeout: 60000 });
        if (syncRes.ok()) { const b = await syncRes.json(); film = b.film; }
      } catch (error) { console.log("[poll] sync error: " + String(error)); }
      if (!film) film = (await readFilmSafe(request, PROJECT_ID, SCENE_ID))?.film || null;
      const shot = film ? (film.shots || []).find((s: any) => s.id === SHOT_ID) : null;
      const seg = shot ? (shot.segments || []).find((s: any) => s.id === newSegmentId) : null;
      if (seg) {
        finalSegment = seg;
        if (seg.status !== lastStatus || pollLog.length % 8 === 0) {
          pollLog.push({ at: new Date().toISOString(), status: seg.status, assetId: seg.assetId || null });
        }
        lastStatus = seg.status;
        if (["completed", "failed", "cancelled"].indexOf(seg.status) >= 0) break;
      } else {
        pollLog.push({ at: new Date().toISOString(), status: "(segment not found yet)", assetId: null });
      }
      await new Promise((resolve) => setTimeout(resolve, 15000));
    }
    observed.pollLog = pollLog;
    observed.finalSegment = segmentView(finalSegment);
    observed.finalSegmentStatus = finalSegment ? finalSegment.status : "(never observed)";
    const generationCompleted = Boolean(finalSegment && finalSegment.status === "completed" && finalSegment.assetId);
    record(12, "GENERATION COMPLETED: new segment reached terminal COMPLETED with an asset", generationCompleted, { status: finalSegment && finalSegment.status, assetId: finalSegment && finalSegment.assetId, error: finalSegment && finalSegment.error });

    // ---- Step 6: asset + 3 segments + preview dims (reload persistence) ----
    const filmAfter = await readFilmSafe(request, PROJECT_ID, SCENE_ID);
    const shotAfter = filmAfter ? (filmAfter.film.shots || []).find((s: any) => s.id === SHOT_ID) : null;
    const segsAfter = shotAfter ? shotAfter.segments || [] : [];
    observed.shotAfter = shotAfter ? {
      status: shotAfter.status,
      segments: segsAfter.map(segmentView),
      stitchAssetId: (shotAfter.state && shotAfter.state.stitchAssetId) || null,
    } : null;
    const newSegAfter = segsAfter.find((s: any) => s.id === newSegmentId);
    const assetIngested = Boolean(newSegAfter && newSegAfter.status === "completed" && newSegAfter.assetId);
    record(13, "OUTPUT INGEST: finished asset attached to new segment", assetIngested, { assetId: newSegAfter && newSegAfter.assetId, status: newSegAfter && newSegAfter.status });
    record(14, "Shot now has 3 segments (2 prior + 1 new)", segsAfter.length === 3, { segmentIds: segsAfter.map((s: any) => s.id), statuses: segsAfter.map((s: any) => s.status) });

    // Reload persistence
    await page.reload({ waitUntil: "domcontentloaded" });
    await openTimeline(page, TIMELINE_URL);
    await page.waitForTimeout(2500);
    const reloadedTracks = await readVideoTrackChips(page);
    observed.reloadVideoTrackChips = reloadedTracks;
    const reloadedPrompt = await page.getByTestId("film-timeline-prompt").inputValue();
    observed.reloadPrompt = reloadedPrompt;
    record(15, "RELOAD PERSISTENCE: 3 video segments persist after reload", reloadedTracks.length === 3, reloadedTracks);

    // Select the new segment (last chip) and read preview dims.
    let selectedPreview: any = { count: 0 };
    if (reloadedTracks.length) {
      const videoTrack = page.locator(".film-timeline__track").filter({ has: page.locator("span", { hasText: /^Video$/ }) });
      const newIndex = segsAfter.findIndex((s: any) => s.id === newSegmentId);
      const chip = videoTrack.getByRole("button").nth(newIndex >= 0 ? newIndex : reloadedTracks.length - 1);
      await chip.click();
      await page.waitForTimeout(1500);
      // Wait for the video element to report intrinsic dimensions.
      await expect.poll(async () => {
        const v = await readMonitorVideo(page);
        return v && v.videoWidth > 0 ? v.videoWidth + "x" + v.videoHeight : "";
      }, { timeout: 60000 }).toMatch(/^\d+x\d+$/);
      selectedPreview = await readMonitorVideo(page);
    }
    observed.monitorVideoSelectedSegment = selectedPreview;
    const previewDimsPass = selectedPreview && selectedPreview.videoWidth === EXPECTED_WIDTH && selectedPreview.videoHeight === EXPECTED_HEIGHT;
    record(16, "Preview shows selected new segment output at 1728x736", Boolean(previewDimsPass), selectedPreview, previewDimsPass ? undefined : "videoWidth/Height must be 1728x736");
    writeShot("c04_generation_finished_preview.png", await page.screenshot({ fullPage: false }));

    const telemetrySummary = {
      consoleErrorCount: telemetry.consoleErrors.length,
      pageErrorCount: telemetry.pageErrors.length,
      badResponseCount: telemetry.badResponses.length,
      requestFailureCount: telemetry.requestFailures.length,
      consoleErrors: telemetry.consoleErrors,
      pageErrors: telemetry.pageErrors,
      badResponses: telemetry.badResponses,
      requestFailures: telemetry.requestFailures,
    };
    observed.telemetry = telemetrySummary;
    record(17, "Browser console/pageerror/failed-network/4xx-5xx captured throughout", true, { consoleErrorCount: telemetrySummary.consoleErrorCount, pageErrorCount: telemetrySummary.pageErrorCount, badResponseCount: telemetrySummary.badResponseCount, requestFailureCount: telemetrySummary.requestFailureCount }, "capture is informational; see evidence JSON");

    const verdict = resolvedPass && notSmall && generationCompleted && assetIngested && segsAfter.length === 3 && previewDimsPass
      ? "CONTINUE SHOT PASS"
      : (generationCompleted ? "CONTINUE SHOT INCOMPLETE - assertion failure" : "CONTINUE SHOT BLOCKED - generation not completed within budget; last status=" + (finalSegment ? finalSegment.status : "never observed"));
    finish(verdict);

    expect(resolvedPass && notSmall, "resolvedGeneration must inherit 1728x736").toBeTruthy();
    expect(generationCompleted, "generation must complete within budget").toBeTruthy();
    expect(assetIngested, "new segment must have a finished asset").toBeTruthy();
    expect(segsAfter.length, "shot must have 3 segments").toBe(3);
    expect(previewDimsPass, "preview video must be 1728x736").toBeTruthy();
  });
});
