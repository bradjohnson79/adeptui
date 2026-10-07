"use strict";

const fs = require("node:fs");
const path = require("node:path");

const versionFile = path.join(__dirname, "version.json");
const identity = JSON.parse(fs.readFileSync(versionFile, "utf8"));

const pyDir = path.join(__dirname, "build", `python-${process.platform}-${process.arch}`);

/** @type {import('electron-builder').Configuration} */
const config = {
  appId: identity.appId,
  productName: identity.productName,
  executableName: "Adept UI",
  copyright: "",
  directories: {
    output: path.join(__dirname, "dist"),
    buildResources: path.join(__dirname, "icons"),
  },
  extraMetadata: {
    version: identity.version,
    main: "electron/main.cjs",
  },
  files: [
    "electron/main.cjs",
    "electron/endpoint.cjs",
    "electron/preload.cjs",
    "electron/renderer-server.cjs",
    "electron/runtime.cjs",
    "electron/security.cjs",
    "electron/version.json",
    "electron/platform/**",
    "electron/update/bridge.cjs",
    "electron/update/fixture-catalog.json",
    "package.json",
  ],
  extraResources: [
    { from: "studio-web/dist", to: "renderer" },
    { from: "electron/version.json", to: "version.json" },
    ...(fs.existsSync(path.join(__dirname, "build", "studio-api"))
      ? [{ from: "electron/build/studio-api", to: "studio-api" }]
      : []),
    ...(fs.existsSync(pyDir) ? [{ from: pyDir, to: "python" }] : []),
  ],
  asar: true,
  npmRebuild: false,
  publish: null,
  win: {
    target: [
      { target: "nsis", arch: ["x64"] },
      { target: "dir", arch: ["x64"] },
    ],
    icon: "electron/icons/icon.ico",
    signAndEditExecutable: false,
  },
  nsis: {
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true,
    deleteAppDataOnUninstall: false,
    runAfterFinish: false,
    artifactName: "${productName}-Setup-${version}-win-x64.${ext}",
    uninstallDisplayName: identity.productName,
  },
  mac: {
    target: [
      { target: "dmg", arch: ["arm64"] },
      { target: "dir", arch: ["arm64"] },
    ],
    icon: "electron/icons/icon.png",
    category: "public.app-category.video",
    identity: null,
    notarize: false,
    hardenedRuntime: true,
    gatekeeperAssess: false,
    entitlements: "electron/entitlements.mac.plist",
    entitlementsInherit: "electron/entitlements.mac.plist",
    artifactName: "${productName}-${version}-mac-arm64.${ext}",
  },
  dmg: {
    artifactName: "${productName}-${version}-mac-arm64.${ext}",
  },
  linux: {
    target: [
      { target: "AppImage", arch: ["x64"] },
      { target: "deb", arch: ["x64"] },
      { target: "rpm", arch: ["x64"] },
    ],
    icon: "electron/icons/png",
    category: "Video",
    artifactName: "${productName}-${version}-linux-x64.${ext}",
    maintainer: "Adept UI",
    desktop: {
      Name: "Adept UI",
      Comment: "Desktop filmmaking studio",
      Categories: "AudioVideo;Video;",
      StartupWMClass: "Adept UI",
      Terminal: "false",
    },
  },
  deb: {
    artifactName: "${productName}-${version}-linux-x64.${ext}",
    packageName: "adept-ui",
  },
  rpm: {
    artifactName: "Adept.UI-${version}-linux-x64.${ext}",
    packageName: "adept-ui",
  },
  appImage: {
    artifactName: "${productName}-${version}-linux-x64.${ext}",
  },
};

module.exports = config;
