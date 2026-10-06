import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { auditPackagedTree } from "../packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const dist = path.join(root, "electron", "dist");
const unpackedDir = path.join(dist, "linux-unpacked");
const unpackedBin = path.join(unpackedDir, "Adept UI");
const appImage = path.join(dist, `Adept UI-${version}-linux-x64.AppImage`);
const deb = path.join(dist, `Adept UI-${version}-linux-x64.deb`);
const evidenceDir = path.join(root, "electron", "build", "linux-evidence");
const resultPath = path.join(root, "electron", "build", "linux-smoke-result.json");
const work = path.join(os.tmpdir(), "adept-ui-linux-smoke");

const gates = {};
const evidence = {
  runner: {
    platform: process.platform,
    arch: process.arch,
    kernel: spawnSync("uname", ["-srv"], { encoding: "utf8" }).stdout.trim(),
    osRelease: fs.existsSync("/etc/os-release") ? fs.readFileSync("/etc/os-release", "utf8") : "",
  },
  adeptVersion: version,
  commit: spawnSync("git", ["rev-parse", "HEAD"], { cwd: root, encoding: "utf8" }).stdout.trim(),
};

function setGate(name, value) {
  gates[name] = value;
  console.log(`${name} = ${value}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function request(url, { method = "GET", payload = null, timeoutMs = 8000 } = {}) {
  const body = payload ? Buffer.from(JSON.stringify(payload)) : null;
  return new Promise((resolve) => {
    const req = http.request(url, {
      method,
      headers: body ? { "content-type": "application/json", "content-length": body.length } : {},
    }, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve({
        status: res.statusCode,
        body: Buffer.concat(chunks).toString("utf8").slice(0, 8000),
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
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (pattern.test(entry.name)) count += 1;
      if (entry.isDirectory()) walk(path.join(current, entry.name));
    }
  };
  walk(dir);
  return count;
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

async function closeApp(app) {
  if (!app) return;
  try {
    await app.close();
  } catch {
    /* already closed */
  }
  await waitPortClosed();
}

function prepareProfile(userData) {
  fs.rmSync(userData, { recursive: true, force: true });
  fs.mkdirSync(userData, { recursive: true });
}

async function launchElectron(executable, userData, extraArgs = []) {
  const { _electron: electron } = await import("@playwright/test");
  const args = [...extraArgs, `--user-data-dir=${userData}`];
  const options = { executablePath: executable, args, timeout: 180000 };
  try {
    return await electron.launch(options);
  } catch (err) {
    const text = String(err && err.message ? err.message : err);
    if (!/sandbox|namespace|chrome-sandbox/i.test(text)) throw err;
    evidence.sandboxFirstError = text.slice(0, 800);
    return electron.launch({ ...options, args: ["--no-sandbox", ...args] });
  }
}

async function bootReport() {
  const boot = await request("http://127.0.0.1:8760/api/boot/certification", { timeoutMs: 120000 });
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

function isBundledSecret(name) {
  const lower = name.toLowerCase();
  if (lower === ".env" || lower === ".env.local" || lower === ".env.production") return true;
  if (lower.startsWith("id_rsa") || lower.startsWith("id_ed25519")) return true;
  if (lower === "credentials.json" || lower === "service-account.json") return true;
  return lower.endsWith(".pem") && lower !== "cacert.pem";
}

function matchingNames(dir, test) {
  const found = [];
  const walk = (current) => {
    if (!fs.existsSync(current)) return;
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (test(entry.name)) found.push(path.join(current, entry.name));
      if (entry.isDirectory()) walk(path.join(current, entry.name));
    }
  };
  walk(dir);
  return found;
}

function allowedFreshBootMiss(row) {
  const blob = `${row.system || ""} ${row.check || ""} ${row.detail || ""}`.toLowerCase();
  return blob.includes("background services") || blob.includes("control plane") || blob.includes("8759");
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
  if (process.platform !== "linux" || process.arch !== "x64") {
    setGate("LINUX NATIVE RUNNER", "FAIL");
    throw new Error(`Smoke must run on Linux x64. This process is ${process.platform} ${process.arch}.`);
  }
  setGate("LINUX NATIVE RUNNER", "PASS");
  if (!fs.existsSync(unpackedBin) || !fs.existsSync(appImage) || !fs.existsSync(deb)) {
    setGate("LINUX X64 BUILD", "FAIL");
    throw new Error("AppImage, deb, or unpacked binary is missing");
  }
  setGate("APPIMAGE BUILD", "PASS");
  setGate("DEB BUILD", "PASS");
  setGate("LINUX X64 BUILD", "PASS");
  fs.mkdirSync(evidenceDir, { recursive: true });
  fs.chmodSync(appImage, 0o755);
  fs.chmodSync(unpackedBin, 0o755);
  const chromeSandbox = path.join(unpackedDir, "chrome-sandbox");
  if (fs.existsSync(chromeSandbox)) fs.chmodSync(chromeSandbox, 0o4755);

  const resources = path.join(unpackedDir, "resources");
  const foreign = auditPackagedTree(path.join(resources, "python"), { rejectMac: true });
  setGate("WINDOWS BINARIES BUNDLED", foreign.filter((item) => /\.(exe|dll|pyd)$/i.test(item) || item.toLowerCase().includes("win_amd64")).length);
  setGate("MACOS BINARIES BUNDLED", foreign.filter((item) => item.endsWith(".dylib") || /macosx/i.test(item)).length);
  setGate("PYWIN32 BUNDLED", foreign.some((item) => /\/pywin32([/.-]|$)/i.test(item)) ? 1 : 0);
  setGate("DEV VENV", countNames(resources, /^\.venv$/));
  setGate("DEV .ENV", countNames(resources, /^\.env$/));
  setGate("USER PROJECTS BUNDLED", countNames(resources, /^studio\.db$/));
  setGate("USER LIBRARY ASSETS BUNDLED", countNames(path.join(resources, "studio-api"), /^studio\.db$/));
  setGate("MODEL WEIGHTS BUNDLED", countNames(resources, /\.(safetensors|ckpt|gguf)$/i));
  setGate("BACKUPS BUNDLED", countNames(resources, /\.(bak|backup)$/i));
  const playwrightBundled = matchingNames(resources, (name) => /^playwright/i.test(name));
  const secretsBundled = matchingNames(resources, isBundledSecret);
  evidence.playwrightBundled = playwrightBundled.slice(0, 20);
  evidence.secretsBundled = secretsBundled.slice(0, 20);
  setGate("PLAYWRIGHT ARTIFACTS BUNDLED", playwrightBundled.length);
  setGate("SECRETS BUNDLED", secretsBundled.length);
  setGate("WINDOWS COMFY FILES BUNDLED", countNames(resources, /^ComfyUI$/));

  const python = path.join(resources, "python", "bin", "python");
  const py = spawnSync(python, ["-c", "import platform,sys; print(sys.version.split()[0]); print(platform.machine())"], { encoding: "utf8" });
  evidence.python = (py.stdout || "").trim();
  const pyLines = evidence.python.split(/\n/);
  setGate("PYTHON ARCH", pyLines[1] === "x86_64" ? "x64" : "FAIL");
  setGate("PLATFORM", "linux");

  const fresh = path.join(work, "fresh");
  prepareProfile(fresh);
  const beforeFiles = fs.readdirSync(fresh);
  setGate("ADEPT PROJECTS BEFORE LAUNCH", beforeFiles.length === 0 ? 0 : beforeFiles.length);
  setGate("WINDOWS PROJECT DATA", countNames(fresh, /\.(db|json)$/));

  const bystander = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { stdio: "ignore" });
  const app = await launchElectron(unpackedBin, fresh);
  setGate("ELECTRON PROCESS STARTED", app ? "PASS" : "FAIL");
  const page = await app.firstWindow();
  await page.waitForURL(/127\.0\.0\.1:(?!5173)\d+/, { timeout: 120000 });
  const origin = new URL(page.url()).origin;
  setGate("PACKAGED RENDERER LOADED", origin.includes("127.0.0.1") && !origin.endsWith(":5173") ? "PASS" : "FAIL");
  await page.screenshot({ path: path.join(evidenceDir, "startup.png") });

  const health = await waitHealth();
  setGate("STUDIO API :8760", health.status === 200 ? "PASS" : "FAIL");
  setGate("STUDIO API HEALTH", health.status === 200 ? "PASS" : "FAIL");
  const status = readStatus(fresh);
  const command = String(status?.apiCommand || "");
  evidence.apiCommand = command;
  setGate("VITE :5173 DEPENDENCY", status?.viteContacted === true || origin.endsWith(":5173") ? 1 : 0);
  setGate("DEV VENV DEPENDENCY", command.includes("/.venv/") ? 1 : 0);
  setGate("DEV REPO DEPENDENCY", status?.paths?.devRepoPathDependency ? 1 : 0);
  setGate("SYSTEM PYTHON DEPENDENCY", command.startsWith("/usr/bin/python") ? 1 : 0);
  evidence.sandboxFallback = Boolean(evidence.sandboxFirstError);

  const boot = await bootReport();
  evidence.bootVerdict = boot.body?.verdict || null;
  evidence.bootFailed = boot.failed;
  const supervisorOnly = boot.failed.length > 0 && boot.failed.every(allowedFreshBootMiss);
  setGate("BOOT MANAGER", boot.boot.status === 200 && !boot.fakeGo ? "PASS" : "FAIL");
  setGate("FAILED REQUIRED CHECKS", boot.failed.length);
  setGate("BOOT SUPERVISOR ONLY", supervisorOnly ? "YES" : "NO");
  const cudaClaim = JSON.stringify(boot.body || {}).toLowerCase();
  const nvidia = spawnSync("nvidia-smi", ["-L"], { encoding: "utf8" });
  const cudaAvailable = nvidia.status === 0;
  const falseCuda = !cudaAvailable && /cuda[^"]{0,40}(ready|pass|available)/i.test(cudaClaim);
  setGate("CUDA AVAILABLE", cudaAvailable ? "YES" : "NO");
  setGate("FALSE CUDA READY STATES", falseCuda ? 1 : 0);
  const unexpectedBoot = boot.failed.filter((row) => !allowedFreshBootMiss(row));
  evidence.unexpectedBootFailures = unexpectedBoot;
  console.log(`BOOT UNEXPECTED = ${JSON.stringify(unexpectedBoot)}`);
  setGate("BOOT REQUIRED ASIDE FROM SUPERVISOR", unexpectedBoot.length === 0 ? "PASS" : "FAIL");
  setGate("COMFY TRUTHFUL", /ComfyUI|8188/.test(JSON.stringify(boot.body || {})) ? "PASS" : "FAIL");

  const projects = await request("http://127.0.0.1:8760/api/projects");
  let projectList = [];
  try { projectList = JSON.parse(projects.body || "[]"); } catch { projectList = null; }
  setGate("FRESH PROFILE PROJECT COUNT", Array.isArray(projectList) ? projectList.length : "FAIL");
  setGate("FRESH PROFILE", Array.isArray(projectList) && projectList.length === 0 ? "PASS" : "FAIL");
  const created = await request("http://127.0.0.1:8760/api/projects", { method: "POST", payload: { name: "Linux Smoke" } });
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
    const errors = [];
    const onError = (err) => errors.push(String(err));
    page.on("pageerror", onError);
    try {
      await page.goto(`${origin}${target}`, { waitUntil: "domcontentloaded", timeout: 30000 });
      try {
        await page.waitForFunction(() => {
          const text = (document.body && document.body.innerText) || "";
          return text.trim().length > 20 && !/^\s*Loading\.\.\.\s*$/.test(text);
        }, undefined, { timeout: 20000 });
      } catch (err) {
        errors.push(`still loading ${err}`);
      }
      await page.screenshot({ path: path.join(evidenceDir, `${label.toLowerCase().replace(/\s+/g, "-")}.png`) });
      if (!errors.length && page.url().includes("127.0.0.1")) surfacePass += 1;
      else surfaceErrors.push(`${label} ${errors[0] || page.url()}`);
    } catch (err) {
      surfaceErrors.push(`${label} ${err}`);
    }
    page.off("pageerror", onError);
  }
  evidence.surfaceErrors = surfaceErrors;
  setGate("MAJOR PRODUCT SURFACE SMOKE", surfacePass === surfaces.length ? "PASS" : "FAIL");

  const stream = projectId
    ? await request("http://127.0.0.1:8760/api/codirector/chat/stream", {
      method: "POST",
      timeoutMs: 60000,
      payload: { projectId, messages: [{ role: "user", content: "Say hello in one short sentence." }] },
    })
    : { status: 0, body: "", headers: {} };
  const streamClass = classifyStream(stream);
  evidence.coDirector = { status: stream.status, wiring: streamClass.wiring, execution: streamClass.execution, body: stream.body.slice(0, 500) };
  setGate("CO-DIRECTOR STREAM WIRING", streamClass.wiring);
  setGate("CO-DIRECTOR MODEL EXECUTION", streamClass.execution);

  const logPath = path.join(fresh, "logs", "studio-api.log");
  evidence.apiLogTail = fs.existsSync(logPath) ? fs.readFileSync(logPath, "utf8").slice(-2000) : "";
  await closeApp(app);
  setGate("CLEAN SHUTDOWN", (await waitPortClosed()) ? "PASS" : "FAIL");
  setGate("UNOWNED PROCESS KILLED", alive(bystander.pid) ? "NO" : "YES");

  const reopened = await launchElectron(unpackedBin, fresh);
  const reopenedPage = await reopened.firstWindow();
  await reopenedPage.waitForURL(/127\.0\.0\.1/, { timeout: 120000 });
  await waitHealth();
  const again = await request("http://127.0.0.1:8760/api/projects");
  let still = false;
  try { still = JSON.parse(again.body || "[]").some((row) => row.id === projectId); } catch { still = false; }
  setGate("FIRST PROJECT PERSISTENCE", projectId && still ? "PASS" : "FAIL");
  await closeApp(reopened);

  const listener = spawn(process.execPath, ["-e", "require('net').createServer().listen(8760,'127.0.0.1')"], { stdio: "ignore" });
  await sleep(400);
  const collisionProfile = path.join(work, "collision");
  prepareProfile(collisionProfile);
  const collided = await launchElectron(unpackedBin, collisionProfile);
  await sleep(5000);
  const collisionStatus = readStatus(collisionProfile);
  setGate("8760 COLLISION HANDLING", collisionStatus?.collision === true && alive(listener.pid) ? "PASS" : "FAIL");
  await closeApp(collided);
  listener.kill();
  await waitPortClosed();

  const lossProfile = path.join(work, "loss");
  prepareProfile(lossProfile);
  const lossApp = await launchElectron(unpackedBin, lossProfile);
  await lossApp.firstWindow();
  const lossHealth = await waitHealth();
  const listing = spawnSync("ps", ["-eo", "pid,args"], { encoding: "utf8" }).stdout || "";
  let apiPid = 0;
  for (const line of listing.split("\n")) {
    if (line.includes("uvicorn") && line.includes("8760")) {
      apiPid = Number(line.trim().split(/\s+/)[0]) || 0;
      if (apiPid) break;
    }
  }
  if (apiPid) process.kill(apiPid, "SIGTERM");
  await sleep(2000);
  const afterLoss = await request("http://127.0.0.1:8760/api/healthz", { timeoutMs: 2000 });
  const lossStatus = readStatus(lossProfile);
  setGate("PACKAGED API LOSS DETECTION", lossHealth.status === 200 && afterLoss.status !== 200 ? "PASS" : "FAIL");
  setGate("FALSE HEALTHY STATES", afterLoss.status === 200 || boot.fakeGo ? 1 : 0);
  await closeApp(lossApp);
  if (bystander.pid) bystander.kill();

  const imageProfile = path.join(work, "appimage");
  prepareProfile(imageProfile);
  let imageApp = null;
  try {
    imageApp = await launchElectron(appImage, imageProfile);
  } catch (err) {
    evidence.appImageDirectError = String(err).slice(0, 500);
    imageApp = await launchElectron(appImage, imageProfile, ["--appimage-extract-and-run"]);
    evidence.appImageMode = "extract-and-run";
  }
  const imagePage = await imageApp.firstWindow();
  await imagePage.waitForURL(/127\.0\.0\.1/, { timeout: 120000 });
  const imageHealth = await waitHealth();
  setGate("APPIMAGE EXECUTION", imageHealth.status === 200 ? "PASS" : "FAIL");
  await closeApp(imageApp);

  const packageName = (spawnSync("dpkg-deb", ["-f", deb, "Package"], { encoding: "utf8" }).stdout || "adept-ui").trim() || "adept-ui";
  evidence.debPackage = packageName;
  const installed = spawnSync("sudo", ["dpkg", "-i", deb], { encoding: "utf8" });
  evidence.debInstallLog = `${installed.stdout || ""}\n${installed.stderr || ""}`.slice(-2000);
  const listingDeb = spawnSync("dpkg", ["-L", packageName], { encoding: "utf8" }).stdout || "";
  const desktopFile = listingDeb.split("\n").find((line) => line.endsWith(".desktop")) || "";
  const installedBin = listingDeb
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.endsWith("/Adept UI"))
    .sort((a, b) => b.length - a.length)[0] || "";
  let desktopText = "";
  if (desktopFile && fs.existsSync(desktopFile)) desktopText = fs.readFileSync(desktopFile, "utf8");
  evidence.desktop = desktopText;
  const desktopOk = /Name=Adept UI/.test(desktopText) && /Terminal=false/.test(desktopText) && /Icon=/.test(desktopText);
  setGate("DEB INSTALL", installed.status === 0 && installedBin ? "PASS" : "FAIL");
  setGate("DESKTOP ENTRY", desktopOk ? "PASS" : "FAIL");
  const debProfile = path.join(work, "deb");
  prepareProfile(debProfile);
  fs.writeFileSync(path.join(debProfile, "keep.txt"), "keep");
  let debHealth = { status: 0 };
  if (installedBin) {
    const debApp = await launchElectron(installedBin, debProfile);
    await debApp.firstWindow();
    debHealth = await waitHealth();
    const debStatus = readStatus(debProfile);
    setGate("USER DATA OUTSIDE PACKAGE", debStatus?.paths?.userData && !String(debStatus.paths.userData).startsWith("/opt") ? "PASS" : "FAIL");
    await closeApp(debApp);
  } else {
    setGate("USER DATA OUTSIDE PACKAGE", "FAIL");
  }
  setGate("DEB APPLICATION LAUNCH", debHealth.status === 200 ? "PASS" : "FAIL");
  const removed = spawnSync("sudo", ["dpkg", "-r", packageName], { encoding: "utf8" });
  const stillInstalled = spawnSync("dpkg", ["-s", packageName], { encoding: "utf8" });
  setGate("DEB UNINSTALL", removed.status === 0 && stillInstalled.status !== 0 ? "PASS" : "FAIL");
  setGate("DEFAULT UNINSTALL PRESERVES USER DATA", fs.existsSync(path.join(debProfile, "keep.txt")) ? "PASS" : "FAIL");

  evidence.appImage = hashFile(appImage);
  evidence.deb = hashFile(deb);
  evidence.gates = gates;
  console.log(JSON.stringify({ appImage: evidence.appImage, deb: evidence.deb, bootVerdict: evidence.bootVerdict, surfaces: surfacePass }, null, 2));

  const numericFails = ["PYWIN32 BUNDLED", "VITE :5173 DEPENDENCY", "DEV VENV DEPENDENCY", "DEV REPO DEPENDENCY", "SYSTEM PYTHON DEPENDENCY", "FALSE CUDA READY STATES", "FALSE HEALTHY STATES", "WINDOWS BINARIES BUNDLED", "MACOS BINARIES BUNDLED", "USER PROJECTS BUNDLED", "USER LIBRARY ASSETS BUNDLED", "MODEL WEIGHTS BUNDLED", "BACKUPS BUNDLED", "PLAYWRIGHT ARTIFACTS BUNDLED", "SECRETS BUNDLED", "WINDOWS COMFY FILES BUNDLED", "DEV VENV", "DEV .ENV", "ADEPT PROJECTS BEFORE LAUNCH", "WINDOWS PROJECT DATA"];
  const passFails = ["ELECTRON PROCESS STARTED", "PACKAGED RENDERER LOADED", "STUDIO API :8760", "BOOT MANAGER", "BOOT REQUIRED ASIDE FROM SUPERVISOR", "FRESH PROFILE", "FIRST PROJECT PERSISTENCE", "MAJOR PRODUCT SURFACE SMOKE", "APPIMAGE EXECUTION", "DEB INSTALL", "DEB APPLICATION LAUNCH", "DEB UNINSTALL", "DEFAULT UNINSTALL PRESERVES USER DATA", "CLEAN SHUTDOWN", "8760 COLLISION HANDLING", "PACKAGED API LOSS DETECTION", "COMFY TRUTHFUL", "DESKTOP ENTRY", "CO-DIRECTOR STREAM WIRING"];
  const bad = numericFails.some((name) => gates[name] !== 0)
    || passFails.some((name) => gates[name] !== "PASS")
    || gates["UNOWNED PROCESS KILLED"] === "YES"
    || gates["PYTHON ARCH"] !== "x64"
    || gates["PLATFORM"] !== "linux";
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
