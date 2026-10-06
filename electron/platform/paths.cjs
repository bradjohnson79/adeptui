"use strict";

const fs = require("node:fs");
const path = require("node:path");

function readDesktopVersion(resourcesPath, moduleDir) {
  const candidates = [
    path.join(resourcesPath || "", "version.json"),
    path.join(moduleDir, "version.json"),
  ];
  for (const file of candidates) {
    try {
      if (file && fs.existsSync(file)) {
        const body = JSON.parse(fs.readFileSync(file, "utf8"));
        if (body && body.version) return body;
      }
    } catch {
      /* try the next candidate */
    }
  }
  throw new Error("electron/version.json is missing");
}

function packagedLayout(resourcesPath) {
  return {
    python: path.join(resourcesPath, "python", process.platform === "win32" ? "python.exe" : "bin/python"),
    apiSource: path.join(resourcesPath, "studio-api"),
    renderer: path.join(resourcesPath, "renderer"),
    versionFile: path.join(resourcesPath, "version.json"),
  };
}

function userLayout(userData) {
  return {
    userData,
    dataDir: path.join(userData, "data"),
    logs: path.join(userData, "logs"),
    temp: path.join(userData, "temp"),
    comfyInput: path.join(userData, "comfy", "input"),
    comfyOutput: path.join(userData, "comfy", "output"),
    comfyModels: path.join(userData, "comfy", "models"),
    runtimeHome: path.join(userData, "runtime"),
  };
}

function ensureUserDirs(layout) {
  for (const key of ["dataDir", "logs", "temp", "comfyInput", "comfyOutput", "comfyModels", "runtimeHome"]) {
    fs.mkdirSync(layout[key], { recursive: true });
  }
}

function pathTouchesDevRepo(filePath, devRepo) {
  if (!filePath || !devRepo) return false;
  const norm = path.resolve(filePath).toLowerCase();
  const root = path.resolve(devRepo).toLowerCase();
  return norm === root || norm.startsWith(root + path.sep);
}

module.exports = {
  readDesktopVersion,
  packagedLayout,
  userLayout,
  ensureUserDirs,
  pathTouchesDevRepo,
};
