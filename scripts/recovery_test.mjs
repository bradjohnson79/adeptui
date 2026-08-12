/**
 * Live failure/recovery test for Adept UI hosted frontend.
 *
 * Opens https://adeptui.vercel.app and monitors /api/healthz and /api/health
 * probes continuously. Detects:
 *   1. healthy baseline state
 *   2. API outage (healthz starts failing)
 *   3. API recovery (healthz succeeds again)
 *   4. 5-minute post-recovery soak
 *
 * The script does NOT stop/start the Studio API itself. An external operator
 * stops the API after baseline is established, then restarts it. The script
 * detects both transitions from observed probe responses.
 *
 * Usage:
 *   node scripts/recovery_test.mjs
 *   node scripts/recovery_test.mjs --outage-timeout-ms=120000
 *   node scripts/recovery_test.mjs --post-recovery-ms=300000
 */
import { chromium } from "playwright";

const TARGET = "https://adeptui.vercel.app";

const args = process.argv.slice(2);
function arg(name, fallback) {
  const flag = `--${name}=`;
  const hit = args.find((a) => a.startsWith(flag));
  if (!hit) return fallback;
  const v = hit.slice(flag.length);
  const n = Number(v);
  return Number.isFinite(n) ? n : v;
}

const OUTAGE_TIMEOUT_MS = arg("outage-timeout-ms", 10 * 60 * 1000);
const POST_RECOVERY_MS = arg("post-recovery-ms", 5 * 60 * 1000);
const BASELINE_MS = arg("baseline-ms", 30 * 1000);
const PROBE_TIMEOUT_MS = arg("probe-timeout-ms", 30000);

const log = (msg) => {
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${msg}`);
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  let browser;
  let page;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1920, height: 1080 },
    });
    page = await context.newPage();
  } catch (e) {
    console.error("FATAL: failed to launch browser:", e.message);
    process.exitCode = 2;
    return;
  }

  // Probe tracking
  const probes = {
    healthz: { total: 0, success: 0, fail: 0, responses: [] },
    health: { total: 0, success: 0, fail: 0, responses: [] },
  };

  const stateTransitions = [];
  const consoleErrors = [];
  const pageErrors = [];
  let peakConcurrent = 0;
  let currentInFlight = 0;

  const recordTransition = (label, detail = {}) => {
    const t = {
      time: Date.now(),
      timeISO: new Date().toISOString(),
      label,
      ...detail,
    };
    stateTransitions.push(t);
    log(`TRANSITION: ${label} ${JSON.stringify(detail)}`);
  };

  const classifyProbe = (url) => {
    if (url.includes("/api/healthz")) return "healthz";
    if (url.endsWith("/api/health") || url.includes("/api/health?")) return "health";
    return null;
  };

  page.on("request", (req) => {
    const kind = classifyProbe(req.url());
    if (!kind) return;
    probes[kind].total++;
    currentInFlight++;
    if (currentInFlight > peakConcurrent) peakConcurrent = currentInFlight;
  });

  page.on("requestfinished", async (req) => {
    const kind = classifyProbe(req.url());
    if (!kind) return;
    if (currentInFlight > 0) currentInFlight--;
    let status = null;
    try {
      const resp = await req.response();
      status = resp ? resp.status() : null;
    } catch (_) {}
    const ok = status !== null && status >= 200 && status < 500;
    if (ok) probes[kind].success++;
    else probes[kind].fail++;
    probes[kind].responses.push({ t: Date.now(), status, ok });
  });

  page.on("requestfailed", (req) => {
    const kind = classifyProbe(req.url());
    if (!kind) return;
    if (currentInFlight > 0) currentInFlight--;
    let errText = "";
    try {
      const f = req.failure();
      errText = f ? f.errorText : "unknown";
    } catch (_) {}
    probes[kind].fail++;
    probes[kind].responses.push({ t: Date.now(), status: null, ok: false, errText });
  });

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push({ t: Date.now(), text: msg.text() });
  });

  page.on("pageerror", (err) => {
    pageErrors.push({ t: Date.now(), message: err.message });
  });

  // Helpers to read DOM-derived connection state
  async function readDomState() {
    const state = {
      studioApi: null,
      comfyui: null,
      runtime: null,
      bodyText: "",
    };
    try {
      state.bodyText = (await page.locator("body").innerText({ timeout: 5000 }).catch(() => "")) || "";
    } catch (_) {}
    const checks = [
      { key: "studioApi", re: /Studio\s*API\s*(Online|Offline|Disconnected|Error|Unreachable|Connecting)/i },
      { key: "comfyui", re: /ComfyUI\s*(Connected|Disconnected|Offline|Error|Connecting)/i },
      { key: "runtime", re: /(Runtime|Background)\s*(Ready|Starting|Offline|Error|Unreachable)/i },
    ];
    for (const c of checks) {
      const m = state.bodyText.match(c.re);
      if (m) state[c.key] = m[1];
    }
    return state;
  }

  // Phase 1: open and verify healthy
  log(`Opening ${TARGET}`);
  try {
    await page.goto(TARGET, { waitUntil: "networkidle", timeout: PROBE_TIMEOUT_MS });
  } catch (e) {
    console.error("FATAL: page.goto failed:", e.message);
    await browser.close().catch(() => {});
    process.exitCode = 2;
    return;
  }
  log("Page loaded. Establishing healthy baseline...");

  const openTime = Date.now();

  // Give DOM time to render status surfaces
  await sleep(5000);
  const initialDom = await readDomState();
  log(`Initial DOM state: ${JSON.stringify(initialDom)}`);

  const initialSnapshot = {
    healthzTotal: probes.healthz.total,
    healthzSuccess: probes.healthz.success,
    healthzFail: probes.healthz.fail,
    healthTotal: probes.health.total,
    healthSuccess: probes.health.success,
    healthFail: probes.health.fail,
    studioApi: initialDom.studioApi,
    comfyui: initialDom.comfyui,
    runtime: initialDom.runtime,
  };
  recordTransition("INITIAL_STATE", initialSnapshot);

  const healthy =
    initialSnapshot.healthzSuccess > 0 ||
    initialSnapshot.healthSuccess > 0 ||
    initialSnapshot.studioApi === "Online";

  if (!healthy) {
    log("WARNING: initial state does not appear healthy. Continuing to monitor anyway.");
  } else {
    log("Healthy baseline confirmed.");
  }

  // Phase 2: baseline window
  log(`Baseline window: ${BASELINE_MS}ms`);
  await sleep(BASELINE_MS);

  const baselineEnd = Date.now();
  const baselineCounts = {
    healthzTotal: probes.healthz.total,
    healthzSuccess: probes.healthz.success,
    healthzFail: probes.healthz.fail,
    healthTotal: probes.health.total,
    healthSuccess: probes.health.success,
    healthFail: probes.health.fail,
  };
  const baselineDom = await readDomState();
  recordTransition("BASELINE_END", { ...baselineCounts, dom: baselineDom });
  log(`Baseline end: ${JSON.stringify(baselineCounts)} dom=${JSON.stringify(baselineDom)}`);

  // Phase 3: detect outage — wait for healthz/health to start failing
  log(`Waiting for API outage (timeout ${OUTAGE_TIMEOUT_MS}ms)...`);
  let outageStart = null;
  let lastDomDuringOutage = null;
  const outageDeadline = Date.now() + OUTAGE_TIMEOUT_MS;

  while (!outageStart && Date.now() < outageDeadline) {
    await sleep(2000);
    const recent = probes.healthz.responses.slice(-3).concat(probes.health.responses.slice(-3));
    const recentFail = recent.filter((r) => !r.ok);
    if (recentFail.length >= 2) {
      outageStart = recentFail[0].t;
      recordTransition("OUTAGE_DETECTED", {
        firstFailAt: new Date(outageStart).toISOString(),
        healthzFail: probes.healthz.fail,
        healthFail: probes.health.fail,
      });
      lastDomDuringOutage = await readDomState();
      log(`Outage detected. DOM during outage: ${JSON.stringify(lastDomDuringOutage)}`);
      recordTransition("OUTAGE_DOM", lastDomDuringOutage);
      break;
    }
  }

  if (!outageStart) {
    log("No outage detected within timeout. Skipping recovery phase.");
    recordTransition("NO_OUTAGE", { reason: "timeout", deadline: new Date(outageDeadline).toISOString() });
  } else {
    // Phase 4: detect recovery — wait for healthz/health to succeed again
    log("Outage confirmed. Waiting for API recovery...");
    let recoveryStart = null;
    while (!recoveryStart) {
      await sleep(2000);
      const recent = probes.healthz.responses.slice(-3).concat(probes.health.responses.slice(-3));
      const recentOk = recent.filter((r) => r.ok);
      if (recentOk.length >= 2) {
        recoveryStart = recentOk[0].t;
        recordTransition("RECOVERY_DETECTED", {
          firstOkAt: new Date(recoveryStart).toISOString(),
        });
        break;
      }
    }

    const recoveryDom = await readDomState();
    recordTransition("RECOVERY_DOM", recoveryDom);
    log(`Recovery detected. DOM after recovery: ${JSON.stringify(recoveryDom)}`);

    const outageDurationMs = recoveryStart - outageStart;
    log(`Outage duration: ${outageDurationMs}ms`);

    // Probe counts during outage window
    const outageWindowProbes = {
      healthzTotal: probes.healthz.responses.filter((r) => r.t >= outageStart && r.t <= recoveryStart).length,
      healthzFail: probes.healthz.responses.filter((r) => r.t >= outageStart && r.t <= recoveryStart && !r.ok).length,
      healthTotal: probes.health.responses.filter((r) => r.t >= outageStart && r.t <= recoveryStart).length,
      healthFail: probes.health.responses.filter((r) => r.t >= outageStart && r.t <= recoveryStart && !r.ok).length,
    };
    recordTransition("OUTAGE_WINDOW_PROBES", outageWindowProbes);
    log(`Outage-window probes: ${JSON.stringify(outageWindowProbes)}`);

    // Phase 5: post-recovery soak
    log(`Starting ${POST_RECOVERY_MS}ms post-recovery soak...`);
    const soakStart = Date.now();
    let lastSnapshot = Date.now();
    while (Date.now() - soakStart < POST_RECOVERY_MS) {
      await sleep(15000);
      const dom = await readDomState();
      const snap = {
        elapsedSinceRecoveryMs: Date.now() - recoveryStart,
        healthzTotal: probes.healthz.total,
        healthzFail: probes.healthz.fail,
        healthTotal: probes.health.total,
        healthFail: probes.health.fail,
        dom,
      };
      if (Date.now() - lastSnapshot > 60000) {
        log(`SOAK: ${JSON.stringify(snap)}`);
        lastSnapshot = Date.now();
      }
    }
  }

  // Phase 6: final report
  const finalDom = await readDomState();
  const finalCounts = {
    healthzTotal: probes.healthz.total,
    healthzSuccess: probes.healthz.success,
    healthzFail: probes.healthz.fail,
    healthTotal: probes.health.total,
    healthSuccess: probes.health.success,
    healthFail: probes.health.fail,
  };
  log("=== RECOVERY TEST COMPLETE ===");
  log(`Final counts: ${JSON.stringify(finalCounts)}`);
  log(`Final DOM: ${JSON.stringify(finalDom)}`);
  log(`Console errors: ${consoleErrors.length}`);
  log(`Page errors: ${pageErrors.length}`);
  log(`Peak concurrent probes: ${peakConcurrent}`);

  console.log("\nTransitions:");
  for (const t of stateTransitions) {
    console.log(`  ${t.timeISO}  ${t.label}  ${JSON.stringify({ ...t, time: undefined, timeISO: undefined })}`);
  }

  if (consoleErrors.length > 0) {
    console.log("\nFirst 5 console errors:");
    for (const e of consoleErrors.slice(0, 5)) console.log(`  ${e.text}`);
  }
  if (pageErrors.length > 0) {
    console.log("\nFirst 5 page errors:");
    for (const e of pageErrors.slice(0, 5)) console.log(`  ${e.message}`);
  }

  const result = {
    target: TARGET,
    openTimeISO: new Date(openTime).toISOString(),
    healthy,
    finalCounts,
    finalDom,
    transitions: stateTransitions,
    consoleErrors: consoleErrors.length,
    pageErrors: pageErrors.length,
    peakConcurrent,
    outageDetected: stateTransitions.some((t) => t.label === "OUTAGE_DETECTED"),
    recoveryDetected: stateTransitions.some((t) => t.label === "RECOVERY_DETECTED"),
  };
  console.log("\nRESULT_JSON:", JSON.stringify(result));

  await page.close().catch(() => {});
  await browser.close().catch(() => {});
})().catch((e) => {
  console.error("UNCAUGHT:", e && e.stack ? e.stack : e);
  process.exitCode = 1;
});
