/**
 * Current ERS Edit/Inpaint Legend overlay state (one authority).
 * Position is normalized to the ERS sheet (0..1), not screen pixels.
 * Survives tool change / remount within the edit session; Save commits a snapshot.
 */

import {
  ERS_LEGEND_CHARACTER_COLORS,
  ERS_LEGEND_PROP_COLORS,
  type DrawColor,
} from "./ersAnnotationPalette";
import {
  ERS_LEGEND_SLOT_COUNT,
  clampErsLegendBox,
  defaultErsLegendBox,
  type ErsNormalizedBox,
} from "./ersSheetLayout";

export type ErsLegendSlot = { color: string; label: string };

export type ErsLegendEditSnapshot = {
  position: ErsNormalizedBox;
  characters: ErsLegendSlot[];
  props: ErsLegendSlot[];
  /** True once the user has dragged away from the default center column. */
  userMoved: boolean;
  /** Direction / Movement plain-text note (max 50 words). */
  directionMovement: string;
};

function slotsFor(colors: readonly string[]): ErsLegendSlot[] {
  return Array.from({ length: ERS_LEGEND_SLOT_COUNT }, (_, index) => ({
    color: colors[index] || "#9ca3af",
    label: "",
  }));
}

export const ERS_DIRECTION_MOVEMENT_MAX_WORDS = 50;

/**
 * Clamp Direction/Movement to max 50 words WITHOUT collapsing whitespace.
 * Used while typing so spaces, newlines, and caret position stay accurate.
 */
export function clampDirectionMovementText(raw: string | null | undefined): string {
  const textVal = String(raw ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (!textVal) return "";
  const words = textVal.match(/\S+/g);
  if (!words || words.length <= ERS_DIRECTION_MOVEMENT_MAX_WORDS) {
    return textVal;
  }
  let count = 0;
  let end = 0;
  const re = /\S+/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(textVal)) !== null) {
    count += 1;
    end = match.index + match[0].length;
    if (count >= ERS_DIRECTION_MOVEMENT_MAX_WORDS) break;
  }
  return textVal.slice(0, end);
}

/** Trim ends for Save/compare only — never collapses internal spaces/newlines. */
export function finalizeDirectionMovementText(raw: string | null | undefined): string {
  return clampDirectionMovementText(raw).replace(/^\s+/, "").replace(/\s+$/, "");
}

export function createDefaultErsLegendSnapshot(): ErsLegendEditSnapshot {
  return {
    position: defaultErsLegendBox(),
    characters: slotsFor(ERS_LEGEND_CHARACTER_COLORS),
    props: slotsFor(ERS_LEGEND_PROP_COLORS),
    userMoved: false,
    directionMovement: "",
  };
}

export function ersLegendStateKey(input: {
  projectId: string;
  sheetId: string;
  sourceAssetId: string;
}): string {
  return `ers-legend:${input.projectId}:${input.sheetId}:${input.sourceAssetId}`;
}

const live = new Map<string, ErsLegendEditSnapshot>();
/** Save commits land here so reload works even when sessionStorage is unavailable (Node/tests). */
const durable = new Map<string, ErsLegendEditSnapshot>();

function storageKey(key: string): string {
  return `adept.ersLegendEdit.${key}`;
}

function cloneSnapshot(snap: ErsLegendEditSnapshot): ErsLegendEditSnapshot {
  return {
    position: { ...snap.position },
    characters: snap.characters.map((s) => ({ ...s })),
    props: snap.props.map((s) => ({ ...s })),
    userMoved: snap.userMoved,
    // Live clone keeps typing whitespace; Save finalizes separately.
    directionMovement: clampDirectionMovementText(snap.directionMovement),
  };
}

function sanitizeSnapshot(raw: unknown): ErsLegendEditSnapshot | null {
  if (!raw || typeof raw !== "object") return null;
  const obj = raw as Record<string, unknown>;
  const pos = obj.position as Record<string, unknown> | undefined;
  if (!pos || typeof pos.left !== "number" || typeof pos.top !== "number") return null;
  const base = createDefaultErsLegendSnapshot();
  const width = typeof pos.width === "number" ? pos.width : base.position.width;
  const height = typeof pos.height === "number" ? pos.height : base.position.height;
  const characters = Array.isArray(obj.characters)
    ? obj.characters.map((slot, i) => {
        const s = (slot || {}) as Record<string, unknown>;
        return {
          color: typeof s.color === "string" ? s.color : base.characters[i]?.color || "#9ca3af",
          label: typeof s.label === "string" ? s.label : "",
        };
      })
    : base.characters;
  const props = Array.isArray(obj.props)
    ? obj.props.map((slot, i) => {
        const s = (slot || {}) as Record<string, unknown>;
        return {
          color: typeof s.color === "string" ? s.color : base.props[i]?.color || "#9ca3af",
          label: typeof s.label === "string" ? s.label : "",
        };
      })
    : base.props;
  while (characters.length < ERS_LEGEND_SLOT_COUNT) {
    characters.push({ color: ERS_LEGEND_CHARACTER_COLORS[characters.length] || "#9ca3af", label: "" });
  }
  while (props.length < ERS_LEGEND_SLOT_COUNT) {
    props.push({ color: ERS_LEGEND_PROP_COLORS[props.length] || "#9ca3af", label: "" });
  }
  const directionMovement = finalizeDirectionMovementText(
    typeof obj.directionMovement === "string"
      ? obj.directionMovement
      : typeof obj.direction_movement === "string"
        ? obj.direction_movement
        : typeof obj.movement === "string"
          ? obj.movement
          : "",
  );
  return {
    position: clampErsLegendBox({
      left: pos.left,
      top: pos.top,
      width,
      height,
    }),
    characters: characters.slice(0, ERS_LEGEND_SLOT_COUNT),
    props: props.slice(0, ERS_LEGEND_SLOT_COUNT),
    userMoved: Boolean(obj.userMoved),
    directionMovement,
  };
}

/** Load live edit state, else last Save commit, else defaults. */
export function loadErsLegendEditState(key: string): ErsLegendEditSnapshot {
  const existing = live.get(key);
  if (existing) return cloneSnapshot(existing);
  const saved = durable.get(key);
  if (saved) {
    live.set(key, saved);
    return cloneSnapshot(saved);
  }
  try {
    if (typeof sessionStorage !== "undefined") {
      const raw = sessionStorage.getItem(storageKey(key));
      if (raw) {
        const parsed = sanitizeSnapshot(JSON.parse(raw));
        if (parsed) {
          durable.set(key, parsed);
          live.set(key, parsed);
          return cloneSnapshot(parsed);
        }
      }
    }
  } catch {
    /* ignore corrupt storage */
  }
  const fresh = createDefaultErsLegendSnapshot();
  live.set(key, fresh);
  return cloneSnapshot(fresh);
}

/** Update live edit state (drag / label / color). Does not commit Save. */
export function updateErsLegendEditState(
  key: string,
  patch: Partial<ErsLegendEditSnapshot> | ((prev: ErsLegendEditSnapshot) => ErsLegendEditSnapshot),
): ErsLegendEditSnapshot {
  const prev = loadErsLegendEditState(key);
  const next =
    typeof patch === "function"
      ? patch(prev)
      : {
          ...prev,
          ...patch,
          position: patch.position ? clampErsLegendBox(patch.position) : prev.position,
          characters: patch.characters ?? prev.characters,
          props: patch.props ?? prev.props,
        };
  const clamped = {
    ...next,
    position: clampErsLegendBox(next.position),
  };
  live.set(key, clamped);
  return cloneSnapshot(clamped);
}

/** Persist Save commit: labels, colors, legend position, metadata flags. */
export function saveErsLegendEditState(key: string, snap?: ErsLegendEditSnapshot): ErsLegendEditSnapshot {
  const toSave = clampSnapshot(snap ? cloneSnapshot(snap) : loadErsLegendEditState(key));
  live.set(key, toSave);
  durable.set(key, cloneSnapshot(toSave));
  try {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.setItem(storageKey(key), JSON.stringify(toSave));
    }
  } catch {
    /* quota / private mode — durable map still holds the Save commit */
  }
  return cloneSnapshot(toSave);
}

function clampSnapshot(snap: ErsLegendEditSnapshot): ErsLegendEditSnapshot {
  return {
    ...snap,
    position: clampErsLegendBox(snap.position),
    characters: snap.characters.map((s) => ({ ...s })),
    props: snap.props.map((s) => ({ ...s })),
    directionMovement: finalizeDirectionMovementText(snap.directionMovement),
  };
}


/** Test helper: drop live map only so Save storage can be reloaded. */

function snapshotEqual(a: ErsLegendEditSnapshot, b: ErsLegendEditSnapshot): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** True when live Legend edits differ from the last Save commit (or defaults if never saved). */
export function ersLegendEditHasUnsavedChanges(key: string): boolean {
  const liveSnap = live.get(key);
  if (!liveSnap) return false;
  const committed = durable.get(key);
  if (!committed) {
    // Never saved: dirty if user moved or edited labels/colors away from defaults.
    const defaults = createDefaultErsLegendSnapshot();
    return !snapshotEqual(clampSnapshot(liveSnap), defaults);
  }
  return !snapshotEqual(clampSnapshot(liveSnap), clampSnapshot(committed));
}

export function dropLiveErsLegendEditState(key: string): void {
  live.delete(key);
}

/** Test helper: clear live + storage for a key. */
export function clearErsLegendEditState(key: string): void {
  live.delete(key);
  durable.delete(key);
  try {
    if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(storageKey(key));
  } catch {
    /* ignore */
  }
}

export type { DrawColor };
