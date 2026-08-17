import assert from "node:assert/strict";
import test from "node:test";
import {
  applyUserShortcut,
  chordFromEvent,
  chordsEqual,
  DEFAULT_HOTKEYS,
  findConflict,
  formatChord,
  isEditableTarget,
  loadHotkeys,
  matchHotkey,
  registerTimelineCommand,
  resetHotkeys,
  resetTimelineCommandsForTests,
  runTimelineCommand,
  saveHotkeys,
  TIMELINE_HOTKEYS_KEY,
} from "./timelineHotkeys.ts";

function fakeStorage() {
  const map = new Map<string, string>();
  globalThis.localStorage = {
    getItem: (k: string) => map.get(k) ?? null,
    setItem: (k: string, v: string) => {
      map.set(k, v);
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
    clear: () => map.clear(),
    key: () => null,
    length: 0,
  } as Storage;
}

test("defaults include generate, preflight, space, and open hotkeys", () => {
  const ids = DEFAULT_HOTKEYS.map((item) => item.actionId);
  assert.ok(ids.includes("generateScene"));
  assert.ok(ids.includes("preflight"));
  assert.ok(ids.includes("playPause"));
  assert.ok(ids.includes("openHotkeys"));
  assert.ok(ids.includes("toggleLeftDrawer"));
  assert.ok(ids.includes("toggleRightDrawer"));
  assert.ok(ids.includes("focusTimeline"));
});

test("conflict is detected and replace unassigns the other command", () => {
  const bindings = resetHotkeys();
  const first = applyUserShortcut(bindings, "preflight", { key: "g" }, false);
  assert.equal(first.conflict?.actionId, "generateScene");
  const replaced = applyUserShortcut(bindings, "preflight", { key: "g" }, true);
  assert.equal(replaced.conflict, null);
  const generate = replaced.bindings.find((item) => item.actionId === "generateScene");
  const preflight = replaced.bindings.find((item) => item.actionId === "preflight");
  assert.equal(generate?.enabled, false);
  assert.equal(preflight?.userShortcut?.key, "g");
  assert.equal(findConflict(replaced.bindings, "preflight", { key: "g" }), null);
});

test("platform labels use Ctrl or command", () => {
  assert.equal(formatChord({ key: "z", ctrl: true }, false), "Ctrl + Z");
  assert.equal(formatChord({ key: "d", ctrl: true }, true), "⌘ D");
  assert.equal(formatChord({ key: "" }, false), "—");
});

test("text-entry targets suppress global shortcuts", () => {
  const textarea = { tagName: "TEXTAREA", isContentEditable: false, closest: () => null, dataset: {} };
  const button = { tagName: "BUTTON", isContentEditable: false, closest: () => null, dataset: {} };
  assert.equal(isEditableTarget(textarea as unknown as EventTarget), true);
  assert.equal(isEditableTarget(button as unknown as EventTarget), false);
  const event = { key: "g", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  assert.ok(matchHotkey(event, resetHotkeys())?.actionId === "generateScene");
});

test("custom mapping survives save and load", () => {
  fakeStorage();
  const assigned = applyUserShortcut(resetHotkeys(), "generateScene", { key: "k" }, true).bindings;
  saveHotkeys(assigned);
  const raw = globalThis.localStorage.getItem(TIMELINE_HOTKEYS_KEY);
  assert.ok(raw && raw.includes("generateScene"));
  const loaded = loadHotkeys();
  const generate = loaded.find((item) => item.actionId === "generateScene");
  assert.equal(generate?.userShortcut?.key, "k");
  const reset = resetHotkeys();
  assert.equal(reset.find((item) => item.actionId === "generateScene")?.userShortcut, null);
});

test("commands dispatch the registered handler only", () => {
  resetTimelineCommandsForTests();
  let count = 0;
  registerTimelineCommand("generateScene", () => {
    count += 1;
  });
  runTimelineCommand("generateScene");
  runTimelineCommand("missing");
  assert.equal(count, 1);
});

test("unbound drawer commands do not steal keystrokes", () => {
  const event = { key: "g", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  assert.equal(matchHotkey(event, resetHotkeys())?.actionId, "generateScene");
  const empty = { key: "", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  assert.equal(matchHotkey(empty, resetHotkeys()), null);
});

test("ctrl/meta chords match", () => {
  const event = { key: "d", ctrlKey: true, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  assert.ok(chordsEqual(chordFromEvent(event), { key: "d", ctrl: true }));
});

test("Shift+/ opens Hot Keys and letters in prose would match only when not typing", () => {
  const question = { key: "?", ctrlKey: false, metaKey: false, shiftKey: true, altKey: false } as KeyboardEvent;
  assert.equal(matchHotkey(question, resetHotkeys())?.actionId, "openHotkeys");
  const slash = { key: "/", ctrlKey: false, metaKey: false, shiftKey: true, altKey: false } as KeyboardEvent;
  assert.equal(matchHotkey(slash, resetHotkeys())?.actionId, "openHotkeys");
  const g = { key: "g", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  const r = { key: "r", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  const i = { key: "i", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
  assert.equal(matchHotkey(g, resetHotkeys())?.actionId, "generateScene");
  assert.equal(matchHotkey(r, resetHotkeys())?.actionId, "retake");
  assert.equal(matchHotkey(i, resetHotkeys())?.actionId, "imagePlanning");
  const typing = { tagName: "TEXTAREA", isContentEditable: false, closest: () => null, dataset: {} };
  assert.equal(isEditableTarget(typing as unknown as EventTarget), true);
});
