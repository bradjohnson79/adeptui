import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", cwd: root, ...opts });
  if (result.status !== 0) process.exit(result.status || 1);
}

if (process.platform !== "linux" || process.arch !== "x64") {
  console.error("LINUX NATIVE RUNNER = FAIL");
  console.error(`Adept UI for Linux must be built on Linux x64. This process is ${process.platform} ${process.arch}.`);
  process.exit(1);
}

console.log("LINUX NATIVE RUNNER = PASS");
run(process.execPath, ["electron/scripts/audit-linux-wheels.mjs"]);
run(process.execPath, ["electron/scripts/stage-packaged-runtime-linux.mjs"]);
const py = path.join(root, "electron", "build", "python-linux-x64", "bin", "python");
const api = path.join(root, "electron", "build", "studio-api", "app", "main.py");
if (!fs.existsSync(py) || !fs.existsSync(api)) {
  console.error("STUDIO API STAGED = FAIL");
  process.exit(1);
}
const vite = path.join(root, "studio-web", "node_modules", "vite", "bin", "vite.js");
run(process.execPath, [vite, "build"], { cwd: path.join(root, "studio-web") });
const builder = path.join(root, "node_modules", "electron-builder", "cli.js");
run(process.execPath, [builder, "--linux", "--x64", "--config", "electron/builder.config.cjs"], {
  env: { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: "false" },
});

const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const unpacked = path.join(root, "electron", "dist", "linux-unpacked", "Adept UI");
const appImage = path.join(root, "electron", "dist", `Adept UI-${version}-linux-x64.AppImage`);
const deb = path.join(root, "electron", "dist", `Adept UI-${version}-linux-x64.deb`);
const rpm = path.join(root, "electron", "dist", `Adept.UI-${version}-linux-x64.rpm`);
if (!fs.existsSync(unpacked) || !fs.existsSync(appImage) || !fs.existsSync(deb) || !fs.existsSync(rpm)) {
  console.error("LINUX X64 BUILD = FAIL");
  console.error(JSON.stringify({
    unpacked: fs.existsSync(unpacked),
    appImage: fs.existsSync(appImage),
    deb: fs.existsSync(deb),
    rpm: fs.existsSync(rpm),
  }));
  process.exit(1);
}
fs.chmodSync(appImage, 0o755);
fs.chmodSync(unpacked, 0o755);
console.log("LINUX X64 BUILD = PASS");
console.log("APPIMAGE BUILD = PASS");
console.log("DEB BUILD = PASS");
console.log("RPM BUILD = PASS");
console.log(appImage);
console.log(deb);
console.log(rpm);
