import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", cwd: root, ...opts });
  if (result.status !== 0) process.exit(result.status || 1);
}

if (process.platform !== "darwin" || process.arch !== "arm64") {
  console.error("MACOS NATIVE RUNNER = FAIL");
  console.error(`Adept UI.app must be built on Apple Silicon. This process is ${process.platform} ${process.arch}.`);
  process.exit(1);
}

console.log("MACOS NATIVE RUNNER = PASS");
// Build + stage the Universal Adept Launcher Mach-O before packaging. The
// launcher is installed as Contents/MacOS/Adept UI (matching CFBundleExecutable);
// the real Electron binary is renamed to Adept UI.bin in the post-build step.
run("python3", ["install/launcher/build.py", "--stage"]);
run(process.execPath, ["electron/scripts/stage-packaged-runtime-darwin.mjs"]);
const py = path.join(root, "electron", "build", "python-darwin-arm64", "bin", "python");
const api = path.join(root, "electron", "build", "studio-api", "app", "main.py");
if (!fs.existsSync(py) || !fs.existsSync(api)) {
  console.error("STUDIO API STAGED = FAIL");
  process.exit(1);
}
const vite = path.join(root, "studio-web", "node_modules", "vite", "bin", "vite.js");
run(process.execPath, [vite, "build"], { cwd: path.join(root, "studio-web") });
const builder = path.join(root, "node_modules", "electron-builder", "cli.js");
run(process.execPath, [builder, "--mac", "--arm64", "--config", "electron/builder.config.cjs"], {
  env: { ...process.env, CSC_IDENTITY_AUTO_DISCOVERY: "false" },
});

const version = JSON.parse(fs.readFileSync(path.join(root, "electron", "version.json"), "utf8")).version;
const candidates = [
  path.join(root, "electron", "dist", "mac-arm64", "Adept UI.app"),
  path.join(root, "electron", "dist", "mac", "Adept UI.app"),
];
const app = candidates.find((item) => fs.existsSync(item));
if (!app) {
  console.error("Adept UI.app BUILT = FAIL");
  process.exit(1);
}
console.log("Adept UI.app BUILT = PASS");
console.log(app);
const terminalRevision = process.env.ADEPT_TERMINAL_REVISION || "r7";
const terminalZip = path.join(root, "electron", "dist", `Adept.UI-${version}-terminal-${terminalRevision}-mac-arm64.zip`);
// ditto keeps the ad-hoc bundle seal. Python's zipfile does not.
run("ditto", ["-c", "-k", "--keepParent", app, terminalZip]);
const zipCheck = path.join(root, "electron", "build", "zip-verify");
fs.rmSync(zipCheck, { recursive: true, force: true });
fs.mkdirSync(zipCheck, { recursive: true });
run("ditto", ["-x", "-k", terminalZip, zipCheck]);
run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", path.join(zipCheck, "Adept UI.app")]);
console.log("MACOS ARCHIVE SIGNATURE = PASS");
