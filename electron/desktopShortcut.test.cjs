"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { linuxDesktopEntry, recordShortcut, removeRecordedShortcut } = require("./desktopShortcut.cjs");

test("linux desktop entry names Adept UI and does not open a terminal", () => {
  const text = linuxDesktopEntry("/usr/bin/adept-ui");
  assert.match(text, /^Name=Adept UI$/m);
  assert.match(text, /^Terminal=false$/m);
  assert.match(text, /^Exec="\/usr\/bin\/adept-ui"$/m);
  assert.match(text, /^Icon=Adept UI$/m);
});

test("a recorded shortcut is the only file removed", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-shortcut-"));
  const shortcut = path.join(dir, "Adept UI.desktop");
  const other = path.join(dir, "notes.txt");
  const record = path.join(dir, "desktop-shortcut.json");
  fs.writeFileSync(shortcut, "[Desktop Entry]\nName=Adept UI\n", "utf8");
  fs.writeFileSync(other, "keep", "utf8");
  assert.equal(recordShortcut(record, shortcut).recorded, true);
  assert.equal(removeRecordedShortcut(record).removed, true);
  assert.equal(fs.existsSync(shortcut), false);
  assert.equal(fs.readFileSync(other, "utf8"), "keep");
  fs.rmSync(dir, { recursive: true, force: true });
});

test("a recorded path that is not an Adept UI shortcut is left alone", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "adept-shortcut-"));
  const record = path.join(dir, "desktop-shortcut.json");
  const other = path.join(dir, "notes.txt");
  fs.writeFileSync(other, "keep", "utf8");
  fs.writeFileSync(record, JSON.stringify({ path: other, name: "Adept UI" }), "utf8");
  const result = removeRecordedShortcut(record);
  assert.equal(result.removed, false);
  assert.equal(fs.readFileSync(other, "utf8"), "keep");
  fs.rmSync(dir, { recursive: true, force: true });
});
