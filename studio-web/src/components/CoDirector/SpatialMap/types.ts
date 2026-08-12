/**
 * Spatial Map frontend types — mirrors the frozen backend schema in
 * studio-api/app/spatial_map/schemas.py (SpatialPlacement extension + grid
 * fields added in V1).
 *
 * NOTE: The shared contract in `studio-web/src/contracts/spatialMapM411.ts`
 * predates the V1 grid placement extension (gridRow/gridColumn/slotIndex/
 * colorKey/miniPrompt/tag). We extend it here WITHOUT modifying the frozen
 * contract, casting through the existing `api.spatialMap` client.
 */
import type {
  SpatialMapDocument as _SpatialMapDocument,
  SpatialCharacterPlacement as _SpatialCharacterPlacement,
  SpatialPropPlacement as _SpatialPropPlacement,
  SpatialMapCreateBody,
  SpatialMapUpdateBody,
  SpatialMapListResponse,
  SpatialMapDocumentResponse,
  SpatialCharacterPlacementBody as _SpatialCharacterPlacementBody,
  SpatialCharacterPlacementUpdateBody as _SpatialCharacterPlacementUpdateBody,
  SpatialPropPlacementBody as _SpatialPropPlacementBody,
  SpatialPropPlacementUpdateBody as _SpatialPropPlacementUpdateBody,
  ProviderHonestyMode,
  SpatialBounds,
  SpatialAnchor,
  SpatialCamera,
  SpatialMovementPath,
  Spatial360Collage,
} from "../../../contracts/spatialMapM411";

/** Grid placement extension (V1) — added to base SpatialPlacement in backend. */
export type SpatialPlacementGridExtension = {
  gridRow: number; // 0-9, -1 = unplaced
  gridColumn: number; // 0-9, -1 = unplaced
  slotIndex: number; // 0-3, -1 = none
  colorKey: string; // red|blue|orange|green (characters), purple|brown|aqua|gray (props)
  miniPrompt: string; // e.g. "@Korri is standing behind the barista bar."
  tag: string; // "@Korri" or "#coffee-cup" — friendly reference
};

export type SpatialPlacement = _SpatialCharacterPlacement & SpatialPlacementGridExtension;

export type SpatialCharacterPlacement = Omit<_SpatialCharacterPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension;

export type SpatialPropPlacement = Omit<_SpatialPropPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension;

export type SpatialMapDocument = Omit<_SpatialMapDocument, "characters" | "props"> & {
  characters: SpatialCharacterPlacement[];
  props: SpatialPropPlacement[];
};

/** Body types extended with V1 grid fields (sent via PATCH to persist grid). */
export type SpatialCharacterPlacementBody = _SpatialCharacterPlacementBody & Partial<SpatialPlacementGridExtension>;

export type SpatialCharacterPlacementUpdateBody = _SpatialCharacterPlacementUpdateBody &
  Partial<SpatialPlacementGridExtension>;

export type SpatialPropPlacementBody = _SpatialPropPlacementBody & Partial<SpatialPlacementGridExtension>;

export type SpatialPropPlacementUpdateBody = _SpatialPropPlacementUpdateBody & Partial<SpatialPlacementGridExtension>;

export type {
  SpatialMapCreateBody,
  SpatialMapUpdateBody,
  SpatialMapListResponse,
  SpatialMapDocumentResponse,
  ProviderHonestyMode,
  SpatialBounds,
  SpatialAnchor,
  SpatialCamera,
  SpatialMovementPath,
  Spatial360Collage,
};

/** V1 slot configuration — amendment: accessible labels in addition to color. */
export type SlotKind = "character" | "prop";

export type SlotColorKey = "red" | "blue" | "orange" | "green" | "purple" | "brown" | "aqua" | "gray";

export type SlotDef = {
  index: number; // 0-3
  colorKey: SlotColorKey;
  label: string; // "Character 1 (Red)"
  kind: SlotKind;
};

export const CHARACTER_SLOTS: SlotDef[] = [
  { index: 0, colorKey: "red", label: "Character 1 (Red)", kind: "character" },
  { index: 1, colorKey: "blue", label: "Character 2 (Blue)", kind: "character" },
  { index: 2, colorKey: "orange", label: "Character 3 (Orange)", kind: "character" },
  { index: 3, colorKey: "green", label: "Character 4 (Green)", kind: "character" },
];

export const PROP_SLOTS: SlotDef[] = [
  { index: 0, colorKey: "purple", label: "Prop 1 (Purple)", kind: "prop" },
  { index: 1, colorKey: "brown", label: "Prop 2 (Brown)", kind: "prop" },
  { index: 2, colorKey: "aqua", label: "Prop 3 (Aqua)", kind: "prop" },
  { index: 3, colorKey: "gray", label: "Prop 4 (Gray)", kind: "prop" },
];

export const SLOT_COLORS: Record<SlotColorKey, string> = {
  red: "#e5484d",
  blue: "#3b82f6",
  orange: "#f97316",
  green: "#22c55e",
  purple: "#a855f7",
  brown: "#a16207",
  aqua: "#06b6d4",
  gray: "#94a3b8",
};

/** 10x10 grid coordinate helpers. Columns A-J, rows 1-10. */
export const GRID_SIZE = 10;

export function columnLetter(column: number): string {
  // 0 -> A, 9 -> J
  return String.fromCharCode("A".charCodeAt(0) + column);
}

export function cellLabel(row: number, column: number): string {
  // row 0 -> "1", column 0 -> "A" → "A1"
  return `${columnLetter(column)}${row + 1}`;
}

/** Normalize a human prop label into a project-safe tag (#coffee-cup). */
export function normalizePropTag(label: string): string {
  const s = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return s || "prop";
}

/** Build the @ tag for a character name (amendment #5 — real names with spaces). */
export function characterTag(name: string): string {
  const trimmed = name.trim();
  return trimmed ? `@${trimmed}` : "";
}
