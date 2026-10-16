"use strict";

/**
 * A terminal install lives in the home directory. Linux will not honor
 * chrome-sandbox unless that helper is owned by root and marked setuid.
 * When it is not, Electron shows an Error dialog and the Studio window
 * never appears. This is not a graphics setting.
 */
function rendererSandboxEnabled({ platform, argv, env, sandboxStat }) {
  if (platform !== "linux") return true;
  const args = Array.isArray(argv) ? argv : [];
  if (args.includes("--no-sandbox") || env.ELECTRON_DISABLE_SANDBOX === "1") return false;
  if (!sandboxStat || sandboxStat.uid !== 0) return false;
  return (sandboxStat.mode & 0o4000) !== 0;
}

module.exports = { rendererSandboxEnabled };
