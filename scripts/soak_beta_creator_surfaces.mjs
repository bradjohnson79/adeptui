/**
 * Adept UI Beta — 30-minute creator-surface soak driver.
 *
 * Exercises the creator surfaces in a loop against the LIVE Beta while
 * scripts/beta_health_monitor.py records server-side health independently:
 *   project landing → project switching (selector) → Timeline → Preview
 *   Monitor → Inspector (batch select) → Co-Director open/close →
 *   save/reload persistence → multi-batch authoring → ComfyUI preflight →
 *   browser refresh.
 *
 * Never kills/rebuilds the live Beta. Uses ONE soak project, deleted at the
 * end. Records failures and continues — the monitor + this report give the
 * dual-metric verdict (zero unintended restarts AND zero failed health
 * samples AND zero soak step failures).
 *
 * Usage:
 *   node scripts/soak_beta_creator_surfaces.mjs --duration-minutes 30 \
 *     --out docs/release-gate/timeline-full-audit/artifacts/beta-soak-creator-surfaces.json
 */
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const API = process.env.STUDIO_API_BASE || "http://127.0.0.1:8758";
const UI = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const TL = `${API}/api/director-timeline`;

const args = process.argv.slice(2);
function argValue(flag, fallback) {
  const i = args.indexOf(flag);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
const DURATION_MIN = Number(argValue("--duration-minutes", "30"));
const OUT = argValue(
  "--out",
  "docs/release-gate/timeline-full-audit/artifacts/beta-soak-creator-surfaces.json",
);

// Same classification as wiring-cert gate T: Timeline-critical URL patterns.
const TIMELINE_CRITICAL = [
  "/api/director-timeline/",
  "/api/projects/",
  "/api/assets/",
  "/api/jobs",
];
const NOISE_PATTERNS = [
  "favicon",
  "/api/setup/",
  "/api/codirector/providers/active/health",
  "ERR_NETWORK_CHANGED", // client-side Windows network stack event, see stability audit
  "ERR_ABORTED", // navigation/reload aborts in-flight requests — not a server failure
];

function classifyUrl(url) {
  if (NOISE_PATTERNS.some((p) => url.includes(p))) return "noise";
  if (TIMELINE_CRITICAL.some((p) => url.includes(p))) return "timeline-critical";
  return "unrelated";
}

const report = {
  startedAt: new Date().toISOString(),
  durationMinutesRequested: DURATION_MIN,
  iterations: [],
  stepFailureCount: 0,
  timelineCriticalConsoleErrors: [],
  timelineCriticalRequestFailures: [],
  verdict: "UNKNOWN",
};

function writeReport() {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 2), "utf8");
}

async function apiJson(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: { "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${url} → ${res.status}`);
  return res.json();
}

async function step(iteration, name, fn) {
  const entry = { name, ok: true, ms: 0 };
  const started = Date.now();
  try {
    await fn();
  } catch (err) {
    entry.ok = false;
    entry.error = String(err && err.message ? err.message : err).slice(0, 300);
    report.stepFailureCount += 1;
  }
  entry.ms = Date.now() - started;
  iteration.steps.push(entry);
  return entry.ok;
}

async function main() {
  const deadline = Date.now() + DURATION_MIN * 60_000;

  // One soak project (created once, deleted at the end — no project spam).
  const project = await apiJson("POST", `${API}/api/projects`, {
    name: `ADEPT Beta Soak ${new Date().toISOString().slice(0, 16)}`,
  });
  const pid = project.id;
  report.projectId = pid;

  const scenesPayload = await (await fetch(`${API}/api/projects/${pid}/scenes`)).json();
  const scenes = Array.isArray(scenesPayload) ? scenesPayload : scenesPayload.scenes || [];
  const sid = scenes[0].id;

  // Multi-batch authoring surface: two batches authored once, verified every iteration.
  await apiJson("POST", `${TL}/projects/${pid}/scenes/${sid}/batches`, { plannedDuration: 4 });
  await apiJson("POST", `${TL}/projects/${pid}/scenes/${sid}/batches`, { plannedDuration: 6 });

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text() || "";
    if (NOISE_PATTERNS.some((p) => text.includes(p))) return;
    const locationUrl = msg.location()?.url || "";
    if (classifyUrl(locationUrl) === "timeline-critical" || text.includes("director-timeline")) {
      report.timelineCriticalConsoleErrors.push({ at: new Date().toISOString(), text: text.slice(0, 300) });
    }
  });
  page.on("pageerror", (err) => {
    report.timelineCriticalConsoleErrors.push({
      at: new Date().toISOString(),
      text: `pageerror: ${String(err).slice(0, 300)}`,
    });
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    const failure = req.failure()?.errorText || "";
    if (NOISE_PATTERNS.some((p) => url.includes(p) || failure.includes(p))) return;
    if (classifyUrl(url) === "timeline-critical") {
      report.timelineCriticalRequestFailures.push({
        at: new Date().toISOString(),
        url: url.slice(0, 200),
        failure,
      });
    }
  });

  let iterationIndex = 0;
  while (Date.now() < deadline) {
    iterationIndex += 1;
    const iteration = { index: iterationIndex, at: new Date().toISOString(), steps: [] };
    report.iterations.push(iteration);

    await step(iteration, "project-landing", async () => {
      await page.goto(`${UI}/project/${pid}`, { waitUntil: "domcontentloaded" });
      await page.locator(".project-dash-actions button.primary").waitFor({ timeout: 30_000 });
    });

    if (iterationIndex % 3 === 0) {
      await step(iteration, "project-switch-via-selector", async () => {
        await page.goto(`${UI}/`, { waitUntil: "domcontentloaded" });
        await page.locator("button.ds-menu-trigger", { hasText: "Project" }).first().click();
        const item = page.locator('button[role="menuitem"]', { hasText: "Soak" }).first();
        await item.waitFor({ timeout: 10_000 });
        await item.click();
        await page.locator(".project-dash-actions button.primary").waitFor({ timeout: 30_000 });
      });
    }

    await step(iteration, "timeline-open", async () => {
      await page.goto(`${UI}/project/${pid}?workspace=timeline`, { waitUntil: "domcontentloaded" });
      await page.getByTestId("timeline-editor-shell").waitFor({ timeout: 45_000 });
      await page.getByTestId("timeline-track-board").waitFor({ timeout: 30_000 });
    });

    await step(iteration, "multi-batch-authoring-verify", async () => {
      const master = (await apiJson("GET", `${TL}/projects/${pid}/scenes/${sid}/master`)).master;
      if (!master || (master.batchBlocks || []).length < 2) {
        throw new Error("expected >=2 batch blocks in master");
      }
    });

    await step(iteration, "preview-monitor-present", async () => {
      await page.getByTestId("live-preview-monitor").waitFor({ timeout: 30_000 });
    });

    await step(iteration, "inspector-batch-select", async () => {
      const master = (await apiJson("GET", `${TL}/projects/${pid}/scenes/${sid}/master`)).master;
      const batchId = master.batchBlocks[0].id;
      const clip = page.getByTestId(`timeline-batch-${batchId}`);
      await clip.waitFor({ timeout: 30_000 });
      await clip.click();
    });

    await step(iteration, "save-reload-persistence", async () => {
      const marker = `soak-${iterationIndex}-${Date.now()}`;
      const sceneList = await (await fetch(`${API}/api/projects/${pid}/scenes`)).json();
      const scene = (Array.isArray(sceneList) ? sceneList : sceneList.scenes || [])[0];
      await apiJson("PATCH", `${API}/api/projects/${pid}/scenes/${scene.id}`, { prompt: marker });
      await page.reload({ waitUntil: "domcontentloaded" });
      await page.getByTestId("timeline-editor-shell").waitFor({ timeout: 45_000 });
      const after = await (await fetch(`${API}/api/projects/${pid}/scenes`)).json();
      const sceneAfter = (Array.isArray(after) ? after : after.scenes || [])[0];
      if (sceneAfter.prompt !== marker) throw new Error("scene prompt did not survive reload");
      const master = (await apiJson("GET", `${TL}/projects/${pid}/scenes/${sid}/master`)).master;
      if ((master.batchBlocks || []).length < 2) throw new Error("batches lost across save/reload");
    });

    await step(iteration, "codirector-open-close", async () => {
      await page.getByTestId("chrome-codirector").click();
      await page.waitForURL(/co-director/, { timeout: 15_000 });
      await page.goBack();
      await page.getByTestId("timeline-editor-shell").waitFor({ timeout: 45_000 });
    });

    await step(iteration, "comfyui-preflight", async () => {
      const res = await apiJson("GET", `${TL}/projects/${pid}/scenes/${sid}/preflight`);
      if (!res.ok) throw new Error("preflight endpoint not ok");
    });

    writeReport();
  }

  await browser.close();
  await fetch(`${API}/api/projects/${pid}`, { method: "DELETE" }).catch(() => undefined);

  report.endedAt = new Date().toISOString();
  report.verdict =
    report.stepFailureCount === 0 &&
    report.timelineCriticalConsoleErrors.length === 0 &&
    report.timelineCriticalRequestFailures.length === 0
      ? "SOAK CLEAN"
      : "SOAK FAILURES RECORDED";
  writeReport();
  console.log(
    JSON.stringify(
      {
        verdict: report.verdict,
        iterations: report.iterations.length,
        stepFailureCount: report.stepFailureCount,
        timelineCriticalConsoleErrors: report.timelineCriticalConsoleErrors.length,
        timelineCriticalRequestFailures: report.timelineCriticalRequestFailures.length,
        out: OUT,
      },
      null,
      2,
    ),
  );
  process.exit(report.verdict === "SOAK CLEAN" ? 0 : 1);
}

main().catch((err) => {
  report.verdict = "SOAK DRIVER CRASH";
  report.driverCrash = String(err && err.stack ? err.stack : err).slice(0, 1000);
  writeReport();
  console.error(err);
  process.exit(1);
});
