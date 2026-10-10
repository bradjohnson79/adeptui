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
    legalTrademarks: identity.description,
    signExecutable: false,
    signtoolOptions: {
      publisherName: identity.publisher,
    },
  },
  nsis: {
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true,
    createDesktopShortcut: true,
    createStartMenuShortcut: true,
    shortcutName: identity.productName,
    menuCategory: identity.publisher,
    installerIcon: "electron/icons/icon.ico",
    uninstallerIcon: "electron/icons/icon.ico",
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
  dmg: {
    title: `${identity.productName} ${identity.version}`,
    icon: "electron/icons/icon.icns",
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
    artifactName: "${productName}-${version}-linux-x64.${ext}",
  },
  deb: {
    artifactName: "${productName}-${version}-linux-x64.${ext}",
    packageName: "adept-ui",
    fpm: [
      "electron/icons/linux/app.adeptui.desktop.metainfo.xml=/usr/share/metainfo/app.adeptui.desktop.metainfo.xml",
      "electron/icons/png/48x48.png=/usr/share/icons/hicolor/48x48/apps/app.adeptui.desktop.png",
      "electron/icons/png/64x64.png=/usr/share/icons/hicolor/64x64/apps/app.adeptui.desktop.png",
      "electron/icons/png/128x128.png=/usr/share/icons/hicolor/128x128/apps/app.adeptui.desktop.png",
      "electron/icons/png/256x256.png=/usr/share/icons/hicolor/256x256/apps/app.adeptui.desktop.png",
      "electron/icons/png/512x512.png=/usr/share/icons/hicolor/512x512/apps/app.adeptui.desktop.png",
    ],
  },
  rpm: {
    artifactName: "Adept.UI-${version}-linux-x64.${ext}",
    packageName: "adept-ui",
    fpm: [
      "electron/icons/linux/app.adeptui.desktop.metainfo.xml=/usr/share/metainfo/app.adeptui.desktop.metainfo.xml",
      "electron/icons/png/48x48.png=/usr/share/icons/hicolor/48x48/apps/app.adeptui.desktop.png",
      "electron/icons/png/64x64.png=/usr/share/icons/hicolor/64x64/apps/app.adeptui.desktop.png",
      "electron/icons/png/128x128.png=/usr/share/icons/hicolor/128x128/apps/app.adeptui.desktop.png",
      "electron/icons/png/256x256.png=/usr/share/icons/hicolor/256x256/apps/app.adeptui.desktop.png",
      "electron/icons/png/512x512.png=/usr/share/icons/hicolor/512x512/apps/app.adeptui.desktop.png",
    ],
  },
  appImage: {
    artifactName: "${productName}-${version}-linux-x64.${ext}",
  },
};

module.exports = config;
