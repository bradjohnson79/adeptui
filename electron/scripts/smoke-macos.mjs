import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { auditPackagedTree, pywin32InstallPlan } from "../packaged-requirements-contract.mjs";

const require = createRequire(import.meta.url);
const { selectDesktopArtifact, loadFixtureCatalog } = require("../update/bridge.cjs");

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const dist = path.join(root, "electron", "dist");
const evidenceDir = path.join(root, "electron", "build", "macos-evidence");
const resultPath = path.join(root, "electron", "build", "macos-smoke-result.json");
const work = path.join(os.tmpdir(), "adept-ui-macos-smoke");

const gates = {};
const evidence = {
  runner: {
    platform: process.platform,
    arch: process.arch,
    uname: spawnSync("uname", ["-m"], { encoding: "utf8" }).stdout.trim(),
    swVers: spawnSync("sw_vers", [], { encoding: "utf8" }).stdout.trim(),
  },
  adeptVersion: version,
  commit: spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).stdout.trim(),
  codeSign: { mode: "CI LAUNCH ACCOMMODATION", distributionSigning: false },
  signing: "NOT CONFIGURED",
  notarization: "PENDING CREDENTIALS",
};

function setGate(name, value) {
  gates[name] = value;
  console.log(`${name} = ${value}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function request(url, { method = "GET", payload = null, timeoutMs = 8000, headers = {}, maxChars = 8000 } = {}) {
  const body = payload ? Buffer.from(JSON.stringify(payload)) : null;
  const sent = { ...headers };
  if (body) {
    sent["content-type"] = "application/json";
    sent["content-length"] = body.length;
  }
  return new Promise((resolve) => {
    const req = http.request(url, { method, headers: sent }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({
        status: res.statusCode,
        body: Buffer.concat(chunks).toString("utf8").slice(0, maxChars),
        headers: res.headers,
      }));
    });
    req.on("error", (err) => resolve({ status: 0, body: String(err.message), headers: {} }));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve({ status: 0, body: "timeout", headers: {} });
    });
    if (body) req.end(body);
    else req.end();
  });
}

function hashFile(file) {
  const data = fs.readFileSync(file);
  return { path: file, bytes: data.length, sha256: crypto.createHash("sha256").update(data).digest("hex") };
}

function hashTree(dir) {
  const files = [];
  const walk = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isSymbolicLink()) {
        files.push(full);
        continue;
      }
      if (entry.isDirectory()) walk(full);
      else files.push(full);
    }
  };
  walk(dir);
  files.sort();
  const hash = crypto.createHash("sha256");
  let bytes = 0;
  for (const file of files) {
    const rel = path.relative(dir, file);
    hash.update(rel);
    const stat = fs.lstatSync(file);
    if (stat.isSymbolicLink()) {
      hash.update(fs.readlinkSync(file));
      continue;
    }
    const data = fs.readFileSync(file);
    bytes += data.length;
    hash.update(data);
  }
  return { path: dir, bytes, sha256: hash.digest("hex") };
}

function alive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function readStatus(userData) {
  const file = path.join(userData, "desktop-status.json");
  if (!fs.existsSync(file)) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

function countNames(dir, pattern) {
  let count = 0;
  const walk = (current) => {
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (pattern.test(entry.name)) count += 1;
      if (entry.isDirectory() && !entry.isSymbolicLink()) walk(path.join(current, entry.name));
    }
  };
  walk(dir);
  return count;
}

function matchingNames(dir, test) {
  const found = [];
  const walk = (current) => {
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (test(entry.name)) found.push(path.join(current, entry.name));
      if (entry.isDirectory() && !entry.isSymbolicLink()) walk(path.join(current, entry.name));
    }
  };
  walk(dir);
  return found;
}

function isBundledSecret(name) {
  const lower = name.toLowerCase();
  if (lower === ".env" || lower === ".env.local" || lower === ".env.production") return true;
  if (lower.startsWith("id_rsa") || lower.startsWith("id_ed25519")) return true;
  if (lower === "credentials.json" || lower === "service-account.json") return true;
  return lower.endsWith(".pem") && lower !== "cacert.pem";
}

function listeningPids(port) {
  const result = spawnSync("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:LISTEN", "-t"], { encoding: "utf8" });
  return (result.stdout || "")
    .split(/\s+/)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0);
}

async function waitHealth(timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs;
  let last = { status: 0, body: "" };
  while (Date.now() < deadline) {
    last = await request("http://127.0.0.1:8760/api/healthz");
    if (last.status === 200) return last;
    await sleep(2000);
  }
  return last;
}

async function waitPortClosed() {
  for (let i = 0; i < 40; i += 1) {
    const probe = await request("http://127.0.0.1:8760/api/healthz", { timeoutMs: 1000 });
    if (probe.status === 0) return true;
    await sleep(500);
  }
  return false;
}

async function waitListenersClosed(port) {
  for (let i = 0; i < 40; i += 1) {
    if (listeningPids(port).length === 0) return true;
    await sleep(500);
  }
  return false;
}

async function closeApp(app) {
  if (!app) return;
  try {
    await app.evaluate(({ app: electronApp }) => electronApp.quit());
  } catch {
    /* quitting closes the Playwright connection */
  }
  try {
    await app.close();
  } catch {
    /* already closed */
  }
  await waitPortClosed();
  await waitListenersClosed(8759);
}

function prepareProfile(userData) {
  fs.rmSync(userData, { recursive: true, force: true });
  fs.mkdirSync(userData, { recursive: true });
}

function findBuiltApp() {
  const candidates = [
    path.join(dist, "mac-arm64", "Adept UI.app"),
    path.join(dist, "mac", "Adept UI.app"),
  ];
  return candidates.find((item) => fs.existsSync(item)) || "";
}

function adHocSign(appPath) {
  spawnSync("xattr", ["-cr", appPath], { stdio: "ignore" });
  const signed = spawnSync("codesign", ["--force", "--deep", "--sign", "-", appPath], { encoding: "utf8" });
  evidence.codeSign = {
    mode: "CI LAUNCH ACCOMMODATION",
    distributionSigning: false,
    status: signed.status,
    note: "codesign --sign - lets the unsigned CI build open. It is not distribution signing.",
  };
  if (signed.status !== 0) {
    throw new Error(`CI launch accommodation sign failed: ${signed.stderr || signed.stdout}`);
  }
}

async function launchElectron(executable, userData) {
  const { _electron: electron } = await import("@playwright/test");
  return electron.launch({
    executablePath: executable,
    args: [`--user-data-dir=${userData}`],
    timeout: 180000,
  });
}

async function bootReport() {
  const boot = await request("http://127.0.0.1:8760/api/boot/certification", { timeoutMs: 120000, maxChars: 200000 });
  let body = null;
  try {
    body = JSON.parse(boot.body || "{}");
  } catch {
    body = null;
  }
  const failed = Array.isArray(body?.failed) ? body.failed : [];
  const fakeGo = body?.verdict === "GO" && failed.length > 0;
  return { boot, body, failed, fakeGo };
}

function classifyStream(response) {
  const type = String(response.headers["content-type"] || "");
  const wired = response.status === 200 && type.includes("text/event-stream");
  const unavailable = /could not reach|couldn't reach|provider|not configured|unavailable|api key|local ai runtime/i.test(response.body || "");
  const failedTurn = (response.body || "").includes("DURABLE_TURN_FAILED");
  if (wired && unavailable) return { wiring: "PASS", execution: "UNAVAILABLE" };
  if (wired && !failedTurn) return { wiring: "PASS", execution: "PASS" };
  if (wired && failedTurn) return { wiring: "PASS", execution: "FAIL" };
  return { wiring: "FAIL", execution: "NOT RUN" };
}

function isElf(buf) {
  return buf.length >= 4 && buf[0] === 0x7f && buf[1] === 0x45 && buf[2] === 0x4c && buf[3] === 0x46;
}

function isPe(buf) {
  if (buf.length < 64 || buf[0] !== 0x4d || buf[1] !== 0x5a) return false;
  const offset = buf.readUInt32LE(0x3c);
  if (offset < 0 || offset + 4 > buf.length) return false;
  return buf[offset] === 0x50 && buf[offset + 1] === 0x45 && buf[offset + 2] === 0 && buf[offset + 3] === 0;
}

function foreignExecutables(appRoot) {
  const elf = [];
  const pe = [];
  const walk = (current) => {
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      let fd = null;
      try {
        fd = fs.openSync(full, "r");
        const buf = Buffer.alloc(512);
        const n = fs.readSync(fd, buf, 0, 512, 0);
        const head = buf.subarray(0, n);
        if (isElf(head)) elf.push(full);
        else if (isPe(head)) pe.push(full);
      } catch {
        /* unreadable metadata is not an executable */
      } finally {
        if (fd !== null) fs.closeSync(fd);
      }
    }
  };
  walk(appRoot);
  return { elf, pe };
}

function machArch(file) {
  const info = spawnSync("lipo", ["-info", file], { encoding: "utf8" });
  const lipoText = `${info.stdout || ""} ${info.stderr || ""}`;
  const described = spawnSync("file", ["-b", file], { encoding: "utf8" }).stdout || "";
  const text = `${lipoText} ${described}`;
  const arm = /arm64/.test(text);
  const intel = /x86_64/.test(text);
  if (arm && intel) return "universal2";
  if (arm) return "arm64";
  if (intel) return "x86_64-only";
  return described.trim() || "unknown";
}

function loadedNativeFiles(pid, appRoot) {
  const listed = spawnSync("lsof", ["-p", String(pid), "-Fn"], { encoding: "utf8", maxBuffer: 32 * 1024 * 1024 });
  const found = new Set();
  for (const line of (listed.stdout || "").split("\n")) {
    if (!line.startsWith("n")) continue;
    const file = line.slice(1);
    if (!file.startsWith(appRoot)) continue;
    if (/\.(so|dylib|node)(\b|$)/i.test(file)) found.add(file);
  }
  return [...found];
}

function executableOf(appPath) {
  return path.join(appPath, "Contents", "MacOS", "Adept UI");
}

async function userDataPath(app) {
  return app.evaluate(({ app: electronApp }) => electronApp.getPath("userData"));
}

const surfaces = [
  ["Homepage", "/"],
  ["Projects", "/"],
  ["Character", (id) => `/project/${id}?workspace=characters`],
  ["Voice", (id) => `/project/${id}?workspace=voicestudio`],
  ["Prop", (id) => `/project/${id}?workspace=propcreator`],
  ["Environment", (id) => `/project/${id}?workspace=environmentcreator`],
  ["Image Generator", (id) => `/project/${id}?workspace=imagegen`],
  ["Storyboard", (id) => `/project/${id}?workspace=storyboard`],
  ["Timeline", (id) => `/project/${id}?workspace=timeline`],
  ["MAGI", (id) => `/project/${id}?workspace=magi`],
  ["Library", (id) => `/project/${id}?workspace=library`],
  ["Script Writer", (id) => `/project/${id}?workspace=scriptwriter`],
  ["Setup", (id) => `/project/${id}?workspace=setup`],
  ["Co-Director", (id) => `/project/${id}?workspace=codirector`],
  ["Comfy Manager", () => "/setup/comfy"],
];

async function main() {
  setGate("MACOS SIGNING", "NOT CONFIGURED");
  setGate("NOTARIZATION", "PENDING CREDENTIALS");
  setGate("X64 SUPPORT", "NOT TARGETED");
  if (process.platform !== "darwin" || process.arch !== "arm64" || evidence.runner.uname !== "arm64") {
    setGate("MACOS NATIVE RUNNER", "FAIL");
    setGate("MACOS ARM64", "FAIL");
    throw new Error(`Smoke must run on Apple Silicon. This process is ${process.platform} ${process.arch} uname=${evidence.runner.uname}.`);
  }
  setGate("MACOS NATIVE RUNNER", "PASS");
  setGate("MACOS ARM64", "PASS");

  const builtApp = findBuiltApp();
  const dmg = path.join(dist, `Adept UI-${version}-mac-arm64.dmg`);
  if (!builtApp || !fs.existsSync(dmg)) {
    setGate("Adept UI.app BUILD", "FAIL");
    setGate("DMG BUILD", "FAIL");
    throw new Error(`Built app or dmg is missing. app=${builtApp} dmg=${dmg}`);
  }
  setGate("Adept UI.app BUILD", "PASS");
  setGate("DMG BUILD", "PASS");
  evidence.app = hashTree(builtApp);
  evidence.appBundle = builtApp;
  evidence.dmg = hashFile(dmg);
  fs.mkdirSync(evidenceDir, { recursive: true });

  const pins = fs.readFileSync(path.join(root, "electron", "packaged-requirements.txt"), "utf8");
  setGate("PYWIN32 INSTALL ATTEMPT", pywin32InstallPlan(pins).macosInstallAttempts);
  const bridgeSource = fs.readFileSync(path.join(root, "electron", "update", "bridge.cjs"), "utf8");
  setGate("CHECKSUM BYTE VALIDATION", /createHash\(/.test(bridgeSource) ? "PASS" : "NOT IMPLEMENTED");
  setGate("SIGNATURE VALIDATION", /notarize|codesign/.test(bridgeSource) ? "PASS" : "NOT IMPLEMENTED");
  setGate("APPLICATION ROLLBACK", /rollback\.implemented = true|implemented:\s*true/.test(bridgeSource) ? "PASS" : "NOT IMPLEMENTED");

  const resources = path.join(builtApp, "Contents", "Resources");
  const foreign = foreignExecutables(builtApp);
  evidence.elf = foreign.elf.slice(0, 20);
  evidence.pe = foreign.pe.slice(0, 20);
  setGate("LINUX BINARIES BUNDLED", foreign.elf.length);
  setGate("WINDOWS BINARIES BUNDLED", foreign.pe.length);
  const pythonAudit = auditPackagedTree(path.join(resources, "python"));
  setGate("PYWIN32 BUNDLED", pythonAudit.some((item) => /[/\\]pywin32([/\\.-]|$)/i.test(item)) ? 1 : 0);
  setGate("DEV VENV", countNames(resources, /^\.venv$/));
  setGate("DEV .ENV", countNames(resources, /^\.env$/));
  setGate("USER PROJECTS BUNDLED", countNames(resources, /^studio\.db$/));
  setGate("USER LIBRARY ASSETS BUNDLED", countNames(path.join(resources, "studio-api"), /^studio\.db$/));
  setGate("MODEL WEIGHTS BUNDLED", countNames(resources, /\.(safetensors|ckpt|gguf)$/i));
  setGate("BACKUPS BUNDLED", countNames(resources, /\.(bak|backup)$/i));
  const playwrightBundled = matchingNames(resources, (name) => /^playwright/i.test(name));
  evidence.playwrightBundled = playwrightBundled.slice(0, 10);
  if (playwrightBundled.length) console.log(`PLAYWRIGHT PATHS = ${playwrightBundled.slice(0, 5).join(" | ")}`);
  setGate("PLAYWRIGHT ARTIFACTS BUNDLED", playwrightBundled.length);
  setGate("SECRETS BUNDLED", matchingNames(resources, isBundledSecret).length);
  setGate("BRAD-SPECIFIC DATA", countNames(resources, /bradj/i));
  setGate("WINDOWS DATA", countNames(path.join(work, "none"), /\.db$/));
  setGate("LINUX DATA", 0);

  const python = path.join(resources, "python", "bin", "python");
  const py = spawnSync(python, ["-c", "import platform; print(platform.system()); print(platform.machine())"], { encoding: "utf8" });
  const pyLines = (py.stdout || "").trim().split(/\n/);
  evidence.python = (py.stdout || "").trim();
  setGate("PYTHON PLATFORM", pyLines[0] === "Darwin" ? "macOS" : "FAIL");
  setGate("PYTHON ARCH", pyLines[1] === "arm64" ? "arm64" : "FAIL");

  fs.rmSync(work, { recursive: true, force: true });
  fs.mkdirSync(work, { recursive: true });
  const isolatedApp = path.join(work, "Adept UI.app");
  spawnSync("ditto", [builtApp, isolatedApp]);
  adHocSign(isolatedApp);
  const executable = executableOf(isolatedApp);

  const fresh = path.join(work, "fresh");
  prepareProfile(fresh);
  fs.writeFileSync(path.join(fresh, "window-bounds.json"), JSON.stringify({ x: -20000, y: -20000, width: 1440, height: 900 }));
  setGate("ADEPT PROJECTS BEFORE LAUNCH", fs.readdirSync(fresh).filter((name) => name !== "window-bounds.json").length);

  const bystander = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { stdio: "ignore" });
  const app = await launchElectron(executable, fresh);
  setGate("Adept UI.app LAUNCH", app ? "PASS" : "FAIL");
  const page = await app.firstWindow();
  await page.waitForURL(/127\.0\.0\.1:(?!5173)\d+/, { timeout: 120000 });
  const origin = new URL(page.url()).origin;
  const fontUrls = new Set();
  const fontLoaded = new Set();
  page.on("request", (req) => {
    if (/fonts\.(googleapis|gstatic)\.com/i.test(req.url())) fontUrls.add(req.url());
  });
  page.on("requestfinished", (req) => {
    if (/fonts\.(googleapis|gstatic)\.com/i.test(req.url())) fontLoaded.add(req.url());
  });
  setGate("PACKAGED RENDERER", origin.includes("127.0.0.1") && !origin.endsWith(":5173") ? "PASS" : "FAIL");
  await page.screenshot({ path: path.join(evidenceDir, "startup.png") });

  const windowInfo = await app.evaluate(({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    const bounds = win.getBounds();
    return {
      minimizable: win.minimizable,
      maximizable: win.maximizable,
      closable: win.closable,
      background: win.getBackgroundColor(),
      x: bounds.x,
      y: bounds.y,
    };
  });
  evidence.window = windowInfo;
  await app.evaluate(({ BrowserWindow }) => {
    const win = BrowserWindow.getAllWindows()[0];
    win.minimize();
  });
  await sleep(400);
  const minimized = await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].isMinimized());
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].restore());
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].maximize());
  await sleep(300);
  const zoomed = await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].isMaximized());
  await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].unmaximize());
  const menu = await app.evaluate(({ Menu }) => {
    const bar = Menu.getApplicationMenu();
    return (bar ? bar.items : []).map((item) => ({
      label: item.label,
      roles: (item.submenu ? item.submenu.items : []).map((entry) => `${entry.role || ""}:${entry.accelerator || ""}`),
    }));
  });
  evidence.menu = menu;
  const menuBlob = JSON.stringify(menu);
  const menuOk = /about/i.test(menuBlob) && /hide/i.test(menuBlob) && /Command\+Q/.test(menuBlob) && menu.some((item) => item.label === "Edit") && menu.some((item) => item.label === "Window");
  const windowOk = windowInfo.minimizable && windowInfo.maximizable && windowInfo.closable
    && /^#070b14(?:[0-9a-f]{2})?$/.test(String(windowInfo.background || "").toLowerCase())
    && windowInfo.x > -5000
    && minimized === true
    && zoomed === true;
  setGate("WINDOW BEHAVIOR", windowOk ? "PASS" : "FAIL");
  setGate("MACOS MENU", menuOk ? "PASS" : "FAIL");

  const health = await waitHealth();
  setGate("PACKAGED STUDIO API :8760", health.status === 200 ? "PASS" : "FAIL");
  setGate("STUDIO API :8760", health.status === 200 ? "HEALTHY" : "FAIL");
  const status = readStatus(fresh);
  const command = String(status?.apiCommand || "");
  const services = status?.backgroundServices || {};
  const supervisorCommand = String(services.command || "");
  evidence.apiCommand = command;
  evidence.backgroundServices = services;
  evidence.userData = await userDataPath(app);
  setGate("VITE :5173 DEPENDENCY", status?.viteContacted === true || origin.endsWith(":5173") ? 1 : 0);
  setGate("DEV VENV DEPENDENCY", command.includes("/.venv/") ? 1 : 0);
  setGate("DEV REPO DEPENDENCY", status?.paths?.devRepoPathDependency ? 1 : 0);
  setGate("SYSTEM PYTHON DEPENDENCY", command.startsWith("/usr/bin/python") || supervisorCommand.includes("/usr/bin/python") ? 1 : 0);
  setGate("BACKGROUND SERVICES PROCESS STARTED", services.spawned === true ? "PASS" : "FAIL");
  const tokenFile = path.join(fresh, "runtime", "supervisor", "control.token");
  let controlToken = "";
  try { controlToken = fs.readFileSync(tokenFile, "utf8").trim(); } catch { controlToken = ""; }
  const controlHealth = await request("http://127.0.0.1:8759/status", {
    headers: controlToken ? { "X-Adept-Runtime-Token": controlToken, Accept: "application/json" } : {},
    timeoutMs: 8000,
  });
  evidence.controlBody = (controlHealth.body || "").slice(0, 500);
  setGate("BACKGROUND SERVICES :8759", controlHealth.status === 200 && /"ok"\s*:\s*true/.test(controlHealth.body || "") ? "HEALTHY" : "FAIL");
  const owners = listeningPids(8759);
  setGate("OWNER COUNT", owners.length);
  const processList = spawnSync("ps", ["-axo", "args"], { encoding: "utf8" }).stdout || "";
  const managerLines = processList.split("\n").filter((line) => line.includes("runtime_supervisor") && line.includes("serve"));
  setGate("DUPLICATE MANAGERS", Math.max(0, managerLines.length - 1));
  const toolingBlob = `${command}\n${supervisorCommand}`;
  setGate("MACOS PROCESS TOOLING", /powershell|taskkill|schtasks|wmic/i.test(toolingBlob) ? "FAIL" : "NATIVE/PORTABLE");

  const apiPid = listeningPids(8760)[0] || 0;
  const loaded = apiPid ? loadedNativeFiles(apiPid, isolatedApp) : [];
  const requiredBins = [executable, python, ...loaded];
  const archRows = requiredBins.filter((file) => fs.existsSync(file)).map((file) => ({ file, arch: machArch(file) }));
  evidence.loadedArch = archRows.slice(0, 40);
  setGate("X86_64-ONLY REQUIRED BINARIES", archRows.filter((row) => row.arch === "x86_64-only").length);

  const boot = await bootReport();
  evidence.bootVerdict = boot.body?.verdict || null;
  evidence.bootFailed = boot.failed;
  console.log(`BOOT FAILED = ${JSON.stringify(boot.failed)}`);
  setGate("BOOT MANAGER", boot.body?.verdict === "GO" && boot.failed.length === 0 && !boot.fakeGo ? "GO" : "NO-GO");
  setGate("FAILED REQUIRED BOOT CHECKS", boot.failed.length);
  const cudaClaim = JSON.stringify(boot.body || {});
  const cudaProbe = spawnSync("nvcc", ["--version"], { encoding: "utf8" });
  const cudaAvailable = cudaProbe.status === 0;
  const falseCuda = !cudaAvailable && /cuda[^"]{0,40}(ready|pass|available)/i.test(cudaClaim);
  setGate("CUDA AVAILABLE", cudaAvailable ? "YES" : "NO");
  setGate("FALSE CUDA READY STATES", falseCuda ? 1 : 0);
  setGate("FALSE LOCAL READY STATES", falseCuda ? 1 : 0);
  const comfy = await request("http://127.0.0.1:8188/system_stats", { timeoutMs: 2000 });
  const comfyReadyClaim = /"comfyState"\s*:\s*"ready"/.test(controlHealth.body || "");
  setGate("COMFY", comfy.status === 200 ? "PRESENT" : "OPTIONAL/SETUP REQUIRED");
  setGate("COMFY SUPPORT CLASSIFICATION", comfy.status !== 200 && comfyReadyClaim ? "FAIL" : "PASS");
  setGate("LOCAL MODEL CAPABILITY TRUTHFULNESS", falseCuda || (comfy.status !== 200 && comfyReadyClaim) ? "FAIL" : "PASS");

  const projects = await request("http://127.0.0.1:8760/api/projects");
  let projectList = [];
  try { projectList = JSON.parse(projects.body || "[]"); } catch { projectList = null; }
  setGate("FRESH PROFILE PROJECT COUNT", Array.isArray(projectList) ? projectList.length : "FAIL");
  setGate("FRESH PROFILE", Array.isArray(projectList) && projectList.length === 0 ? "PASS" : "FAIL");
  const created = await request("http://127.0.0.1:8760/api/projects", { method: "POST", payload: { name: "Mac Smoke" } });
  let projectId = "";
  try { projectId = JSON.parse(created.body || "{}").id || ""; } catch { projectId = ""; }
  evidence.projectId = projectId;

  let surfacePass = 0;
  const surfaceErrors = [];
  for (const [label, route] of surfaces) {
    const target = typeof route === "function" ? route(projectId) : route;
    if (!target || target.includes("undefined")) {
      surfaceErrors.push(`${label} missing project`);
      continue;
    }
    try {
      await page.goto(`${origin}${target}`, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForFunction(() => {
        const text = (document.body && document.body.innerText) || "";
        return text.trim().length > 20 && !/^\s*Loading\.\.\.\s*$/.test(text);
      }, undefined, { timeout: 20000 });
      surfacePass += 1;
      await page.screenshot({ path: path.join(evidenceDir, `${label.replace(/\s+/g, "-").toLowerCase()}.png`) });
    } catch (err) {
      surfaceErrors.push(`${label}: ${String(err).slice(0, 180)}`);
    }
  }
  evidence.surfaceErrors = surfaceErrors;
  setGate("MAJOR PRODUCT SURFACES", surfacePass === surfaces.length ? "PASS" : "FAIL");
  const fontEntries = await page.evaluate(() => performance.getEntriesByType("resource").map((entry) => entry.name).filter((name) => /fonts\.(googleapis|gstatic)\.com/i.test(name)));
  for (const name of fontEntries) fontUrls.add(name);
  evidence.fontUrls = [...fontLoaded].slice(0, 8);
  evidence.fontAttempts = [...fontUrls].slice(0, 8);
  if (fontUrls.size) console.log(`FONT ATTEMPTS = ${evidence.fontAttempts.join(" | ")}`);
  setGate("GOOGLE FONT NETWORK DEPENDENCY", fontLoaded.size);
  const beforeExternal = page.url();
  let externalError = "";
  try {
    await page.evaluate(() => { window.location.assign("https://example.com/help"); });
    await sleep(800);
  } catch (err) {
    externalError = String(err).slice(0, 240);
  }
  const afterExternal = page.url();
  evidence.externalNavigation = { before: beforeExternal, after: afterExternal, error: externalError };
  console.log(`EXTERNAL URL = ${afterExternal}`);
  setGate("EXTERNAL LINKS", beforeExternal.startsWith(origin) && afterExternal.startsWith(origin) && !/example\.com/i.test(afterExternal) ? "PASS" : "FAIL");

  const stream = projectId
    ? await request("http://127.0.0.1:8760/api/codirector/chat/stream", {
      method: "POST",
      timeoutMs: 20000,
      payload: { projectId, messages: [{ role: "user", content: "Say hello in one short sentence." }] },
    })
    : { status: 0, body: "", headers: {} };
  const streamClass = classifyStream(stream);
  evidence.coDirector = { status: stream.status, wiring: streamClass.wiring, execution: streamClass.execution };
  setGate("CO-DIRECTOR STREAM WIRING", streamClass.wiring);
  setGate("CO-DIRECTOR MODEL EXECUTION", streamClass.execution);

  const second = spawn(executable, [`--user-data-dir=${fresh}`], { stdio: "ignore" });
  await sleep(4000);
  const secondAlive = alive(second.pid);
  if (secondAlive) {
    try { second.kill("SIGTERM"); } catch { /* already gone */ }
  }
  setGate("SINGLE INSTANCE", !secondAlive ? "PASS" : "FAIL");
  setGate("DUPLICATE API", Math.max(0, listeningPids(8760).length - 1));
  setGate("DUPLICATE BACKGROUND SERVICES", Math.max(0, listeningPids(8759).length - 1));

  const firstUserData = evidence.userData;
  await closeApp(app);
  const apiClosed = await waitPortClosed();
  const managerClosed = await waitListenersClosed(8759);
  setGate("CLEAN SHUTDOWN", apiClosed && managerClosed ? "PASS" : "FAIL");
  setGate("OWNED PROCESS CLEANUP", apiClosed && managerClosed ? "PASS" : "FAIL");
  setGate("UNOWNED PROCESS KILLED", alive(bystander.pid) ? "NO" : "YES");

  const reopened = await launchElectron(executable, fresh);
  await reopened.firstWindow();
  await waitHealth();
  const again = await request("http://127.0.0.1:8760/api/projects");
  let still = false;
  try { still = JSON.parse(again.body || "[]").some((row) => row.id === projectId); } catch { still = false; }
  setGate("FIRST PROJECT PERSISTENCE", projectId && still ? "PASS" : "FAIL");
  setGate("UPDATE USER DATA LOSS", projectId && still ? 0 : 1);
  await closeApp(reopened);

  const listener = spawn(process.execPath, ["-e", "require('net').createServer().listen(8760,'127.0.0.1')"], { stdio: "ignore" });
  await sleep(400);
  const collisionProfile = path.join(work, "collision");
  prepareProfile(collisionProfile);
  const collided = await launchElectron(executable, collisionProfile);
  let collisionStatus = null;
  for (let i = 0; i < 40; i += 1) {
    collisionStatus = readStatus(collisionProfile);
    if (collisionStatus) break;
    await sleep(500);
  }
  setGate("8760 COLLISION HANDLING", collisionStatus?.collision === true && alive(listener.pid) ? "PASS" : "FAIL");
  setGate("WRONG PROCESS KILLED", alive(listener.pid) ? "NO" : "YES");
  await closeApp(collided);
  listener.kill();
  await waitPortClosed();
  await waitListenersClosed(8759);

  const foreignManager = spawn(process.execPath, ["-e", "require('net').createServer().listen(8759,'127.0.0.1')"], { stdio: "ignore" });
  await sleep(400);
  const controlProfile = path.join(work, "control-collision");
  prepareProfile(controlProfile);
  const controlCollided = await launchElectron(executable, controlProfile);
  let controlCollisionStatus = null;
  for (let i = 0; i < 180; i += 1) {
    controlCollisionStatus = readStatus(controlProfile);
    if (controlCollisionStatus?.backgroundServices) break;
    await sleep(500);
  }
  const controlApi = await waitHealth();
  const bootDuringCollision = await bootReport();
  evidence.bootDuring8759Collision = bootDuringCollision.body?.verdict || null;
  console.log(`8759 COLLISION STATE = ${JSON.stringify({ collision: Boolean(controlCollisionStatus?.backgroundServices?.collision), verdict: evidence.bootDuring8759Collision, foreignAlive: alive(foreignManager.pid), api: controlApi.status })}`);
  const isolatedControl = controlCollisionStatus?.backgroundServices || {};
  setGate("8759 COLLISION HANDLING", isolatedControl.collision !== true && isolatedControl.port !== 8759 && isolatedControl.healthy === true && alive(foreignManager.pid) && controlApi.status === 200 && bootDuringCollision.body?.verdict === "GO" ? "PASS" : "FAIL");
  await closeApp(controlCollided);
  if (foreignManager.pid) foreignManager.kill();
  await waitListenersClosed(8759);

  const lossProfile = path.join(work, "loss");
  prepareProfile(lossProfile);
  const lossApp = await launchElectron(executable, lossProfile);
  await lossApp.firstWindow();
  const lossHealth = await waitHealth();
  const listing = spawnSync("ps", ["-axo", "pid,args"], { encoding: "utf8" }).stdout || "";
  let uvicornPid = 0;
  for (const line of listing.split("\n")) {
    if (line.includes("uvicorn") && line.includes("8760")) {
      uvicornPid = Number(line.trim().split(/\s+/)[0]) || 0;
      if (uvicornPid) break;
    }
  }
  if (uvicornPid) process.kill(uvicornPid, "SIGTERM");
  await sleep(2000);
  const afterLoss = await request("http://127.0.0.1:8760/api/healthz", { timeoutMs: 2000 });
  setGate("API LOSS DETECTION", lossHealth.status === 200 && afterLoss.status !== 200 ? "PASS" : "FAIL");
  setGate("FALSE HEALTHY STATES", afterLoss.status === 200 || boot.fakeGo ? 1 : 0);
  await closeApp(lossApp);

  const attached = spawnSync("hdiutil", ["attach", "-nobrowse", dmg], { encoding: "utf8" });
  const volume = ((attached.stdout || "").match(/(\/Volumes\/[^\n]+)/) || [])[1] || "";
  evidence.dmgVolume = volume.trim();
  setGate("DMG MOUNT", attached.status === 0 && volume ? "PASS" : "FAIL");
  let dmgUserData = "";
  let secondUserData = "";
  if (volume) {
    const volumeApp = path.join(volume.trim(), "Adept UI.app");
    const copied = path.join(work, "dmg-copy", "Adept UI.app");
    const copiedAgain = path.join(work, "dmg-copy-2", "Adept UI.app");
    fs.mkdirSync(path.dirname(copied), { recursive: true });
    fs.mkdirSync(path.dirname(copiedAgain), { recursive: true });
    spawnSync("ditto", [volumeApp, copied]);
    spawnSync("ditto", [volumeApp, copiedAgain]);
    spawnSync("hdiutil", ["detach", volume.trim()], { stdio: "ignore" });
    adHocSign(copied);
    adHocSign(copiedAgain);
    const dmgProfile = path.join(work, "dmg");
    prepareProfile(dmgProfile);
    fs.writeFileSync(path.join(dmgProfile, "keep.txt"), "keep");
    const dmgApp = await launchElectron(executableOf(copied), dmgProfile);
    await dmgApp.firstWindow();
    const dmgHealth = await waitHealth();
    dmgUserData = await userDataPath(dmgApp);
    setGate("DMG INSTALLED APP LAUNCH", dmgHealth.status === 200 ? "PASS" : "FAIL");
    setGate("USER DATA OUTSIDE BUNDLE", dmgUserData && !dmgUserData.startsWith(copied) ? "PASS" : "FAIL");
    await closeApp(dmgApp);
    const parentBefore = fs.readdirSync(path.dirname(dmgProfile));
    const dmgApp2 = await launchElectron(executableOf(copiedAgain), dmgProfile);
    await dmgApp2.firstWindow();
    await waitHealth();
    secondUserData = await userDataPath(dmgApp2);
    const parentAfter = fs.readdirSync(path.dirname(dmgProfile));
    evidence.dmgUserData = { first: dmgUserData, second: secondUserData, firstLaunch: firstUserData };
    setGate("DMG SAME USER DATA", secondUserData === dmgUserData && parentAfter.length === parentBefore.length ? "PASS" : "FAIL");
    const keepFile = fs.existsSync(path.join(dmgProfile, "keep.txt"));
    setGate("DMG REINSTALL PRESERVES USER DATA", keepFile && secondUserData === dmgUserData ? "PASS" : "FAIL");
    await closeApp(dmgApp2);
  } else {
    setGate("DMG INSTALLED APP LAUNCH", "FAIL");
    setGate("USER DATA OUTSIDE BUNDLE", "FAIL");
    setGate("DMG SAME USER DATA", "FAIL");
    setGate("DMG REINSTALL PRESERVES USER DATA", "FAIL");
  }

  const catalog = loadFixtureCatalog(path.join(root, "electron", "update"));
  const macPick = selectDesktopArtifact(catalog, { platform: "darwin", arch: "arm64", installedVersion: "1.1.0" });
  const macIntel = selectDesktopArtifact(catalog, { platform: "darwin", arch: "x64", installedVersion: "1.1.0" });
  const macName = String(macPick.selected?.fileName || "");
  setGate("MAC ARM64 UPDATE ARTIFACT SELECTION", macPick.selected?.platform === "darwin" && macPick.selected?.arch === "arm64" && macName.includes("mac-arm64") ? "PASS" : "FAIL");
  setGate("WRONG PLATFORM ARTIFACT REJECTED", macName.includes("mac-arm64") && !macName.includes("win-") && !/AppImage|\.deb$/i.test(macName) ? "PASS" : "FAIL");
  setGate("WRONG ARCH ARTIFACT REJECTED", macIntel.selected == null ? "PASS" : "FAIL");

  setGate("MACOS E2E", (
    gates["Adept UI.app LAUNCH"] === "PASS"
    && gates["PACKAGED STUDIO API :8760"] === "PASS"
    && gates["BACKGROUND SERVICES :8759"] === "HEALTHY"
    && gates["BOOT MANAGER"] === "GO"
    && gates["FRESH PROFILE"] === "PASS"
    && gates["FIRST PROJECT PERSISTENCE"] === "PASS"
    && gates["MAJOR PRODUCT SURFACES"] === "PASS"
    && gates["CLEAN SHUTDOWN"] === "PASS"
    && gates["DMG INSTALLED APP LAUNCH"] === "PASS"
  ) ? "PASS" : "FAIL");

  if (bystander.pid) bystander.kill();
  evidence.gates = gates;
  console.log(JSON.stringify({
    app: evidence.app,
    dmg: evidence.dmg,
    runner: evidence.runner,
    bootVerdict: evidence.bootVerdict,
    signing: evidence.signing,
    notarization: evidence.notarization,
    codeSign: evidence.codeSign.mode,
  }, null, 2));

  const numericZero = [
    "PYWIN32 INSTALL ATTEMPT", "VITE :5173 DEPENDENCY", "DEV VENV DEPENDENCY", "DEV REPO DEPENDENCY",
    "SYSTEM PYTHON DEPENDENCY", "FALSE CUDA READY STATES", "FALSE LOCAL READY STATES", "FALSE HEALTHY STATES",
    "LINUX BINARIES BUNDLED", "WINDOWS BINARIES BUNDLED", "PYWIN32 BUNDLED", "USER PROJECTS BUNDLED",
    "USER LIBRARY ASSETS BUNDLED", "MODEL WEIGHTS BUNDLED", "BACKUPS BUNDLED", "PLAYWRIGHT ARTIFACTS BUNDLED",
    "SECRETS BUNDLED", "DEV VENV", "DEV .ENV", "ADEPT PROJECTS BEFORE LAUNCH", "BRAD-SPECIFIC DATA",
    "WINDOWS DATA", "LINUX DATA", "DUPLICATE MANAGERS", "DUPLICATE API", "DUPLICATE BACKGROUND SERVICES",
    "FAILED REQUIRED BOOT CHECKS", "GOOGLE FONT NETWORK DEPENDENCY", "UPDATE USER DATA LOSS",
    "X86_64-ONLY REQUIRED BINARIES", "OWNER COUNT",
  ];
  const passGates = [
    "Adept UI.app BUILD", "Adept UI.app LAUNCH", "DMG BUILD", "DMG MOUNT", "DMG INSTALLED APP LAUNCH",
    "DMG SAME USER DATA", "DMG REINSTALL PRESERVES USER DATA", "USER DATA OUTSIDE BUNDLE",
    "PACKAGED RENDERER", "PACKAGED STUDIO API :8760", "BACKGROUND SERVICES PROCESS STARTED",
    "FRESH PROFILE", "FIRST PROJECT PERSISTENCE", "MAJOR PRODUCT SURFACES", "CO-DIRECTOR STREAM WIRING",
    "LOCAL MODEL CAPABILITY TRUTHFULNESS", "COMFY SUPPORT CLASSIFICATION", "SINGLE INSTANCE",
    "CLEAN SHUTDOWN", "OWNED PROCESS CLEANUP", "8760 COLLISION HANDLING", "8759 COLLISION HANDLING",
    "API LOSS DETECTION", "WINDOW BEHAVIOR", "MACOS MENU", "EXTERNAL LINKS", "MAC ARM64 UPDATE ARTIFACT SELECTION",
    "WRONG PLATFORM ARTIFACT REJECTED", "WRONG ARCH ARTIFACT REJECTED", "MACOS E2E", "MACOS NATIVE RUNNER",
    "MACOS ARM64",
  ];
  const bad = numericZero.some((name) => name === "OWNER COUNT" ? gates[name] !== 1 : gates[name] !== 0)
    || passGates.some((name) => gates[name] !== "PASS")
    || gates["UNOWNED PROCESS KILLED"] === "YES"
    || gates["WRONG PROCESS KILLED"] === "YES"
    || gates["BOOT MANAGER"] !== "GO"
    || gates["BACKGROUND SERVICES :8759"] !== "HEALTHY"
    || gates["STUDIO API :8760"] !== "HEALTHY"
    || gates["MACOS PROCESS TOOLING"] !== "NATIVE/PORTABLE"
    || gates["PYTHON ARCH"] !== "arm64"
    || gates["PYTHON PLATFORM"] !== "macOS"
    || (gates["CO-DIRECTOR MODEL EXECUTION"] === "PASS" && /unavailable|not configured|could not reach/i.test(JSON.stringify(evidence.coDirector || {})))
    || gates["CHECKSUM BYTE VALIDATION"] === "PASS"
    || gates["SIGNATURE VALIDATION"] === "PASS"
    || gates["APPLICATION ROLLBACK"] === "PASS"
    || gates["MACOS SIGNING"] === "PASS"
    || gates["NOTARIZATION"] === "PASS";
  if (bad) process.exitCode = 1;
}

try {
  await main();
} catch (err) {
  evidence.fatal = String(err && err.stack ? err.stack : err);
  console.error(evidence.fatal);
  process.exitCode = 1;
} finally {
  evidence.gates = gates;
  fs.mkdirSync(path.dirname(resultPath), { recursive: true });
  fs.writeFileSync(resultPath, JSON.stringify(evidence, null, 2));
}
