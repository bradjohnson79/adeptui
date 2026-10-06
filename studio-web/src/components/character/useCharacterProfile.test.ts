/**
 * Phase 4 — Character approval truth (CDX-004) frontend units.
 * getHeroIdentity must return no hero for draft-only rows, and the candidate
 * grid label must not show "Selected" before canonical+approved.
 *
 * Instant saved-character dropdown refresh: upsertCharacterSummary is the
 * shared in-place upsert both dropdowns (Express + Standard) apply when the
 * adept:character-profile-saved event fires; source assertions pin the
 * dispatch + listener wiring (no DOM render harness in this repo).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { candidateSelectionLabel } from "./types";
import type { CharacterProfile, CharacterReference } from "./types";
import {
  CHARACTER_PROFILE_SAVED_EVENT,
  DRAFT_CHARACTER_ID,
  applyLoadedCharacterState,
  characterLoadIsStale,
  characterProfileFingerprint,
  characterSaveIntent,
  getHeroIdentity,
  getPendingHeroIdentity,
  notifyCharacterProfileSaved,
  pendingPatchForCurrentCharacter,
  profileAfterServerLoad,
  replaceCharacterProfile,
  serverCharacterId,
  upsertCharacterSummary,
} from "./useCharacterProfile";

function ref(over: Partial<CharacterReference>): CharacterReference {
  return {
    id: "r1",
    asset_id: "asset-1",
    reference_role: "hero_identity",
    approval_status: "draft",
    canonical: false,
    ...over,
  };
}

describe("getHeroIdentity (CDX-004)", () => {
  it("returns undefined when only a draft hero_identity exists", () => {
    const refs: CharacterReference[] = [
      ref({ id: "draft", asset_id: "draft-asset", canonical: false, approval_status: "draft" }),
    ];
    expect(getHeroIdentity(refs)).toBeUndefined();
  });

  it("returns undefined for canonical-but-unapproved rows", () => {
    const refs: CharacterReference[] = [
      ref({ id: "canon-draft", asset_id: "canon-draft-asset", canonical: true, approval_status: "draft" }),
    ];
    expect(getHeroIdentity(refs)).toBeUndefined();
  });

  it("returns the canonical + approved hero_identity when present", () => {
    const good = ref({ id: "good", asset_id: "approved-asset", canonical: true, approval_status: "approved" });
    const refs: CharacterReference[] = [
      ref({ id: "draft", asset_id: "draft-asset", canonical: false, approval_status: "draft" }),
      good,
    ];
    expect(getHeroIdentity(refs)?.asset_id).toBe("approved-asset");
  });

  it("accepts a canonical+approved legacy hero_portrait row (role alias)", () => {
    const refs: CharacterReference[] = [
      ref({ id: "portrait", asset_id: "portrait-asset", reference_role: "hero_portrait", canonical: true, approval_status: "approved" }),
    ];
    expect(getHeroIdentity(refs)?.asset_id).toBe("portrait-asset");
  });

  it("ignores non-hero roles entirely", () => {
    const refs: CharacterReference[] = [
      ref({ id: "front", asset_id: "front-asset", reference_role: "full_body_front", canonical: true, approval_status: "approved" }),
    ];
    expect(getHeroIdentity(refs)).toBeUndefined();
  });
});

describe("getPendingHeroIdentity (CDX-004)", () => {
  it("returns the draft hero when nothing is canonical+approved", () => {
    const draft = ref({ id: "draft", asset_id: "draft-asset", canonical: false, approval_status: "draft" });
    expect(getPendingHeroIdentity([draft])?.asset_id).toBe("draft-asset");
  });

  it("returns undefined once a canonical+approved hero exists", () => {
    const good = ref({ id: "good", asset_id: "approved-asset", canonical: true, approval_status: "approved" });
    expect(getPendingHeroIdentity([good])).toBeUndefined();
  });
});

describe("candidateSelectionLabel (CDX-004 grid)", () => {
  it('labels the canonical+approved asset "Selected"', () => {
    expect(candidateSelectionLabel({ isSelected: true, isPendingReview: false })).toBe("Selected");
  });

  it('labels the draft (pending review) asset "Pending review" — never "Selected"', () => {
    expect(candidateSelectionLabel({ isSelected: false, isPendingReview: true })).toBe("Pending review");
  });

  it('labels unattached ready candidates "Use This Look"', () => {
    expect(candidateSelectionLabel({ isSelected: false, isPendingReview: false })).toBe("Use This Look");
  });

  it("Selected wins over Pending review", () => {
    expect(candidateSelectionLabel({ isSelected: true, isPendingReview: true })).toBe("Selected");
  });
});

describe("Load Character atomic replace", () => {
  const korri: CharacterProfile = {
    id: "char-a",
    name: "Korri",
    gender_presentation: "female",
    visual_style: "anime",
    description: "A grounded heroine.",
  };
  const korriRefs: CharacterReference[] = [
    ref({
      id: "ref-a",
      asset_id: "korri-ref",
      reference_role: "reference_image",
      canonical: false,
      approval_status: "draft",
    }),
  ];

  it("A → B replaces name, gender, style, description, and references", () => {
    const loadedA = applyLoadedCharacterState({
      requestedCharacterId: "char-a",
      currentCharacterId: "char-a",
      profile: korri,
      references: korriRefs,
    });
    expect(loadedA).not.toBe("stale");
    if (loadedA === "stale") return;
    expect(loadedA.profile?.name).toBe("Korri");
    expect(loadedA.references[0]?.asset_id).toBe("korri-ref");

    const loadedB = applyLoadedCharacterState({
      requestedCharacterId: "char-b",
      currentCharacterId: "char-b",
      profile: {
        id: "char-b",
        name: "Anadriya",
        gender_presentation: "nonbinary",
        visual_style: "cinematic",
        description: "An elven scout.",
      },
      references: [],
    });
    expect(loadedB).not.toBe("stale");
    if (loadedB === "stale") return;
    expect(loadedB.profile).toEqual(
      expect.objectContaining({
        name: "Anadriya",
        gender_presentation: "nonbinary",
        visual_style: "cinematic",
        description: "An elven scout.",
      }),
    );
    expect(loadedB.references).toEqual([]);
  });

  it("does not keep the previous gender when B omits gender", () => {
    const replaced = replaceCharacterProfile({
      id: "char-b",
      name: "Anadriya",
      gender_presentation: undefined,
      visual_style: "cinematic",
      description: "An elven scout.",
    });
    expect(replaced?.gender_presentation).toBe("");
    expect(replaced?.gender_presentation).not.toBe("female");
  });

  it("does not flush a pending patch from A against B", () => {
    const pendingA = { characterId: "char-a", fields: { name: "Korri", gender_presentation: "female" } };
    expect(pendingPatchForCurrentCharacter(pendingA, "char-b")).toBeNull();
    expect(pendingPatchForCurrentCharacter(pendingA, "char-a")).toEqual(pendingA.fields);
  });

  it("treats a profile load that started before Save as stale", () => {
    expect(characterLoadIsStale(1, 2)).toBe(true);
    expect(characterLoadIsStale(2, 2)).toBe(false);
  });

  it("ignores a stale in-flight load after the selected id changes", () => {
    expect(
      applyLoadedCharacterState({
        requestedCharacterId: "char-a",
        currentCharacterId: "char-b",
        profile: korri,
        references: korriRefs,
      }),
    ).toBe("stale");
  });

  it("clears a previous reference preview when the next character has none", () => {
    const withImage = applyLoadedCharacterState({
      requestedCharacterId: "char-a",
      currentCharacterId: "char-a",
      profile: korri,
      references: korriRefs,
    });
    expect(withImage).not.toBe("stale");
    if (withImage === "stale") return;
    expect(withImage.references.some((r) => r.asset_id === "korri-ref")).toBe(true);

    const empty = applyLoadedCharacterState({
      requestedCharacterId: "char-b",
      currentCharacterId: "char-b",
      profile: { id: "char-b", name: "Anadriya" },
      references: [],
    });
    expect(empty).not.toBe("stale");
    if (empty === "stale") return;
    expect(empty.references).toEqual([]);
  });
});

describe("characterSaveIntent", () => {
  it("does not silently no-op when the character has no id and no name", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: "",
      fields: { description: "orphan draft" },
    });
    expect(intent).toEqual({
      ok: false,
      error: "Give the character a name, then Save Character.",
    });
  });

  it("creates from name-only when there is no character id", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: null,
      fields: { name: "Anadriya" },
    });
    expect(intent).toEqual({
      ok: true,
      method: "POST",
      name: "Anadriya",
      extra: {},
    });
  });

  it("does not fake-succeed when there is nothing to write", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: "char-1",
      fields: {},
      pending: null,
      profile: null,
    });
    expect(intent.ok).toBe(false);
    if (intent.ok) return;
    expect(intent.error).toMatch(/nothing to save/i);
  });

  it("patches an existing character instead of returning a silent success", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: "char-1",
      fields: { name: "Anadriya", description: "Updated profile" },
    });
    expect(intent).toEqual({
      ok: true,
      method: "PATCH",
      characterId: "char-1",
      fields: { name: "Anadriya", description: "Updated profile" },
    });
  });

  it("first save of a populated new character posts the entered fields, not New Character", () => {
    const description = "Renkoka keeps the ridge watch. She is not replaced by a placeholder.";
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: DRAFT_CHARACTER_ID,
      fields: {
        name: "Renkoka",
        gender_presentation: "female",
        visual_style: "live_action",
        description,
        is_global: false,
        isGlobal: false,
      },
      profile: {
        id: "",
        name: "New Character",
        gender_presentation: "",
        visual_style: "",
        description: "",
      },
    });
    expect(intent.ok).toBe(true);
    if (!intent.ok) return;
    expect(intent.method).toBe("POST");
    if (intent.method !== "POST") return;
    expect(intent.name).toBe("Renkoka");
    expect(intent.name).not.toBe("New Character");
    expect(intent.extra).toEqual({
      gender_presentation: "female",
      visual_style: "live_action",
      description,
      is_global: false,
      isGlobal: false,
    });
    expect(intent.extra.description).toBe(description);
  });

  it("does not let a stored placeholder name replace the name in the form", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: "char-1",
      fields: {
        name: "Renkoka",
        gender_presentation: "female",
        visual_style: "cinematic",
        description: "The first save keeps this profile.",
      },
      profile: { id: "char-1", name: "New Character", project_id: "proj-1", description: "" },
    });
    expect(intent).toEqual({
      ok: true,
      method: "PATCH",
      characterId: "char-1",
      fields: {
        name: "Renkoka",
        gender_presentation: "female",
        visual_style: "cinematic",
        description: "The first save keeps this profile.",
      },
    });
  });

  it("does not serialize New Character onto an existing named profile", () => {
    const intent = characterSaveIntent({
      projectId: "proj-1",
      characterId: "char-korri",
      fields: { name: "New Character", is_global: true, isGlobal: true },
      profile: { id: "char-korri", name: "Korri", slug: "korri", project_id: "proj-1" },
    });
    expect(intent).toEqual({
      ok: true,
      method: "PATCH",
      characterId: "char-korri",
      fields: { name: "Korri", is_global: true, isGlobal: true },
    });
  });

  it("refuses to PATCH a foreign Global character from another project", () => {
    const intent = characterSaveIntent({
      projectId: "cade-scenes",
      characterId: "foreign-global",
      fields: { name: "Cade O'Connor" },
      profile: { id: "foreign-global", name: "TestGlobal", project_id: "other-project", is_global: true },
    });
    expect(intent.ok).toBe(false);
    if (intent.ok) return;
    expect(intent.error).toMatch(/project that created them/i);
  });
});

describe("profileAfterServerLoad (reference reload must not restore the placeholder)", () => {
  const entered = {
    id: "char-1",
    name: "Renkoka",
    gender_presentation: "female",
    visual_style: "live_action",
    description: "Renkoka keeps the ridge watch. The second sentence is still here.",
  };
  const placeholder = {
    id: "char-1",
    name: "New Character",
    gender_presentation: "",
    visual_style: "",
    description: "",
  };

  it("keeps the unsaved form when a reference reload returns New Character", () => {
    const loaded = profileAfterServerLoad({
      local: entered,
      loaded: placeholder,
      committedFingerprint: characterProfileFingerprint(placeholder),
      force: false,
    });
    expect(loaded?.name).toBe("Renkoka");
    expect(loaded?.name).not.toBe("New Character");
    expect(loaded?.gender_presentation).toBe("female");
    expect(loaded?.visual_style).toBe("live_action");
    expect(loaded?.description).toBe(entered.description);
  });

  it("accepts the server row after the form has been saved", () => {
    const loaded = profileAfterServerLoad({
      local: entered,
      loaded: entered,
      committedFingerprint: characterProfileFingerprint(entered),
      force: false,
    });
    expect(loaded?.name).toBe("Renkoka");
    expect(loaded?.description).toBe(entered.description);
  });

  it("reset still replaces the form with the server row", () => {
    const loaded = profileAfterServerLoad({
      local: entered,
      loaded: placeholder,
      committedFingerprint: characterProfileFingerprint(placeholder),
      force: true,
    });
    expect(loaded?.name).toBe("New Character");
  });

  it("treats the draft selection as unsaved so the first save is a create", () => {
    expect(serverCharacterId(DRAFT_CHARACTER_ID)).toBeNull();
    expect(serverCharacterId("")).toBeNull();
    expect(serverCharacterId("char-1")).toBe("char-1");
  });
});

describe("upsertCharacterSummary (instant saved-character dropdown)", () => {
  const list = [
    { id: "char-a", name: "Korri" },
    { id: "char-b", name: "New Character" },
    { id: "char-c", name: "Mieke" },
  ];

  it("rename updates the label in place and preserves position", () => {
    const next = upsertCharacterSummary(list, { id: "char-b", name: "Anadriya" });
    expect(next.map((c) => c.id)).toEqual(["char-a", "char-b", "char-c"]);
    expect(next[1].name).toBe("Anadriya");
    expect(next).not.toBe(list);
  });

  it("a brand-new saved profile is appended, never duplicated", () => {
    const next = upsertCharacterSummary(list, { id: "char-d", name: "Vex" });
    expect(next.map((c) => c.id)).toEqual(["char-a", "char-b", "char-c", "char-d"]);
    const again = upsertCharacterSummary(next, { id: "char-d", name: "Vex" });
    expect(again.filter((c) => c.id === "char-d")).toHaveLength(1);
  });

  it("merge keeps existing row fields while applying saved ones", () => {
    const withStatus: Array<{ id: string; name: string; status?: string }> = [
      { id: "char-a", name: "Korri", status: "approved" },
    ];
    const next = upsertCharacterSummary(withStatus, { id: "char-a", name: "Korri V2" });
    expect(next[0]).toEqual({ id: "char-a", name: "Korri V2", status: "approved" });
  });

  it("empty list becomes a one-row list (first save in a project)", () => {
    const next = upsertCharacterSummary([], { id: "char-a", name: "Korri" });
    expect(next).toEqual([{ id: "char-a", name: "Korri" }]);
  });
});

describe("notifyCharacterProfileSaved", () => {
  it("dispatches the window event with projectId + canonical profile", () => {
    const seen: Array<{ type: string; detail: unknown }> = [];
    vi.stubGlobal("window", { dispatchEvent: (ev: { type: string; detail: unknown }) => seen.push(ev) });
    try {
      notifyCharacterProfileSaved("proj-1", { id: "char-1", name: "Korri" } as CharacterProfile);
    } finally {
      vi.unstubAllGlobals();
    }
    expect(seen).toHaveLength(1);
    expect(seen[0].type).toBe(CHARACTER_PROFILE_SAVED_EVENT);
    const detail = seen[0].detail as { projectId: string; profile: CharacterProfile };
    expect(detail.projectId).toBe("proj-1");
    expect(detail.profile).toEqual({ id: "char-1", name: "Korri" });
  });

  it("never throws outside a DOM environment", () => {
    vi.stubGlobal("window", undefined);
    try {
      expect(() =>
        notifyCharacterProfileSaved("proj-1", { id: "char-1", name: "Korri" } as CharacterProfile),
      ).not.toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("instant dropdown refresh wiring (source assertions)", () => {
  const hookSrc = readFileSync(resolve(__dirname, "useCharacterProfile.ts"), "utf8");
  const coreSrc = readFileSync(resolve(__dirname, "CharacterCore.tsx"), "utf8");
  const standardSrc = readFileSync(resolve(__dirname, "../CharacterProfileWorkspace.tsx"), "utf8");
  const expressSrc = readFileSync(resolve(__dirname, "../CoDirector/characters/CharacterCompactView.tsx"), "utf8");

  it("save() returns the saved profile (not a bare boolean)", () => {
    expect(hookSrc).toMatch(/save: \(fields\?: Record<string, unknown>\) => Promise<CharacterProfile \| null>/);
  });

  it("both POST (create) and PATCH (rename) branches dispatch the saved event", () => {
    const dispatches = hookSrc.match(/notifyCharacterProfileSaved\(projectId,/g) || [];
    expect(dispatches.length).toBeGreaterThanOrEqual(2);
  });

  it("Standard workspace listens and upserts into the Load Character list", () => {
    expect(standardSrc).toMatch(/addEventListener\(CHARACTER_PROFILE_SAVED_EVENT/);
    expect(standardSrc).toMatch(/upsertCharacterSummary\(prev, saved\)/);
    expect(standardSrc).toMatch(/detail\.projectId !== project\.id/);
  });

  it("Express compact view listens and upserts into the Saved Characters list", () => {
    expect(expressSrc).toMatch(/addEventListener\(CHARACTER_PROFILE_SAVED_EVENT/);
    expect(expressSrc).toMatch(/upsertCharacterSummary\(prev, saved\)/);
    expect(expressSrc).toMatch(/detail\.projectId !== projectId/);
    expect(expressSrc).toMatch(/pickOwnedCharacterId\(list, projectId, prev\)/);
    expect(expressSrc).toMatch(/data-testid="character-compact-create"/);
  });

  it("both listeners clean up on unmount", () => {
    expect(standardSrc).toMatch(/removeEventListener\(CHARACTER_PROFILE_SAVED_EVENT/);
    expect(expressSrc).toMatch(/removeEventListener\(CHARACTER_PROFILE_SAVED_EVENT/);
  });

  it("CharacterCore save path surfaces the saved profile (event flows from the hook)", () => {
    expect(coreSrc).toMatch(/const savedProfile = await cp\.save\(/);
  });

  it("save drops an in-flight profile load so the first save is not overwritten", () => {
    expect(hookSrc).toMatch(/loadGenRef\.current \+= 1/);
    expect(hookSrc).toMatch(/characterLoadIsStale\(gen, loadGenRef\.current\)/);
  });

  it("Express and Standard both save through CharacterCore", () => {
    expect(expressSrc).toMatch(/<CharacterCore/);
    expect(expressSrc).toMatch(/mode="express"/);
    expect(standardSrc).toMatch(/<CharacterCore/);
    expect(standardSrc).toMatch(/mode="standard"/);
  });

  it("Create opens a draft and does not persist New Character or Untitled Character first", () => {
    expect(expressSrc).toMatch(/DRAFT_CHARACTER_ID/);
    expect(standardSrc).toMatch(/DRAFT_CHARACTER_ID/);
    expect(expressSrc).not.toMatch(/createCharacterProfile\(/);
    expect(standardSrc).not.toMatch(/name:\s*"Untitled Character"/);
    expect(expressSrc).not.toMatch(/name:\s*"New Character"/);
  });

  it("Standard drops a profile reload that started before Save", () => {
    expect(standardSrc).toMatch(/characterLoadIsStale\(gen, profileLoadGen\.current\)/);
    expect(standardSrc).toMatch(/profileLoadGen\.current \+= 1/);
  });
});

describe("character delete wiring", () => {
  const hookSrc = readFileSync(resolve(__dirname, "useCharacterProfile.ts"), "utf8");

  it("remove no longer calls window.confirm", () => {
    expect(hookSrc).not.toMatch(/window\.confirm/);
  });

  it("remove accepts confirmCrossProject options and passes them to the delete API", () => {
    expect(hookSrc).toMatch(/remove = useCallback\(async \(opts\?: \{ confirmCrossProject\?: boolean \}\)/);
    expect(hookSrc).toMatch(/api\.deleteCharacterProfile\(projectId, cid, opts\?\.confirmCrossProject \?\? false\)/);
  });
});
