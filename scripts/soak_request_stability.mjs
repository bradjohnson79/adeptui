/**
 * 10-minute idle soak test for Adept UI frontend request stability.
 *
 * Opens the hosted Vercel frontend, stays idle on Home for 10 minutes,
 * and measures all API request counts at regular intervals.
 */
import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";
const SOAK_MS = 10 * 60 * 1000; // 10 minutes
const CHECKPOINTS = [
  { label: "T+0",   ms: 0 },
  { label: "T+60",  ms: 60 * 1000 },
  { label: "T+120", ms: 120 * 1000 },
  { label: "T+180", ms: 180 * 1000 },
  { label: "T+300", ms: 300 * 1000 },
  { label: "T+600", ms: 600 * 1000 },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  const counts = {
    "/api/health": 0,
    "/api/healthz": 0,
    "/api/capabilities": 0,
    "/api/gpu/stats": 0,
    "/api/runtime/beta": 0,
    "/api/runtime-manager/status": 0,
    "/api/codirector/": 0,
    totalApi: 0,
    totalAll: 0,
    failed: 0,
  };
  const consoleErrors = [];
  const corsErrors = [];
  let peakConcurrent = 0;
  let currentInFlight = 0;

  const checkpointData = [];

  // Track all requests
  page.on("request", (req) => {
    const url = req.url();
    counts.totalAll++;
    if (url.includes("/api/")) {
      counts.totalApi++;
      if (url.includes("/api/health?") || url.endsWith("/api/health")) counts["/api/health"]++;
      else if (url.includes("/api/healthz")) counts["/api/healthz"]++;
      else if (url.includes("/api/capabilities")) counts["/api/capabilities"]++;
      else if (url.includes("/api/gpu/stats") || url.includes("/api/gpu-stats")) counts["/api/gpu/stats"]++;
      else if (url.includes("/api/runtime/beta") || url.includes("/api/runtime-beta")) counts["/api/runtime/beta"]++;
      else if (url.includes("/api/runtime-manager/")) counts["/api/runtime-manager/status"]++;
      else if (url.includes("/api/codirector/")) counts["/api/codirector/"]++;
      currentInFlight++;
      if (currentInFlight > peakConcurrent) peakConcurrent = currentInFlight;
    }
  });

  page.on("requestfinished", () => {
    if (currentInFlight > 0) currentInFlight--;
  });

  page.on("requestfailed", (req) => {
    if (currentInFlight > 0) currentInFlight--;
    const url = req.url();
    if (url.includes("/api/")) counts.failed++;
    const failure = req.failure();
    if (failure && failure.errorText.includes("INSUFFICIENT_RESOURCES")) {
      consoleErrors.push(`ERR_INSUFFICIENT_RESOURCES: ${url}`);
    }
  });

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      consoleErrors.push(text);
      if (text.includes("CORS") || text.includes("Access-Control")) {
        corsErrors.push(text);
      }
      if (text.includes("INSUFFICIENT_RESOURCES")) {
        consoleErrors.push(`ERR_INSUFFICIENT_RESOURCES: ${text}`);
      }
    }
  });

  page.on("pageerror", (err) => {
    consoleErrors.push(`pageerror: ${err.message}`);
  });

  console.log("Opening", TARGET);
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
  console.log("Page loaded. Starting 10-minute idle soak...");

  const startTime = Date.now();

  for (const cp of CHECKPOINTS) {
    const targetTime = startTime + cp.ms;
    const now = Date.now();
    const wait = targetTime - now;
    if (wait > 0) {
      await page.waitForTimeout(wait);
    }

    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const snapshot = {
      checkpoint: cp.label,
      elapsedSec: elapsed,
      health: counts["/api/health"],
      healthz: counts["/api/healthz"],
      capabilities: counts["/api/capabilities"],
      gpu: counts["/api/gpu/stats"],
      runtime: counts["/api/runtime/beta"],
      runtimeManager: counts["/api/runtime-manager/status"],
      codirector: counts["/api/codirector/"],
      totalApi: counts.totalApi,
      totalAll: counts.totalAll,
      failed: counts.failed,
      peakConcurrent,
      consoleErrors: consoleErrors.length,
      corsErrors: corsErrors.length,
    };
    checkpointData.push(snapshot);
    console.log(`[${cp.label}] ${elapsed}s elapsed:`, JSON.stringify(snapshot));
  }

  console.log("\n=== SOAK TEST COMPLETE ===\n");
  console.log("Checkpoint data:");
  for (const cp of checkpointData) {
    console.log(`  ${cp.checkpoint} (${cp.elapsedSec}s): health=${cp.health} healthz=${cp.healthz} caps=${cp.capabilities} gpu=${cp.gpu} total=${cp.totalApi} failed=${cp.failed} peak=${cp.peakConcurrent} errors=${cp.consoleErrors}`);
  }

  console.log("\nConsole errors:", consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.log("First 5:", consoleErrors.slice(0, 5));
  }
  console.log("CORS errors:", corsErrors.length);
  console.log("ERR_INSUFFICIENT_RESOURCES:", consoleErrors.filter(e => e.includes("INSUFFICIENT_RESOURCES")).length);
  console.log("Peak concurrent API requests:", peakConcurrent);

  await page.close();
  await browser.close();

  // Output machine-readable result
  const result = {
    checkpoints: checkpointData,
    finalCounts: counts,
    consoleErrors: consoleErrors.length,
    corsErrors: corsErrors.length,
    insufficientResources: consoleErrors.filter(e => e.includes("INSUFFICIENT_RESOURCES")).length,
    peakConcurrent,
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));
})();
