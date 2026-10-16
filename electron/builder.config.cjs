"use strict";

const fs = require("node:fs");
const path = require("node:path");

const versionFile = path.join(__dirname, "version.json");
const identity = JSON.parse(fs.readFileSync(versionFile, "utf8"));

const pyDir = path.join(__dirname, "build", `python-${process.platform}-${process.arch}`);

// Universal Adept Launcher: the single update authority that runs before Electron.
// Built per-platform by install/launcher/build.py and staged into electron/build.
const launcherDir = path.join(__dirname, "build", "launcher");
const launcherName =
  process.platform === "win32" ? "Adept Launcher.exe"
  : process.platform === "darwin" ? "Adept UI"
  : "adept-launcher";
const launcherBinary = path.join(launcherDir, launcherName);

/** @type {import('electron-builder').Configuration} */
const config = {
  appId: identity.appId,
  productName: identity.productName,
  executableName: "Adept UI",
  copyright: identity.copyright,
  directories: {
    output: path.join(__dirname, "dist"),
    buildResources: path.join(__dirname, "icons"),
    // electron-builder treats a www/package.json as the app root. The website
    // lives there. The desktop app root is this repository.
    app: path.join(__dirname, ".."),
  },
  extraMetadata: {
    version: identity.version,
    description: identity.description,
    author: { name: identity.publisher },
    main: "electron/main.cjs",
  },
  files: [
    "electron/main.cjs",
    "electron/linux-sandbox.cjs",
    "electron/desktopShortcut.cjs",
    "electron/endpoint.cjs",
    "electron/preload.cjs",
    "electron/renderer-server.cjs",
    "electron/runtime.cjs",
    "electron/security.cjs",
    "electron/version.json",
    "electron/icons/png/256x256.png",
    "electron/platform/**",
    "electron/update/bridge.cjs",
    "electron/update/fixture-catalog.json",
    "package.json",
  ],
  extraResources: [
    { from: "studio-web/dist", to: "renderer" },
    { from: "electron/version.json", to: "version.json" },
    { from: "install/lifecycle/adept_lifecycle", to: "lifecycle/adept_lifecycle" },
    ...(fs.existsSync(path.join(__dirname, "build", "studio-api"))
      ? [{ from: "electron/build/studio-api", to: "studio-api" }]
      : []),
    ...(fs.existsSync(pyDir) ? [{ from: pyDir, to: "python" }] : []),
    // macOS and Linux install the launcher via afterPack. Windows must not use
    // extraResources: that hides Adept Launcher.exe under resources\, where the
    // NSIS shortcut retarget cannot see it and the launcher cannot find the
    // sibling Adept UI.exe.
    ...(process.platform !== "win32" && fs.existsSync(launcherBinary)
      ? [{ from: launcherBinary, to: launcherName }]
      : []),
  ],
  extraFiles: [
    ...(process.platform === "win32" && fs.existsSync(launcherBinary)
      ? [{ from: launcherBinary, to: launcherName }]
      : []),
  ],
  asar: true,
  npmRebuild: false,
  publish: null,
  // Install the Universal Launcher as the application executable after packaging.
  // macOS uses the bundle executable slot. Linux renames Electron to Adept UI.bin.
  // Windows places Adept Launcher.exe beside Adept UI.exe.
  afterPack: "electron/scripts/launcher-swap.cjs",
  win: {
    target: [{ target: "dir", arch: ["x64"] }],
    icon: "electron/icons/icon.ico",
    legalTrademarks: identity.description,
    signExecutable: false,
    signtoolOptions: {
      publisherName: identity.publisher,
    },
  },
  mac: {
    target: [{ target: "dir", arch: ["arm64"] }],
    icon: "electron/icons/icon.icns",
    category: "public.app-category.video",
    identity: null,
    notarize: false,
    hardenedRuntime: true,
    gatekeeperAssess: false,
    entitlements: "electron/entitlements.mac.plist",
    entitlementsInherit: "electron/entitlements.mac.plist",
    extendInfo: {
      CFBundleDisplayName: identity.productName,
      CFBundleName: identity.productName,
      NSHumanReadableCopyright: identity.copyright,
    },
    artifactName: "${productName}-${version}-mac-arm64.${ext}",
  },
  linux: {
    target: [{ target: "dir", arch: ["x64"] }],
    icon: "electron/icons/png",
    category: "Video",
    synopsis: identity.description,
    description: identity.description,
    maintainer: identity.publisher,
    vendor: identity.publisher,
    desktop: {
      entry: {
        Name: identity.productName,
        Comment: identity.description,
        Icon: "app.adeptui.desktop",
        StartupWMClass: identity.productName,
      },
    },
  },
};

module.exports = config;
