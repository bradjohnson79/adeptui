import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const unpacked = JSON.parse(fs.readFileSync(path.join(root, "electron", "build", "cert-result.json"), "utf8"));
const installed = JSON.parse(fs.readFileSync(path.join(root, "electron", "build", "installer-cert.json"), "utf8"));
const failures = [];

if (unpacked.desktopHealth?.status !== 200) failures.push("unpacked health");
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
if (installed.exeAfterUninstall !== false) failures.push("executable remained after uninstall");
if (installed.installedHealth !== 200) failures.push("installed health");
if (installed.installedBoot !== "GO") failures.push(`installed boot ${installed.installedBoot}`);
if (installed.installedDiagPort !== 8760) failures.push("installed API port");
if (installed.comfyUnchanged !== true) failures.push("installer changed ComfyUI");
if (installed.apiUnchanged !== true) failures.push("installer changed development API");

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("WINDOWS PACKAGED BOOT = GO");
