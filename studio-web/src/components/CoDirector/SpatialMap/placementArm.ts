/**
 * Entity enablement (persisted `visible`) and singular placement target.
 *
 * USER LAW: Enabled is many. Visible is many. Associated is many.
 * Selected may be one. Placement target may be one.
 * Never use the entity ON/OFF switch as a global radio.
 *
 * Switch ON/OFF writes that entity's persisted `visible` only.
 * Place / Move / card click / map-click set placementMode.
 * Changing the placement target must not flip other switches.
 */
export const ENTITY_ENABLED_SWITCH_LABEL = "Enabled";
/** Switch label. Enablement, not placement-arm. */
export const PLACEMENT_ACTIVE_SWITCH_LABEL = ENTITY_ENABLED_SWITCH_LABEL;
export const PLACEMENT_ACTIVE_BADGE = "PLACEMENT ACTIVE";

export type PlacementArmKind = "character" | "prop" | "camera";

export type PlacementArm = {
  action: "place" | "move";
  kind: PlacementArmKind;
  id: string;
  label: string;
} | null;

export function isEntityEnabled(visible: boolean | undefined): boolean {
  return visible !== false;
}

export function isPlacementArmed(
  arm: PlacementArm,
  kind: PlacementArmKind,
  id: string | null | undefined,
): boolean {
  return !!id && arm?.kind === kind && arm.id === id;
}

export function entitySwitchAriaLabel(
  slotLabel: string,
  enabled: boolean,
  opts: { assigned: boolean },
): string {
  if (!opts.assigned) return `${slotLabel} enablement unavailable`;
  return `${slotLabel} ${enabled ? "enabled" : "disabled"}`;
}

/** Aria is enablement, not placement-arm. `attached` does not disable the switch. */
export function placementSwitchAriaLabel(
  slotLabel: string,
  enabled: boolean,
  opts: { assigned: boolean; attached?: boolean },
): string {
  return entitySwitchAriaLabel(slotLabel, enabled, { assigned: opts.assigned });
}

export function slotPlacementBadge(isPlacementTarget: boolean): string | null {
  return isPlacementTarget ? PLACEMENT_ACTIVE_BADGE : null;
}

export type ToggleEntity = {
  id: string;
  kind: PlacementArmKind;
  visible: boolean;
  gridRow?: number;
  gridColumn?: number;
  normalizedX?: number | null;
  normalizedY?: number | null;
  placementMode?: "independent" | "attached";
  attachedCharacterId?: string | null;
  relationship?: string | null;
  attachmentPoint?: string | null;
  tag?: string;
  fovPreset?: string;
};

export type MultiToggleState = {
  entities: ToggleEntity[];
  placementTargetId: string | null;
};

/** Toggle only this entity's visible. Others, coords, FOV, associations, tags stay. */
export function toggleEntityEnabled(state: MultiToggleState, id: string): MultiToggleState {
  return {
    placementTargetId: state.placementTargetId,
    entities: state.entities.map((entity) =>
      entity.id === id ? { ...entity, visible: entity.visible === false } : entity,
    ),
  };
}

/** Set the singular placement target. Does not flip any switch / visible. */
export function setPlacementTarget(state: MultiToggleState, id: string | null): MultiToggleState {
  return {
    entities: state.entities.map((entity) => ({ ...entity })),
    placementTargetId: id,
  };
}

export function switchOnIds(state: MultiToggleState): string[] {
  return state.entities.filter((entity) => isEntityEnabled(entity.visible)).map((entity) => entity.id);
}

/**
 * Replace the in-memory placement arm. Returns the same entity records
 * so visible and attach fields are unchanged.
 */
export function replacePlacementArm<T>(
  entities: T[],
  next: NonNullable<PlacementArm>,
): { arm: NonNullable<PlacementArm>; entities: T[] } {
  return { arm: next, entities };
}

/** All placed cameras get an FOV layer. Selection is not a filter. */
export function fovLayersForCameras(
  cameras: Array<{
    id: string;
    visible?: boolean;
    gridRow: number;
    gridColumn: number;
    normalizedX?: number | null;
    normalizedY?: number | null;
  }>,
  _selectedCameraId?: string | null,
): Array<{ id: string; hidden: boolean }> {
  return cameras
    .filter(
      (camera) =>
        (typeof camera.normalizedX === "number" && typeof camera.normalizedY === "number") ||
        (camera.gridRow >= 0 && camera.gridColumn >= 0),
    )
    .map((camera) => ({ id: camera.id, hidden: camera.visible === false }));
}

/** Reload hydrates switch ON from persisted visible (default true). Coords stay. */
export function hydrateEnabledFromDocument(
  entities: Array<{ id: string; visible?: boolean; gridRow?: number; gridColumn?: number }>,
): Array<{ id: string; enabled: boolean; gridRow?: number; gridColumn?: number }> {
  return entities.map((entity) => ({
    id: entity.id,
    enabled: isEntityEnabled(entity.visible),
    gridRow: entity.gridRow,
    gridColumn: entity.gridColumn,
  }));
}
