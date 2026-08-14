/**
 * Spatial Map character-prop attachment UI helpers.
 * Frozen field names live in types.ts / attachment.py — do not rename.
 */
import {
  ATTACHMENT_POINTS,
  attachedSlotFromSlotIndex,
  CHARACTER_SLOTS,
  type AttachmentPoint,
  type AttachedCharacterSlot,
  type PropRelationship,
  type SpatialCharacterPlacement,
  type SpatialMapDocument,
  type SpatialPropAttachmentFields,
  type SpatialPropPlacement,
} from "./types";

export type AssignedCharacterOption = {
  slot: AttachedCharacterSlot;
  id: string;
  name: string;
};

export type AssignedPropOption = {
  id: string;
  slotIndex: number;
  name: string;
  placementMode?: SpatialPropPlacement["placementMode"];
  visible?: boolean;
};

export type AttachedBadge =
  | { type: "single"; slotLabel: string }
  | { type: "count"; count: number };

export const INDEPENDENT_ATTACHMENT: SpatialPropAttachmentFields = {
  placementMode: "independent",
  attachedCharacterSlot: null,
  attachedCharacterId: null,
  relationship: null,
  attachmentPoint: null,
};

export const ATTACHMENT_POINTS_BY_RELATIONSHIP: Record<PropRelationship, readonly AttachmentPoint[]> = {
  held: ["left_hand", "right_hand", "both_hands"],
  carried: ["back", "shoulder", "both_hands", "left_hand", "right_hand", "unspecified"],
  worn: ["head", "upper_body", "lower_body", "waist", "wrist", "shoulder"],
  using: ["left_hand", "right_hand", "both_hands"],
  interacting: ["left_hand", "right_hand", "both_hands", "unspecified"],
  associated: ["unspecified"],
};

export function isAttachedProp(prop: { placementMode?: string | null } | null | undefined): boolean {
  return prop?.placementMode === "attached";
}

export function attachmentPointsFor(relationship: PropRelationship | null | undefined): readonly AttachmentPoint[] {
  if (!relationship) return ATTACHMENT_POINTS;
  return ATTACHMENT_POINTS_BY_RELATIONSHIP[relationship] || ATTACHMENT_POINTS;
}

export function formatRelationshipLabel(relationship: string | null | undefined): string {
  if (!relationship) return "";
  return relationship.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatAttachmentPointLabel(point: string | null | undefined): string {
  if (!point) return "";
  return point.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function propSlotLabel(slotIndex: number | null | undefined): string {
  if (slotIndex === 0 || slotIndex === 1 || slotIndex === 2 || slotIndex === 3) {
    return `P${slotIndex + 1}`;
  }
  return "P";
}

export function characterSlotTag(slot: AttachedCharacterSlot | number | null | undefined): string {
  if (slot === 1 || slot === 2 || slot === 3 || slot === 4) return `C${slot}`;
  return "";
}

export function assignedSpatialMapCharacters(
  characters: SpatialCharacterPlacement[] | null | undefined,
): AssignedCharacterOption[] {
  const out: AssignedCharacterOption[] = [];
  for (const slot of CHARACTER_SLOTS) {
    const found = (characters || []).find((c) => c.slotIndex === slot.index);
    if (!found) continue;
    const attachedSlot = attachedSlotFromSlotIndex(slot.index);
    if (!attachedSlot) continue;
    out.push({
      slot: attachedSlot,
      id: found.characterId,
      name: found.label || found.tag || `Character ${attachedSlot}`,
    });
  }
  return out;
}

export function matchesAttachedCharacter(
  prop: SpatialPropPlacement,
  character: SpatialCharacterPlacement,
): boolean {
  if (!isAttachedProp(prop)) return false;
  if (prop.attachedCharacterId && character.characterId && prop.attachedCharacterId === character.characterId) {
    return true;
  }
  const slot = attachedSlotFromSlotIndex(character.slotIndex);
  return slot != null && prop.attachedCharacterSlot === slot;
}

export function attachedPropsForCharacter(
  character: SpatialCharacterPlacement,
  props: SpatialPropPlacement[],
): SpatialPropPlacement[] {
  return props.filter((p) => matchesAttachedCharacter(p, character));
}

export function visibleAttachedPropsForCharacter(
  character: SpatialCharacterPlacement,
  props: SpatialPropPlacement[],
): SpatialPropPlacement[] {
  return attachedPropsForCharacter(character, props).filter((p) => p.visible !== false);
}

export function attachedBadgeFor(props: SpatialPropPlacement[]): AttachedBadge | null {
  const visible = props.filter((p) => p.visible !== false);
  if (visible.length === 0) return null;
  if (visible.length === 1) {
    return { type: "single", slotLabel: propSlotLabel(visible[0].slotIndex) };
  }
  return { type: "count", count: visible.length };
}

export function formatAttachedPropSummary(prop: SpatialPropPlacement): string {
  const name = prop.label || prop.tag || "Prop";
  const rel = formatRelationshipLabel(prop.relationship);
  const point = formatAttachmentPointLabel(prop.attachmentPoint);
  if (rel && point) return `${name} — ${rel} — ${point}`;
  if (rel) return `${name} — ${rel}`;
  return name;
}

export function formatCharacterAttachmentTooltip(
  character: SpatialCharacterPlacement,
  attached: SpatialPropPlacement[],
): string {
  const name = character.label || character.tag || "Character";
  const visible = attached.filter((p) => p.visible !== false);
  if (!visible.length) return name;
  return `${name} / Attached: ${visible.map(formatAttachedPropSummary).join("; ")}`;
}

export function independentAssignedProps(props: SpatialPropPlacement[]): AssignedPropOption[] {
  return props
    .filter((p) => !isAttachedProp(p))
    .map((p) => ({
      id: p.id,
      slotIndex: p.slotIndex,
      name: p.label || p.tag || "Prop",
      placementMode: p.placementMode,
      visible: p.visible,
    }));
}

export function normalizeMapDocumentProps(doc: SpatialMapDocument): SpatialMapDocument {
  return {
    ...doc,
    props: doc.props.map((p) => ({
      ...p,
      placementMode: p.placementMode === "attached" ? "attached" : "independent",
      attachedCharacterSlot: p.placementMode === "attached" ? p.attachedCharacterSlot ?? null : null,
      attachedCharacterId: p.placementMode === "attached" ? p.attachedCharacterId ?? null : null,
      relationship: p.placementMode === "attached" ? p.relationship ?? null : null,
      attachmentPoint: p.placementMode === "attached" ? p.attachmentPoint ?? null : null,
    })),
  };
}
