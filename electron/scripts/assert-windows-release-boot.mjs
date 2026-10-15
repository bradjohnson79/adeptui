import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const unpacked = JSON.parse(fs.readFileSync(path.join(root, "electron", "build", "cert-result.json"), "utf8"));
const installed = JSON.parse(fs.readFileSync(path.join(root, "electron", "build", "installer-cert.json"), "utf8"));
const failures = [];

if (unpacked.desktopHealth?.status !== 200) failures.push("unpacked health");
if (unpacked.freshStatus?.backgroundServices?.healthy !== true) failures.push("unpacked background services");
if (unpacked.bootVerdict !== "GO") failures.push(`unpacked boot ${unpacked.bootVerdict}`);
if (unpacked.projectCreated !== true || unpacked.projectReopened !== true) failures.push("project create or reopen");
if (unpacked.setupFirstRunComplete !== false) failures.push("fresh setup handoff");
if (unpacked.collision !== false) failures.push("unpacked port 8760 collision");
if (unpacked.viteContacted !== 0) failures.push("vite contacted");
if (unpacked.devVenvDependency !== 0) failures.push("developer venv used");
if (unpacked.devRepoPathDependency !== 0) failures.push("developer repo used");
if (unpacked.apiPidUnchanged !== true) failures.push("development API process changed");
if (unpacked.comfyRestarted !== false) failures.push("ComfyUI process changed");
if (installed.installA !== 0) failures.push("install");
if (installed.installB !== 0) failures.push("reinstall");
if (installed.uninstallStatus !== 0) failures.push("uninstall");
if (installed.exeAfterA !== true || installed.exeAfterB !== true) failures.push("installed executable missing");
if (installed.after?.exeAfterUninstall !== false) failures.push("executable remained after uninstall");
if (installed.installedHealth !== 200) failures.push("installed health");
if (installed.installedBoot !== "GO") failures.push(`installed boot ${installed.installedBoot}`);
if (installed.backgroundServicesHealthy !== true) failures.push("installed background services");
if (installed.installedDiagPort !== 8760) failures.push("installed API port");
if (installed.comfyUnchanged !== true) failures.push("installer changed ComfyUI");
if (installed.apiUnchanged !== true) failures.push("installer changed development API");
const setupNames = [
  "API PROFILE OMITS COMFY",
  "OFFICIAL COMFY DOWNLOAD URL",
  "CONNECT REJECTS NON COMFY FOLDER",
  "CONNECT EXISTING LEAVES FILES",
  "COMFY INSTALL NOT FABRICATED",
  "LOCAL REQUIREMENT MATCHES COMFY HEALTH",
  "HYBRID REQUIREMENT MATCHES COMFY HEALTH",
  "RENDERER SHIPS COMFY PREREQUISITE",
];
for (const name of setupNames) {
  if (unpacked.setupGates?.[name] !== "PASS") failures.push(`unpacked ${name}`);
  if (installed.setupGates?.[name] !== "PASS") failures.push(`installed ${name}`);
}
if (!["PRESENT", "ABSENT"].includes(unpacked.setupGates?.["COMFY DETECTED WHEN REACHABLE"])) failures.push("unpacked comfy detection");
if (installed.setupGates?.["DESKTOP SHORTCUT"] !== "PASS") failures.push("desktop shortcut");

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("WINDOWS PACKAGED BOOT = GO");
