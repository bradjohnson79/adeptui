/** MAGI shortcut registry. Same chord helpers as Timeline, separate storage and map. */

import {
  loadHotkeyBindings,
  resetHotkeyBindings,
  saveHotkeyBindings,
  type TimelineHotkeyBinding,
} from "../timelineMaster/timelineHotkeys";

export const MAGI_HOTKEYS_KEY = "adept_magi_hotkeys_v1";

export const DEFAULT_MAGI_HOTKEYS: TimelineHotkeyBinding[] = [
  { actionId: "playPause", label: "Play / Pause", category: "Playback", defaultShortcut: { key: " " }, userShortcut: null, enabled: true },
  { actionId: "playPauseK", label: "Play / Pause", category: "Playback", defaultShortcut: { key: "k" }, userShortcut: null, enabled: true },
  { actionId: "jogBack", label: "Jump backward", category: "Playback", defaultShortcut: { key: "j" }, userShortcut: null, enabled: true },
  { actionId: "jogForward", label: "Jump forward", category: "Playback", defaultShortcut: { key: "l" }, userShortcut: null, enabled: true },
  { actionId: "frameBack", label: "Back", category: "Playback", defaultShortcut: { key: "ArrowLeft" }, userShortcut: null, enabled: true },
  { actionId: "frameForward", label: "Forward", category: "Playback", defaultShortcut: { key: "ArrowRight" }, userShortcut: null, enabled: true },
  { actionId: "goToStart", label: "Beginning", category: "Playback", defaultShortcut: { key: "Home" }, userShortcut: null, enabled: true },
  { actionId: "goToEnd", label: "End", category: "Playback", defaultShortcut: { key: "End" }, userShortcut: null, enabled: true },
  { actionId: "undo", label: "Undo", category: "Editing", defaultShortcut: { key: "z", ctrl: true }, userShortcut: null, enabled: true },
  { actionId: "redo", label: "Redo", category: "Editing", defaultShortcut: { key: "z", ctrl: true, shift: true }, userShortcut: null, enabled: true },
  { actionId: "deleteClip", label: "Delete selected clip", category: "Editing", defaultShortcut: { key: "Delete" }, userShortcut: null, enabled: true },
  { actionId: "deleteClipBackspace", label: "Delete selected clip", category: "Editing", defaultShortcut: { key: "Backspace" }, userShortcut: null, enabled: true },
  { actionId: "splitAtPlayhead", label: "Split at playhead", category: "Editing", defaultShortcut: { key: "s" }, userShortcut: null, enabled: true },
  { actionId: "copy", label: "Copy selected clips", category: "Editing", defaultShortcut: { key: "c", ctrl: true }, userShortcut: null, enabled: true },
  { actionId: "paste", label: "Paste clips", category: "Editing", defaultShortcut: { key: "v", ctrl: true }, userShortcut: null, enabled: true },
  { actionId: "zoomIn", label: "Zoom in", category: "View", defaultShortcut: { key: "+" }, userShortcut: null, enabled: true },
  { actionId: "zoomOut", label: "Zoom out", category: "View", defaultShortcut: { key: "-" }, userShortcut: null, enabled: true },
  { actionId: "compare", label: "Compare", category: "View", defaultShortcut: { key: "c" }, userShortcut: null, enabled: true },
  { actionId: "splitView", label: "Split View", category: "View", defaultShortcut: { key: "\\" }, userShortcut: null, enabled: true },
  { actionId: "openHotkeys", label: "Open Hot Keys", category: "View", defaultShortcut: { key: "?" }, userShortcut: null, enabled: true },
];

export function resetMagiHotkeys(): TimelineHotkeyBinding[] {
  return resetHotkeyBindings(DEFAULT_MAGI_HOTKEYS);
}

export function loadMagiHotkeys(): TimelineHotkeyBinding[] {
  return loadHotkeyBindings(MAGI_HOTKEYS_KEY, DEFAULT_MAGI_HOTKEYS);
}

export function saveMagiHotkeys(bindings: TimelineHotkeyBinding[]): void {
  saveHotkeyBindings(MAGI_HOTKEYS_KEY, bindings);
}
