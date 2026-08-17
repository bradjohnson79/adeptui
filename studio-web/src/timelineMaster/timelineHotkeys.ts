/** Central Timeline hotkey registry. Keyboard and buttons share the same commands. */

export const TIMELINE_HOTKEYS_KEY = "adept_timeline_hotkeys_v1";

export type HotkeyCategory = "Playback" | "Editing" | "Generation" | "Clips & Tracks" | "Reference Authoring";

export type ShortcutChord = {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
};

export type TimelineHotkeyBinding = {
  actionId: string;
  label: string;
  category: HotkeyCategory;
  defaultShortcut: ShortcutChord;
  userShortcut: ShortcutChord | null;
  enabled: boolean;
};

export type TimelineHotkeysFile = {
  version: 1;
  bindings: Record<string, { shortcut: ShortcutChord | null; enabled: boolean }>;
};

const isMac = () =>
  typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || "");

export const DEFAULT_HOTKEYS: TimelineHotkeyBinding[] = [
  { actionId: "playPause", label: "Play / Pause Viewer", category: "Playback", defaultShortcut: { key: " " }, userShortcut: null, enabled: true },
  { actionId: "playheadLeft", label: "Playhead step back", category: "Playback", defaultShortcut: { key: "ArrowLeft" }, userShortcut: null, enabled: true },
  { actionId: "playheadRight", label: "Playhead step forward", category: "Playback", defaultShortcut: { key: "ArrowRight" }, userShortcut: null, enabled: true },
  { actionId: "playheadLeftLarge", label: "Playhead jump back", category: "Playback", defaultShortcut: { key: "ArrowLeft", shift: true }, userShortcut: null, enabled: true },
  { actionId: "playheadRightLarge", label: "Playhead jump forward", category: "Playback", defaultShortcut: { key: "ArrowRight", shift: true }, userShortcut: null, enabled: true },
  { actionId: "generateScene", label: "Generate Scene", category: "Generation", defaultShortcut: { key: "g" }, userShortcut: null, enabled: true },
  { actionId: "preflight", label: "Preflight", category: "Generation", defaultShortcut: { key: "p" }, userShortcut: null, enabled: true },
  { actionId: "retake", label: "Re-take", category: "Generation", defaultShortcut: { key: "r" }, userShortcut: null, enabled: true },
  { actionId: "imagePlanning", label: "Image Planning", category: "Generation", defaultShortcut: { key: "i" }, userShortcut: null, enabled: true },
  { actionId: "videoFinishing", label: "Video Finishing", category: "Generation", defaultShortcut: { key: "v" }, userShortcut: null, enabled: true },
  { actionId: "fullscreen", label: "Full Screen", category: "Playback", defaultShortcut: { key: "f" }, userShortcut: null, enabled: true },
  { actionId: "undo", label: "Undo", category: "Editing", defaultShortcut: { key: "z", ctrl: true }, userShortcut: null, enabled: true },
  { actionId: "redo", label: "Redo", category: "Editing", defaultShortcut: { key: "z", ctrl: true, shift: true }, userShortcut: null, enabled: true },
  { actionId: "deleteClip", label: "Delete selected clip", category: "Editing", defaultShortcut: { key: "Delete" }, userShortcut: null, enabled: true },
  { actionId: "deleteClipBackspace", label: "Delete selected clip", category: "Editing", defaultShortcut: { key: "Backspace" }, userShortcut: null, enabled: true },
  { actionId: "duplicateClip", label: "Duplicate selected clip", category: "Editing", defaultShortcut: { key: "d", ctrl: true }, userShortcut: null, enabled: true },
  { actionId: "zoomIn", label: "Timeline Zoom In", category: "Editing", defaultShortcut: { key: "+" }, userShortcut: null, enabled: true },
  { actionId: "zoomOut", label: "Timeline Zoom Out", category: "Editing", defaultShortcut: { key: "-" }, userShortcut: null, enabled: true },
  { actionId: "toggleSnap", label: "Toggle Snap", category: "Editing", defaultShortcut: { key: "s" }, userShortcut: null, enabled: true },
  { actionId: "escape", label: "Clear selection / close overlay", category: "Editing", defaultShortcut: { key: "Escape" }, userShortcut: null, enabled: true },
  { actionId: "openHotkeys", label: "Open Hot Keys", category: "Editing", defaultShortcut: { key: "?" }, userShortcut: null, enabled: true },
  { actionId: "addPrompt", label: "Prompt clip", category: "Clips & Tracks", defaultShortcut: { key: "t" }, userShortcut: null, enabled: true },
  { actionId: "addLipSync", label: "Lip Sync clip", category: "Clips & Tracks", defaultShortcut: { key: "l" }, userShortcut: null, enabled: true },
];

export function normalizeChord(chord: ShortcutChord): ShortcutChord {
  const key = chord.key === "Space" ? " " : chord.key.length === 1 ? chord.key.toLowerCase() : chord.key;
  return {
    key,
    ctrl: Boolean(chord.ctrl),
    shift: Boolean(chord.shift),
    alt: Boolean(chord.alt),
    meta: Boolean(chord.meta),
  };
}

export function chordFromEvent(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey">): ShortcutChord {
  let key = event.key;
  if ((key === "/" || key === "Slash") && event.shiftKey) key = "?";
  const chord = normalizeChord({
    key,
    ctrl: event.ctrlKey || event.metaKey,
    shift: event.shiftKey,
    alt: event.altKey,
  });
  const named = chord.key.length > 1;
  const alnum = /^[a-z0-9]$/i.test(chord.key);
  if (!named && !alnum) return { ...chord, shift: false };
  return chord;
}

export function chordsEqual(a: ShortcutChord, b: ShortcutChord): boolean {
  const left = normalizeChord(a);
  const right = normalizeChord(b);
  return (
    left.key === right.key &&
    Boolean(left.ctrl) === Boolean(right.ctrl) &&
    Boolean(left.shift) === Boolean(right.shift) &&
    Boolean(left.alt) === Boolean(right.alt)
  );
}

export function formatChord(chord: ShortcutChord, platformMac = isMac()): string {
  const parts: string[] = [];
  const n = normalizeChord(chord);
  if (n.ctrl) parts.push(platformMac ? "⌘" : "Ctrl");
  if (n.shift) parts.push("Shift");
  if (n.alt) parts.push(platformMac ? "⌥" : "Alt");
  const keyLabel =
    n.key === " " ? "Space" : n.key === "Escape" ? "Esc" : n.key === "ArrowLeft" ? "Left" : n.key === "ArrowRight" ? "Right" : n.key.length === 1 ? n.key.toUpperCase() : n.key;
  parts.push(keyLabel);
  return platformMac && n.ctrl && parts[0] === "⌘" ? parts.join(" ") : parts.join(" + ");
}

export function effectiveChord(binding: TimelineHotkeyBinding): ShortcutChord {
  return binding.userShortcut ? normalizeChord(binding.userShortcut) : normalizeChord(binding.defaultShortcut);
}

export function findConflict(
  bindings: TimelineHotkeyBinding[],
  actionId: string,
  chord: ShortcutChord,
): TimelineHotkeyBinding | null {
  return (
    bindings.find(
      (item) => item.enabled && item.actionId !== actionId && chordsEqual(effectiveChord(item), chord),
    ) || null
  );
}

export function applyUserShortcut(
  bindings: TimelineHotkeyBinding[],
  actionId: string,
  chord: ShortcutChord,
  replace = false,
): { bindings: TimelineHotkeyBinding[]; conflict: TimelineHotkeyBinding | null } {
  const conflict = findConflict(bindings, actionId, chord);
  if (conflict && !replace) return { bindings, conflict };
  const next = bindings.map((item) => {
    if (item.actionId === actionId) return { ...item, userShortcut: normalizeChord(chord), enabled: true };
    if (replace && conflict && item.actionId === conflict.actionId) {
      return { ...item, userShortcut: null, enabled: false };
    }
    return item;
  });
  return { bindings: next, conflict: null };
}

export function resetHotkeys(): TimelineHotkeyBinding[] {
  return DEFAULT_HOTKEYS.map((item) => ({ ...item, userShortcut: null, enabled: true }));
}

export function loadHotkeys(): TimelineHotkeyBinding[] {
  const base = resetHotkeys();
  try {
    const raw = localStorage.getItem(TIMELINE_HOTKEYS_KEY);
    if (!raw) return base;
    const parsed = JSON.parse(raw) as TimelineHotkeysFile;
    if (!parsed || parsed.version !== 1 || !parsed.bindings) return base;
    return base.map((item) => {
      const saved = parsed.bindings[item.actionId];
      if (!saved) return item;
      return {
        ...item,
        userShortcut: saved.shortcut ? normalizeChord(saved.shortcut) : null,
        enabled: saved.enabled !== false,
      };
    });
  } catch {
    return base;
  }
}

export function saveHotkeys(bindings: TimelineHotkeyBinding[]): void {
  const file: TimelineHotkeysFile = { version: 1, bindings: {} };
  for (const item of bindings) {
    file.bindings[item.actionId] = {
      shortcut: item.userShortcut,
      enabled: item.enabled,
    };
  }
  localStorage.setItem(TIMELINE_HOTKEYS_KEY, JSON.stringify(file));
}

export function isEditableTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  if (el.dataset?.hotkeyCapture === "true") return false;
  if (el.isContentEditable) return true;
  const tag = (el.tagName || "").toUpperCase();
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return Boolean(el.closest("input, textarea, select, [contenteditable='true'], [role='textbox']"));
}

export function matchHotkey(
  event: KeyboardEvent,
  bindings: TimelineHotkeyBinding[],
): TimelineHotkeyBinding | null {
  const chord = chordFromEvent(event);
  return bindings.find((item) => item.enabled && chordsEqual(effectiveChord(item), chord)) || null;
}

const commandHandlers = new Map<string, () => void>();

export function registerTimelineCommand(actionId: string, handler: () => void): () => void {
  commandHandlers.set(actionId, handler);
  return () => {
    if (commandHandlers.get(actionId) === handler) commandHandlers.delete(actionId);
  };
}

export function runTimelineCommand(actionId: string): void {
  commandHandlers.get(actionId)?.();
}

export function resetTimelineCommandsForTests(): void {
  commandHandlers.clear();
}
