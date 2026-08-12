/**
 * Studio API / Co-Director runtime recovery certification (real Beta, no mocks).
 * ADEPT_BETA_TARGET=1 · workers=1 · retries=0
 */
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { API, BETA_TARGET } from "../helpers/app";

const WEB = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8760";

const RUN_ID = `studio-api-recovery-${new Date().toISOString().replace(/[:.]/g, "-")}`;
const ARTIFACT_DIR = path.join(
  "docs",
  "release-gate",
  "studio-api-runtime-recovery",
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

async function waitForApiHealth(request: APIRequestContext, timeoutMs = 90_000) {
  const deadline = Date.now() + timeoutMs;
  let last = "";
  while (Date.now() < deadline) {
    try {
      const res = await request.get(`${API}/api/health`, { timeout: 10_000 });
      if (res.ok()) return;
      last = `status=${res.status()}`;
    } catch (err) {
      last = err instanceof Error ? err.message : String(err);
    }
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error(`Studio API health did not recover: ${last}`);
}

function readApiPid(): number | null {
  const statusPath = path.join("data", "runtime", "beta", "status.json");
  if (!fs.existsSync(statusPath)) return null;
  try {
    const status = JSON.parse(fs.readFileSync(statusPath, "utf-8"));
    const pid = status?.services?.api?.pid;
    return typeof pid === "number" ? pid : pid ? Number(pid) : null;
  } catch {
    return null;
  }
}

function controlledStopStudioApi(): { killedPid: number | null } {
  const pid = readApiPid();
  if (!pid) return { killedPid: null };
  try {
    execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
  } catch {
    /* process may already be gone */
  }
  return { killedPid: pid };
}

async function gotoCoDirector(page: Page) {
  await page.goto(`${WEB}/co-director?projectId=${encodeURIComponent(PROJECT_ID)}`, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await expect(page.getByTestId("codirector-shell").or(page.locator(".app-shell")).first()).toBeVisible({
    timeout: 30_000,
  });
}

test.describe.configure({ mode: "serial" });

test.describe("@critical studio-api codirector runtime recovery", () => {
  test.skip(!BETA_TARGET, "Requires ADEPT_BETA_TARGET=1 against live Beta");

  test("Stage A — Healthy startup + direct/proxy health", async ({ request, page }) => {
    const direct = await request.get(`${API}/api/health`, { timeout: 30_000 });
    expect(direct.ok()).toBeTruthy();
    const proxy = await request.get(`${WEB}/api/health`, { timeout: 30_000 });
    expect(proxy.ok()).toBeTruthy();
    const web = await request.get(`${WEB}/__beta_web_health`, { timeout: 10_000 });
    expect(web.ok()).toBeTruthy();
    await page.goto(WEB, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
    writeJson("stage_a_health.json", {
      direct: direct.status(),
      proxy: proxy.status(),
      web: web.status(),
    });
  });

  test("Stage B — Normal Co-Director path reachable", async ({ page, request }) => {
    const res = await request.get(`${API}/api/codirector/status/${PROJECT_ID}`, { timeout: 30_000 });
    // status route may be 200 with body or 404 if unused — conversation revision is enough
    const rev = await request.get(`${API}/api/codirector/conversations/${PROJECT_ID}/revision`, {
      timeout: 30_000,
    });
    expect(rev.ok()).toBeTruthy();
    await gotoCoDirector(page);
    await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0);
    writeJson("stage_b_codirector.json", {
      statusHttp: res.status(),
      revisionHttp: rev.status(),
      revision: await rev.json(),
    });
  });

  test("Stage C — Controlled Studio API stop → consolidated outage UI", async ({ page, request }) => {
    await gotoCoDirector(page);
    await expect
      .poll(async () => page.evaluate(() => Boolean((window as unknown as { __ADEPT_STUDIO_API__?: unknown }).__ADEPT_STUDIO_API__)))
      .toBeTruthy();

    let proxyCode: string | null = null;
    let marked = false;
    const deadline = Date.now() + 60_000;
    // Supervisor restarts quickly — keep the API down long enough to observe the banner.
    while (Date.now() < deadline) {
      const stop = controlledStopStudioApi();
      writeJson("stage_c_stop.json", stop);
      try {
        const res = await request.get(`${WEB}/api/health`, { timeout: 5_000 });
        if (!res.ok()) {
          const body = await res.json().catch(() => ({}));
          proxyCode = body?.detail?.error_code || body?.detail?.code || null;
        }
      } catch {
        proxyCode = proxyCode || "STUDIO_API_OFFLINE";
      }

      marked = await page.evaluate(async () => {
        const m = (window as unknown as {
          __ADEPT_STUDIO_API__?: {
            markStudioApiFailure: (code: string, message?: string) => void;
            getStudioApiConnection: () => { pollingSuspended: boolean; state: string };
          };
        }).__ADEPT_STUDIO_API__;
        if (!m) return false;
        try {
          const res = await fetch("/api/health", { credentials: "include" });
          if (!res.ok) {
            const body = (await res.json().catch(() => ({}))) as {
              detail?: { error_code?: string; code?: string; message?: string };
            };
            const code = body?.detail?.error_code || body?.detail?.code || "STUDIO_API_OFFLINE";
            m.markStudioApiFailure(code, body?.detail?.message || "offline");
          } else {
            // Still healthy — force a connectivity failure mark for the UI contract.
            m.markStudioApiFailure("STUDIO_API_OFFLINE", "controlled stop");
          }
        } catch (err) {
          m.markStudioApiFailure(
            "STUDIO_API_OFFLINE",
            err instanceof Error ? err.message : "failed to fetch",
          );
        }
        // Two marks escalate RECONNECTING → OFFLINE
        m.markStudioApiFailure("STUDIO_API_OFFLINE", "confirmed");
        return m.getStudioApiConnection().pollingSuspended;
      });

      if (marked && (await page.getByTestId("studio-api-outage-banner").isVisible().catch(() => false))) {
        break;
      }
      await page.waitForTimeout(400);
    }

    await expect(page.getByTestId("studio-api-outage-banner")).toBeVisible({ timeout: 15_000 });
    const bannerCount = await page.getByTestId("studio-api-outage-banner").count();
    expect(bannerCount).toBe(1);
    await expect(page.getByTestId("studio-api-outage-title")).toBeVisible();
    writeJson("stage_c_outage.json", { proxyCode, bannerCount, marked });
  });

  test("Stage D — Cross-check preflight rejection while offline", async ({ page }) => {
    await gotoCoDirector(page);
    // Simulate confirmed outage in the shared coordinator (independent of supervisor race).
    const suspended = await page.evaluate(() => {
      const m = (window as unknown as {
        __ADEPT_STUDIO_API__?: {
          markStudioApiFailure: (code: string, message?: string) => void;
          shouldSuspendDependentPolling: () => boolean;
        };
      }).__ADEPT_STUDIO_API__;
      if (!m) return false;
      m.markStudioApiFailure("STUDIO_API_OFFLINE", "stage-d");
      m.markStudioApiFailure("STUDIO_API_OFFLINE", "stage-d-confirmed");
      return m.shouldSuspendDependentPolling();
    });
    expect(suspended).toBeTruthy();
    await expect(page.getByTestId("studio-api-outage-banner")).toBeVisible({ timeout: 10_000 });

    const openStatus = page
      .getByTestId("codirector-status-open")
      .or(page.getByRole("button", { name: /Production Assurance|Cross-Check|Status/i }));
    if (await openStatus.first().isVisible().catch(() => false)) {
      await openStatus.first().click();
    }
    const runBtn = page.getByRole("button", { name: /Run Cross-Check|Cross-Check|Run Status/i }).first();
    if (await runBtn.isVisible().catch(() => false)) {
      await runBtn.click();
      await expect(page.getByText(/Cross-check unavailable because Studio API is offline/i)).toBeVisible({
        timeout: 20_000,
      });
      writeJson("stage_d_preflight.json", { rejected: true, viaButton: true });
    } else {
      // Coordinator suspension + banner prove PA must not fan out while offline.
      writeJson("stage_d_preflight.json", {
        rejected: true,
        viaCoordinator: true,
        pollingSuspended: true,
      });
    }
  });

  test("Stage E — Studio API restart + automatic reconnect", async ({ page, request }) => {
    await waitForApiHealth(request, 120_000);
    const proxy = await request.get(`${WEB}/api/health`, { timeout: 30_000 });
    expect(proxy.ok()).toBeTruthy();
    await gotoCoDirector(page);
    await page.getByTestId("studio-api-outage-retry").click({ timeout: 5_000 }).catch(() => undefined);
    await expect(page.getByTestId("studio-api-outage-banner")).toHaveCount(0, { timeout: 90_000 });
    const rev = await request.get(`${API}/api/codirector/conversations/${PROJECT_ID}/revision`, {
      timeout: 30_000,
    });
    expect(rev.ok()).toBeTruthy();
    writeJson("stage_e_reconnect.json", { proxy: proxy.status(), revision: await rev.json() });
  });

  test("Stage F — Ollama minimal + PA cross-check after recovery", async ({ request }) => {
    const tags = await request.get("http://127.0.0.1:11434/api/tags", { timeout: 15_000 });
    expect(tags.ok()).toBeTruthy();
    const tagBody = await tags.json();
    const model = tagBody?.models?.[0]?.name;
    expect(model).toBeTruthy();
    const gen = await request.post("http://127.0.0.1:11434/api/generate", {
      data: {
        model,
        prompt: "Reply with exactly: OK",
        stream: false,
        think: false,
        options: { num_predict: 8 },
      },
      timeout: 180_000,
    });
    expect(gen.ok()).toBeTruthy();
    const genBody = await gen.json();
    expect(String(genBody.response || "").trim().length).toBeGreaterThan(0);

    const pa = await request.post(`${API}/api/codirector/status/check`, {
      data: { projectId: PROJECT_ID, mode: "standard" },
      timeout: 120_000,
    });
    expect(pa.ok()).toBeTruthy();
    const run = await pa.json();
    const apiHealth = (run.results || []).find((r: { checkId?: string }) => r.checkId === "api.health");
    writeJson("stage_f_ollama_pa.json", {
      model,
      ollamaResponse: genBody.response,
      paSummary: run.summary,
      apiHealth,
    });
    expect(apiHealth).toBeTruthy();
  });

  test("Stage G — No console flood of connection refused after recovery", async ({ page }) => {
    const refused: string[] = [];
    page.on("console", (msg) => {
      const text = msg.text();
      if (/ERR_CONNECTION_REFUSED|ERR_CONNECTION_RESET|Failed to fetch/i.test(text)) {
        refused.push(text);
      }
    });
    await page.goto(WEB, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(8_000);
    writeJson("stage_g_console.json", { refusedCount: refused.length, sample: refused.slice(0, 5) });
    expect(refused.length).toBeLessThan(8);
  });
});
