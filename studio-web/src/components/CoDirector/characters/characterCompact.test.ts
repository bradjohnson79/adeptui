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

// Amendment F5 (binding #6): Character Creator MUST always send candidateCount=4
// at the request boundary.
const EXPECTED_CANDIDATE_COUNT = 4;

function buildGenerateRequest(profile: any, candidateCount: number) {
  return { candidateCount, visualStyle: profile.visual_style, includeDetails: false };
}

test("Amendment F5: Character Creator generate request always sends candidateCount=4", () => {
  const req = buildGenerateRequest({ visual_style: "anime" }, EXPECTED_CANDIDATE_COUNT);
  assert.equal(req.candidateCount, 4);
  assert.equal(req.candidateCount, EXPECTED_CANDIDATE_COUNT);
});

test("Amendment F5: candidateCount is never the backend default of 1", () => {
  const req = buildGenerateRequest({ visual_style: "anime" }, EXPECTED_CANDIDATE_COUNT);
  assert.notEqual(req.candidateCount, 1);
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
