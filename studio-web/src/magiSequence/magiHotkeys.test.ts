import { describe, expect, it } from "vitest";
import { matchHotkey, resetHotkeys, TIMELINE_HOTKEYS_KEY } from "../timelineMaster/timelineHotkeys";
import { DEFAULT_MAGI_HOTKEYS, loadMagiHotkeys, MAGI_HOTKEYS_KEY, saveMagiHotkeys } from "./magiHotkeys";

describe("MAGI hotkey registry", () => {
  it("keeps MAGI commands out of the Timeline list and storage", () => {
    const magiIds = DEFAULT_MAGI_HOTKEYS.map((item) => item.actionId);
    expect(magiIds).toContain("playPause");
    expect(magiIds).toContain("splitAtPlayhead");
    expect(magiIds).toContain("compare");
    expect(magiIds).toContain("splitView");
    expect(magiIds).toContain("zoomIn");
    expect(magiIds).not.toContain("generateScene");
    expect(MAGI_HOTKEYS_KEY).not.toBe(TIMELINE_HOTKEYS_KEY);
    const space = { key: " ", ctrlKey: false, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
    expect(matchHotkey(space, resetHotkeys())?.actionId).toBe("playPause");
    expect(matchHotkey(space, loadMagiHotkeys())?.label).toBe("Play / Pause");
    const undo = { key: "z", ctrlKey: true, metaKey: false, shiftKey: false, altKey: false } as KeyboardEvent;
    expect(matchHotkey(undo, resetHotkeys())?.actionId).toBe("undo");
    expect(matchHotkey(undo, loadMagiHotkeys())?.actionId).toBe("undo");
    const store = new Map<string, string>();
    const previous = globalThis.localStorage;
    globalThis.localStorage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => store.clear(),
      key: () => null,
      length: 0,
    } as Storage;
    try {
      saveMagiHotkeys(loadMagiHotkeys());
      expect(store.get(TIMELINE_HOTKEYS_KEY)).toBeUndefined();
      expect(store.get(MAGI_HOTKEYS_KEY)).toContain("splitAtPlayhead");
      expect(store.get(MAGI_HOTKEYS_KEY)).not.toContain("generateScene");
    } finally {
      globalThis.localStorage = previous;
    }
  });
});
