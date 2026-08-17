/**
 * Phase 4 — Character approval truth (CDX-004) frontend units.
 * getHeroIdentity must return no hero for draft-only rows, and the candidate
 * grid label must not show "Selected" before canonical+approved.
 */
import { describe, expect, it } from "vitest";
import { candidateSelectionLabel } from "./types";
import type { CharacterReference } from "./types";
import { getHeroIdentity, getPendingHeroIdentity } from "./useCharacterProfile";

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
