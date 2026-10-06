import { spawnSync } from "node:child_process";
import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const build = path.join(root, "electron", "build");
const pyDir = path.join(build, "python-win32-x64");
const apiDir = path.join(build, "studio-api");
// 3.11.15 is the developer venv, but python.org has no embeddable zip for that
// patch (HTTP 404). 3.11.9 is the published embeddable CPython with the same
// cp311 ABI. It is not the developer .venv.
const embedUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip";
const zipPath = path.join(build, "python-3.11.9-embed-amd64.zip");

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const request = https.get(url, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        fs.rmSync(dest, { force: true });
        download(res.headers.location, dest).then(resolve, reject);
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
  const result = spawnSync(cmd, args, { stdio: "inherit", windowsHide: true, ...opts });
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

const stamp = path.join(pyDir, ".staged");
if (fs.existsSync(stamp) && fs.existsSync(path.join(pyDir, "python.exe"))) {
  stageApiSource();
  console.log("packaged python reused; studio-api source refreshed");
  process.exit(0);
}

fs.mkdirSync(build, { recursive: true });
if (!fs.existsSync(path.join(pyDir, "python.exe"))) {
  fs.mkdirSync(pyDir, { recursive: true });
  if (!fs.existsSync(zipPath)) await download(embedUrl, zipPath);
  run("tar", ["-xf", zipPath, "-C", pyDir]);
}

const pthName = fs.readdirSync(pyDir).find((name) => name.endsWith("._pth"));
if (!pthName) throw new Error("embeddable python ._pth not found");
const pthPath = path.join(pyDir, pthName);
let pth = fs.readFileSync(pthPath, "utf8");
if (!pth.includes("Lib\\site-packages") && !pth.includes("Lib/site-packages")) {
  pth = `${pth.trim()}\r\nLib\\site-packages\r\n`;
}
pth = pth.replace(/^#import site/m, "import site");
if (!pth.includes("../studio-api")) {
  pth = `${pth.trim()}\r\n../studio-api\r\n`;
}
fs.writeFileSync(pthPath, pth.endsWith("\n") ? pth : `${pth}\n`);
fs.mkdirSync(path.join(pyDir, "Lib", "site-packages"), { recursive: true });

const py = path.join(pyDir, "python.exe");
const sitePackages = path.join(pyDir, "Lib", "site-packages");
// A clean resolve of requirements.txt conflicts (Starlette). Copy the already
// installed packages into the embeddable interpreter. The packaged process
// uses this interpreter, not studio-api/.venv. Torch is not in that set.
const sourcePackages = path.join(root, "studio-api", ".venv", "Lib", "site-packages");
fs.rmSync(sitePackages, { recursive: true, force: true });
fs.mkdirSync(sitePackages, { recursive: true });
const copy = spawnSync(
  "robocopy",
  [sourcePackages, sitePackages, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/XD", "__pycache__", "/XF", "*.pyc"],
  { windowsHide: true },
);
if (copy.status > 7) throw new Error(`robocopy site-packages failed (${copy.status})`);
const venvCfg = fs.readFileSync(path.join(root, "studio-api", ".venv", "pyvenv.cfg"), "utf8");
const home = (venvCfg.match(/^home = (.+)$/m) || [])[1];
if (!home) throw new Error("developer pyvenv.cfg has no home; cannot copy the stdlib venv module");
fs.cpSync(path.join(home.trim(), "Lib", "venv"), path.join(sitePackages, "venv"), { recursive: true });
for (const name of fs.readdirSync(sitePackages)) {
  if (name === "playwright" || name.startsWith("playwright-")) {
    fs.rmSync(path.join(sitePackages, name), { recursive: true, force: true });
  }
}

stageApiSource();
fs.writeFileSync(stamp, new Date().toISOString());
console.log("staged packaged runtime");
