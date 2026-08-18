/**
 * Phase 4 — Character approval truth (CDX-004) frontend units.
 * getHeroIdentity must return no hero for draft-only rows, and the candidate
 * grid label must not show "Selected" before canonical+approved.
 */
import { describe, expect, it } from "vitest";
import { candidateSelectionLabel } from "./types";
import type { CharacterProfile, CharacterReference } from "./types";
import {
  applyLoadedCharacterState,
  getHeroIdentity,
  getPendingHeroIdentity,
  pendingPatchForCurrentCharacter,
  replaceCharacterProfile,
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
