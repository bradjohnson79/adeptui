import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { auditPackagedTree } from "../packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const isolatedRoot = path.join(os.tmpdir(), "adept-ui-isolated-mac");
const userData = path.join(os.tmpdir(), "adept-ui-profile-mac");
const resultPath = path.join(root, "electron", "build", "macos-smoke-result.json");

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (process.platform !== "darwin" || process.arch !== "arm64") {
  fail(`MACOS NATIVE RUNNER = FAIL\nSmoke must run on Apple Silicon. This process is ${process.platform} ${process.arch}.`);
}

function get(url, timeoutMs = 8000) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8").slice(0, 1500) }));
    });
    req.on("error", (err) => resolve({ status: 0, body: String(err.message) }));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve({ status: 0, body: "timeout" });
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function findApp() {
  const candidates = [
    path.join(root, "electron", "dist", "mac-arm64", "Adept UI.app"),
    path.join(root, "electron", "dist", "mac", "Adept UI.app"),
  ];
  return candidates.find((item) => fs.existsSync(item)) || "";
}

const sourceApp = findApp();
if (!sourceApp) fail("Adept UI.app BUILT = FAIL");

fs.rmSync(isolatedRoot, { recursive: true, force: true });
fs.mkdirSync(isolatedRoot, { recursive: true });
const app = path.join(isolatedRoot, "Adept UI.app");
fs.cpSync(sourceApp, app, { recursive: true, verbatimSymlinks: true });
spawnSync("xattr", ["-cr", app], { stdio: "inherit" });
const signed = spawnSync("codesign", ["--force", "--deep", "--sign", "-", app], { encoding: "utf8" });
if (signed.status !== 0) fail(`ad-hoc sign failed: ${signed.stderr || signed.stdout}`);

const resources = path.join(app, "Contents", "Resources");
const python = path.join(resources, "python", "bin", "python");
const apiMain = path.join(resources, "studio-api", "app", "main.py");
const windowsBits = auditPackagedTree(path.join(resources, "python"));
const arch = spawnSync(python, ["-c", "import platform; print(platform.machine())"], { encoding: "utf8" });
const machine = (arch.stdout || "").trim();
if (!fs.existsSync(apiMain)) fail("STUDIO API STAGED = FAIL");
if (arch.status !== 0 || machine !== "arm64") fail(`PACKAGED PYTHON ARM64 = FAIL (${machine || arch.stderr})`);
if (windowsBits.length) fail(`WINDOWS BINARIES IN MAC PACKAGE = FAIL\n${windowsBits.slice(0, 20).join("\n")}`);

fs.rmSync(userData, { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });
const executable = path.join(app, "Contents", "MacOS", "Adept UI");
const child = spawn(executable, [`--user-data-dir=${userData}`], {
  cwd: path.dirname(executable),
  stdio: "ignore",
  detached: false,
});
console.log("Adept UI.app LAUNCHED = PASS");

let health = { status: 0, body: "" };
for (let i = 0; i < 90; i += 1) {
  health = await get("http://127.0.0.1:8760/api/healthz");
  if (health.status === 200) break;
  if (child.exitCode !== null) break;
  await sleep(2000);
}
const boot = health.status === 200 ? await get("http://127.0.0.1:8760/api/boot/certification", 120000) : { status: 0, body: "" };
const statusFile = path.join(userData, "desktop-status.json");
const status = fs.existsSync(statusFile) ? JSON.parse(fs.readFileSync(statusFile, "utf8")) : null;
const logPath = path.join(userData, "logs", "studio-api.log");
const logTail = fs.existsSync(logPath) ? fs.readFileSync(logPath, "utf8").slice(-4000) : "";
const command = String(status?.apiCommand || "");
const rendererPort = status?.rendererOrigin ? new URL(status.rendererOrigin).port : "";
const result = {
  macosNativeRunner: "PASS",
  packagedPythonArch: machine === "arm64" ? "PASS" : "FAIL",
  studioApiStaged: fs.existsSync(apiMain) ? "PASS" : "FAIL",
  appBuilt: "PASS",
  appLaunched: "PASS",
  studioApi8760: health.status === 200 ? "HTTP 200" : `HTTP ${health.status}`,
  bootManagerReachable: boot.status === 200 ? "PASS" : "FAIL",
  viteDependency: status?.viteContacted === true || rendererPort === "5173" ? 1 : 0,
  devVenvDependency: command.includes(`${path.sep}.venv${path.sep}`) || command.includes("/.venv/") ? 1 : 0,
  devRepoDependency: status?.paths?.devRepoPathDependency ? 1 : 0,
  windowsBinariesInMacPackage: windowsBits.length,
  pywin32InMacPackage: windowsBits.some((item) => item.toLowerCase().includes("pywin32")) ? 1 : 0,
  windowsWheels: windowsBits.length,
  apiCommand: command,
  python,
  health,
  bootStatus: boot.status,
  rendererOrigin: status?.rendererOrigin || null,
  logTail,
};
fs.mkdirSync(path.dirname(resultPath), { recursive: true });
fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));
if (child.pid) {
  try {
    process.kill(child.pid, "SIGTERM");
  } catch {
    /* already gone */
  }
}
console.log(JSON.stringify({
  studioApi8760: result.studioApi8760,
  bootManagerReachable: result.bootManagerReachable,
  viteDependency: result.viteDependency,
  devVenvDependency: result.devVenvDependency,
  devRepoDependency: result.devRepoDependency,
  pywin32InMacPackage: result.pywin32InMacPackage,
  windowsBinariesInMacPackage: result.windowsBinariesInMacPackage,
}, null, 2));
if (health.status !== 200 || boot.status !== 200 || result.viteDependency !== 0 || result.devVenvDependency !== 0 || result.devRepoDependency !== 0) {
  if (logTail) console.error(logTail);
  process.exit(1);
}
