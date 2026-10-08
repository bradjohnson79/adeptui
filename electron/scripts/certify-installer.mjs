import { spawn, spawnSync } from "node:child_process";
import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { logicalSnapshot, preservationVerdict } from "./db-preservation.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const setup = path.join(root, "electron", "dist", `Adept UI-Setup-${version}-win-x64.exe`);
const installDir = path.join(process.env.TEMP, "adept-install-a");
const markerDir = path.join(process.env.APPDATA, "Adept UI");
const marker = path.join(markerDir, "cert-disposable-project.txt");
const liveDb = path.join(root, "data", "studio.db");

function hashFile(file) {
  if (!fs.existsSync(file)) return null;
  const data = fs.readFileSync(file);
  return { bytes: data.length, sha256: crypto.createHash("sha256").update(data).digest("hex") };
}

function listeningPid(port) {
  const text = spawnSync("netstat.exe", ["-ano", "-p", "tcp"], { encoding: "utf8", windowsHide: true }).stdout || "";
  for (const line of text.split(/\r?\n/)) {
    if (!line.includes(`:${port}`) || !/\bLISTENING\b/i.test(line)) continue;
    const parts = line.trim().split(/\s+/);
    return Number(parts[parts.length - 1]) || null;
  }
  return null;
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

spawnSync("powershell.exe", ["-NoProfile", "-Command",
  "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*adept-ui-isolated-win*' -or $_.ExecutablePath -like '*adept-install-a*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
], { windowsHide: true });
for (const port of [8760, 8759, 8779]) {
  const pid = listeningPid(port);
  const cmd = commandLine(pid).toLowerCase();
  if (pid && (cmd.includes("adept-ui-isolated-win") || cmd.includes("adept-install-a"))) {
    spawnSync("taskkill.exe", ["/PID", String(pid), "/T", "/F"], { windowsHide: true });
  }
}

const before = { liveDb: hashFile(liveDb), liveLogical: logicalSnapshot(liveDb), comfyPid: listeningPid(8188), apiPid: listeningPid(8758) };
fs.rmSync(installDir, { recursive: true, force: true });
const installA = spawnSync(setup, ["/S", `/D=${installDir}`], { windowsHide: true, timeout: 180000 });
const exe = path.join(installDir, "Adept UI.exe");
const exeAfterA = fs.existsSync(exe);
fs.mkdirSync(markerDir, { recursive: true });
fs.writeFileSync(marker, "disposable-project-marker");
const installB = spawnSync(setup, ["/S", `/D=${installDir}`], { windowsHide: true, timeout: 180000 });
const markerAfterUpgrade = fs.existsSync(marker) ? fs.readFileSync(marker, "utf8") : null;
const exeAfterB = fs.existsSync(exe);
const userData = path.join(process.env.TEMP, "adept-ui-installed-profile");
fs.rmSync(userData, { recursive: true, force: true });
fs.mkdirSync(userData, { recursive: true });
const child = spawn(exe, [`--user-data-dir=${userData}`], { cwd: installDir, windowsHide: false, stdio: "ignore" });
const statusFile = path.join(userData, "desktop-status.json");
const statusDeadline = Date.now() + 150000;
while (Date.now() < statusDeadline && !fs.existsSync(statusFile)) {
  await new Promise((r) => setTimeout(r, 500));
}
function get(url, timeoutMs = 20000) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", (err) => resolve({ status: 0, body: String(err.message) }));
    req.setTimeout(timeoutMs, () => { req.destroy(); resolve({ status: 0, body: "timeout" }); });
  });
}
let installedHealth = { status: 0, body: "" };
for (let i = 0; i < 120; i += 1) {
  installedHealth = await get("http://127.0.0.1:8760/api/healthz");
  if (installedHealth.status === 200) break;
  await new Promise((r) => setTimeout(r, 1500));
}
const installedBoot = await get("http://127.0.0.1:8760/api/boot/certification", 120000);
const installedDiag = await get("http://127.0.0.1:8760/api/diagnostics/run", 60000);
const installedProjects = await get("http://127.0.0.1:8760/api/projects");
let installedBootJson = null;
let installedDiagPort = null;
let installedProjectCount = null;
try { installedBootJson = JSON.parse(installedBoot.body); } catch { installedBootJson = null; }
try { installedDiagPort = JSON.parse(installedDiag.body).layers.apiDirect.tcp.port; } catch { installedDiagPort = null; }
try { installedProjectCount = JSON.parse(installedProjects.body).length; } catch { installedProjectCount = null; }
const installedStatus = fs.existsSync(path.join(userData, "desktop-status.json"))
  ? JSON.parse(fs.readFileSync(path.join(userData, "desktop-status.json"), "utf8"))
  : null;
spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true });
const uninstaller = path.join(installDir, "Uninstall Adept UI.exe");
const uninstall = fs.existsSync(uninstaller)
  ? spawnSync(uninstaller, ["/S"], { windowsHide: true, timeout: 180000 })
  : { status: null, error: "uninstaller missing" };
for (let i = 0; i < 20 && fs.existsSync(exe); i += 1) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500);
}
const after = {
  liveDb: hashFile(liveDb),
  liveLogical: logicalSnapshot(liveDb),
  comfyPid: listeningPid(8188),
  apiPid: listeningPid(8758),
  markerRemains: fs.existsSync(marker),
  installDirRemains: fs.existsSync(installDir),
  exeAfterUninstall: fs.existsSync(exe),
};
if (fs.existsSync(marker)) fs.rmSync(marker, { force: true });
const setupBytes = fs.readFileSync(setup);
const result = {
  installA: installA.status,
  installB: installB.status,
  exeAfterA,
  exeAfterB,
  markerAfterUpgrade,
  uninstallStatus: uninstall.status,
  before,
  after,
  liveDbUnchanged: Boolean(before.liveDb && after.liveDb && before.liveDb.sha256 === after.liveDb.sha256),
  liveDbPreservation: preservationVerdict(before.liveLogical, after.liveLogical),
  comfyUnchanged: before.comfyPid === after.comfyPid,
  apiUnchanged: before.apiPid === after.apiPid,
  deleteAppDataStringInInstaller: setupBytes.includes(Buffer.from("deleteAppDataOnUninstall")),
  installedHealth: installedHealth.status,
  installedBoot: installedBootJson && installedBootJson.verdict,
  installedStudioApi: installedBootJson && installedBootJson.studioApi,
  installedDiagPort,
  installedProjectCount,
  installedEndpoint: installedStatus && installedStatus.endpoint,
  installedCommand: installedStatus && installedStatus.apiCommand,
  backgroundServicesHealthy: Boolean(installedStatus?.backgroundServices?.healthy),
  backgroundServicesPort: installedStatus?.backgroundServices?.port || null,
  backgroundServicesCollision: Boolean(installedStatus?.backgroundServices?.collision),
  backgroundServicesReason: installedStatus?.backgroundServices?.reason || null,
};
fs.writeFileSync(path.join(root, "electron", "build", "installer-cert.json"), JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
