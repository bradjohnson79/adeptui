import { describe, expect, it } from "vitest";
import { isAttachedProp } from "./attachmentUi";
import {
  ENTITY_ENABLED_SWITCH_LABEL,
  PLACEMENT_ACTIVE_BADGE,
  PLACEMENT_ACTIVE_SWITCH_LABEL,
  fovLayersForCameras,
  hydrateEnabledFromDocument,
  isEntityEnabled,
  isPlacementArmed,
  placementSwitchAriaLabel,
  replacePlacementArm,
  setPlacementTarget,
  slotPlacementBadge,
  switchOnIds,
  toggleEntityEnabled,
  type MultiToggleState,
  type PlacementArm,
  type ToggleEntity,
} from "./placementArm";

const korri: ToggleEntity = {
  id: "char-korri",
  kind: "character",
  visible: true,
  gridRow: 8,
  gridColumn: 9,
  normalizedX: 0.1,
  normalizedY: 0.2,
  tag: "",
};

const cup: ToggleEntity = {
  id: "prop-cup",
  kind: "prop",
  visible: true,
  gridRow: -1,
  gridColumn: -1,
  normalizedX: null,
  normalizedY: null,
  placementMode: "attached",
  attachedCharacterId: "c49371ed",
  relationship: "held",
  attachmentPoint: "right_hand",
  tag: "#coffeecup",
};

const c1: ToggleEntity = {
  id: "cam-1",
  kind: "camera",
  visible: true,
  gridRow: 2,
  gridColumn: 2,
  fovPreset: "medium",
};

const c2: ToggleEntity = {
  id: "cam-2",
  kind: "camera",
  visible: true,
  gridRow: 6,
  gridColumn: 6,
  fovPreset: "wide",
};

const char2: ToggleEntity = {
  id: "char-two",
  kind: "character",
  visible: true,
  gridRow: 3,
  gridColumn: 4,
};

function scene(entities: ToggleEntity[], placementTargetId: string | null = null): MultiToggleState {
  return {
    entities: entities.map((entity) => ({ ...entity })),
    placementTargetId,
  };
}

describe("switch is enablement, not placement-arm", () => {
  it("labels the switch Enabled and badges only the placement target", () => {
    expect(ENTITY_ENABLED_SWITCH_LABEL).toBe("Enabled");
    expect(PLACEMENT_ACTIVE_SWITCH_LABEL).toBe("Enabled");
    expect(slotPlacementBadge(true)).toBe(PLACEMENT_ACTIVE_BADGE);
    expect(slotPlacementBadge(false)).toBeNull();
    expect(placementSwitchAriaLabel("Character 1 (Red)", true, { assigned: true })).toBe(
      "Character 1 (Red) enabled",
    );
    expect(placementSwitchAriaLabel("Prop 1 (Purple)", false, { assigned: true })).toBe(
      "Prop 1 (Purple) disabled",
    );
    expect(placementSwitchAriaLabel("Prop 1 (Purple)", true, { assigned: true, attached: true })).toBe(
      "Prop 1 (Purple) enabled",
    );
    expect(placementSwitchAriaLabel("Camera 1", false, { assigned: false })).toBe(
      "Camera 1 enablement unavailable",
    );
  });
});

describe("A multi character — turning C2 ON does not turn C1 off", () => {
  it("keeps Character 1 enabled when Character 2 is turned on", () => {
    const start = scene(
      [
        { ...korri, visible: true },
        { ...char2, visible: false },
      ],
      korri.id,
    );
    const after = toggleEntityEnabled(start, char2.id);
    expect(switchOnIds(after).sort()).toEqual([char2.id, korri.id].sort());
    expect(after.entities.find((e) => e.id === korri.id)?.visible).toBe(true);
    expect(after.entities.find((e) => e.id === char2.id)?.visible).toBe(true);
    expect(after.placementTargetId).toBe(korri.id);
  });
});

describe("B multi prop — turning Prop 1 ON does not set Character 1 switch off", () => {
  it("keeps Korri enabled when Coffee Cup is turned on", () => {
    const start = scene(
      [
        { ...korri, visible: true },
        { ...cup, visible: false },
      ],
      korri.id,
    );
    const after = toggleEntityEnabled(start, cup.id);
    expect(after.entities.find((e) => e.id === korri.id)?.visible).toBe(true);
    expect(after.entities.find((e) => e.id === cup.id)?.visible).toBe(true);
    expect(isEntityEnabled(after.entities.find((e) => e.id === korri.id)?.visible)).toBe(true);
  });
});

describe("C multi camera — several visible cameras keep several FOVs", () => {
  it("turning C2 ON does not turn C1 off and both FOV layers stay visible", () => {
    const start = scene(
      [
        { ...c1, visible: true },
        { ...c2, visible: false },
      ],
      c1.id,
    );
    const after = toggleEntityEnabled(start, c2.id);
    expect(after.entities.find((e) => e.id === c1.id)?.visible).toBe(true);
    expect(after.entities.find((e) => e.id === c2.id)?.visible).toBe(true);
    const layers = fovLayersForCameras(after.entities, c2.id);
    expect(layers).toEqual([
      { id: c1.id, hidden: false },
      { id: c2.id, hidden: false },
    ]);
  });
});

describe("D mixed — select cup for place does not hide Korri or break Held By", () => {
  it("keeps both switches ON and association intact when placement target moves to the cup", () => {
    const start = scene([korri, cup], korri.id);
    const after = setPlacementTarget(start, cup.id);
    expect(switchOnIds(after).sort()).toEqual([cup.id, korri.id].sort());
    expect(after.placementTargetId).toBe(cup.id);
    expect(slotPlacementBadge(after.placementTargetId === cup.id)).toBe(PLACEMENT_ACTIVE_BADGE);
    expect(slotPlacementBadge(after.placementTargetId === korri.id)).toBeNull();
    const afterCup = after.entities.find((e) => e.id === cup.id);
    expect(afterCup).toMatchObject({
      visible: true,
      placementMode: "attached",
      attachedCharacterId: "c49371ed",
      relationship: "held",
      attachmentPoint: "right_hand",
      tag: "#coffeecup",
    });
    expect(isAttachedProp(afterCup)).toBe(true);
    expect(after.entities.find((e) => e.id === korri.id)?.visible).toBe(true);
  });
});

describe("E individual off — only that entity hides; coords, FOV, assoc, tags stay", () => {
  it("turning Korri OFF leaves the cup ON and keeps Korri coordinates and the Held By record", () => {
    const start = scene([korri, cup, c1], korri.id);
    const after = toggleEntityEnabled(start, korri.id);
    const afterKorri = after.entities.find((e) => e.id === korri.id);
    const afterCup = after.entities.find((e) => e.id === cup.id);
    expect(afterKorri?.visible).toBe(false);
    expect(afterCup?.visible).toBe(true);
    expect(afterKorri).toMatchObject({
      gridRow: 8,
      gridColumn: 9,
      normalizedX: 0.1,
      normalizedY: 0.2,
      tag: "",
    });
    expect(afterCup).toMatchObject({
      placementMode: "attached",
      attachedCharacterId: "c49371ed",
      relationship: "held",
      attachmentPoint: "right_hand",
      tag: "#coffeecup",
    });
    expect(after.entities.find((e) => e.id === c1.id)?.visible).toBe(true);
    expect(after.entities.find((e) => e.id === c1.id)?.fovPreset).toBe("medium");
  });
});

describe("F selection independence — Place/Move/select does not flip switches", () => {
  it("changing placement target from Korri to C2 does not flip any switch", () => {
    const start = scene([korri, cup, c1, c2], korri.id);
    const after = setPlacementTarget(start, c2.id);
    expect(switchOnIds(after).sort()).toEqual([c1.id, c2.id, cup.id, korri.id].sort());
    expect(after.placementTargetId).toBe(c2.id);
    expect(after.entities.every((e) => e.visible === start.entities.find((s) => s.id === e.id)?.visible)).toBe(
      true,
    );
  });
});

describe("placement arm replace still does not write visible or attach", () => {
  it("replacePlacementArm keeps Korri visible and cup Held By", () => {
    const armedKorri: PlacementArm = {
      action: "move",
      kind: "character",
      id: korri.id,
      label: "Korri",
    };
    expect(isPlacementArmed(armedKorri, "character", korri.id)).toBe(true);
    const next = replacePlacementArm([korri, cup], {
      action: "move",
      kind: "prop",
      id: cup.id,
      label: "Coffee Cup",
    });
    expect(isPlacementArmed(next.arm, "prop", cup.id)).toBe(true);
    expect(isPlacementArmed(next.arm, "character", korri.id)).toBe(false);
    expect(next.entities.find((e) => e.id === korri.id)?.visible).toBe(true);
    expect(next.entities.find((e) => e.id === cup.id)).toMatchObject({
      placementMode: "attached",
      relationship: "held",
      attachmentPoint: "right_hand",
    });
  });
});

describe("legacy hydrate — one placement-active entity still loads; coords stay", () => {
  it("defaults missing visible to enabled and does not clear coordinates", () => {
    const hydrated = hydrateEnabledFromDocument([
      { id: korri.id, gridRow: 8, gridColumn: 9 },
      { id: cup.id, visible: true, gridRow: -1, gridColumn: -1 },
    ]);
    expect(hydrated).toEqual([
      { id: korri.id, enabled: true, gridRow: 8, gridColumn: 9 },
      { id: cup.id, enabled: true, gridRow: -1, gridColumn: -1 },
    ]);
  });
});
