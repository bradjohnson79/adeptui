/**
 * 1 Frame end-to-end render certification (MiniMax H3, prepared Korri prompt).
 * Captures console/page/request errors, runs the prepared prompt, polls the
 * job, verifies the output (ffprobe video+audio+sync), writes an evidence
 * report. Requires ADEPT_ALLOW_KORRI_MUTATION=1 + live Vite :5173 + Studio API :8758.
 */
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const API = process.env.STUDIO_API_BASE?.trim() || "http://127.0.0.1:8758";
const PROJECT_ID = process.env.ADEPT_1F_PROJECT_ID || "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const SCENE_ID = process.env.ADEPT_1F_SCENE_ID || "1f46b621-46f9-4b7e-8273-202a49e1ca7c";
const RENDER_TIMEOUT_MS = Number(process.env.ADEPT_1F_RENDER_TIMEOUT_MS || 25 * 60_000);
const ARTIFACT_DIR = path.join("artifacts", "one-frame-e2e", SCENE_ID);

function ensureDir(dir: string) { fs.mkdirSync(dir, { recursive: true }); }
function writeJson(dir: string, name: string, data: unknown) {
  ensureDir(dir);
  fs.writeFileSync(path.join(dir, name), JSON.stringify(data, null, 2));
}

function ffprobe(filePath: string): Record<string, any> {
  try {
    const out = execFileSync("ffprobe", [
      "-v", "error", "-print_format", "json", "-show_streams", "-show_format", filePath,
    ], { encoding: "utf-8", timeout: 30_000 });
    const parsed = JSON.parse(out);
    const streams = (parsed.streams || []) as Array<Record<string, any>>;
    return {
      ok: true,
      video: streams.find((s) => s.codec_type === "video") || null,
      audio: streams.find((s) => s.codec_type === "audio") || null,
      format: parsed.format || null,
    };
  } catch (e: unknown) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) };
  }
}

test.describe("1 Frame end-to-end render (MiniMax H3)", () => {
  test.describe.configure({ mode: "serial", timeout: 35 * 60_000 });

  test("1 Frame prepared prompt renders end-to-end", async ({ page, request }: { page: Page; request: APIRequestContext }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const requestFailures: string[] = [];
    const httpErrors: string[] = [];

    page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("requestfailed", (req) => {
      requestFailures.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText || "no-error-text"}`);
    });
    page.on("response", async (res) => {
      if (res.status() >= 400) {
        try {
          const body = await res.text();
          httpErrors.push(`HTTP ${res.status()} ${res.url()} :: ${body.slice(0, 400)}`);
        } catch { httpErrors.push(`HTTP ${res.status()} ${res.url()}`); }
      }
    });

    // 1. Open the 1 Frame surface.
    await page.goto(`/project/${PROJECT_ID}?workspace=one&sceneId=${SCENE_ID}`);
    const panel = page.getByTestId("one-frame-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });

    // 2. Verify prepared prompt + first frame + engine + megapixel resolution.
    const prompt = page.locator("#one-frame-motion-prompt");
    await expect(prompt).toHaveValue(/./);
    const promptValue = await prompt.inputValue();
    expect(promptValue.length, "prepared prompt is non-empty").toBeGreaterThan(20);
    await expect(page.locator("#one-frame-engine")).toHaveValue("minimax-h3");
    await expect(page.locator("#one-frame-resolution")).toHaveValue(/MP/);
    await expect(panel.locator(".frame-slot img")).toBeVisible();
    ensureDir(ARTIFACT_DIR);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, "1-prepared.png"), fullPage: true });

    // 3. Intercept the render POST to capture the job id.
    const renderResponsePromise = page.waitForResponse(
      (res) => res.url().includes(`/api/projects/${PROJECT_ID}/render`) && res.request().method() === "POST",
      { timeout: 60_000 },
    );
    const generateBtn = page.getByTestId("one-frame-generate");
    await expect(generateBtn).toBeEnabled();
    await generateBtn.click();
    const renderRes = await renderResponsePromise;
    expect(renderRes.ok(), `render POST -> ${renderRes.status()}`).toBeTruthy();
    const renderBody = await renderRes.json();
    const jobId = String(renderBody.id || "");
    expect(jobId, "render returned a job id").toBeTruthy();

    // 4. Poll the job until done / failed / cancelled. Resilient to transient
    //    connection drops (socket hang up / ECONNRESET) which can happen when
    //    the API is spinning up a heavy render — retry instead of failing.
    const renderStart = Date.now();
    let job: Record<string, any> = { status: "queued", progress: 0, message: "" };
    let pollCount = 0;
    let consecutiveConnErrors = 0;
    while (Date.now() - renderStart < RENDER_TIMEOUT_MS) {
      let res: Awaited<ReturnType<typeof request.get>> | null = null;
      try {
        res = await request.get(`${API}/api/jobs/${jobId}`);
        consecutiveConnErrors = 0;
      } catch (e: unknown) {
        consecutiveConnErrors++;
        const msg = String(e instanceof Error ? e.message : e);
        requestFailures.push(`poll#${pollCount} GET /api/jobs/${jobId} :: ${msg}`);
        if (consecutiveConnErrors >= 6) throw new Error(`job poll gave up after 6 consecutive connection errors: ${msg}`);
        await page.waitForTimeout(5000);
        continue;
      }
      expect(res.ok(), `GET /api/jobs/${jobId} -> ${res!.status()}`).toBeTruthy();
      job = await res!.json();
      pollCount++;
      if (["done", "failed", "cancelled"].includes(job.status)) break;
      await page.waitForTimeout(5000);
    }
    const elapsedSec = Math.round((Date.now() - renderStart) / 1000);
    const finalStatus = String(job.status);

    // 5. On done, verify scene output_path + ffprobe (video + audio + sync).
    let scene: Record<string, any> = {};
    let ffprobeResult: Record<string, any> = { ok: false, skipped: true };
    let outputPath = "";
    if (finalStatus === "done") {
      const sceneRes = await request.get(`${API}/api/projects/${PROJECT_ID}`);
      const projBody = await sceneRes.json();
      scene = (projBody.scenes || []).find((s: any) => s.id === SCENE_ID) || {};
      outputPath = String(scene.output_path || "");
      if (outputPath && fs.existsSync(outputPath)) {
        ffprobeResult = ffprobe(outputPath);
      } else {
        ffprobeResult = { ok: false, skipped: true, reason: `output_path missing or not on disk: ${outputPath}` };
      }
    }

    // 6. Evidence report.
    const report = {
      projectId: PROJECT_ID, sceneId: SCENE_ID, jobId, finalStatus,
      jobMessage: job.message, jobProgress: job.progress, elapsedSec, pollCount,
      promptLength: promptValue.length, outputPath, ffprobe: ffprobeResult,
      consoleErrors, pageErrors, requestFailures, httpErrors,
    };
    writeJson(ARTIFACT_DIR, "e2e-report.json", report);
    await page.screenshot({ path: path.join(ARTIFACT_DIR, `2-final-${finalStatus}.png`), fullPage: true });

    // 7. Honest error surfacing + assertions.
    if (consoleErrors.length) console.log(`[1F-E2E] console errors (${consoleErrors.length}):\n${consoleErrors.join("\n")}`);
    if (pageErrors.length) console.log(`[1F-E2E] page errors (${pageErrors.length}):\n${pageErrors.join("\n")}`);
    if (requestFailures.length) console.log(`[1F-E2E] request failures (${requestFailures.length}):\n${requestFailures.join("\n")}`);
    if (httpErrors.length) console.log(`[1F-E2E] http 4xx/5xx (${httpErrors.length}):\n${httpErrors.join("\n")}`);

    expect(finalStatus, `render did not complete: ${job.message}`).toBe("done");

    // AV integrity: a fast-but-silent render fails certification.
    expect(outputPath, "scene output_path was not set").toBeTruthy();
    expect(fs.existsSync(outputPath), `output file not on disk: ${outputPath}`).toBe(true);
    expect(ffprobeResult.ok, `ffprobe failed: ${ffprobeResult.error || ffprobeResult.reason}`).toBe(true);
    expect(ffprobeResult.video, "output has no video stream").toBeTruthy();
    expect(ffprobeResult.audio, "output has no audio stream (AV must remain native)").toBeTruthy();
    expect(ffprobeResult.video.codec_name, `unexpected video codec: ${ffprobeResult.video.codec_name}`).toMatch(/h264|hevc|vp9|av1/i);
    expect(ffprobeResult.audio.codec_name, `unexpected audio codec: ${ffprobeResult.audio.codec_name}`).toMatch(/aac|mp3|opus|pcm/i);

    console.log(`[1F-E2E] DONE in ${elapsedSec}s (${pollCount} polls). video=${ffprobeResult.video.codec_name} ${ffprobeResult.video.width}x${ffprobeResult.video.height}, audio=${ffprobeResult.audio.codec_name}.`);
  });
});
