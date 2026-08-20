/**
 * Spatial Map frontend types — mirrors the backend schema in
 * studio-api/app/spatial_map/schemas.py.
 *
 * The shared contract in `studio-web/src/contracts/spatialMapM411.ts` is frozen.
 * We extend it here locally with the V1 Cartesian grid fields and camera
 * blocking fields, casting through the existing `api.spatialMap` client.
 */
import type {
  SpatialMapDocument as _SpatialMapDocument,
  SpatialCharacterPlacement as _SpatialCharacterPlacement,
  SpatialPropPlacement as _SpatialPropPlacement,
  SpatialMapCreateBody,
  SpatialMapUpdateBody as _SpatialMapUpdateBody,
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

/** Cartesian grid placement extension. */
export type SpatialPlacementGridExtension = {
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridRow: number;
  gridColumn: number;
  slotIndex: number;
  colorKey: string;
  miniPrompt: string;
  tag: string;
  visible?: boolean;
};

/** Frozen character-prop attachment. Names match studio-api attachment.py. */
export type PlacementMode = "independent" | "attached";
export type PropRelationship =
  | "held"
  | "carried"
  | "worn"
  | "using"
  | "interacting"
  | "associated";
export type AttachmentPoint =
  | "left_hand"
  | "right_hand"
  | "both_hands"
  | "head"
  | "upper_body"
  | "lower_body"
  | "back"
  | "waist"
  | "wrist"
  | "shoulder"
  | "unspecified";
/** Product Character 1-4. Not slotIndex (0-3). Mapping: slot = slotIndex + 1. */
export type AttachedCharacterSlot = 1 | 2 | 3 | 4;

export const PLACEMENT_MODES = ["independent", "attached"] as const;
export const PROP_RELATIONSHIPS = [
  "held",
  "carried",
  "worn",
  "using",
  "interacting",
  "associated",
] as const;
export const ATTACHMENT_POINTS = [
  "left_hand",
  "right_hand",
  "both_hands",
  "head",
  "upper_body",
  "lower_body",
  "back",
  "waist",
  "wrist",
  "shoulder",
  "unspecified",
] as const;
export const ATTACHED_CHARACTER_SLOTS = [1, 2, 3, 4] as const;

export type SpatialPropAttachmentFields = {
  placementMode: PlacementMode;
  attachedCharacterSlot: AttachedCharacterSlot | null;
  attachedCharacterId: string | null;
  relationship: PropRelationship | null;
  attachmentPoint: AttachmentPoint | null;
};

export type SpatialPlacement = _SpatialCharacterPlacement & SpatialPlacementGridExtension;

export type SpatialCharacterPlacement = Omit<_SpatialCharacterPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension;

export type SpatialPropPlacement = Omit<_SpatialPropPlacement, keyof SpatialPlacementGridExtension> & SpatialPlacementGridExtension & SpatialPropAttachmentFields;

export type SpatialCamera = _SpatialCamera & {
  cameraSlot: number;
  orientation: string;
  fovPreset: string;
  /** Scene Creator Mini: framing-only shot size (auto|wide|medium_wide|medium|medium_close|close_up|extreme_close). */
  shotSize?: string;
  /** Scene Creator Mini: auto|environment|<characterId>. */
  primarySubject?: string;
  normalizedX?: number | null;
  normalizedY?: number | null;
  gridRow: number;
  gridColumn: number;
  visible?: boolean;
};

export const SHOT_SIZES = [
  "auto",
  "wide",
  "medium_wide",
  "medium",
  "medium_close",
  "close_up",
  "extreme_close",
] as const;
export type ShotSize = (typeof SHOT_SIZES)[number];

export function normalizeShotSize(value: string | null | undefined): ShotSize {
  const v = String(value || "auto").trim().toLowerCase().replace(/[ -]/g, "_");
  return (SHOT_SIZES as readonly string[]).includes(v) ? (v as ShotSize) : "auto";
}

export function shotSizeLabel(value: string | null | undefined): string {
  const v = normalizeShotSize(value);
  if (v === "auto") return "Auto";
  return v
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Atlas Scene Intent — compact semantic snapshot taken at Atlas creation. */
export type SceneIntent = {
  version?: number;
  purpose?: string;
  sceneTitle?: string;
  locationType?: string;
  summary?: string;
  productionIntent?: string;
  keySubjects?: string[];
  keyProps?: string[];
  environmentTraits?: string[];
  sourcePromptSummary?: string;
  sourceReferenceAssetIds?: string[];
};

export type MovementDialogue = {
  speaker: string;
  text: string;
};

export type MovementAction = {
  actor?: string;
  verb?: string;
  target?: string;
  hand?: string;
  emotion?: string;
};

export type MovementContinuity = {
  requiredUnchanged?: string[];
  requiredChanged?: string[];
  notes?: string;
};

export type MovementSegment = {
  id: string;
  segmentNumber: number;
  beatName?: string;
  characterStates: SpatialCharacterPlacement[];
  propStates: SpatialPropPlacement[];
  cameraStateRefs?: string[];
  userDirection?: string;
  productionPrompt?: string;
  actions?: MovementAction[];
  dialogue?: MovementDialogue[];
  continuity?: MovementContinuity;
  timingHintSeconds?: number | null;
  revision?: number;
  createdAt?: string;
  updatedAt?: string;
};

export type MovementCreateBody = {
  beatName?: string;
  userDirection?: string;
  productionPrompt?: string;
  dialogue?: MovementDialogue[];
  actions?: MovementAction[];
  inheritFromId?: string | null;
};

export type MovementUpdateBody = {
  beatName?: string | null;
  userDirection?: string | null;
  productionPrompt?: string | null;
  dialogue?: MovementDialogue[] | null;
  actions?: MovementAction[] | null;
  continuity?: MovementContinuity | null;
  timingHintSeconds?: number | null;
};

export type MovementArrow = {
  characterId: string;
  label: string;
  fromAlias: string;
  toAlias: string;
  from: { normalizedX?: number | null; normalizedY?: number | null; gridRow?: number; gridColumn?: number };
  to: { normalizedX?: number | null; normalizedY?: number | null; gridRow?: number; gridColumn?: number };
};

export type SpatialMapDocument = Omit<_SpatialMapDocument, "characters" | "props" | "cameras"> & {
  characters: SpatialCharacterPlacement[];
  props: SpatialPropPlacement[];
  cameras: SpatialCamera[];
  gridScale: number;
  placementGrid?: string;
  sceneIntent?: SceneIntent | null;
  originalEnvironmentReferenceAssetId?: string | null;
  originatingUserPrompt?: string;
  /** Server-computed lineage fingerprint for ERS staleness. */
  groundingFingerprint?: string;
  /** Explicit Save commit marker (Spatial Map Save Gate). Dirty = savedVersion !== version. */
  savedAt?: string | null;
  savedVersion?: string | null;
  movementSegments?: MovementSegment[];
  activeMovementSegmentId?: string | null;
  movementSegmentRevision?: number;
};

/** Body types extended with V1 Cartesian grid fields. */
export type SpatialCharacterPlacementBody = _SpatialCharacterPlacementBody & Partial<SpatialPlacementGridExtension>;

export type SpatialCharacterPlacementUpdateBody = _SpatialCharacterPlacementUpdateBody & Partial<SpatialPlacementGridExtension>;

export type SpatialPropPlacementBody = _SpatialPropPlacementBody & Partial<SpatialPlacementGridExtension> & Partial<SpatialPropAttachmentFields>;

export type SpatialPropPlacementUpdateBody = _SpatialPropPlacementUpdateBody & Partial<SpatialPlacementGridExtension> & Partial<SpatialPropAttachmentFields>;

export type SpatialMapUpdateBody = _SpatialMapUpdateBody & {
  gridScale?: number;
  sceneDescription?: string | null;
  sceneIntent?: SceneIntent | null;
  originalEnvironmentReferenceAssetId?: string | null;
  originatingUserPrompt?: string | null;
};

export type SpatialMapSceneIntentCreateBody = SpatialMapCreateBody & {
  sceneDescription?: string | null;
  sceneIntent?: SceneIntent | null;
  originalEnvironmentReferenceAssetId?: string | null;
  originatingUserPrompt?: string | null;
};

export type {
  SpatialMapCreateBody,
  SpatialMapListResponse,
  SpatialMapDocumentResponse,
  ProviderHonestyMode,
  SpatialBounds,
  SpatialAnchor,
  SpatialMovementPath,
  Spatial360Collage,
};

export type SlotKind = "character" | "prop" | "camera";

export type ActivePlacement = {
  type: SlotKind;
  slot: number;
  entityId: string;
};

export type SavedOption = {
  id: string;
  name: string;
  thumbnailUrl?: string | null;
  assetId?: string | null;
  source?: "project" | "character" | "library";
};

/** Project PropEntity.id is the only value allowed in SpatialPropPlacement.propId. */
export type PropPlacementIdentity = {
  propId: string | null;
  category: "project" | "character_prop" | "prop";
};

export function propPlacementIdentity(option: Pick<SavedOption, "id" | "source">): PropPlacementIdentity {
  if (option.source === "project") {
    return { propId: option.id, category: "project" };
  }
  if (option.source === "character") {
    return { propId: null, category: "character_prop" };
  }
  return { propId: null, category: "prop" };
}

/**
 * CDX-012: only approved project PropEntities (source "project") bind a
 * canonical propId that Scene Creator / ERS downstream consumers accept.
 * Character-Props and Library placements carry propId:null and are silently
 * dropped from shots — so they are MAP-ONLY and must be labeled + warned.
 */
export const PROP_MAP_ONLY_SOURCES: ReadonlySet<SavedOption["source"]> = new Set([
  "character",
  "library",
]);

export function propOptionPropagatesToSceneCreator(
  option: Pick<SavedOption, "source"> | null | undefined,
): boolean {
  return option?.source === "project";
}

/** Dropdown group label for a saved-prop source (CDX-012 honesty). */
export function propSourceGroupLabel(
  source: SavedOption["source"] | undefined,
): string {
  if (source === "project") return "Project Props";
  if (source === "character") return "Character Props (map only)";
  return "Library (map only)";
}

/** Neutral descriptor for a map-only prop placement (CDX-012, Save Gate cleanup).
 * No longer an alarming warning: the map is the authoritative source and
 * binding controls remain available on the slot. */
export const PROP_MAP_ONLY_WARNING =
  "Map-only placement — bind an approved Project Prop to include this prop in Scene Creator shots.";

/** Positive state shown once a placement binds to an approved Project Prop. */
export const PROP_BOUND_TO_APPROVED_MESSAGE =
  "Bound to approved Project Prop — included in Scene Creator shots.";

/** Positive state shown once a placement binds to a Project Prop that is not
 * approved for production (still honest: it will not propagate). */
export const PROP_BOUND_UNAPPROVED_MESSAGE =
  "Project Prop selected, but it is not approved for production.";

/** A placement resolves to a canonical approved Project Prop when it carries a
 * propId that matches a project-source saved option (approved-only list). */
export function propPlacementIsBoundApproved(
  placement: Pick<SpatialPropPlacement, "propId"> | null | undefined,
  savedOptions: ReadonlyArray<Pick<SavedOption, "id" | "source">>,
): boolean {
  if (!placement || !placement.propId) return false;
  return savedOptions.some(
    (o) => o.id === placement.propId && (o.source || "library") === "project",
  );
}

export type SlotColorKey = "red" | "blue" | "orange" | "green" | "purple" | "brown" | "aqua" | "gray";

export type SlotDef = {
  index: number;
  colorKey: SlotColorKey;
  label: string;
  kind: SlotKind;
};

// CHARACTER_SLOTS.index is 0-based slotIndex. Product attachedCharacterSlot is 1-4.
// Mapping: attachedCharacterSlot = slotIndex + 1. Never store 0-based in attachedCharacterSlot.
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

export type PropAttachmentInput = {
  placementMode?: PlacementMode | null;
  attachedCharacterSlot?: AttachedCharacterSlot | number | null;
  attachedCharacterId?: string | null;
  relationship?: PropRelationship | string | null;
  attachmentPoint?: AttachmentPoint | string | null;
};

/** Map existing 0-based slotIndex to product attachedCharacterSlot (1-4). */
export function attachedSlotFromSlotIndex(slotIndex: number | null | undefined): AttachedCharacterSlot | null {
  if (slotIndex === 0 || slotIndex === 1 || slotIndex === 2 || slotIndex === 3) {
    return (slotIndex + 1) as AttachedCharacterSlot;
  }
  return null;
}

/** Map product attachedCharacterSlot (1-4) to existing 0-based slotIndex. */
export function slotIndexFromAttachedSlot(attachedCharacterSlot: AttachedCharacterSlot): number {
  return attachedCharacterSlot - 1;
}

function isAttachedSlot(value: unknown): value is AttachedCharacterSlot {
  return value === 1 || value === 2 || value === 3 || value === 4;
}

export function normalizePropAttachment<T extends PropAttachmentInput>(prop: T): T {
  const mode = prop.placementMode === "attached" ? "attached" : "independent";
  if (mode !== "attached") {
    prop.placementMode = "independent";
    prop.attachedCharacterSlot = null;
    prop.attachedCharacterId = null;
    prop.relationship = null;
    prop.attachmentPoint = null;
    return prop;
  }
  prop.placementMode = "attached";
  if (typeof prop.attachedCharacterId === "string" && !prop.attachedCharacterId.trim()) {
    prop.attachedCharacterId = null;
  }
  return prop;
}

export function validatePropAttachment<T extends PropAttachmentInput>(prop: T): T {
  normalizePropAttachment(prop);
  if (prop.placementMode !== "attached") {
    return prop;
  }
  const slot = prop.attachedCharacterSlot;
  if (slot != null && !isAttachedSlot(slot)) {
    throw new Error(
      "attachedCharacterSlot must be 1-4 (Character 1-4); do not use slotIndex 0-3 here (mapping: attachedCharacterSlot = slotIndex + 1)",
    );
  }
  const hasCharacter = Boolean(prop.attachedCharacterId && String(prop.attachedCharacterId).trim()) || isAttachedSlot(slot);
  if (!hasCharacter) {
    throw new Error("attached prop requires attachedCharacterId or attachedCharacterSlot (1-4)");
  }
  if (!PROP_RELATIONSHIPS.includes(prop.relationship as (typeof PROP_RELATIONSHIPS)[number])) {
    throw new Error("attached prop requires relationship (held|carried|worn|using|interacting|associated)");
  }
  if (prop.attachmentPoint != null && !ATTACHMENT_POINTS.includes(prop.attachmentPoint as (typeof ATTACHMENT_POINTS)[number])) {
    throw new Error(`invalid attachmentPoint: ${prop.attachmentPoint}`);
  }
  return prop;
}
