import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", cwd: root, windowsHide: true, shell: false, ...opts });
  if (result.status !== 0) process.exit(result.status || 1);
}

// Headless Python for the launcher build (no console window). Prefer pythonw.
function pythonw() {
  const venv = path.join(root, "studio-api", ".venv", "Scripts", "pythonw.exe");
  if (fs.existsSync(venv)) return venv;
  return "pythonw";
}

run("node", ["electron/scripts/make-icons.mjs"]);
// Build + stage the Universal Adept Launcher (single update authority) before packaging.
run(pythonw(), ["install/launcher/build.py", "--stage"]);
run(process.execPath, ["electron/scripts/stage-packaged-runtime.mjs"]);
const vite = path.join(root, "studio-web", "node_modules", "vite", "bin", "vite.js");
run(process.execPath, [vite, "build"], { cwd: path.join(root, "studio-web") });
const builder = path.join(root, "node_modules", "electron-builder", "cli.js");
run(process.execPath, [builder, "--win", "--config", "electron/builder.config.cjs"], {
  env: { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: "false" },
});
const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const setup = path.join(root, "electron", "dist", `Adept UI-Setup-${version}-win-x64.exe`);
const unpacked = path.join(root, "electron", "dist", "win-unpacked", "Adept UI.exe");
if (!fs.existsSync(unpacked)) {
  console.error("unpacked exe missing");
  process.exit(1);
}
console.log(`unpacked ${unpacked}`);
console.log(fs.existsSync(setup) ? `installer ${setup}` : "installer missing");
