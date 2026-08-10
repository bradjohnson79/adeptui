/**
 * Start API (no --reload) + Vite for Playwright.
 * Waits for /api/health and /api/setup/status before exiting success as a long-running supervisor.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const apiDir = path.join(root, "studio-api");
const isWin = process.platform === "win32";
const venvPython = path.join(
  apiDir,
  ".venv",
  isWin ? "Scripts" : "bin",
  isWin ? "python.exe" : "python",
);

const host = process.env.STUDIO_API_HOST || "127.0.0.1";
const apiPort = process.env.STUDIO_API_PORT || "8742";
const webPort = process.env.PLAYWRIGHT_WEB_PORT || "5173";
const fixturePort = process.env.E2E_FIXTURE_PORT || "8765";

const dataDir =
  process.env.STUDIO_DATA_DIR ||
  fs.mkdtempSync(path.join(os.tmpdir(), "adept-e2e-data-"));

fs.mkdirSync(path.join(root, "artifacts", "functional-audit"), { recursive: true });
const logDir = path.join(root, "artifacts", "functional-audit", "logs");
fs.mkdirSync(logDir, { recursive: true });

// Everything below is Playwright-only. These fixture providers, mock Co-Director provider
// and fixture-mode flags exist so the suite never depends on a real Comfy/Ollama/fal
// install — they are handed to the child processes spawned here and nowhere else.
// Production and `npm run dev` must never inherit them: the API treats every one of these
// as OFF by default and refuses fixture/mock success paths without them.
const env = {
  ...process.env,
  STUDIO_E2E: "1",
  STUDIO_DATA_DIR: dataDir,
  STUDIO_API_HOST: host,
  STUDIO_API_PORT: String(apiPort),
  ADEPT_PACK_PROVIDER: process.env.ADEPT_PACK_PROVIDER || "fixture_http",
  ADEPT_PACK_FIXTURE_BASE_URL:
    process.env.ADEPT_PACK_FIXTURE_BASE_URL || `http://${host}:${fixturePort}`,
  ADEPT_PACK_GITHUB_OWNER: process.env.ADEPT_PACK_GITHUB_OWNER || "",
  ADEPT_PACK_GITHUB_REPOSITORY: process.env.ADEPT_PACK_GITHUB_REPOSITORY || "",
  // Co-Director talks to the deterministic mock provider in E2E so chat/health/model
  // assertions never depend on a real local Ollama install. Override with `ollama` to
  // exercise the real provider path locally.
  ADEPT_CODIRECTOR_PROVIDER: process.env.ADEPT_CODIRECTOR_PROVIDER || "mock",
  STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2:
    process.env.STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2 || "1",
  // M2.6.1 closed-loop: enable Vision + Timeline References in E2E by default.
  // Override with "0"/"false" for flags-off regression runs.
  STUDIO_FEATURE_VISION_VALIDATION_V1:
    process.env.STUDIO_FEATURE_VISION_VALIDATION_V1 || "1",
  STUDIO_FEATURE_TIMELINE_REFERENCES_V1:
    process.env.STUDIO_FEATURE_TIMELINE_REFERENCES_V1 || "1",
  // M2.7.1: Production Executive closed-loop in E2E (API flag still defaults OFF outside e2e-start).
  // Override with "0"/"false" for flags-off regression runs.
  STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1:
    process.env.STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1 || "1",
  // The Production Executive ships a background poller *and* a synchronous
  // `POST /api/codirector/jobs/worker/drain` helper the specs use to step the queue. With the
  // poller at its 0.25 s default the two race: a drain can return zero steps because the
  // poller already holds the next job in flight, and a spec that reads the job immediately
  // afterwards sees an unfinished state. Parking the poller makes the drain the only executor
  // under Playwright, so job progress is caused by the test rather than by timing. Real
  // background polling still runs everywhere else — this value is Playwright-only.
  STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL:
    process.env.STUDIO_PRODUCTION_EXECUTIVE_POLL_INTERVAL || "3600",
  // M2.8 capability intelligence: fixture mode on; feature flags default off unless suite sets them.
  ADEPT_M28_FIXTURE_MODE: process.env.ADEPT_M28_FIXTURE_MODE || "1",
  STUDIO_FEATURE_MODEL_RADAR_V1: process.env.STUDIO_FEATURE_MODEL_RADAR_V1 || "1",
  STUDIO_FEATURE_SANDBOX_RUNTIME_V1: process.env.STUDIO_FEATURE_SANDBOX_RUNTIME_V1 || "1",
  STUDIO_FEATURE_VIRTUAL_STAGE_V1: process.env.STUDIO_FEATURE_VIRTUAL_STAGE_V1 || "1",
  STUDIO_FEATURE_SHOT_PROFILES_V1: process.env.STUDIO_FEATURE_SHOT_PROFILES_V1 || "1",
  STUDIO_FEATURE_PRODUCTION_RECIPE_V1: process.env.STUDIO_FEATURE_PRODUCTION_RECIPE_V1 || "1",
  STUDIO_FEATURE_LOCATION_SPIN_V1: process.env.STUDIO_FEATURE_LOCATION_SPIN_V1 || "1",
  // M2.9 production suite: fixture mode on; feature flags default off unless suite sets them.
  // Does not enable M2.10 discovery.
  ADEPT_M29_FIXTURE_MODE: process.env.ADEPT_M29_FIXTURE_MODE || "1",
  STUDIO_FEATURE_IMAGE_PRODUCTION_V1: process.env.STUDIO_FEATURE_IMAGE_PRODUCTION_V1 || "0",
  STUDIO_FEATURE_FRAME_PRODUCTION_V1: process.env.STUDIO_FEATURE_FRAME_PRODUCTION_V1 || "0",
  STUDIO_FEATURE_VIDEO_PRODUCTION_V1: process.env.STUDIO_FEATURE_VIDEO_PRODUCTION_V1 || "0",
  // M3.0 Completion Phase 3: the sound path (M2.9 audio -> Director timeline, blocker B4)
  // needs these two on to be exercised at all, so they are ON for E2E. They stay OFF in
  // `feature_flags.py` and can be forced off here for a flags-off regression run.
  STUDIO_FEATURE_DIRECTOR_TIMELINE_V1: process.env.STUDIO_FEATURE_DIRECTOR_TIMELINE_V1 || "1",
  STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1: process.env.STUDIO_FEATURE_LIPSYNC_PRODUCTION_V1 || "0",
  STUDIO_FEATURE_AUDIO_PRODUCTION_V1: process.env.STUDIO_FEATURE_AUDIO_PRODUCTION_V1 || "1",
  STUDIO_FEATURE_EDITING_PRODUCTION_V1: process.env.STUDIO_FEATURE_EDITING_PRODUCTION_V1 || "0",
  STUDIO_FEATURE_RENDER_PRODUCTION_V1: process.env.STUDIO_FEATURE_RENDER_PRODUCTION_V1 || "0",
  STUDIO_FEATURE_CODIRECTOR_PRODUCTION_CONTROL_V1:
    process.env.STUDIO_FEATURE_CODIRECTOR_PRODUCTION_CONTROL_V1 || "0",
  // M2.14 unified experience replaces the whole Co-Director conversation surface, so it
  // cannot be switched on process-wide without rerouting every chat spec to a different
  // screen. It is left OFF here and the M2.14 specs turn it on for themselves through
  // POST /api/e2e/feature-flags (E2E-only), which gives real ON *and* OFF coverage.
  // Set it to "1" to run the whole suite against the unified surface.
  STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1:
    process.env.STUDIO_FEATURE_CODIRECTOR_UNIFIED_EXPERIENCE_V1 || "0",
  // M3.3 Character Identity — Character Profile / Voice System
  STUDIO_FEATURE_CHARACTER_IDENTITY_V1:
    process.env.STUDIO_FEATURE_CHARACTER_IDENTITY_V1 || "1",
  // M3.0 Completion Phase 6: startup would otherwise promote a real fal key out of .env
  // and probe fal.ai on every E2E boot. The suite never renders through fal, so keep the
  // stack offline.
  STUDIO_FAL_ENV_BRIDGE: process.env.STUDIO_FAL_ENV_BRIDGE || "0",
  // ADEPT_MOCK_IMAGEGEN is deliberately NOT set: ImageGen polls real Comfy jobs and the
  // adapter refuses to fabricate a completion even when that variable is present.
};

fs.writeFileSync(
  path.join(root, "artifacts", "functional-audit", "e2e-env.json"),
  JSON.stringify(
    {
      dataDir,
      api: `http://${host}:${apiPort}`,
      web: `http://127.0.0.1:${webPort}`,
      fixture: env.ADEPT_PACK_FIXTURE_BASE_URL,
    },
    null,
    2,
  ),
);

function appendLog(name, chunk) {
  fs.appendFileSync(path.join(logDir, name), chunk);
}

function spawnLogged(command, args, name, cwd, extraEnv = {}) {
  const child = spawn(command, args, {
    cwd,
    env: { ...env, ...extraEnv },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
    // Windows cannot spawn .cmd shims with shell:false (Node EINVAL).
    shell: isWin,
  });
  child.stdout.on("data", (d) => {
    process.stdout.write(`[${name}] ${d}`);
    appendLog(`${name}.log`, d);
  });
  child.stderr.on("data", (d) => {
    process.stderr.write(`[${name}] ${d}`);
    appendLog(`${name}.log`, d);
  });
  child.on("exit", (code, signal) => {
    appendLog(
      `${name}.log`,
      `\n[exit] code=${code} signal=${signal}\n`,
    );
    if (name === "api" && code && code !== 0) {
      console.error(`[e2e-start] API exited unexpectedly code=${code}`);
    }
  });
  return child;
}

function waitHttp(url, { timeoutMs = 120000, ok = (s) => s === 200 } = {}) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (ok(res.statusCode || 0)) return resolve(res.statusCode);
        if (Date.now() - start > timeoutMs) {
          return reject(new Error(`Timeout waiting for ${url} (last ${res.statusCode})`));
        }
        setTimeout(tick, 500);
      });
      req.on("error", () => {
        if (Date.now() - start > timeoutMs) {
          return reject(new Error(`Timeout waiting for ${url}`));
        }
        setTimeout(tick, 500);
      });
    };
    tick();
  });
}

if (!fs.existsSync(venvPython)) {
  console.error(`[e2e-start] Missing venv at ${venvPython}. Run npm run install:all`);
  process.exit(1);
}

const reuseExternalApi =
  process.env.ADEPT_M32G_REAL_LOCAL === "1" || process.env.ADEPT_E2E_REUSE_API === "1";

async function alreadyReady() {
  try {
    await waitHttp(`http://${host}:${fixturePort}/health`, { timeoutMs: 1500 });
    await waitHttp(`http://${host}:${apiPort}/api/health`, { timeoutMs: 1500 });
    if (!reuseExternalApi) {
      await waitHttp(`http://${host}:${apiPort}/api/e2e/status`, { timeoutMs: 1500 });
    }
    await waitHttp(`http://127.0.0.1:${webPort}/`, { timeoutMs: 1500 });
    return true;
  } catch {
    return false;
  }
}

if (await alreadyReady()) {
  console.log("[e2e-start] reusing already-running E2E stack");
  fs.writeFileSync(
    path.join(root, "artifacts", "functional-audit", "ready.json"),
    JSON.stringify({ readyAt: new Date().toISOString(), dataDir, reused: true }, null, 2),
  );
  await new Promise(() => {});
}

const children = [];

const fixture = spawnLogged(
  process.execPath,
  [path.join(root, "scripts", "e2e-fixture-server.mjs")],
  "fixture",
  root,
);
children.push(fixture);

let api = null;
if (reuseExternalApi) {
  try {
    await waitHttp(`http://${host}:${apiPort}/api/health`, { timeoutMs: 5000 });
    console.log(`[e2e-start] REAL_LOCAL/reuse: using existing API on ${host}:${apiPort}`);
  } catch (err) {
    console.error(
      `[e2e-start] ADEPT_M32G_REAL_LOCAL/ADEPT_E2E_REUSE_API set but API not healthy at http://${host}:${apiPort}/api/health`,
    );
    process.exit(1);
  }
} else {
  api = spawnLogged(
    venvPython,
    ["-m", "uvicorn", "app.main:app", "--host", host, "--port", String(apiPort)],
    "api",
    apiDir,
  );
  children.push(api);
}

const viteJs = path.join(root, "studio-web", "node_modules", "vite", "bin", "vite.js");
if (!fs.existsSync(viteJs)) {
  console.error(`[e2e-start] Missing vite at ${viteJs}. Run npm --prefix studio-web install`);
  process.exit(1);
}
const web = spawnLogged(
  process.execPath,
  [viteJs, "--host", "127.0.0.1", "--port", String(webPort), "--strictPort"],
  "web",
  path.join(root, "studio-web"),
);
children.push(web);

function shutdown() {
  for (const child of children) {
    try {
      child.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    shutdown();
    process.exit(0);
  });
}

try {
  await waitHttp(`http://${host}:${fixturePort}/health`);
  await waitHttp(`http://${host}:${apiPort}/api/health`);
  if (!reuseExternalApi) {
    await waitHttp(`http://${host}:${apiPort}/api/setup/status`);
  }
  await waitHttp(`http://127.0.0.1:${webPort}/`);
  console.log("[e2e-start] ready");
  fs.writeFileSync(
    path.join(root, "artifacts", "functional-audit", "ready.json"),
    JSON.stringify({
      readyAt: new Date().toISOString(),
      dataDir,
      reusedApi: reuseExternalApi,
    }, null, 2),
  );
  // Keep alive for Playwright webServer reuse
  await new Promise(() => {});
} catch (err) {
  console.error("[e2e-start] failed:", err.message);
  shutdown();
  process.exit(1);
}
