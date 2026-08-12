/**
 * Live failure/recovery test.
 * Opens the page, verifies healthy state, then the operator stops Studio API externally.
 * Script detects outage, then operator restarts API. Script verifies recovery.
 */
import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  const probes = { healthz: [], health: [] };
  const consoleErrors = [];
  let peakConcurrent = 0;
  let currentInFlight = 0;
  let totalApi = 0;

  page.on("request", (req) => {
    const url = req.url();
    if (url.includes("/api/")) {
      totalApi++;
      currentInFlight++;
      if (currentInFlight > peakConcurrent) peakConcurrent = currentInFlight;
    }
  });
  page.on("response", (res) => {
    const url = res.url();
    if (url.includes("/api/healthz")) {
      probes.healthz.push({ t: Date.now(), ok: res.ok(), status: res.status() });
    }
    if (url.includes("/api/health") && !url.includes("healthz")) {
      probes.health.push({ t: Date.now(), ok: res.ok(), status: res.status() });
    }
  });
  page.on("requestfinished", () => { if (currentInFlight > 0) currentInFlight--; });
  page.on("requestfailed", () => { if (currentInFlight > 0) currentInFlight--; });
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

  console.log("Opening", TARGET);
  await page.goto(TARGET, { waitUntil: "networkidle", timeout: 30000 });
  
  // Verify healthy state
  console.log("Verifying healthy state...");
  await page.waitForTimeout(5000);
  const bodyText = await page.textContent("body").catch(() => "");
  const healthyText = bodyText?.toLowerCase() || "";
  
  const studioApiOnline = healthyText.includes("online") || healthyText.includes("connected");
  console.log("Studio API online:", studioApiOnline);
  console.log("Initial probes: healthz=", probes.healthz.length, "health=", probes.health.length);

  // Phase 1: Establish baseline (30s)
  console.log("\n--- BASELINE (30s) ---");
  await page.waitForTimeout(30000);
  const baselineHealthz = probes.healthz.length;
  const baselineHealth = probes.health.length;
  const baselineApi = totalApi;
  console.log(`Baseline: healthz=${baselineHealthz} health=${baselineHealth} totalApi=${baselineApi}`);

  // Phase 2: Wait for operator to stop API (detect outage)
  console.log("\n--- WAITING FOR OUTAGE (stop Studio API now) ---");
  console.log("Monitoring for healthz failures...");
  
  let outageDetected = false;
  const outageStart = Date.now();
  while (Date.now() - outageStart < 180000) { // 3 min timeout
    await page.waitForTimeout(2000);
    const recent = probes.healthz.slice(-3);
    const failures = recent.filter(p => !p.ok).length;
    if (failures >= 2) {
      outageDetected = true;
      console.log(`OUTAGE DETECTED at ${Date.now() - outageStart}ms: ${failures}/${recent.length} recent healthz failed`);
      break;
    }
  }

  if (!outageDetected) {
    console.log("WARNING: No outage detected within 3 minutes. Proceeding to recovery phase.");
  }

  // Record outage state
  const outageApiCount = totalApi - baselineApi;
  console.log(`During outage window: ${outageApiCount} API requests, ${probes.healthz.filter(p => !p.ok).length} failed healthz`);

  // Phase 3: Wait for recovery (detect API coming back)
  console.log("\n--- WAITING FOR RECOVERY (restart Studio API now) ---");
  console.log("Monitoring for healthz success...");
  
  let recoveryDetected = false;
  const recoveryStart = Date.now();
  while (Date.now() - recoveryStart < 180000) { // 3 min timeout
    await page.waitForTimeout(2000);
    const recent = probes.healthz.slice(-3);
    const successes = recent.filter(p => p.ok).length;
    if (successes >= 2 && outageDetected) {
      recoveryDetected = true;
      const recoveryTime = Date.now() - recoveryStart;
      console.log(`RECOVERY DETECTED at ${recoveryTime}ms: ${successes}/${recent.length} recent healthz succeeded`);
      break;
    }
  }

  if (!recoveryDetected && outageDetected) {
    // Check if health probes (not healthz) succeeded
    const recentHealth = probes.health.slice(-3).filter(p => p.ok).length;
    if (recentHealth >= 1) {
      recoveryDetected = true;
      console.log(`RECOVERY DETECTED via /api/health at ${Date.now() - recoveryStart}ms`);
    }
  }

  // Phase 4: Post-recovery soak (5 minutes)
  console.log("\n--- POST-RECOVERY SOAK (5 min) ---");
  const soakStartCounts = { healthz: probes.healthz.length, health: probes.health.length, api: totalApi };
  await page.waitForTimeout(300000); // 5 minutes

  const soakHealthz = probes.healthz.length - soakStartCounts.healthz;
  const soakHealth = probes.health.length - soakStartCounts.health;
  const soakApi = totalApi - soakStartCounts.api;
  const soakFailed = probes.healthz.slice(soakStartCounts.healthz).filter(p => !p.ok).length;

  console.log(`\nPost-recovery 5-min soak:`);
  console.log(`  healthz=${soakHealthz} health=${soakHealth} totalApi=${soakApi} failed=${soakFailed}`);
  console.log(`  console errors=${consoleErrors.length} peakConcurrent=${peakConcurrent}`);

  // Final summary
  console.log("\n=== FAILURE/RECOVERY TEST COMPLETE ===\n");
  console.log(`Outage detected: ${outageDetected}`);
  console.log(`Recovery detected: ${recoveryDetected}`);
  console.log(`Total healthz probes: ${probes.healthz.length} (ok: ${probes.healthz.filter(p => p.ok).length}, fail: ${probes.healthz.filter(p => !p.ok).length})`);
  console.log(`Total health probes: ${probes.health.length}`);
  console.log(`Total API requests: ${totalApi}`);
  console.log(`Peak concurrent: ${peakConcurrent}`);
  console.log(`Console errors: ${consoleErrors.length}`);
  if (consoleErrors.length > 0) console.log("First 5:", consoleErrors.slice(0, 5));

  const result = {
    outageDetected,
    recoveryDetected,
    totalHealthz: probes.healthz.length,
    healthzOk: probes.healthz.filter(p => p.ok).length,
    healthzFail: probes.healthz.filter(p => !p.ok).length,
    totalHealth: probes.health.length,
    totalApi,
    peakConcurrent,
    consoleErrors: consoleErrors.length,
    postRecoverySoak: { healthz: soakHealthz, health: soakHealth, totalApi: soakApi, failed: soakFailed },
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));

  await page.close();
  await browser.close();
})();
