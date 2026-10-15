"use strict";

/**
 * Linux afterPack hook — install the Universal Adept Launcher as the package
 * executable while preserving the real Electron binary.
 *
 * electron-builder produces linux-unpacked/<productName> ("Adept UI") as the
 * real Electron ELF, and the deb/rpm/AppImage desktop entry Exec resolves to
 * that same executable name. The launcher must run FIRST, so we:
 *
 *   1. rename  linux-unpacked/Adept UI      -> linux-unpacked/Adept UI.bin
 *      (the real Electron binary; the launcher boots it after the update check)
 *   2. install the staged PyInstaller launcher as linux-unpacked/Adept UI
 *      (keeps the executable name the desktop entry / CLI already invokes)
 *
 * The launcher resolves the sibling Electron binary as "Adept UI.bin" next to
 * it. The replacement worker runs from OUTSIDE the payload
 * (~/.adept-ui/updater) so the running process is never overwritten.
 *
 * AppImage note: electron-builder packs linux-unpacked into the AppImage, so
 * the swap applies there too. The AppImage's AppRun execs the inner "Adept UI"
 * (now the launcher), which then boots "Adept UI.bin".
 */

const fs = require("node:fs");
const path = require("node:path");

const ELECTRON_RENAMED = "Adept UI.bin";
const STAGED_LAUNCHER = "adept-launcher";

module.exports = async function linuxLauncherSwap(context) {
  if (context.electronPlatformName !== "linux") return;
  const appOutDir = context.appOutDir;
  const productName = context.packager.appInfo.productFilename;
  const electronBin = path.join(appOutDir, productName);
  const renamedBin = path.join(appOutDir, ELECTRON_RENAMED);

  // The staged launcher ELF (built by install/launcher/build.py --stage).
  const stagedLauncher = path.join(
    context.packager.projectDir,
    "electron",
    "build",
    "launcher",
    STAGED_LAUNCHER,
  );

  if (!fs.existsSync(stagedLauncher)) {
    throw new Error(
      `linux launcher swap: staged launcher missing at ${stagedLauncher}. ` +
        `Run: python3 install/launcher/build.py --stage`,
    );
  }
  if (!fs.existsSync(electronBin)) {
    throw new Error(`linux launcher swap: Electron binary missing at ${electronBin}`);
  }

  // 1. Rename the real Electron binary out of the executable slot.
  if (fs.existsSync(renamedBin)) fs.rmSync(renamedBin, { force: true });
  fs.renameSync(electronBin, renamedBin);
  fs.chmodSync(renamedBin, 0o755);

  // 2. Install the launcher in the executable slot the desktop entry invokes.
  fs.copyFileSync(stagedLauncher, electronBin);
  fs.chmodSync(electronBin, 0o755);

  // Marker for certification: prove the swap happened and layout is intact.
  const marker = {
    launcher: electronBin,
    electron: renamedBin,
    executableName: productName,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(
    path.join(appOutDir, "launcher-swap.json"),
    JSON.stringify(marker, null, 2),
  );

  console.log(
    `linux launcher swap: ${productName} -> ${ELECTRON_RENAMED}, launcher installed as ${productName}`,
  );
};
