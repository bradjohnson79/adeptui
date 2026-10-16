"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { rendererSandboxEnabled } = require("./linux-sandbox.cjs");

test("Windows and macOS keep the renderer sandbox", () => {
  assert.equal(rendererSandboxEnabled({ platform: "win32", argv: [], env: {}, sandboxStat: null }), true);
  assert.equal(rendererSandboxEnabled({ platform: "darwin", argv: [], env: {}, sandboxStat: null }), true);
});

test("a home-directory Linux install does not use the missing setuid helper", () => {
  assert.equal(
    rendererSandboxEnabled({ platform: "linux", argv: [], env: {}, sandboxStat: { uid: 1000, mode: 0o755 } }),
    false,
  );
  assert.equal(rendererSandboxEnabled({ platform: "linux", argv: [], env: {}, sandboxStat: null }), false);
});

test("an explicit no-sandbox start does not also sandbox the renderer", () => {
  assert.equal(
    rendererSandboxEnabled({
      platform: "linux",
      argv: ["--no-sandbox"],
      env: {},
      sandboxStat: { uid: 0, mode: 0o4755 },
    }),
    false,
  );
  assert.equal(
    rendererSandboxEnabled({
      platform: "linux",
      argv: [],
      env: { ELECTRON_DISABLE_SANDBOX: "1" },
      sandboxStat: { uid: 0, mode: 0o4755 },
    }),
    false,
  );
});

test("a root setuid helper keeps the renderer sandbox", () => {
  assert.equal(
    rendererSandboxEnabled({
      platform: "linux",
      argv: [],
      env: {},
      sandboxStat: { uid: 0, mode: 0o4755 },
    }),
    true,
  );
});
