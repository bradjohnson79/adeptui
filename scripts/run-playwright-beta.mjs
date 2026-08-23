/**
 * Run Playwright against the live Adept UI Beta (certification target).
 * Does not start the isolated e2e-start harness (5173/8742/STUDIO_E2E).
 *
 * Usage: npm run test:e2e:beta -- [playwright args...]
 * Example: npm run test:e2e:beta -- tests/e2e/setup/ai-guided-setup-lifecycle.spec.ts --project=chromium
 */
import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const env = {
  ...process.env,
  ADEPT_BETA_TARGET: "1",
  PLAYWRIGHT_BASE_URL: "http://127.0.0.1:5173",
  STUDIO_API_BASE: "http://127.0.0.1:8758",
  STUDIO_API_PORT: "8758",
};

// Live Beta UI is Vite :5173 (or hosted Vercel). Retired :8760 is not a creator UI.
delete env.CI;

console.log(
  `[test:e2e:beta] target UI=${env.PLAYWRIGHT_BASE_URL} API=${env.STUDIO_API_BASE} ADEPT_BETA_TARGET=${env.ADEPT_BETA_TARGET}`,
);

const args = process.argv.slice(2);
// On Windows, spawning *.cmd with shell:false raises EINVAL (Node ≥20).
const child = spawn(
  process.platform === "win32" ? "npx.cmd" : "npx",
  ["playwright", "test", ...args],
  {
    env,
    stdio: "inherit",
    shell: process.platform === "win32",
    cwd: root,
  },
);

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
