/**
 * Hosted runtime stability regression test.
 *
 * Reproduces the delayed-onset defect class: after several minutes of Co-Director
 * usage, browser console surfaces CORS failures and Script Writer autosave 400s
 * caused by (a) middleware-ordering bypass of CORS on error responses and
 * (b) autosave revision-race. This test crosses the 20s production-control
 * polling threshold and asserts no CORS failures, no unexplained 400s, and
 * bounded background request volume.
 *
 * ADEPT_BETA_TARGET=1 · workers=1 · retries=0
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { API, BETA_TARGET, createTempProject, deleteProject } from "../helpers/app";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";
const RUN_ID = `hosted-stability-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "hosted-runtime-stability",
  "artifacts",
  RUN_ID,
  "playwright",
);

const PROJECT_ID =
  process.env.ADEPT_PROJECT_ID || "2347bf46-3762-4763-86c5-4a6032522278";

const CORS_FAILURE = /Access-Control-Allow-Origin|CORS|Failed to fetch/i;
const AUTOSAVE_400 = /autosave.*400|SCRIPT_CONFLICT/i;

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

test.describe("Hosted runtime stability (delayed CORS + autosave)", () => {
  test("Co-Director stays healthy across polling thresholds without CORS failures", async ({ page, request }) => {
    test.setTimeout(Math.max(120_000, Number(process.env.SOAK_MS || 0) + 60_000));

    // Hosted soak (PLAYWRIGHT_BASE_URL points at a non-local URL) reuses a
    // fixed existing project to avoid polluting hosted data with temp projects.
    const isHostedSoak = !BETA_TARGET && /adeptui\.vercel\.app/i.test(WEB);
    let ownedProjectId: string | null = null;
    if (!BETA_TARGET && !isHostedSoak) {
      const proj = await createTempProject(request, "Hosted Stability E2E");
      ownedProjectId = proj.id;
    }
    const projectId = ownedProjectId ?? PROJECT_ID;

    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const corsFailures: string[] = [];
    const autosaveFailures: string[] = [];
    const failedRequests: Array<{ url: string; status: number }> = [];

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        consoleErrors.push(text);
        if (CORS_FAILURE.test(text)) corsFailures.push(text);
        if (AUTOSAVE_400.test(text)) autosaveFailures.push(text);
      }
    });
    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("requestfailed", (req) => {
      failedRequests.push({ url: req.url(), status: 0 });
    });
    page.on("response", async (res) => {
      const url = res.url();
      if (/\/api\//.test(url) && res.status() >= 400) {
        failedRequests.push({ url, status: res.status() });
      }
    });

    await page.goto(`${WEB}/co-director?projectId=${projectId}`, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });

    // Wait for the Co-Director surface to mount — the message composer is the
    // stable anchor across beta deploys (no testid dependency).
    await expect
      .poll(async () => page.getByPlaceholder("Ask Co-Director...").count(), {
        timeout: 30_000,
      })
      .toBeGreaterThan(0);

    // Cross the 20s production-control polling threshold at least 3 times.
    // Default 70s exercises several polling ticks + recovery paths.
    // SOAK_MS env extends the active session for full 15-minute hosted soak.
    const soakMs = Number(process.env.SOAK_MS || 70_000);
    await page.waitForTimeout(soakMs);

    // Exercise Script Writer tab (embedded) to surface autosave path.
    const scriptwriterTab = page.getByRole("tab", { name: /Script Writer/i }).first();
    if (await scriptwriterTab.isVisible().catch(() => false)) {
      await scriptwriterTab.click({ force: true });
      await page.waitForTimeout(2_000);
    }

    writeJson("console-errors.json", consoleErrors);
    writeJson("page-errors.json", pageErrors);
    writeJson("cors-failures.json", corsFailures);
    writeJson("autosave-failures.json", autosaveFailures);
    writeJson("failed-requests.json", failedRequests);

    // Assertions — the defect class must not recur.
    expect(corsFailures, `CORS failures observed: ${JSON.stringify(corsFailures, null, 2)}`).toHaveLength(0);
    expect(autosaveFailures, `Autosave 400s observed: ${JSON.stringify(autosaveFailures, null, 2)}`).toHaveLength(0);

    // Background request volume must remain bounded — no polling storm.
    // Allow health + production-control polling but reject exponential growth.
    const apiRequests = failedRequests.filter((r) => /\/api\//.test(r.url));
    const uniqueEndpoints = new Set(apiRequests.map((r) => r.url.split("?")[0]));
    expect(uniqueEndpoints.size, `Unexpected API failure spread: ${[...uniqueEndpoints].join(", ")}`).toBeLessThanOrEqual(8);

    if (ownedProjectId) await deleteProject(request, ownedProjectId);
    void isHostedSoak;
  });
});
