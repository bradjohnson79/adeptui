import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const require = createRequire(import.meta.url);
const { selectDesktopArtifact, loadFixtureCatalog, parseUpdateResult, applySharedUpdate } = require("./bridge.cjs");
const { classifyNavigation, ALLOWED_CHANNELS } = require("../security.cjs");
const { parseListeningPids } = require("../platform/process.cjs");

const catalog = loadFixtureCatalog(path.dirname(fileURLToPath(import.meta.url)));

test("selects the newer matching platform artifact", () => {
  const result = selectDesktopArtifact(catalog, {
    platform: "win32",
    arch: "x64",
    installedVersion: "1.1.0",
  });
  assert.equal(result.ok, true);
  assert.equal(result.selected.version, "1.2.0");
  assert.equal(result.selected.platform, "win32");
  assert.equal(result.selected.arch, "x64");
  assert.match(result.selected.checksum, /^sha256:/);
  assert.equal(result.rollback.implemented, false);
  assert.equal(result.restartApi.studioApiPort, 8760);
  assert.equal(result.restartApi.runtimeMode, "electron-packaged");
});

test("refuses an older remote and a missing installed version", () => {
  const current = selectDesktopArtifact(catalog, {
    platform: "win32",
    arch: "x64",
    installedVersion: "1.2.0",
  });
  assert.equal(current.selected, null);
  const missing = selectDesktopArtifact(catalog, { platform: "win32", arch: "x64", installedVersion: "" });
  assert.equal(missing.code, "INSTALLED_VERSION_MISSING");
});

test("a Windows artifact is never selected for macOS or Linux", () => {
  const mac = selectDesktopArtifact(catalog, {
    platform: "darwin",
    arch: "arm64",
    installedVersion: "1.1.0",
  });
  assert.equal(mac.selected.fileName.includes("mac-arm64"), true);
  assert.equal(mac.selected.platform, "darwin");
  const linux = selectDesktopArtifact(catalog, {
    platform: "linux",
    arch: "x64",
    installedVersion: "1.1.0",
  });
  assert.equal(linux.selected.platform, "linux");
  assert.equal(linux.selected.arch, "x64");
  assert.match(linux.selected.fileName, /linux-x64\.AppImage$/);
  assert.equal(linux.selected.fileName.includes("win-"), false);
  assert.equal(linux.selected.fileName.includes("mac-"), false);
  const wrongArch = selectDesktopArtifact(catalog, {
    platform: "linux",
    arch: "arm64",
    installedVersion: "1.1.0",
  });
  assert.equal(wrongArch.selected, null);
  assert.equal(wrongArch.code, "NO_UPDATE");
});

test("the desktop selector confirms the launcher result and does not trust a renderer catalog", async () => {
  const parsed = parseUpdateResult("ADEPT_UPDATE_RESULT code=UPDATE_READY version=1.1.5 revision=2\n");
  assert.deepEqual(parsed, { code: "UPDATE_READY", version: "1.1.5", revision: 2 });
  const home = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixture-home");
  const launcher = path.join(home, "Adept Launcher.exe");
  const fs = require("node:fs");
  fs.mkdirSync(path.join(home, ".adept-ui"), { recursive: true });
  fs.writeFileSync(launcher, "");
  fs.writeFileSync(path.join(home, ".adept-ui", "registry.json"), JSON.stringify({ installedRevision: 2 }));
  let spawned = null;
  const result = await applySharedUpdate({
    home,
    launcher,
    spawnUpdate: async (command, env) => {
      spawned = { command, updateOnly: env.ADEPT_UPDATE_ONLY };
      return { status: 0, output: "ADEPT_UPDATE_RESULT code=UPDATE_READY version=1.1.5 revision=2\n" };
    },
  });
  assert.equal(spawned.command, launcher);
  assert.equal(spawned.updateOnly, "1");
  assert.equal(result.ok, true);
  assert.equal(result.code, "UPDATE_READY");
  assert.equal(result.revision, 2);
  fs.rmSync(home, { recursive: true, force: true });
});

test("navigation keeps loopback in the app and sends public http outside", () => {
  const origin = "http://127.0.0.1:41731";
  assert.equal(classifyNavigation(`${origin}/project/abc`, { rendererOrigin: origin, packaged: true }).action, "in-app");
  assert.equal(classifyNavigation("https://example.com/help", { rendererOrigin: origin, packaged: true }).action, "external");
  assert.equal(classifyNavigation("file:///C:/secret", { rendererOrigin: origin, packaged: true }).action, "deny");
  assert.equal(
    classifyNavigation("http://127.0.0.1:5173/", { rendererOrigin: origin, packaged: true }).action,
    "deny",
  );
  assert.equal(ALLOWED_CHANNELS.has("adept:exec"), false);
});

test("netstat parse finds the listening pid only", () => {
  const text = [
    "  TCP    127.0.0.1:8758    0.0.0.0:0    LISTENING    4242",
    "  TCP    127.0.0.1:5173    0.0.0.0:0    LISTENING    1111",
    "  TCP    127.0.0.1:8758    127.0.0.1:9  ESTABLISHED  9999",
  ].join("\n");
  assert.deepEqual(parseListeningPids(text, 8758), [4242]);
});
