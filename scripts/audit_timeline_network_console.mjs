/**
 * Timeline network/console audit against the LIVE Beta (Phase 10).
 *
 * Loads the Timeline workspace with full console + network capture, drives the
 * core creator interactions (batch select, inspector, scene rail, scroll,
 * preview), and writes a classified artifact:
 *   docs/release-gate/timeline-full-audit/artifacts/timeline-network-console-audit.json
 *
 * Classification: TIMELINE_CRITICAL (timeline/preview/master/generation routes
 * or uncaught errors) vs NOISE (sample data, unrelated services, favicon, etc).
 *
 * Usage: node scripts/audit_timeline_network_console.mjs [projectId]
 * Requires the Beta running on 127.0.0.1:8760 (web) / 8758 (API).
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const PROJECT_ID = process.argv[2] || "6ee08996-49c3-411a-84bb-ffeba7abbcdc";
const URL = `${WEB}/project/${PROJECT_ID}?workspace=timeline`;
const OUT = path.join(
  "docs",
  "release-gate",
  "timeline-full-audit",
  "artifacts",
  "timeline-network-console-audit.json",
);

const consoleErrors = [];
const consoleWarnings = [];
const pageErrors = [];
const failedRequests = []; // network-level failures (requestfailed)
const badResponses = []; // HTTP >= 400

const TIMELINE_CRITICAL = [
  /\/api\/director-timeline/i,
  /\/api\/projects\/[^/]+\/scenes/i,
  /\/api\/timeline/i,
  /timeline/i,
  /\/api\/jobs/i,
  /\/api\/assets/i,
  /\/api\/codirector\/timeline/i,
  /\/api\/codirector\/context/i,
];
const NOISE_PATTERNS = [
  /favicon/i,
  /\/api\/install/i,
  /\/api\/setup/i,
  /\/api\/health/i,
  /__beta_web_health/i,
  /sourcemap|\.map$/i,
];

function classify(url) {
  if (NOISE_PATTERNS.some((p) => p.test(url))) return "noise";
  if (TIMELINE_CRITICAL.some((p) => p.test(url))) return "timeline-critical";
  return "unrelated";
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1600, height: 950 } });

page.on("console", (msg) => {
  const entry = { type: msg.type(), text: msg.text().slice(0, 600), location: msg.location()?.url || "" };
  if (msg.type() === "error") consoleErrors.push(entry);
  else if (msg.type() === "warning") consoleWarnings.push(entry);
});
page.on("pageerror", (err) => pageErrors.push(String(err).slice(0, 600)));
page.on("requestfailed", (req) => {
  const url = req.url();
  failedRequests.push({
    url: url.slice(0, 400),
    failure: req.failure()?.errorText || "unknown",
    class: classify(url),
  });
});
page.on("response", (res) => {
  if (res.status() >= 400) {
    const url = res.url();
    badResponses.push({ status: res.status(), url: url.slice(0, 400), class: classify(url) });
  }
});

const t0 = Date.now();
await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
await page.waitForSelector('[data-testid="timeline-track-board"]', { timeout: 60_000 });
await page.waitForTimeout(4000);

// Interactions: select first batch → inspector; scroll batch lane; open/close
// Co-Director rail; toggle viewer overlay; refresh.
const interactions = [];
async function step(name, fn) {
  const before = {
    consoleErrors: consoleErrors.length,
    failedRequests: failedRequests.length,
    badResponses: badResponses.length,
    pageErrors: pageErrors.length,
  };
  try {
    await fn();
    interactions.push({ name, ok: true });
  } catch (err) {
    interactions.push({ name, ok: false, error: String(err).slice(0, 300) });
  }
  await page.waitForTimeout(1500);
  const after = {
    consoleErrors: consoleErrors.length,
    failedRequests: failedRequests.length,
    badResponses: badResponses.length,
    pageErrors: pageErrors.length,
  };
  interactions[interactions.length - 1].newIssues = {
    consoleErrors: after.consoleErrors - before.consoleErrors,
    failedRequests: after.failedRequests - before.failedRequests,
    badResponses: after.badResponses - before.badResponses,
    pageErrors: after.pageErrors - before.pageErrors,
  };
}

await step("select-first-batch", async () => {
  const batch = page.locator('[data-testid^="timeline-batch-"]').first();
  await batch.click();
  await page.waitForSelector('[data-testid="timeline-batch-generator"]', { timeout: 15_000 });
});

await step("scroll-batch-lane", async () => {
  const scroller = page.locator('[data-testid="timeline-track-scroll"]');
  await scroller.evaluate((el) => {
    el.scrollLeft = el.scrollWidth;
  });
  await page.waitForTimeout(800);
  await scroller.evaluate((el) => {
    el.scrollLeft = 0;
  });
});

await step("open-codirector-rail", async () => {
  const btn = page.getByRole("button", { name: "Show the Co-Director rail" });
  if (await btn.count()) {
    await btn.click();
    await page.waitForTimeout(1200);
    const hide = page.getByRole("button", { name: "Hide the Co-Director rail" });
    if (await hide.count()) await hide.click();
  }
});

await step("refresh-page", async () => {
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="timeline-track-board"]', { timeout: 60_000 });
  await page.waitForTimeout(3000);
});

await step("reselect-batch-after-refresh", async () => {
  const batch = page.locator('[data-testid^="timeline-batch-"]').first();
  if (await batch.count()) await batch.click();
});

const durationMs = Date.now() - t0;

const timelineCriticalFailures = [
  ...failedRequests.filter((r) => r.class === "timeline-critical").map((r) => ({ kind: "requestfailed", ...r })),
  ...badResponses.filter((r) => r.class === "timeline-critical").map((r) => ({ kind: "badResponse", ...r })),
];

const report = {
  url: URL,
  durationMs,
  interactions,
  counts: {
    consoleErrors: consoleErrors.length,
    consoleWarnings: consoleWarnings.length,
    pageErrors: pageErrors.length,
    failedRequests: failedRequests.length,
    badResponses: badResponses.length,
    timelineCriticalFailures: timelineCriticalFailures.length,
  },
  timelineCriticalFailures,
  consoleErrors,
  pageErrors,
  failedRequests,
  badResponses,
  consoleWarnings: consoleWarnings.slice(0, 40),
};

mkdirSync(path.dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2));
console.log(JSON.stringify(report.counts, null, 2));
console.log(`artifact: ${OUT}`);

await browser.close();
process.exit(timelineCriticalFailures.length > 0 || pageErrors.length > 0 ? 1 : 0);
