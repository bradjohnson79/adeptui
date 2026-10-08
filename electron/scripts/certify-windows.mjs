import { spawn, spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { logicalSnapshot, preservationVerdict } from "./db-preservation.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const unpackedSrc = path.join(root, "electron", "dist", "win-unpacked");
const isolated = path.join(process.env.TEMP || process.env.TMP, "adept-ui-isolated-win");
const freshProfile = path.join(process.env.TEMP || process.env.TMP, "adept-ui-profile-fresh");
const existingProfile = path.join(process.env.TEMP || process.env.TMP, "adept-ui-profile-existing");
const liveDb = path.join(root, "data", "studio.db");
const repoMarker = path.resolve(root).toLowerCase();

function get(url, timeoutMs = 8000, maxBody = 1200) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8").slice(0, maxBody) }));
    });
    req.on("error", (err) => resolve({ status: 0, body: String(err.message) }));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve({ status: 0, body: "timeout" });
    });
  });
}

function commandLine(pid) {
  if (!pid) return "";
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter "ProcessId=${Number(pid)}").CommandLine`],
    { encoding: "utf8", windowsHide: true },
  );
  return (result.stdout || "").trim();
}

function netstat() {
  const result = spawnSync("netstat.exe", ["-ano", "-p", "tcp"], { encoding: "utf8", windowsHide: true });
  return result.stdout || "";
}

function listeningPid(text, port) {
  for (const line of text.split(/\r?\n/)) {
    if (!line.includes(`:${port}`) || !/\bLISTENING\b/i.test(line)) continue;
    const parts = line.trim().split(/\s+/);
    return Number(parts[parts.length - 1]) || null;
  }
  return null;
}

function hashFile(file) {
  if (!fs.existsSync(file)) return null;
  const data = fs.readFileSync(file);
  return { bytes: data.length, sha256: crypto.createHash("sha256").update(data).digest("hex") };
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function launch(exe, userData, { reset = true } = {}) {
  if (reset) {
    fs.rmSync(userData, { recursive: true, force: true });
    fs.mkdirSync(userData, { recursive: true });
  }
  const child = spawn(exe, [`--user-data-dir=${userData}`], {
    cwd: path.dirname(exe),
    windowsHide: false,
    stdio: "ignore",
    detached: false,
  });
  return child;
}

function post(url, payload, timeoutMs = 20000) {
  const body = JSON.stringify(payload);
  return new Promise((resolve) => {
    const req = http.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
    }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", (err) => resolve({ status: 0, body: String(err.message) }));
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve({ status: 0, body: "timeout" }); });
    req.end(body);
  });
}

async function waitStatus(userData, timeoutMs = 150000) {
  const file = path.join(userData, "desktop-status.json");
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) {
      try {
        return JSON.parse(fs.readFileSync(file, "utf8"));
      } catch {
        /* retry */
      }
    }
    await sleep(500);
  }
  return null;
}

function stopPid(pid) {
  if (!pid) return;
  spawnSync("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { windowsHide: true });
}

function auditTree(dir) {
  const hits = { env: 0, db: 0, weights: 0, playwright: 0, backups: 0, secrets: 0 };
  const walk = (current) => {
    let entries = [];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      const lower = entry.name.toLowerCase();
      if (entry.isDirectory()) {
        if (lower.includes("playwright")) hits.playwright += 1;
        if (lower === "backups" || lower === "backup") hits.backups += 1;
        walk(full);
        continue;
      }
      if (lower === ".env" || lower.startsWith(".env.")) hits.env += 1;
      if (lower.endsWith(".db")) hits.db += 1;
      if (/\.(safetensors|ckpt|gguf|onnx)$/.test(lower)) hits.weights += 1;
      if (lower.includes("credential") || lower.endsWith(".pem") || lower.endsWith(".key")) hits.secrets += 1;
    }
  };
  walk(dir);
  return hits;
}

function touchesRepo(value) {
  return String(value || "").toLowerCase().includes(repoMarker);
}

const beforeNet = netstat();
const before = {
  comfyPid: listeningPid(beforeNet, 8188),
  apiPid: listeningPid(beforeNet, 8758),
  vitePid: listeningPid(beforeNet, 5173),
  liveDb: hashFile(liveDb),
  liveLogical: logicalSnapshot(liveDb),
  comfyHealth: await get("http://127.0.0.1:8188/system_stats"),
};

if (!fs.existsSync(path.join(unpackedSrc, "Adept UI.exe"))) {
  console.error("unpacked exe missing — run desktop:build:win first");
  process.exit(1);
}

fs.rmSync(isolated, { recursive: true, force: true });
fs.cpSync(unpackedSrc, isolated, { recursive: true });
const exe = path.join(isolated, "Adept UI.exe");
const audit = auditTree(path.join(isolated, "resources"));

const fresh = launch(exe, freshProfile);
const freshStatus = await waitStatus(freshProfile);
let desktopHealth = { status: 0, body: "" };
for (let i = 0; i < 120; i += 1) {
  desktopHealth = await get("http://127.0.0.1:8760/api/healthz");
  if (desktopHealth.status === 200) break;
  const statusFile = path.join(freshProfile, "desktop-status.json");
  if (fs.existsSync(statusFile)) {
    try {
      if (JSON.parse(fs.readFileSync(statusFile, "utf8")).apiExited) break;
    } catch {
      /* the status file is still being written */
    }
  }
  await sleep(1500);
}
const devHealth = await get("http://127.0.0.1:8758/api/healthz");
let renderer = null;
let apiProbe = null;
let mediaProbe = null;
let projectsProbe = null;
let bootProbe = null;
if (freshStatus?.rendererOrigin) {
  renderer = await get(`${freshStatus.rendererOrigin}/`);
  apiProbe = await get(`${freshStatus.rendererOrigin}/api/healthz`);
  mediaProbe = await get(`${freshStatus.rendererOrigin}/media/__port_probe__`);
  projectsProbe = await get(`${freshStatus.rendererOrigin}/api/projects`);
  bootProbe = await get(`${freshStatus.rendererOrigin}/api/boot/certification`, 120000, 200000);
}
let bootVerdict = null;
let bootFailed = [];
if (bootProbe?.body) {
  try {
    const parsed = JSON.parse(bootProbe.body);
    bootVerdict = parsed.verdict || null;
    bootFailed = (parsed.checks || []).filter((row) => row.required && row.result !== "PASS").map((row) => row.id);
  } catch {
    bootVerdict = null;
  }
  bootProbe = { status: bootProbe.status, body: bootProbe.body.slice(0, 500) };
}
let projectId = null;
let projectCreated = false;
let setupFirstRunComplete = null;
if (desktopHealth.status === 200) {
  const created = await post("http://127.0.0.1:8760/api/projects", { name: "Packaged Boot" });
  try {
    projectId = JSON.parse(created.body).id || null;
    projectCreated = created.status === 200 && Boolean(projectId);
  } catch {
    projectCreated = false;
  }
  const setup = await get("http://127.0.0.1:8760/api/setup/status", 30000, 500000);
  try { setupFirstRunComplete = JSON.parse(setup.body).firstRunSetupComplete; } catch { setupFirstRunComplete = null; }
}
const desktopPid = listeningPid(netstat(), 8760);
const desktopCommand = commandLine(desktopPid);
const statusAfterProbes = JSON.parse(fs.readFileSync(path.join(freshProfile, "desktop-status.json"), "utf8"));
stopPid(fresh.pid);
for (let i = 0; i < 20; i += 1) {
  if (!listeningPid(netstat(), 8760)) break;
  await sleep(500);
}
let projectReopened = false;
if (projectId) {
  const reopened = launch(exe, freshProfile, { reset: false });
  let reopenedHealth = { status: 0 };
  for (let i = 0; i < 80; i += 1) {
    reopenedHealth = await get("http://127.0.0.1:8760/api/healthz");
    if (reopenedHealth.status === 200) break;
    await sleep(1500);
  }
  if (reopenedHealth.status === 200) {
    const again = await get("http://127.0.0.1:8760/api/projects", 20000, 200000);
    try {
      projectReopened = JSON.parse(again.body).some((row) => row.id === projectId);
    } catch {
      projectReopened = false;
    }
  }
  stopPid(reopened.pid);
  for (let i = 0; i < 20; i += 1) {
    if (!listeningPid(netstat(), 8760)) break;
    await sleep(500);
  }
}

const liveAfterFresh = hashFile(liveDb);
fs.rmSync(existingProfile, { recursive: true, force: true });
const existingData = path.join(existingProfile, "data");
fs.mkdirSync(existingData, { recursive: true });
let copyProof = null;
if (fs.existsSync(liveDb)) {
  const dest = path.join(existingData, "studio.db");
  fs.copyFileSync(liveDb, dest);
  const copied = hashFile(dest);
  const live = hashFile(liveDb);
  copyProof = {
    copiedMatches: Boolean(copied && live && copied.sha256 === live.sha256),
    liveUnchanged: Boolean(before.liveDb && live && before.liveDb.sha256 === live.sha256),
    copyPath: dest,
  };
}
const existing = launch(exe, existingProfile, { reset: false });
const existingBeforeLaunchDb = hashFile(liveDb);
const existingStatus = await waitStatus(existingProfile);
stopPid(existing.pid);
await sleep(500);
if (copyProof) {
  copyProof.profileDataDir = existingStatus?.paths?.dataDir || null;
  copyProof.profilePointsAtCopy = String(existingStatus?.paths?.dataDir || "").toLowerCase() === existingData.toLowerCase();
  copyProof.liveAfterSecondLaunch = hashFile(liveDb);
  copyProof.liveStillUnchanged = Boolean(
    existingBeforeLaunchDb && copyProof.liveAfterSecondLaunch && existingBeforeLaunchDb.sha256 === copyProof.liveAfterSecondLaunch.sha256,
  );
}

const pathValues = freshStatus?.paths ? Object.values(freshStatus.paths) : [];
const repoHits = pathValues.filter((value) => touchesRepo(value)).length;
const command = String(freshStatus?.apiCommand || "");
const venvHit = command.toLowerCase().includes(`${path.sep}studio-api${path.sep}.venv`.toLowerCase()) || command.toLowerCase().includes("studio-api\\.venv");
const afterNet = netstat();
const after = {
  comfyPid: listeningPid(afterNet, 8188),
  apiPid: listeningPid(afterNet, 8758),
  comfyHealth: await get("http://127.0.0.1:8188/system_stats"),
  liveDb: hashFile(liveDb),
  liveLogical: logicalSnapshot(liveDb),
};

const result = {
  isolatedExe: exe,
  freshStatus,
  renderer,
  apiProbe,
  mediaProbe,
  projectsProbe,
  bootProbe,
  desktopHealth,
  devHealth,
  desktopPid,
  desktopCommand,
  proxy: statusAfterProbes?.proxy || null,
  endpoint: statusAfterProbes?.endpoint || null,
  audit,
  copyProof,
  repoPathHitsInLedger: repoHits,
  viteContacted: freshStatus?.viteContacted === true ? 1 : 0,
  rendererPort: freshStatus?.rendererOrigin ? new URL(freshStatus.rendererOrigin).port : null,
  devVenvDependency: venvHit ? 1 : 0,
  devRepoPathDependency: repoHits > 0 || freshStatus?.paths?.devRepoPathDependency ? 1 : 0,
  collision: Boolean(freshStatus?.collision),
  apiOwned: Boolean(freshStatus?.apiOwned),
  bootVerdict,
  bootFailed,
  projectId,
  projectCreated,
  projectReopened,
  setupFirstRunComplete,
  backgroundServices: freshStatus?.backgroundServices || null,
  before,
  after,
  comfyRestarted: before.comfyPid !== after.comfyPid,
  liveDbUnchanged: Boolean(before.liveDb && after.liveDb && before.liveDb.sha256 === after.liveDb.sha256),
  liveDbPreservation: preservationVerdict(before.liveLogical, after.liveLogical),
  apiPidUnchanged: before.apiPid === after.apiPid,
};
fs.mkdirSync(path.join(root, "electron", "build"), { recursive: true });
fs.writeFileSync(path.join(root, "electron", "build", "cert-result.json"), JSON.stringify(result, null, 2));
console.log(JSON.stringify({
  rendererStatus: result.renderer?.status || 0,
  rendererPort: result.rendererPort,
  viteContacted: result.viteContacted,
  devVenvDependency: result.devVenvDependency,
  devRepoPathDependency: result.devRepoPathDependency,
  collision: result.collision,
  apiOwned: result.apiOwned,
  desktopHealth: result.desktopHealth?.status || 0,
  devHealth: result.devHealth?.status || 0,
  desktopPid: result.desktopPid,
  desktopPortInCommand: String(result.desktopCommand || "").includes("--port 8760"),
  proxy: result.proxy,
  bootStudioApi: (() => {
    try { return JSON.parse(result.bootProbe?.body || "{}").studioApi || null; } catch { return null; }
  })(),
  comfyRestarted: result.comfyRestarted,
  liveDbUnchanged: result.liveDbUnchanged,
  apiPidUnchanged: result.apiPidUnchanged,
  audit: result.audit,
}, null, 2));
