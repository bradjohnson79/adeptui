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
// Build + stage the Universal Launcher before packaging. The afterPack swap
// renames Electron to Adept UI.bin and installs the launcher as Adept UI.
run("python3", ["install/launcher/build.py", "--stage"]);
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
// After the afterPack swap, the real Electron ELF is Adept UI.bin; "Adept UI" is the launcher.
const unpacked = path.join(root, "electron", "dist", "linux-unpacked", "Adept UI.bin");
if (!fs.existsSync(unpacked)) {
  console.error("LINUX X64 BUILD = FAIL");
  console.error("unpacked Adept UI.bin missing");
  process.exit(1);
}
fs.chmodSync(unpacked, 0o755);
console.log("LINUX X64 BUILD = PASS");
console.log(unpacked);
const terminalRevision = process.env.ADEPT_TERMINAL_REVISION || "r7";
const terminalZip = path.join(root, "electron", "dist", `Adept.UI-${version}-terminal-${terminalRevision}-linux-x64.zip`);
run("python3", [
  "electron/scripts/pack-terminal-archive.py",
  path.join(root, "electron", "dist", "linux-unpacked"),
  terminalZip,
]);
