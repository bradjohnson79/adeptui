/**
 * Stable API launcher for Local AI Video Studio.
 * Resolves the studio-api venv relative to the repo root (no brittle cd / absolute paths).
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
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
const port = process.env.STUDIO_API_PORT || "8742";

if (!fs.existsSync(venvPython)) {
  console.error(`[studio-api] Missing venv python at:\n  ${venvPython}`);
  console.error("Run: npm run install:all");
  process.exit(1);
}

/**
 * Local product defaults for operator-facing readiness.
 * Only applied when the env var is unset so CI/E2E and explicit overrides win.
 * Set STUDIO_FEATURE_*=0 to force a flag off.
 */
const localProductFlags = {
  STUDIO_FEATURE_CODIRECTOR_INTELLIGENCE_V2: "1",
  STUDIO_FEATURE_VISION_VALIDATION_V1: "1",
  STUDIO_FEATURE_PRODUCTION_EXECUTIVE_V1: "1",
  STUDIO_FEATURE_TIMELINE_REFERENCES_V1: "1",
};
const childEnv = { ...process.env };
for (const [key, value] of Object.entries(localProductFlags)) {
  if (childEnv[key] == null || String(childEnv[key]).trim() === "") {
    childEnv[key] = value;
  }
}

const args = [
  "-m",
  "uvicorn",
  "app.main:app",
  "--host",
  host,
  "--port",
  String(port),
  "--reload",
];

console.log(`[studio-api] ${venvPython} ${args.join(" ")}`);
console.log(`[studio-api] cwd=${apiDir}  http://${host}:${port}`);

const child = spawn(venvPython, args, {
  cwd: apiDir,
  stdio: "inherit",
  env: childEnv,
  windowsHide: true,
});

function shutdown(signal) {
  if (child.killed) return;
  try {
    child.kill(signal);
  } catch {
    // ignore
  }
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => shutdown(signal));
}

child.on("error", (err) => {
  console.error("[studio-api] failed to start:", err.message);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) process.exit(1);
  process.exit(code ?? 1);
});
