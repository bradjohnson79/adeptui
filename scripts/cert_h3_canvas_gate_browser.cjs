const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const http = require("http");

const EV = "C:\\Users\\bradj\\theme_walk\\timeline_v2_h3_canvas_gate_removal";
const API = "http://127.0.0.1:8758";
const WEB = "http://127.0.0.1:5173";
const FORBIDDEN = "multiples of 32";
const FORBIDDEN2 = "Adept will not change your canvas";

function api(method, p, body) {
  return new Promise((resolve, reject) => {
    const u = new URL(API + p);
    const data = body ? JSON.stringify(body) : null;
    const req = http.request(
      { hostname: u.hostname, port: u.port, path: u.pathname + u.search, method,
        headers: { Accept: "application/json", ...(data ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) } : {}) } },
      (res) => { let buf = ""; res.on("data", (c) => (buf += c)); res.on("end", () => { try { resolve(buf ? JSON.parse(buf) : {}); } catch (e) { reject(e); } }); },
    );
    req.on("error", reject);
    if (data) req.write(data);
    req.end();
  });
}

async function upload(projectId, filePath) {
  const boundary = "----AdeBound" + Date.now();
  const file = fs.readFileSync(filePath);
  const body = Buffer.concat([
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\nimage\r\n`),
    Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="ref_character.png"\r\nContent-Type: image/png\r\n\r\n`),
    file,
    Buffer.from(`\r\n--${boundary}--\r\n`),
  ]);
  return new Promise((resolve, reject) => {
    const req = http.request(
      { hostname: "127.0.0.1", port: 8758, path: `/api/projects/${projectId}/assets`, method: "POST",
        headers: { "Content-Type": `multipart/form-data; boundary=${boundary}`, "Content-Length": body.length, Accept: "application/json" } },
      (res) => { let buf = ""; res.on("data", (c) => (buf += c)); res.on("end", () => { const out = JSON.parse(buf || "{}"); resolve(out.id || (out.asset && out.asset.id)); }); },
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

(async () => {
  const report = { steps: [], ok: false };
  const project = await api("POST", "/api/projects", {
    name: `H3 Browser Gate Cert ${Date.now()}`,
    engine_default: "minimax-h3",
    width: 1920,
    height: 824,
    fps: 24,
  });
  const pid = project.id;
  let scenes = project.scenes || (await api("GET", `/api/projects/${pid}`)).scenes || [];
  const sid = scenes[0].id;
  await api("PATCH", `/api/projects/${pid}/scenes/${sid}`, { width: 1920, height: 824, engine: "minimax-h3" });
  const assetId = await upload(pid, path.join(EV, "ref_character.png"));
  report.projectId = pid;
  report.sceneId = sid;
  report.assetId = assetId;

  const created = await api("POST", `/api/film-timeline/projects/${pid}/scenes/${sid}/shots/new`, {
    generatorId: "minimax-h3-i2v-local",
    durationSec: 5.1667,
    timedPrompt: "A calm wide shot of a blue square character standing still in daylight.",
  });
  let shotId = (created.shot && created.shot.id) || created.id;
  if (!shotId) {
    const film = await api("GET", `/api/film-timeline/projects/${pid}/scenes/${sid}`);
    shotId = ((film.film || film).shots || [])[0].id;
  }
  report.shotId = shotId;
  await api("POST", `/api/film-timeline/projects/${pid}/scenes/${sid}/shots/${shotId}/references`, {
    assetId, type: "character", label: "Cert Ref", tag: "character",
  });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  page.on("response", async (res) => {
    try {
      if (res.url().includes("/generate") && res.request().method() === "POST") {
        const json = await res.json().catch(() => null);
        report.generateResponse = json;
        fs.writeFileSync(path.join(EV, "browser_generate_response.json"), JSON.stringify(json, null, 2));
      }
    } catch (_) {}
  });

  // Go directly to Film Timeline workspace
  await page.goto(`${WEB}/project/${pid}?workspace=timeline`, { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(EV, "01_timeline_open.png"), fullPage: true });

  // If still on home, click Open Timeline / Timeline Generator
  if ((await page.getByTestId("film-timeline").count()) === 0) {
    const openTl = page.getByRole("button", { name: /Open Timeline/i });
    if (await openTl.count()) {
      await openTl.first().click();
      await page.waitForTimeout(2000);
    } else {
      const card = page.getByText("Timeline Generator").first();
      if (await card.count()) await card.click();
      await page.waitForTimeout(2000);
    }
  }

  const ft = page.getByTestId("film-timeline");
  await ft.waitFor({ timeout: 60000 });
  report.steps.push("film-timeline-visible");
  await page.screenshot({ path: path.join(EV, "02_film_timeline.png"), fullPage: true });

  const model = page.getByTestId("film-timeline-model");
  await model.waitFor({ timeout: 30000 });
  const values = await model.locator("option").evaluateAll((els) => els.map((e) => e.value));
  report.modelValues = values;
  const h3 = values.find((v) => v.includes("minimax-h3") && v.includes("local")) || values.find((v) => v.includes("minimax-h3"));
  if (!h3) throw new Error("No H3 model: " + values.join(","));
  await model.selectOption(h3);
  report.selectedModel = h3;

  const prompt = page.getByTestId("film-timeline-prompt");
  await prompt.fill("A calm wide shot of a blue square character standing still in daylight.");
  const dur = page.getByTestId("film-timeline-duration");
  await dur.selectOption("10");
  report.durationSec = 10;

  const cancel = page.getByTestId("live-preview-cancel-in-stage");
  await cancel.waitFor({ timeout: 30000 });
  report.cancelIdle = {
    visible: await cancel.isVisible(),
    disabled: await cancel.isDisabled(),
    armed: await cancel.getAttribute("data-cancel-armed"),
  };
  await page.screenshot({ path: path.join(EV, "03_before_generate.png"), fullPage: true });

  const genBtn = page.getByTestId("film-timeline-generate");
  await genBtn.click();
  report.steps.push("generate-clicked");
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(EV, "04_after_generate.png"), fullPage: true });

  let errText = "";
  const errEl = page.getByTestId("film-timeline-error");
  if (await errEl.count()) errText = ((await errEl.textContent()) || "").trim();
  report.uiError = errText;
  report.forbiddenInUi = errText.includes(FORBIDDEN) || errText.includes(FORBIDDEN2);

  let resolved = null, segStatus = null, segError = null;
  for (let i = 0; i < 25; i++) {
    const film = await api("GET", `/api/film-timeline/projects/${pid}/scenes/${sid}`);
    const shots = (film.film || film).shots || [];
    const shot = shots.find((s) => s.id === shotId) || shots[shots.length - 1];
    const seg = (shot && shot.segments && shot.segments[0]) || {};
    segStatus = seg.status;
    segError = seg.error || null;
    const meta = seg.generationMetadata || {};
    resolved = meta.resolvedGeneration || meta.legalCanvas || null;
    report.poll = { i, segStatus, segError, resolved };
    if (resolved && resolved.width === 1152 && resolved.height === 640) break;
    if (segError && (String(segError).includes(FORBIDDEN) || String(segError).includes(FORBIDDEN2))) break;
    if (["completed", "failed", "generating", "processing"].includes(String(segStatus)) && resolved) break;
    await page.waitForTimeout(1000);
  }
  report.resolvedGeneration = resolved;
  report.segmentStatus = segStatus;
  report.segmentError = segError;
  report.forbiddenInSegment = !!(segError && (String(segError).includes(FORBIDDEN) || String(segError).includes(FORBIDDEN2)));

  // Re-check cancel after generate (should arm if job active)
  report.cancelAfter = {
    visible: await cancel.isVisible(),
    disabled: await cancel.isDisabled(),
    armed: await cancel.getAttribute("data-cancel-armed"),
  };

  const genResp = report.generateResponse || {};
  const queueJobId = genResp.queueJobId || genResp.jobId;
  if (queueJobId) {
    try {
      const job = await api("GET", `/api/jobs/${queueJobId}`);
      let params = job.params || {};
      if (typeof job.params_json === "string") params = JSON.parse(job.params_json);
      report.job = { id: queueJobId, status: job.status, width: params.width, height: params.height, resolution: params.resolution, resolvedGeneration: params.resolvedGeneration, engine: params.engine, message: job.message };
    } catch (e) {
      report.job = { error: String(e), id: queueJobId };
    }
  }

  const wxhOk = (resolved && resolved.width === 1152 && resolved.height === 640) || (report.job && report.job.width === 1152 && report.job.height === 640);
  const noForbidden = !report.forbiddenInUi && !report.forbiddenInSegment;
  const queuedOrRunning = ["queued", "generating", "processing", "completed"].includes(String(segStatus));
  report.ok = Boolean(wxhOk && noForbidden && (queuedOrRunning || (genResp && genResp.ok)));
  report.verdict = report.ok ? "GO" : "NO-GO";
  await page.screenshot({ path: path.join(EV, "05_final.png"), fullPage: true });
  await browser.close();
  fs.writeFileSync(path.join(EV, "browser_cert_report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ verdict: report.verdict, ok: report.ok, uiError: report.uiError, segStatus, resolved, job: report.job, cancelIdle: report.cancelIdle, cancelAfter: report.cancelAfter, selectedModel: report.selectedModel }, null, 2));
  process.exit(report.ok ? 0 : 1);
})().catch((err) => {
  console.error(err);
  fs.writeFileSync(path.join(EV, "browser_cert_error.txt"), String(err && err.stack ? err.stack : err));
  process.exit(2);
});

