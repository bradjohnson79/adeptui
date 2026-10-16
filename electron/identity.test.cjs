"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.join(__dirname);
const identity = JSON.parse(fs.readFileSync(path.join(root, "version.json"), "utf8"));
const config = require("./builder.config.cjs");
const metainfo = fs.readFileSync(path.join(root, "icons", "linux", "app.adeptui.desktop.metainfo.xml"), "utf8");

test("the visible product stays Adept UI and the package id stays stable", () => {
  assert.equal(identity.productName, "Adept UI");
  assert.equal(identity.appId, "app.adeptui.desktop");
  assert.equal(identity.publisher, "ANOINT Inc.");
  assert.equal(identity.description, "Adept UI — AI Filmmaking & Production Studio");
  assert.equal(config.productName, "Adept UI");
  assert.equal(config.appId, "app.adeptui.desktop");
  assert.equal(config.executableName, "Adept UI");
  assert.deepEqual(config.win.target, [{ target: "dir", arch: ["x64"] }]);
  assert.deepEqual(config.mac.target, [{ target: "dir", arch: ["arm64"] }]);
  assert.deepEqual(config.linux.target, [{ target: "dir", arch: ["x64"] }]);
  assert.equal(config.nsis, undefined);
  assert.equal(config.dmg, undefined);
  assert.equal(config.deb, undefined);
  assert.equal(config.rpm, undefined);
  assert.equal(config.linux.maintainer, "ANOINT Inc.");
  assert.equal(config.linux.vendor, "ANOINT Inc.");
  assert.equal(config.linux.desktop.entry.Name, "Adept UI");
  assert.equal(config.extraMetadata.author.name, "ANOINT Inc.");
  assert.equal(config.win.signtoolOptions.publisherName, "ANOINT Inc.");
  assert.equal(config.win.signExecutable, false);
  assert.equal(config.mac.identity, null);
  assert.equal(config.mac.notarize, false);
});

test("Windows ships the Universal Launcher beside Electron", () => {
  const configText = fs.readFileSync(path.join(root, "builder.config.cjs"), "utf8");
  assert.match(configText, /extraFiles:\s*\[/);
  assert.match(configText, /process\.platform === "win32" && fs\.existsSync\(launcherBinary\)/);
  assert.match(configText, /process\.platform !== "win32" && fs\.existsSync\(launcherBinary\)/);
  assert.equal(fs.existsSync(path.join(root, "nsis", "installer.nsh")), false);
  const extraFiles = configText.slice(configText.indexOf("extraFiles:"));
  const resourcesOnly = configText.slice(0, configText.indexOf("extraFiles:"));
  assert.match(extraFiles, /process\.platform === "win32"/);
  assert.doesNotMatch(resourcesOnly, /process\.platform === "win32" && fs\.existsSync\(launcherBinary\)/);
});

test("package icons are resized from the official Adept Sun master", () => {
  const script = fs.readFileSync(path.join(root, "scripts", "make-icons.mjs"), "utf8");
  assert.match(script, /adept-sun-master\.jpg/);
  assert.doesNotMatch(script, /adept-ui-emblem/);
  for (const file of ["icon.png", "icon.ico", "icon.icns", path.join("png", "256x256.png")]) {
    assert.equal(fs.existsSync(path.join(root, "icons", file)), true, file);
  }
  assert.equal(fs.readFileSync(path.join(root, "icons", "icon.icns")).subarray(0, 4).toString(), "icns");
});

test("AppStream names Adept UI and ANOINT Inc.", () => {
  assert.match(metainfo, /<name>Adept UI<\/name>/);
  assert.match(metainfo, /<name>ANOINT Inc\.<\/name>/);
  assert.doesNotMatch(metainfo, /<name>adept-ui<\/name>/);
  assert.match(metainfo, /<project_license>LicenseRef-proprietary<\/project_license>/);
  assert.match(metainfo, /<url type="homepage">https:\/\/www\.adeptui\.org\/<\/url>/);
  assert.doesNotMatch(metainfo, /<icon /);
  assert.doesNotMatch(metainfo, /type="stock"/);
  assert.match(metainfo, /<release version="1\.1\.2"/);
  assert.match(metainfo, /<release version="1\.1\.1"/);
  assert.match(metainfo, /<release version="1\.1\.5"/);
  assert.match(metainfo, /<release version="1\.1\.6"/);
  assert.equal(identity.version, "1.1.5");
  assert.equal(config.linux.desktop.entry.Icon, "app.adeptui.desktop");
  for (const size of [48, 64, 128, 256, 512]) {
    const source = path.join(root, "icons", "png", `${size}x${size}.png`);
    assert.equal(fs.existsSync(source), true, source);
  }
  assert.match(metainfo, /<launchable type="desktop-id">Adept UI\.desktop<\/launchable>/);
  assert.match(metainfo, /<metadata_license>CC0-1\.0<\/metadata_license>/);
  assert.match(metainfo, /https:\/\/www\.adeptui\.org\/product\/adept-ui-home\.webp/);
});
