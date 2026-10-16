"use strict";

/**
 * macOS afterPack hook — install the Universal Adept Launcher as the bundle
 * executable while preserving the Gatekeeper layout.
 *
 * electron-builder produces Contents/MacOS/<productName> as the real Electron
 * binary (matching CFBundleExecutable). The launcher must run FIRST, so we:
 *
 *   1. rename  Contents/MacOS/Adept UI      -> Contents/MacOS/Adept UI.bin
 *      (the real Electron binary; the launcher boots it after the update check)
 *   2. install the staged PyInstaller Mach-O launcher as Contents/MacOS/Adept UI
 *      (matches CFBundleExecutable so Gatekeeper/LaunchServices run the launcher)
 *
 * The launcher resolves the sibling Electron binary as "Adept UI.bin" next to it.
 * The replacement worker runs from OUTSIDE the .app (~/Library/Application
 * Support/Adept UI/updater) so the running process is never overwritten.
 */

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const LAUNCHER_NAME = "Adept UI";
const ELECTRON_RENAMED = "Adept UI.bin";

module.exports = async function macosLauncherSwap(context) {
  if (context.electronPlatformName !== "darwin") return;
  const appOutDir = context.appOutDir;
  const productName = context.packager.appInfo.productFilename;
  const appPath = path.join(appOutDir, `${productName}.app`);
  const macosDir = path.join(appPath, "Contents", "MacOS");
  const electronBin = path.join(macosDir, productName);
  const renamedBin = path.join(macosDir, ELECTRON_RENAMED);

  // The staged launcher Mach-O (built by install/launcher/build.py --stage).
  const stagedLauncher = path.join(
    context.packager.projectDir,
    "electron",
    "build",
    "launcher",
    LAUNCHER_NAME,
  );

  if (!fs.existsSync(stagedLauncher)) {
    throw new Error(
      `macOS launcher swap: staged launcher missing at ${stagedLauncher}. ` +
        `Run: python3 install/launcher/build.py --stage`,
    );
  }
  if (!fs.existsSync(electronBin)) {
    throw new Error(`macOS launcher swap: Electron binary missing at ${electronBin}`);
  }

  // 1. Rename the real Electron binary out of the executable slot.
  if (fs.existsSync(renamedBin)) fs.rmSync(renamedBin, { force: true });
  fs.renameSync(electronBin, renamedBin);

  // 2. Install the launcher Mach-O in the CFBundleExecutable slot.
  fs.copyFileSync(stagedLauncher, electronBin);
  fs.chmodSync(electronBin, 0o755);

  // Keep the swap record outside the signed bundle. A loose file in
  // Contents/MacOS is what made codesign --strict report an unsigned object.
  const marker = {
    launcher: electronBin,
    electron: renamedBin,
    cfBundleExecutable: productName,
    timestamp: new Date().toISOString(),
  };
  const evidenceDir = path.join(context.outDir, "..", "build");
  fs.mkdirSync(evidenceDir, { recursive: true });
  fs.writeFileSync(path.join(evidenceDir, "launcher-swap.json"), JSON.stringify(marker, null, 2));

  console.log(`macOS launcher swap: ${productName} -> ${ELECTRON_RENAMED}, launcher installed as ${productName}`);
  resignMacBundle(appPath);
};

function resignMacBundle(appPath) {
  // The launcher is copied in after Electron's own signature. Sign the bundle
  // again so the main executable and the bundle resources agree. This is an
  // ad-hoc signature. It does not notarize the app or disable Gatekeeper.
  const macosDir = path.join(appPath, "Contents", "MacOS");
  for (const name of ["Adept UI", "Adept UI.bin"]) {
    const binary = path.join(macosDir, name);
    if (!fs.existsSync(binary)) continue;
    try {
      execFileSync("codesign", ["--remove-signature", binary], { stdio: "inherit" });
    } catch {
      /* an unsigned binary is already in the state we need */
    }
  }
  execFileSync("codesign", ["--force", "--deep", "--sign", "-", appPath], { stdio: "inherit" });
  execFileSync("codesign", ["--verify", "--deep", "--strict", "--verbose=2", appPath], { stdio: "inherit" });
}

module.exports.resignMacBundle = resignMacBundle;
