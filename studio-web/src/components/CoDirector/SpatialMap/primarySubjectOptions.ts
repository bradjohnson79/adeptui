/**
 * Primary Subject dropdown options for Spatial Map cameras.
 * Same source as the Characters panel: assigned placements that are Enabled.
 * Values are entity characterIds (internal). Never hard-code character names.
 */
import { isEntityEnabled } from "./placementArm";
import type { SpatialCharacterPlacement } from "./types";

export type PrimarySubjectOption = {
  value: string;
  label: string;
};

const BASE_OPTIONS: PrimarySubjectOption[] = [
  { value: "auto", label: "Auto" },
  { value: "environment", label: "Environment" },
];

export function enabledCharacterSubjectOptions(
  characters: SpatialCharacterPlacement[] | null | undefined,
): PrimarySubjectOption[] {
  const seen = new Set<string>();
  const rows: PrimarySubjectOption[] = [];
  for (const c of characters || []) {
    if (!isEntityEnabled(c.visible)) continue;
    const value = String(c.characterId || "").trim();
    if (!value || seen.has(value)) continue;
    seen.add(value);
    const label = String(c.label || c.tag || value).trim() || value;
    rows.push({ value, label });
  }
  return rows;
}

export function primarySubjectOptions(
  characters: SpatialCharacterPlacement[] | null | undefined,
): PrimarySubjectOption[] {
  return [...BASE_OPTIONS, ...enabledCharacterSubjectOptions(characters)];
}

/** Resolve a stored primarySubject to a valid dropdown value (fallback Auto). */
export function resolvePrimarySubjectValue(
  primarySubject: string | null | undefined,
  characters: SpatialCharacterPlacement[] | null | undefined,
): string {
  const raw = String(primarySubject || "auto").trim() || "auto";
  if (raw === "auto" || raw === "environment") return raw;
  const enabled = new Set(enabledCharacterSubjectOptions(characters).map((o) => o.value));
  return enabled.has(raw) ? raw : "auto";
}

/** Cameras whose primarySubject points at this character entity should fall back to Auto. */
export function camerasNeedingSubjectFallback(
  cameras: { id: string; primarySubject?: string | null }[] | null | undefined,
  characterEntityId: string,
): string[] {
  const entity = String(characterEntityId || "").trim();
  if (!entity) return [];
  return (cameras || [])
    .filter((cam) => String(cam.primarySubject || "").trim() === entity)
    .map((cam) => cam.id);
}
