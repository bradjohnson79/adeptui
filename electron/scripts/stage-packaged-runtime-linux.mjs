import crypto from "node:crypto";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { auditPackagedTree, renderSelectedRequirements, selectRequirements } from "../packaged-requirements-contract.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const build = path.join(root, "electron", "build");
const pyDir = path.join(build, "python-linux-x64");
const apiDir = path.join(build, "studio-api");
const pinFile = path.join(root, "electron", "packaged-requirements.txt");
const selectedFile = path.join(build, "packaged-requirements-linux.txt");
const stampFile = path.join(pyDir, ".staged");
const pythonUrl =
  "https://github.com/astral-sh/python-build-standalone/releases/download/20260127/cpython-3.11.14%2B20260127-x86_64-unknown-linux-gnu-install_only.tar.gz";
const tarPath = path.join(build, "cpython-3.11.14-x86_64-unknown-linux-gnu-install_only.tar.gz");

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (process.platform !== "linux" || process.arch !== "x64") {
  fail(`LINUX NATIVE RUNNER = FAIL\nPackaged Linux Python can only be staged on Linux x64. This process is ${process.platform} ${process.arch}.`);
}

function download(url, dest, hops = 0) {
  if (hops > 5) return Promise.reject(new Error(`too many redirects for ${url}`));
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const request = https.get(url, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        fs.rmSync(dest, { force: true });
        download(new URL(res.headers.location, url).toString(), dest, hops + 1).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`download ${url} status ${res.statusCode}`));
        return;
      }
      res.pipe(file);
      file.on("finish", () => file.close(() => resolve()));
    });
    request.on("error", reject);
  });
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, { stdio: "inherit", ...opts });
  if (result.status !== 0) throw new Error(`${cmd} failed (${result.status})`);
}

function stageApiSource() {
  fs.rmSync(apiDir, { recursive: true, force: true });
  fs.mkdirSync(apiDir, { recursive: true });
  for (const name of ["app", "runtime_supervisor", "knowledgebase"]) {
    fs.cpSync(path.join(root, "studio-api", name), path.join(apiDir, name), {
      recursive: true,
      filter: (src) => {
        const base = path.basename(src);
        return base !== "__pycache__" && base !== ".venv" && base !== ".env" && !base.endsWith(".pyc") && !base.endsWith(".db");
      },
    });
  }
  fs.copyFileSync(path.join(root, "studio-api", "requirements.txt"), path.join(apiDir, "requirements.txt"));
}

function pythonBin() {
  return path.join(pyDir, "bin", "python");
}

function ensurePythonName() {
  const bin = path.join(pyDir, "bin");
  const python = path.join(bin, "python");
  if (fs.existsSync(python)) return;
  if (!fs.existsSync(path.join(bin, "python3"))) throw new Error("staged CPython has no bin/python3");
  fs.symlinkSync("python3", python);
}

function assertX64() {
  const result = spawnSync(pythonBin(), ["-c", "import platform; print(platform.system()); print(platform.machine())"], {
    encoding: "utf8",
  });
  const lines = (result.stdout || "").trim().split(/\n/);
  if (result.status !== 0 || lines[0] !== "Linux" || lines[1] !== "x86_64") {
    throw new Error(`PYTHON ARCH = FAIL (${(result.stdout || result.stderr || "").trim()})`);
  }
  console.log("PYTHON ARCH = x64");
  console.log("PLATFORM = linux");
}

function assertNoForeignBits() {
  const problems = auditPackagedTree(pyDir, { rejectMac: true });
  if (problems.length) {
    throw new Error(`foreign binaries in Linux runtime\n${problems.slice(0, 20).join("\n")}`);
  }
  console.log("WINDOWS BINARIES IN LINUX PACKAGE = 0");
  console.log("MACOS BINARIES IN LINUX PACKAGE = 0");
  console.log("PYWIN32 IN LINUX PACKAGE = 0");
}

function stripVendorWindowsLaunchers(sitePackages) {
  for (const name of ["pip", "setuptools"]) {
    const root = path.join(sitePackages, name);
    if (!fs.existsSync(root)) continue;
    const walk = (current) => {
      for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
        const full = path.join(current, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.exe$/i.test(entry.name)) fs.rmSync(full);
      }
    };
    walk(root);
  }
}

function installDependencies() {
  const pins = fs.readFileSync(pinFile, "utf8");
  const rendered = renderSelectedRequirements(pins, "linux");
  if (selectRequirements(rendered, "linux").selected.some((row) => row.name === "pywin32")) {
    throw new Error("generated Linux requirements still select pywin32");
  }
  fs.mkdirSync(build, { recursive: true });
  fs.writeFileSync(selectedFile, rendered);
  console.log("PYWIN32 INSTALL ATTEMPT ON LINUX = 0");
  // The pin file is the Windows site-packages freeze. Windows copies it; it is not a
  // freshly solvable set (sse-starlette 3.4.11 and starlette 0.47.3 ship together).
  run(pythonBin(), [
    "-m", "pip", "install",
    "--disable-pip-version-check",
    "--no-warn-script-location",
    "--no-deps",
    "-r", selectedFile,
  ]);
  const site = path.join(pyDir, "lib");
  for (const versionDir of fs.readdirSync(site)) {
    const sitePackages = path.join(site, versionDir, "site-packages");
    if (!fs.existsSync(sitePackages)) continue;
    for (const name of fs.readdirSync(sitePackages)) {
      if (name === "playwright" || name.startsWith("playwright-")) {
        fs.rmSync(path.join(sitePackages, name), { recursive: true, force: true });
      }
    }
    stripVendorWindowsLaunchers(sitePackages);
  }
}

const expectedStamp = `${pythonUrl}\n${crypto.createHash("sha256").update(fs.readFileSync(pinFile)).digest("hex")}\n`;
if (fs.existsSync(stampFile) && fs.readFileSync(stampFile, "utf8") === expectedStamp && fs.existsSync(pythonBin())) {
  assertX64();
  assertNoForeignBits();
  stageApiSource();
  console.log("STUDIO API STAGED = PASS");
  process.exit(0);
}

fs.mkdirSync(build, { recursive: true });
fs.rmSync(pyDir, { recursive: true, force: true });
if (!fs.existsSync(tarPath)) await download(pythonUrl, tarPath);
const extract = path.join(build, "python-linux-extract");
fs.rmSync(extract, { recursive: true, force: true });
fs.mkdirSync(extract, { recursive: true });
run("tar", ["-xzf", tarPath, "-C", extract]);
const extracted = path.join(extract, "python");
if (!fs.existsSync(extracted)) fail("install_only archive did not contain a python/ directory");
fs.renameSync(extracted, pyDir);
fs.rmSync(extract, { recursive: true, force: true });
ensurePythonName();
const ldd = spawnSync("ldd", [pythonBin()], { encoding: "utf8" });
fs.writeFileSync(path.join(build, "linux-python-ldd.txt"), `${ldd.stdout || ""}${ldd.stderr || ""}`);
assertX64();
installDependencies();
assertNoForeignBits();
stageApiSource();
if (!fs.existsSync(path.join(apiDir, "app", "main.py"))) fail("STUDIO API STAGED = FAIL");
fs.writeFileSync(stampFile, expectedStamp);
console.log("STUDIO API STAGED = PASS");
console.log("DEV VENV DEPENDENCY = 0");
console.log("staged packaged linux runtime");
