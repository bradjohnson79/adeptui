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
  env: process.env,
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
