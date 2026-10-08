import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderSelectedRequirements } from "../packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const venvDir = path.join(root, "studio-api", ".venv");
const sitePackages = path.join(venvDir, "Lib", "site-packages");
const pinFile = path.join(root, "electron", "packaged-requirements.txt");
const selectedFile = path.join(root, "electron", "build", "packaged-requirements-win.txt");

if (fs.existsSync(path.join(sitePackages, "fastapi"))) {
  console.log("windows developer site-packages already present");
  process.exit(0);
}

const python = spawnSync("python", ["-c", "import sys; print(sys.executable)"], { encoding: "utf8" });
if (python.status !== 0 || !python.stdout.trim()) {
  console.error("Windows packaging needs Python 3.11 when studio-api/.venv is absent.");
  process.exit(1);
}

fs.mkdirSync(path.join(root, "electron", "build"), { recursive: true });
const pins = fs.readFileSync(pinFile, "utf8");
fs.writeFileSync(selectedFile, renderSelectedRequirements(pins, "win32"));

function run(cmd, args) {
  const result = spawnSync(cmd, args, { stdio: "inherit", windowsHide: true, cwd: root });
  if (result.status !== 0) {
    console.error(`${cmd} failed (${result.status})`);
    process.exit(result.status || 1);
  }
}

run("python", ["-m", "venv", venvDir]);
const venvPython = path.join(venvDir, "Scripts", "python.exe");
run(venvPython, [
  "-m",
  "pip",
  "install",
  "--disable-pip-version-check",
  "--no-warn-script-location",
  "--no-deps",
  "-r",
  selectedFile,
]);
console.log("windows packaged site-packages installed");
