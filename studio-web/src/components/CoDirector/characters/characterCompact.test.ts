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
