"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { resolveStudioApiEndpoint } = require("../endpoint.cjs");

function parseVersion(value) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(value || "").trim());
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function compareVersion(left, right) {
  for (let i = 0; i < 3; i += 1) {
    if (left[i] !== right[i]) return left[i] - right[i];
  }
  return 0;
}

/**
 * Desktop package selection. This is not a second updater.
 * Setup still owns component plans. This record is the artifact identity
 * Electron may later hand to that owner: platform, architecture, version,
 * and checksum or signature metadata.
 *
 * Older remotes are refused. A missing installed version fails closed.
 * Application rollback is not implemented.
 */
function selectDesktopArtifact(catalog, request) {
  const restartApi = resolveStudioApiEndpoint("electron-packaged");
  const rollback = {
    implemented: false,
    reason:
      "Application rollback is not implemented. Asset-pack checksum verification stays with Setup. Desktop package rollback remains an explicit bridge requirement.",
  };
  const installedVersion = request && request.installedVersion;
  if (!installedVersion) {
    return { ok: false, code: "INSTALLED_VERSION_MISSING", selected: null, rollback, restartApi };
  }
  const installed = parseVersion(installedVersion);
  if (!installed) {
    return { ok: false, code: "INSTALLED_VERSION_INVALID", selected: null, rollback, restartApi };
  }
  const platform = request.platform;
  const arch = request.arch;
  const artifacts = Array.isArray(catalog && catalog.artifacts) ? catalog.artifacts : [];
  let best = null;
  for (const artifact of artifacts) {
    if (!artifact || artifact.platform !== platform || artifact.arch !== arch) continue;
    const version = parseVersion(artifact.version);
    if (!version) continue;
    if (compareVersion(version, installed) <= 0) continue;
    if (!artifact.checksum && !artifact.signature) continue;
    if (!best || compareVersion(version, parseVersion(best.version)) > 0) best = artifact;
  }
  if (!best) return { ok: true, code: "NO_UPDATE", selected: null, rollback, restartApi };
  return {
    ok: true,
    code: "UPDATE_AVAILABLE",
    selected: {
      platform: best.platform,
      arch: best.arch,
      version: best.version,
      checksum: best.checksum || null,
      signature: best.signature || null,
      fileName: best.fileName,
    },
    rollback,
    restartApi,
  };
}

function launcherExecutable(home = os.homedir()) {
  const root = path.join(home, ".adept-ui");
  if (process.platform === "win32") return path.join(root, "bin", "Adept Launcher.exe");
  if (process.platform === "darwin") {
    return path.join(root, "app", "Adept UI.app", "Contents", "MacOS", "Adept UI");
  }
  return path.join(root, "bin", "Adept UI");
}

function parseUpdateResult(text) {
  const match = /ADEPT_UPDATE_RESULT code=(\S+) version=(\S+) revision=(\S+)/.exec(String(text || ""));
  if (!match) return null;
  return { code: match[1], version: match[2], revision: Number(match[3]) };
}

function readInstalledRevision(registryPath) {
  try {
    const body = JSON.parse(fs.readFileSync(registryPath, "utf8"));
    const revision = Number(body.installedRevision);
    return Number.isFinite(revision) ? revision : 0;
  } catch {
    return null;
  }
}

/**
 * Ask the Universal Launcher to run the shared updater.
 * The renderer does not supply a catalog. The launcher checks the signed
 * catalog, verifies the archive, and applies it with the existing rollback.
 */
function applySharedUpdate(options = {}) {
  const home = options.home || os.homedir();
  const launcher = options.launcher || launcherExecutable(home);
  const spawnUpdate = options.spawnUpdate;
  if (!fs.existsSync(launcher)) {
    return Promise.resolve({ ok: false, code: "LAUNCHER_MISSING", version: null, revision: null });
  }
  const run = spawnUpdate || ((command, env) => new Promise((resolve) => {
    const child = spawn(command, [], { env, windowsHide: true });
    let output = "";
    child.stdout?.on("data", (chunk) => { output += chunk.toString(); });
    child.stderr?.on("data", (chunk) => { output += chunk.toString(); });
    child.on("error", () => resolve({ status: 1, output }));
    child.on("close", (status) => resolve({ status: status ?? 1, output }));
  }));
  const env = { ...process.env, ADEPT_UPDATE_ONLY: "1" };
  return run(launcher, env).then((completed) => {
    const parsed = parseUpdateResult(completed.output);
    const registryRevision = readInstalledRevision(path.join(home, ".adept-ui", "registry.json"));
    if (!parsed) {
      return { ok: false, code: "UPDATE_UNCONFIRMED", version: null, revision: registryRevision };
    }
    if (parsed.code === "UPDATE_READY") {
      return {
        ok: completed.status === 0 && Number.isFinite(parsed.revision),
        code: parsed.code,
        version: parsed.version,
        revision: parsed.revision,
      };
    }
    const revision = registryRevision === null ? parsed.revision : registryRevision;
    const confirmed = parsed.code === "NO_UPDATE" || (parsed.code === "UPDATED" && revision === parsed.revision);
    return {
      ok: completed.status === 0 && confirmed,
      code: parsed.code,
      version: parsed.version,
      revision,
    };
  });
}

function readInstalledVersion(versionFile) {
  const body = JSON.parse(fs.readFileSync(versionFile, "utf8"));
  if (!body.version) throw new Error("desktop version missing");
  return body.version;
}

function loadFixtureCatalog(dir) {
  return JSON.parse(fs.readFileSync(path.join(dir, "fixture-catalog.json"), "utf8"));
}

module.exports = {
  parseVersion,
  compareVersion,
  selectDesktopArtifact,
  readInstalledVersion,
  loadFixtureCatalog,
  launcherExecutable,
  parseUpdateResult,
  applySharedUpdate,
};
