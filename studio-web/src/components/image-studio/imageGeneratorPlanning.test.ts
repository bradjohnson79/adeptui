import { describe, expect, it } from "vitest";
import { serializeImageGeneratorPlan } from "./imageGeneratorPlanning";
import { parseIgPromptTokens } from "./igPromptTokens";
import type { CisAuthorityRef } from "./cisAuthorityTypes";

describe("serializeImageGeneratorPlan", () => {
  const character: CisAuthorityRef = {
    key: "char:korri",
    kind: "character",
    assetId: "a-char",
    name: "Korri",
    chip: "@Korri",
  };
  const prop: CisAuthorityRef = {
    key: "prop:blade",
    kind: "prop",
    assetId: "a-prop",
    name: "Blade",
    chip: "%Blade",
  };
  const environment: CisAuthorityRef = {
    key: "env:corridor",
    kind: "environment",
    assetId: "a-env",
    name: "VentureCorridor",
    chip: "#VentureCorridor",
  };
  const pose: CisAuthorityRef = {
    key: "pose:hero",
    kind: "posecraft",
    assetId: "a-pose",
    name: "HeroStance",
    chip: "~PoseCraft_HeroStance",
  };
  const generic: CisAuthorityRef = {
    key: "other:mood",
    kind: "other",
    assetId: "a-gen",
    name: "MoodBoard",
    chip: "~MoodBoard",
  };

  it("partitions authorityRefs into selected* + references + poseCraft", () => {
    const snap = serializeImageGeneratorPlan({
      prompt: "@Korri with %Blade in #VentureCorridor ~PoseCraft_HeroStance ~MoodBoard",
      authorityRefs: [character, prop, environment, pose, generic],
      referenceAssetIds: ["a-char", "a-prop", "a-env", "a-pose", "a-gen"],
      unresolvedTags: [],
      updatedAt: "2026-09-12T00:00:00.000Z",
      generationMode: "best_match",
      category: "production_still",
      batchSize: 2,
      modelId: "provider-1",
      generatorId: "provider-1",
      aspectRatio: "16:9",
      resolution: "1K",
    });

    expect(snap.selectedCharacters).toEqual([character]);
    expect(snap.selectedProps).toEqual([prop]);
    expect(snap.selectedEnvironment).toEqual(environment);
    expect(snap.selectedPoseCraft).toEqual(pose);
    expect(snap.selectedGeneric).toEqual([generic]);
    expect(snap.references).toEqual([
      {
        kind: "character",
        role: "character",
        assetId: "a-char",
        name: "Korri",
        label: "Korri",
        token: "@Korri",
      },
      {
        kind: "prop",
        role: "prop",
        assetId: "a-prop",
        name: "Blade",
        label: "Blade",
        token: "%Blade",
      },
      {
        kind: "environment",
        role: "environment",
        assetId: "a-env",
        name: "VentureCorridor",
        label: "VentureCorridor",
        token: "#VentureCorridor",
      },
      {
        kind: "posecraft",
        role: "posecraft",
        assetId: "a-pose",
        name: "HeroStance",
        label: "HeroStance",
        token: "~PoseCraft_HeroStance",
      },
      {
        kind: "other",
        role: "other",
        assetId: "a-gen",
        name: "MoodBoard",
        label: "MoodBoard",
        token: "~MoodBoard",
      },
    ]);
    expect(snap.poseCraft).toEqual({
      attached: true,
      imageAssetId: "a-pose",
      name: "HeroStance",
      chip: "~PoseCraft_HeroStance",
    });
    expect(snap.generationMode).toBe("best_match");
    expect(snap.category).toBe("production_still");
    expect(snap.batchSize).toBe(2);
    expect(snap.modelId).toBe("provider-1");
    expect(snap.generatorId).toBe("provider-1");
    expect(snap.aspectRatio).toBe("16:9");
    expect(snap.resolution).toBe("1K");
  });

  it("derives promptTags via parseIgPromptTokens (punctuation-safe)", () => {
    const punctuated = "@Korri, walks with @Anadriya. Scene: #VentureCorridor;";
    const tags = parseIgPromptTokens(punctuated).map((t) => t.raw);
    expect(tags).toEqual(["@Korri", "@Anadriya", "#VentureCorridor"]);

    const snap = serializeImageGeneratorPlan({
      prompt: punctuated,
      authorityRefs: [character, environment],
      referenceAssetIds: ["a-char", "a-env"],
      unresolvedTags: [],
      updatedAt: "2026-09-12T00:00:00.000Z",
    });
    expect(snap.promptTags).toEqual(["@Korri", "@Anadriya", "#VentureCorridor"]);
    expect(snap.selectedPoseCraft).toBeNull();
    expect(snap.poseCraft).toEqual({ attached: false });
    expect(snap.selectedGeneric).toEqual([]);
  });
});
