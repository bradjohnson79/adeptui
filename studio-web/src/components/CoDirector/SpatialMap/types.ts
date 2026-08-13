/**
 * Spatial Map frontend types — mirrors the backend schema in
 * studio-api/app/spatial_map/schemas.py.
 *
 * The shared contract in `studio-web/src/contracts/spatialMapM411.ts` is frozen.
 * We extend it here locally with the V1 circular/radial grid fields and camera
 * blocking fields, casting through the existing `api.spatialMap` client.
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
  SpatialCamera as _SpatialCamera,
  SpatialMovementPath,
  Spatial360Collage,
} from "../../../contracts/spatialMapM411";

export type { GridScale } from "./gridGeometry";

/** Circular/radial grid placement extension (V1). */
export type SpatialPlacementGridExtension = {
  gridRow: number; // ring index, 0 = innermost, -1 = unplaced
  gridColumn: number; // spoke index 0..7 (N, NE, E...), -1 = unplaced
  slotIndex: number; // 0-3, -1 = none
  colorKey: string; // red|blue|orange|green (characters), purple|brown|aqua|gray (props)
  miniPrompt: string;
  tag: string;
};

export type SpatialPlacement = _SpatialCharacterPlacement & SpatialPlacementGridExtension;

export type SpatialCharacterPlacement = Omit<_SpatialCharacterPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension;

export type SpatialPropPlacement = Omit<_SpatialPropPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension;

export type SpatialCamera = _SpatialCamera & {
  cameraSlot: number;
  orientation: string; // N, NE, E, SE, S, SW, W, NW
  fovPreset: string; // narrow, medium, wide
};

export type SpatialMapDocument = Omit<_SpatialMapDocument, "characters" | "props" | "cameras" | "gridScale"> & {
  characters: SpatialCharacterPlacement[];
  props: SpatialPropPlacement[];
  cameras: SpatialCamera[];
  gridScale: number;
};

/** Body types extended with V1 circular grid fields. */
export type SpatialCharacterPlacementBody = _SpatialCharacterPlacementBody & Partial<SpatialPlacementGridExtension>;

export type SpatialCharacterPlacementUpdateBody = _SpatialCharacterPlacementUpdateBody & Partial<SpatialPlacementGridExtension>;

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
  SpatialMovementPath,
  Spatial360Collage,
};

export type SlotKind = "character" | "prop" | "camera";

export type SlotColorKey = "red" | "blue" | "orange" | "green" | "purple" | "brown" | "aqua" | "gray";

export type SlotDef = {
  index: number;
  colorKey: SlotColorKey;
  label: string;
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

export const CAMERA_SLOTS: SlotDef[] = [
  { index: 0, colorKey: "gray", label: "C1", kind: "camera" },
  { index: 1, colorKey: "gray", label: "C2", kind: "camera" },
  { index: 2, colorKey: "gray", label: "C3", kind: "camera" },
  { index: 3, colorKey: "gray", label: "C4", kind: "camera" },
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

/** Normalize a human prop label into a project-safe tag (#coffee-cup). */
export function normalizePropTag(label: string): string {
  const s = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  return s || "prop";
}

/** Build the @ tag for a character name. */
export function characterTag(name: string): string {
  const trimmed = name.trim();
  return trimmed ? `@${trimmed}` : "";
}
