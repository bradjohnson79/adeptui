"use strict";

/**
 * Combined afterPack hook — install the Universal Adept Launcher as the package
 * executable on each platform that uses an in-payload swap. Dispatches to the
 * platform-specific swap; no-op elsewhere (Windows uses the NSIS shortcut
 * retarget instead, leaving the Electron executable name intact).
 */

const macosLauncherSwap = require("./macos-launcher-swap.cjs");
const linuxLauncherSwap = require("./linux-launcher-swap.cjs");

module.exports = async function launcherSwap(context) {
  if (context.electronPlatformName === "darwin") {
    await macosLauncherSwap(context);
  } else if (context.electronPlatformName === "linux") {
    await linuxLauncherSwap(context);
  }
};
