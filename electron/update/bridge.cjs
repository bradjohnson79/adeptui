"use strict";

const fs = require("node:fs");
const path = require("node:path");
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
};
