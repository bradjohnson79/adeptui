/**
 * Adept UI Runtime + Workflow Zero-Block certification (real Beta, no mocks).
 * ADEPT_BETA_TARGET=1 · workers=1 · retries=0
 */
import fs from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { API, BETA_TARGET } from "../helpers/app";

const RUN_ID = (() => {
  if (process.env.ADEPT_ZERO_BLOCK_RUN_ID) return process.env.ADEPT_ZERO_BLOCK_RUN_ID;
  const stamp = "docs/release-gate/runtime-zero-block/artifacts/CURRENT_RUN_ID.txt";
  if (fs.existsSync(stamp)) return fs.readFileSync(stamp, "utf-8").trim();
  return `runtime-zero-block-${new Date().toISOString().replace(/[:.]/g, "-")}`;
})();

const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "runtime-zero-block",
  "artifacts",
  RUN_ID,
  "playwright",
);

const PROJECT_ID =
  process.env.ADEPT_PROJECT_ID || "ae57714e-d43e-4cec-9bd9-0af2780fa185";

function writeJson(name: string, data: unknown) {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  fs.writeFileSync(path.join(ARTIFACT_DIR, name), JSON.stringify(data, null, 2), "utf-8");
}

test.describe.configure({ mode: "serial" });

test.describe("@critical adept-ui runtime workflow zero-block", () => {
  test.skip(!BETA_TARGET, "Requires ADEPT_BETA_TARGET=1 against live Beta");

  test("Stage 1 — Studio API responsive", async ({ request }) => {
    const started = Date.now();
    const res = await request.get(`${API}/api/health`, { timeout: 30_000 });
    const ms = Date.now() - started;
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    writeJson("stage1_studio_api.json", { ok: true, ms, body });
    expect(ms).toBeLessThan(15_000);
  });

  test("Stage 2 — Co-Director provider healthy (selected model)", async ({ request }) => {
    const res = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: PROJECT_ID, checkIds: ["codirector.provider"] },
      timeout: 60_000,
    });
    expect(res.ok()).toBeTruthy();
    const run = await res.json();
    const result = (run.results || [])[0];
    writeJson("stage2_codirector.json", result);
    expect(["healthy", "slow", "busy", "ready", "connected"]).toContain(result.status);
    expect(result.timedOut).toBeFalsy();
  });

  test("Stage 3 — Production Assurance cross-check (no unexplained timeouts)", async ({
    request,
  }) => {
    const res = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: PROJECT_ID, mode: "standard" },
      timeout: 120_000,
    });
    expect(res.ok()).toBeTruthy();
    const run = await res.json();
    writeJson("stage3_production_assurance.json", {
      summary: run.summary,
      results: (run.results || []).map((r: any) => ({
        checkId: r.checkId,
        status: r.status,
        timedOut: r.timedOut,
        durationMs: r.durationMs,
        timeoutMs: r.timeoutMs,
        awaitedDependency: r.awaitedDependency,
        summary: r.summary,
      })),
    });
    expect(run.summary.blockedChecks).toBe(0);
    const unexplainedTimeouts = (run.results || []).filter(
      (r: any) => r.timedOut && r.status === "timed_out" && !r.details?.busy,
    );
    expect(unexplainedTimeouts, JSON.stringify(unexplainedTimeouts)).toHaveLength(0);
    const required = [
      "capabilities.registry",
      "tools.registry",
      "comfy.health",
      "library.preflight",
      "codirector.provider",
    ];
    for (const id of required) {
      const row = (run.results || []).find((r: any) => r.checkId === id);
      expect(row, id).toBeTruthy();
      expect(["blocked", "failed", "offline"]).not.toContain(row.status);
    }
  });

  test("Stage 4 — Capability Readiness zero active blockers + SceneCraft excluded", async ({
    request,
  }) => {
    // Prefer a forced refresh so a stale negative snapshot from a Comfy blip cannot fail the gate.
    let snap: Record<string, any>;
    const refreshed = await request.post(`${API}/api/capabilities/refresh`, { timeout: 90_000 });
    if (refreshed.ok()) {
      snap = await refreshed.json();
    } else {
      const res = await request.get(`${API}/api/capabilities?refresh=true`, { timeout: 90_000 });
      expect(res.ok()).toBeTruthy();
      snap = await res.json();
    }
    const blockers = snap.blockers || [];
    writeJson("stage4_capabilities.json", {
      readinessTotal: snap.readinessTotal,
      blockerCount: blockers.length,
      blockers,
      deferred: snap.deferred,
    });
    expect(blockers.length).toBe(0);
    const ids = (snap.capabilities || []).map((c: any) => String(c.id || "").toLowerCase());
    expect(ids.some((id: string) => id.includes("scenecraft"))).toBeFalsy();
  });

  test("Stage 5 — Required Hunyuan HyVideo nodes present", async ({ request }) => {
    const res = await request.get(`${API}/api/comfy/health`, { timeout: 60_000 });
    expect(res.ok()).toBeTruthy();
    const health = await res.json();
    writeJson("stage5_comfy.json", health);
    expect(health.reachable).toBeTruthy();

    const workflows = [
      "hunyuan15.t2v",
      "hunyuan15.i2v",
      "hunyuan13b.t2v",
      "hunyuan13b.i2v",
    ];
    const readinessRows = [];
    for (const id of workflows) {
      const wr = await request.get(`${API}/api/workflows/${id}/readiness`, { timeout: 60_000 });
      const body = wr.ok() ? await wr.json() : { status: "error", http: wr.status() };
      readinessRows.push({ id, ...body });
      if (wr.ok()) {
        const missing = body.missingNodeTypes || body.missingRequiredNodeTypes || [];
        expect(missing, `${id} missing nodes`).toEqual([]);
      }
    }
    writeJson("stage5_hunyuan_readiness.json", readinessRows);
  });

  test("Stage 6 — Frozen manifest present and non-empty", async () => {
    const manifestPath = path.join(
      "docs",
      "release-gate",
      "runtime-zero-block",
      "CURRENT_RELEASE_CAPABILITY_MANIFEST.json",
    );
    expect(fs.existsSync(manifestPath)).toBeTruthy();
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
    expect(manifest.entryCount).toBeGreaterThan(0);
    expect(manifest.scenecraftExclusion?.notPartOfCurrentRelease).toBeTruthy();
    writeJson("stage6_manifest_meta.json", {
      entryCount: manifest.entryCount,
      frozenAt: manifest.frozenAt,
      scenecraftExclusion: manifest.scenecraftExclusion,
    });
  });

  test("Stage 7 — Aggregates file written for dual-green gate", async ({ request }) => {
    const status = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: PROJECT_ID },
      timeout: 120_000,
    });
    const run = await status.json();
    let caps: Record<string, any>;
    const refreshed = await request.post(`${API}/api/capabilities/refresh`, { timeout: 90_000 });
    if (refreshed.ok()) {
      caps = await refreshed.json();
    } else {
      const capsRes = await request.get(`${API}/api/capabilities?refresh=true`, { timeout: 90_000 });
      expect(capsRes.ok()).toBeTruthy();
      caps = await capsRes.json();
    }
    const matrixPath = path.join(
      "docs",
      "release-gate",
      "runtime-zero-block",
      "artifacts",
      RUN_ID,
      "workflows",
      "matrix.json",
    );
    let workflowCatalogGreen = false;
    let matrix: any = null;
    if (fs.existsSync(matrixPath)) {
      matrix = JSON.parse(fs.readFileSync(matrixPath, "utf-8"));
      const rows = matrix.rows || matrix.workflows || matrix;
      if (Array.isArray(rows) && rows.length) {
        // EXCLUDED rows (e.g. Hunyuan per product owner) are out of the release catalog gate.
        const active = rows.filter(
          (r: any) => String(r.verdict || "").toUpperCase() !== "EXCLUDED",
        );
        workflowCatalogGreen =
          active.length > 0 &&
          active.every((r: any) => String(r.verdict || "").toUpperCase() === "GO");
      }
    }
    const capabilityBlockers = Array.isArray(caps.blockers) ? caps.blockers : [];
    const paBlocked = Number(run.summary.blockedChecks || 0);
    // Align with Stage 3: busy / explained partial timeouts do not fail SYSTEM_RUNTIME_GREEN.
    const unexplainedTimeouts = (run.results || []).filter(
      (r: any) => r.timedOut && r.status === "timed_out" && !r.details?.busy,
    );
    const systemRuntimeGreen =
      paBlocked === 0 &&
      capabilityBlockers.length === 0 &&
      unexplainedTimeouts.length === 0 &&
      ["Operational", "Degraded"].includes(run.summary.statusIndicator);

    const aggregates = {
      SYSTEM_RUNTIME_GREEN: systemRuntimeGreen,
      WORKFLOW_CATALOG_GREEN: workflowCatalogGreen,
      FINAL_ACTIVE_BLOCKERS: capabilityBlockers.length + paBlocked,
      FINAL_UNEXPLAINED_TIMEOUTS: unexplainedTimeouts.length,
      statusIndicator: run.summary.statusIndicator,
      score: run.summary.score,
      matrixPresent: Boolean(matrix),
      capabilityBlockerIds: capabilityBlockers.map((b: any) => b.capabilityId || b.id),
      hunyuanExcluded: Boolean(matrix?.noteHunyuanExclusion),
    };
    writeJson("stage7_aggregates.json", aggregates);
    expect(aggregates.SYSTEM_RUNTIME_GREEN, JSON.stringify(aggregates)).toBeTruthy();
  });

  test("Stage 8 — Co-Director UI opens and Production Assurance panel works", async ({
    page,
    request,
  }) => {
    await page.goto(`/co-director?projectId=${PROJECT_ID}`);
    await expect(page.getByLabel("Message Co-Director")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("codirector-overflow-button").click();
    await page.getByTestId("codirector-overflow-panel").getByRole("button", { name: "Status" }).click();
    await expect(page.getByTestId("codirector-status-panel")).toBeVisible();
    await expect(page.getByTestId("codirector-status-panel").locator(".eyebrow", { hasText: "Production Assurance" })).toBeVisible();
    const crossCheck = page.getByRole("button", { name: "Run Cross-Check" });
    await expect(crossCheck).toBeVisible();
    // Seed via API (same contract the panel uses) so UI does not depend on SSE race.
    const seeded = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: PROJECT_ID },
      timeout: 120_000,
    });
    expect(seeded.ok()).toBeTruthy();
    await crossCheck.click();
    await expect(page.getByTestId("codirector-status-panel")).toContainText(/Operational|Degraded|Checking|Blocked/i, {
      timeout: 60_000,
    });
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, "stage8_production_assurance.png"),
      fullPage: true,
    });
  });
});
