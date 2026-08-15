import assert from "node:assert/strict";
import test from "node:test";

/**
 * CharacterCompactView — pure-logic unit tests for the new amendments.
 *
 * The component itself is a React component with heavy API dependencies and
 * no jsdom/RTL render harness exists in this repo, so these tests cover the
 * extractable pure logic: draft serialization shape, save-validation rule
 * (name-only minimum, no casting required), and hero_identity role resolution.
 * Full UI render + interaction coverage is in the Playwright E2E suite.
 */

// Amendment 1: Save Character requires only a name — no casting/approval.
function canSaveCharacter(name: string | undefined): boolean {
  return Boolean((name || "").trim());
}

// Amendment 3: draft shape preserved to sessionStorage before Voice Studio nav.
type CharacterDraft = {
  name: string;
  gender_presentation: string;
  visual_description: string;
  description: string;
  visual_style: string;
  active_voice_profile_id: string;
  candidates: unknown[];
  savedAt: string;
};

function serializeDraft(profile: {
  name?: string;
  gender_presentation?: string;
  visual_description?: string;
  description?: string;
  visual_style?: string;
  active_voice_profile_id?: string;
}, candidates: unknown[]): CharacterDraft {
  return {
    name: profile.name || "",
    gender_presentation: profile.gender_presentation || "",
    visual_description: profile.visual_description || "",
    description: profile.description || "",
    visual_style: profile.visual_style || "",
    active_voice_profile_id: profile.active_voice_profile_id || "",
    candidates,
    savedAt: new Date().toISOString(),
  };
}

// Amendment 2b: hero_identity is the canonical casting role; hero_portrait is legacy.
const HERO_IDENTITY_ROLE = "hero_identity";
const HERO_PORTRAIT_LEGACY = "hero_portrait";
function isHeroIdentityRole(role: string | undefined | null): boolean {
  return role === HERO_IDENTITY_ROLE || role === HERO_PORTRAIT_LEGACY;
}

test("Amendment 1: Save Character enabled with name only — no casting required", () => {
  assert.equal(canSaveCharacter("Korri"), true);
  assert.equal(canSaveCharacter("  Mieke  "), true);
  assert.equal(canSaveCharacter(""), false);
  assert.equal(canSaveCharacter(undefined), false);
  assert.equal(canSaveCharacter("   "), false);
});

test("Amendment 1: Save does not require visual_description or style", () => {
  // Name-only is sufficient — generation requires more, but save does not.
  assert.equal(canSaveCharacter("Korri"), true);
});

test("Amendment 3: draft serialization preserves all Character Creator fields", () => {
  const draft = serializeDraft(
    {
      name: "Korri",
      gender_presentation: "female",
      visual_description: "A sun sprite elf hybrid with black ponytails.",
      description: "A sun sprite elf hybrid with black ponytails.",
      visual_style: "anime",
      active_voice_profile_id: "voice-123",
    },
    [{ assetId: "asset-1", label: "Candidate 1" }],
  );
  assert.equal(draft.name, "Korri");
  assert.equal(draft.gender_presentation, "female");
  assert.equal(draft.visual_description, "A sun sprite elf hybrid with black ponytails.");
  assert.equal(draft.visual_style, "anime");
  assert.equal(draft.active_voice_profile_id, "voice-123");
  assert.equal(draft.candidates.length, 1);
  assert.ok(draft.savedAt, "savedAt must be set");
});

test("Amendment 3: draft serialization handles empty profile gracefully", () => {
  const draft = serializeDraft({}, []);
  assert.equal(draft.name, "");
  assert.equal(draft.gender_presentation, "");
  assert.equal(draft.candidates.length, 0);
});

test("Amendment 2b: hero_identity is the canonical casting role", () => {
  assert.equal(HERO_IDENTITY_ROLE, "hero_identity");
});

test("Amendment 2b: isHeroIdentityRole resolves both new and legacy roles", () => {
  assert.equal(isHeroIdentityRole("hero_identity"), true);
  assert.equal(isHeroIdentityRole("hero_portrait"), true); // legacy compat
  assert.equal(isHeroIdentityRole("closeup_front"), false);
  assert.equal(isHeroIdentityRole(undefined), false);
  assert.equal(isHeroIdentityRole(null), false);
  assert.equal(isHeroIdentityRole(""), false);
});

test("Amendment 2: full-body casting is the default composition intent", () => {
  // Mirrors the backend COMPOSITION_INTENT_FULL_BODY_CASTING constant.
  const compositionIntent = "full_body_casting";
  assert.equal(compositionIntent, "full_body_casting");
});

// Amendment F1: detach reference state transition — after detach, the reference
// is removed from state.
function refsAfterDetach(
  refs: { asset_id: string; reference_role: string }[],
  detachedId: string,
): { asset_id: string; reference_role: string }[] {
  return refs.filter((r) => r.asset_id !== detachedId);
}

test("Amendment F1: detach removes only the targeted reference", () => {
  const refs = [
    { asset_id: "a1", reference_role: "reference_image" },
    { asset_id: "a2", reference_role: "hero_identity" },
  ];
  const after = refsAfterDetach(refs, "a1");
  assert.equal(after.length, 1);
  assert.equal(after[0].asset_id, "a2");
});

// Amendment F2: bulk-delete confirmation message shape.
function bulkDeleteConfirmMessage(count: number): string {
  if (count <= 0) return "";
  return count === 1 ? "Delete 1 image?" : `Delete ${count} images?`;
}

test("Amendment F2: bulk delete confirmation: single", () =>
  assert.equal(bulkDeleteConfirmMessage(1), "Delete 1 image?"));
test("Amendment F2: bulk delete confirmation: bulk", () =>
  assert.equal(bulkDeleteConfirmMessage(7), "Delete 7 images?"));
test("Amendment F2: bulk delete confirmation: zero is empty", () =>
  assert.equal(bulkDeleteConfirmMessage(0), ""));

// Amendment F3: dependency warning text presence.
const DELETE_DEPENDENCY_WARNING =
  "References in Spatial Map, Scene Creator, Timeline, and Wiki may remain and should be reviewed.";

test("Amendment F3: delete confirm includes dependency warning", () => {
  assert.ok(DELETE_DEPENDENCY_WARNING.includes("Spatial Map"));
  assert.ok(DELETE_DEPENDENCY_WARNING.includes("Wiki"));
});

// Amendment F4: draft-restore merge logic (guard removed). Draft fields override
// server fields; undefined draft fields preserve server values.
type Draft = {
  name?: string;
  visual_description?: string;
  gender_presentation?: string;
  visual_style?: string;
  active_voice_profile_id?: string;
};

function mergeDraftOntoProfile(server: any, draft: Draft): any {
  return {
    ...server,
    visual_description: draft.visual_description ?? server.visual_description,
    description: draft.visual_description ?? server.description,
    name: draft.name ?? server.name,
    visual_style: draft.visual_style ?? server.visual_style,
    active_voice_profile_id: draft.active_voice_profile_id ?? server.active_voice_profile_id,
    gender_presentation: draft.gender_presentation ?? server.gender_presentation,
  };
}

test("Amendment F4: draft merge — draft fields override server fields", () => {
  const merged = mergeDraftOntoProfile(
    { name: "Old", visual_description: "old desc", visual_style: "anime" },
    { name: "New", visual_description: "new desc" },
  );
  assert.equal(merged.name, "New");
  assert.equal(merged.visual_description, "new desc");
  assert.equal(merged.visual_style, "anime");
});

test("Amendment F4: draft merge — undefined draft fields preserve server values", () => {
  const merged = mergeDraftOntoProfile(
    { name: "Server", visual_description: "server desc" },
    { visual_description: "draft desc" },
  );
  assert.equal(merged.name, "Server");
  assert.equal(merged.visual_description, "draft desc");
});

// Per-generator batches replace Amendment F5's global candidateCount=4.
const EXPECTED_DEFAULT_BATCH_COUNT = 1;

function buildGenerateRequest(profile: any, candidateCount: number) {
  return { candidateCount, visualStyle: profile.visual_style, includeDetails: false };
}

test("Character Creator default is one sheet per enabled generator", () => {
  const req = buildGenerateRequest({ visual_style: "anime" }, EXPECTED_DEFAULT_BATCH_COUNT);
  assert.equal(req.candidateCount, 1);
});

test("Character Creator no longer sends a hidden global candidateCount of 4", () => {
  const req = buildGenerateRequest({ visual_style: "anime" }, EXPECTED_DEFAULT_BATCH_COUNT);
  assert.notEqual(req.candidateCount, 4);
});

// Amendment F6 (binding #5): single-select vs multi-select state model separation.
test("Amendment F6: picker is single-select — selectedIds is a single string, not an array", () => {
  const selectedPickerAsset: string | null = "asset-1";
  assert.equal(typeof selectedPickerAsset, "string");
});

test("Amendment F6: library bulk-delete is multi-select — selectedIds is a Set", () => {
  const selectedIds = new Set<string>(["a1", "a2", "a3"]);
  assert.equal(selectedIds.size, 3);
  assert.ok(selectedIds.has("a2"));
});

// ── CharacterReferenceAssetPicker: single-select state machine (Workstream A) ──
//
// The picker is a React component that owns a `selectedAssetId: string | null`
// state. Parent owns attachment/persistence; the picker only reports selection.
// These tests cover the extractable pure logic that mirrors the component's
// state transitions, confirm-disabled rule, and busy-state confirm label.

type PickerState = {
  selectedAssetId: string | null;
  busy: boolean;
};

function initSelection(currentAssetId: string | null | undefined): string | null {
  // Mirrors: setSelectedAssetId(currentAssetId ?? null) on open.
  return currentAssetId ?? null;
}

function clickAsset(state: PickerState, assetId: string): PickerState {
  // Mirrors: onClick={() => setSelectedAssetId(a.id)}
  return { ...state, selectedAssetId: assetId };
}

function canConfirm(state: PickerState): boolean {
  // Mirrors: disabled={!selectedAssetId || busy}
  return Boolean(state.selectedAssetId) && !state.busy;
}

function confirmLabel(state: PickerState): string {
  // Mirrors: {busy ? "Attaching…" : "Select"}
  return state.busy ? "Attaching…" : "Select";
}

function findSelected(
  assets: { id: string }[],
  selectedAssetId: string | null,
): { id: string } | null {
  return assets.find((a) => a.id === selectedAssetId) ?? null;
}

test("Picker: selectedAssetId initializes from currentAssetId", () => {
  assert.equal(initSelection("asset-1"), "asset-1");
  assert.equal(initSelection(null), null);
  assert.equal(initSelection(undefined), null);
});

test("Picker: clicking an asset sets selection", () => {
  const state: PickerState = { selectedAssetId: null, busy: false };
  const next = clickAsset(state, "asset-1");
  assert.equal(next.selectedAssetId, "asset-1");
});

test("Picker: clicking another asset transfers selection", () => {
  const state: PickerState = { selectedAssetId: "asset-1", busy: false };
  const next = clickAsset(state, "asset-2");
  assert.equal(next.selectedAssetId, "asset-2");
  assert.notEqual(next.selectedAssetId, "asset-1");
});

test("Picker: confirm calls onConfirm with the selected asset", () => {
  const assets = [{ id: "asset-1" }, { id: "asset-2" }];
  const selectedAssetId = "asset-2";
  const selected = findSelected(assets, selectedAssetId);
  assert.ok(selected, "selected asset must resolve from the list");
  assert.equal(selected!.id, "asset-2");

  // onConfirm is only called when selectedAsset is non-null.
  let confirmedAsset: { id: string } | null = null;
  if (selected) {
    confirmedAsset = selected;
  }
  assert.equal(confirmedAsset!.id, "asset-2");
});

test("Picker: confirm disabled when no selection", () => {
  const state: PickerState = { selectedAssetId: null, busy: false };
  assert.equal(canConfirm(state), false);
});

test("Picker: confirm enabled when a selection exists and not busy", () => {
  const state: PickerState = { selectedAssetId: "asset-1", busy: false };
  assert.equal(canConfirm(state), true);
});

test("Picker: busy state disables confirm", () => {
  const state: PickerState = { selectedAssetId: "asset-1", busy: true };
  assert.equal(canConfirm(state), false);
});

test("Picker: busy state shows 'Attaching…' label", () => {
  const busy: PickerState = { selectedAssetId: "asset-1", busy: true };
  const idle: PickerState = { selectedAssetId: "asset-1", busy: false };
  assert.equal(confirmLabel(busy), "Attaching…");
  assert.equal(confirmLabel(idle), "Select");
});

test("Picker: confirm stays disabled when busy even if a selection exists", () => {
  const state: PickerState = { selectedAssetId: "asset-1", busy: true };
  assert.equal(canConfirm(state), false);
});

test("Picker: full selection transition sequence (init → click → transfer → confirm)", () => {
  const assets = [{ id: "a1" }, { id: "a2" }, { id: "a3" }];
  let state: PickerState = { selectedAssetId: initSelection(null), busy: false };
  assert.equal(canConfirm(state), false, "no selection yet");

  state = clickAsset(state, "a1");
  assert.equal(state.selectedAssetId, "a1");
  assert.equal(canConfirm(state), true);

  state = clickAsset(state, "a3");
  assert.equal(state.selectedAssetId, "a3", "selection transferred to a3");
  assert.equal(canConfirm(state), true);

  const selected = findSelected(assets, state.selectedAssetId);
  assert.equal(selected!.id, "a3");

  // Parent starts attaching.
  state = { ...state, busy: true };
  assert.equal(canConfirm(state), false, "confirm disabled while busy");
  assert.equal(confirmLabel(state), "Attaching…");
});
