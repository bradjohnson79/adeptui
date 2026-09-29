import { describe, expect, it } from "vitest";
import type { ReferenceBindingView } from "../sceneReferences/referenceTokens";
import {
  applyTimedPromptNameBindingPatch,
  bindingIdsFromNameBindings,
  canonicalTimedPromptTag,
  defaultTimedPromptName,
  duplicatePromptNameIndex,
  hydrateTimedPromptNameBindings,
  isSceneSheetBinding,
  labelCharacterBindingFromIdentity,
  normalizePromptNameKey,
  sceneSheetBindings,
  timedPromptBindingMissing,
  timedPromptTypeForBinding,
  validateTimedPromptNameBindings,
} from "./timedPromptNameBindings";

const korri: ReferenceBindingView = {
  id: "bind-korri",
  asset_id: "asset-k",
  identity_id: "char-k",
  alias: "Korri",
  media_kind: "entity",
  reference_type: "character",
  display_token: "@Korri",
  asset_name: "Korri",
};

const anadriya: ReferenceBindingView = {
  id: "bind-ana",
  asset_id: "asset-a",
  identity_id: "char-a",
  alias: "Anadriya",
  media_kind: "entity",
  reference_type: "character",
  display_token: "@Anadriya",
  asset_name: "Anadriya",
};

const corridor: ReferenceBindingView = {
  id: "bind-ers",
  asset_id: "asset-ers",
  alias: "VentureCorridorScene",
  media_kind: "image",
  reference_type: "environment",
  display_token: "#VentureCorridorScene",
  asset_name: "Venture corridor",
};

const video: ReferenceBindingView = {
  id: "bind-vid",
  asset_id: "asset-vid",
  alias: "MinimaxH3",
  media_kind: "video",
  reference_type: "video",
  display_token: "*MinimaxH3",
};

const synthetic: ReferenceBindingView = {
  id: "character:char-k",
  asset_id: "asset-k",
  alias: "Korri",
  media_kind: "entity",
  reference_type: "character",
};

describe("timedPromptNameBindings", () => {
  it("labels a CharacterSheet row from its bound identity without changing the binding id", () => {
    // Canonical law: the binding alias (from the Library asset tag) IS the
    // canonical tag. labelCharacterBindingFromIdentity must respect it,
    // not override it with the character profile name.
    const sheet: ReferenceBindingView = {
      id: "bind-sheet",
      asset_id: "asset-k",
      identity_id: "char-k",
      alias: "Korri40YearsOld",
      media_kind: "entity",
      reference_type: "character",
      display_token: "@Korri40YearsOld",
      asset_name: "Korri-40-years-old",
    };
    const labeled = labelCharacterBindingFromIdentity(sheet, "Korri");
    expect(labeled.id).toBe("bind-sheet");
    expect(labeled.display_token).toBe("@Korri40YearsOld");
    // defaultTimedPromptName returns the human-readable asset_name first
    expect(defaultTimedPromptName(labeled)).toBe("Korri-40-years-old");
    expect(canonicalTimedPromptTag(labeled)).toBe("@Korri40YearsOld");
  });

  it("falls back to the character profile name when the binding has no alias", () => {
    const sheet: ReferenceBindingView = {
      id: "bind-sheet2",
      asset_id: "asset-k",
      identity_id: "char-k",
      alias: "",
      media_kind: "entity",
      reference_type: "character",
      display_token: "",
      asset_name: "",
    };
    const labeled = labelCharacterBindingFromIdentity(sheet, "Korri");
    expect(labeled.display_token).toBe("@Korri");
    expect(defaultTimedPromptName(labeled)).toBe("Korri");
  });

  it("accepts scene Character/Prop/Environment/Video/Audio bindings", () => {
    expect(timedPromptTypeForBinding(korri)).toBe("character");
    expect(timedPromptTypeForBinding(corridor)).toBe("environment");
    expect(timedPromptTypeForBinding(video)).toBe("video");
    expect(isSceneSheetBinding(synthetic)).toBe(false);
    expect(sceneSheetBindings([korri, corridor, video, synthetic]).map((row) => row.id)).toEqual([
      "bind-korri",
      "bind-ers",
      "bind-vid",
    ]);
    expect(sceneSheetBindings([korri, corridor, video], "video").map((row) => row.id)).toEqual(["bind-vid"]);
    expect(sceneSheetBindings([korri, corridor], "environment").map((row) => row.id)).toEqual(["bind-ers"]);
  });

  it("hydrates prompt names from existing IDs without inventing library rows", () => {
    const rows = hydrateTimedPromptNameBindings({
      bindingIds: ["bind-korri", "bind-ana", "bind-ers", "bind-missing"],
      bindings: [korri, anadriya, corridor],
    });
    expect(rows).toEqual([
      { binding_id: "bind-korri", prompt_name: "Korri", type: "character", tag: "@Korri", asset_id: "asset-k", identity_id: "char-k", reference_sheet_id: "" },
      { binding_id: "bind-ana", prompt_name: "Anadriya", type: "character", tag: "@Anadriya", asset_id: "asset-a", identity_id: "char-a", reference_sheet_id: "" },
      { binding_id: "bind-ers", prompt_name: "Venture corridor", type: "environment", tag: "#VentureCorridorScene", asset_id: "asset-ers", identity_id: "", reference_sheet_id: "" },
      { binding_id: "bind-missing", prompt_name: "", type: "character", tag: "", asset_id: "", identity_id: "", reference_sheet_id: "" },
    ]);
    expect(timedPromptBindingMissing(rows[3], [korri, anadriya, corridor])).toBe(true);
    expect(canonicalTimedPromptTag(korri)).toBe("@Korri");
    expect(defaultTimedPromptName(corridor)).toBe("Venture corridor");
  });

  it("keeps saved prompt names and rejects duplicate names plus duplicate binding ids", () => {
    const hydrated = hydrateTimedPromptNameBindings({
      nameBindings: [
        { bindingId: "bind-korri", promptName: "Korri", type: "character", tag: "@Korri" },
      ],
      bindingIds: ["bind-korri", "bind-ana"],
      bindings: [korri, anadriya],
    });
    expect(hydrated[0].prompt_name).toBe("Korri");
    expect(bindingIdsFromNameBindings(hydrated)).toEqual(["bind-korri", "bind-ana"]);
    expect(duplicatePromptNameIndex(hydrated, "korri")).toBe(0);

    const dupName = applyTimedPromptNameBindingPatch(
      hydrated,
      1,
      { prompt_name: "Korri" },
      [korri, anadriya],
    );
    expect(dupName.error).toMatch(/already used/i);

    const dupId = applyTimedPromptNameBindingPatch(
      hydrated,
      1,
      { binding_id: "bind-korri" },
      [korri, anadriya],
    );
    expect(dupId.error).toMatch(/already bound/i);
  });

  it("does not silently retarget when the type changes", () => {
    const rows = hydrateTimedPromptNameBindings({
      nameBindings: [{ binding_id: "bind-korri", prompt_name: "Korri", type: "character", tag: "@Korri" }],
      bindings: [korri, corridor],
    });
    const next = applyTimedPromptNameBindingPatch(rows, 0, { type: "environment" }, [korri, corridor]);
    expect(next.error).toBeNull();
    expect(next.rows[0]).toEqual({
      binding_id: "",
      prompt_name: "Korri",
      type: "environment",
      tag: "",
      asset_id: "",
      identity_id: "",
      reference_sheet_id: "",
    });
  });
  it("resolves leaked image reference_type via # display_token and ERS patterns", () => {
    const leakedErs: ReferenceBindingView = {
      id: "bind-codirector-ers",
      asset_id: "asset-ers-img",
      alias: "CodirectorErs",
      media_kind: "image",
      reference_type: "image",
      display_token: "#CodirectorErs",
      asset_name: "Codirector ERS still",
    };
    const plainImage: ReferenceBindingView = {
      id: "bind-plain-img",
      asset_id: "asset-plain",
      alias: "MoodBoardStill",
      media_kind: "image",
      reference_type: "image",
      display_token: "~MoodBoardStill",
      asset_name: "Mood board",
    };
    const hashOnly: ReferenceBindingView = {
      id: "bind-hash-env",
      asset_id: "asset-hash",
      alias: "VentureHall",
      media_kind: "image",
      reference_type: "image",
      display_token: "#VentureHall",
      asset_name: "Venture hall",
    };
    expect(timedPromptTypeForBinding(leakedErs)).toBe("environment");
    expect(timedPromptTypeForBinding(hashOnly)).toBe("environment");
    expect(timedPromptTypeForBinding(plainImage)).toBeNull();
    expect(sceneSheetBindings([korri, leakedErs, plainImage, video], "environment").map((r) => r.id)).toEqual([
      "bind-codirector-ers",
    ]);
  });

  it("prefix fallback maps @/#/% even when reference_type is media-leaked image", () => {
    expect(
      timedPromptTypeForBinding({
        id: "a",
        asset_id: "a",
        alias: "@Anadriya",
        media_kind: "image",
        reference_type: "image",
        display_token: "@Anadriya",
      }),
    ).toBe("character");
    expect(
      timedPromptTypeForBinding({
        id: "b",
        asset_id: "b",
        alias: "%CoffeeMug",
        media_kind: "image",
        reference_type: "image",
        display_token: "%CoffeeMug",
      }),
    ).toBe("prop");
  });

  it("migrates a persisted tag to the live binding canonical tag", () => {
    const renamed = { ...korri, alias: "KorriRenamed", display_token: "@KorriRenamed" };
    const kept = hydrateTimedPromptNameBindings({
      nameBindings: [{ binding_id: "bind-korri", prompt_name: "Korri", type: "character", tag: "@Korri" }],
      bindings: [renamed],
    });
    expect(kept[0].tag).toBe("@KorriRenamed");
    const filled = hydrateTimedPromptNameBindings({
      nameBindings: [{ binding_id: "bind-korri", prompt_name: "Korri", type: "character", tag: "" }],
      bindings: [renamed],
    });
    expect(filled[0].tag).toBe("@KorriRenamed");
    expect(filled[0].binding_id).toBe("bind-korri");
  });

  it("migrates suffixed Venture/Earth/Cade tags to the identity canonical tag", () => {
    const venture: ReferenceBindingView = {
      id: "bind-venture",
      asset_id: "asset-v",
      alias: "VentureSpaceship",
      media_kind: "entity",
      reference_type: "prop",
      display_token: "%VentureSpaceship",
      asset_name: "Venture Spaceship",
      identity_id: "prop-venture",
    };
    const rows = hydrateTimedPromptNameBindings({
      nameBindings: [
        {
          binding_id: "bind-venture",
          prompt_name: "Venture Spaceship",
          type: "prop",
          tag: "%VentureSpaceship3",
        },
      ],
      bindings: [venture],
    });
    expect(rows[0].tag).toBe("%VentureSpaceship");
  });

  it("treats a scene-scoped library environment as FOUND when the catalog has the binding id", () => {
    const earth: ReferenceBindingView = {
      id: "bind-earth",
      asset_id: "asset-earth",
      alias: "EarthHorizon",
      media_kind: "image",
      reference_type: "environment",
      display_token: "#EarthHorizon",
      asset_name: "Earth Horizon",
    };
    const rows = hydrateTimedPromptNameBindings({
      nameBindings: [
        {
          binding_id: "bind-earth",
          prompt_name: "Earth Horizon",
          type: "environment",
          tag: "#EarthHorizon",
          asset_id: "asset-earth",
        },
      ],
      bindings: [earth],
    });
    expect(timedPromptBindingMissing(rows[0], [earth])).toBe(false);
    expect(timedPromptBindingMissing(rows[0], [])).toBe(true);
    expect(timedPromptBindingMissing(rows[0], [{ ...earth, broken: true }])).toBe(true);
  });



  it("detects #CodirectorErs image refs as Environment and % props (mediaType image must not win)", () => {
    const ersImage: ReferenceBindingView = {
      id: "bind-codirector-ers",
      asset_id: "asset-ers-cd",
      alias: "CodirectorErs3d90b410Sheet",
      media_kind: "image",
      reference_type: "image",
      display_token: "#CodirectorErs3d90b410Sheet",
      asset_name: "CodirectorErs3d90b410Sheet",
    };
    const propImage: ReferenceBindingView = {
      id: "bind-prop",
      asset_id: "asset-prop",
      alias: "TestProp",
      media_kind: "image",
      reference_type: "image",
      display_token: "%TestProp",
    };
    expect(timedPromptTypeForBinding(ersImage)).toBe("environment");
    expect(timedPromptTypeForBinding(propImage)).toBe("prop");
    expect(sceneSheetBindings([korri, ersImage, propImage], "environment").map((row) => row.id)).toEqual([
      "bind-codirector-ers",
    ]);
    expect(sceneSheetBindings([korri, ersImage, propImage], "prop").map((row) => row.id)).toEqual(["bind-prop"]);
  });


  it("does not treat REF TAG namespace as Prompt Name collisions", () => {
    // #AnadriyaQuarters tag on row A vs Prompt Name AnadriyaQuarters on row B is OK.
    const rows = [
      {
        binding_id: "bind-ers",
        prompt_name: "Venture hall",
        type: "environment" as const,
        tag: "#AnadriyaQuarters",
      },
      {
        binding_id: "bind-korri",
        prompt_name: "Korri",
        type: "character" as const,
        tag: "@Korri",
      },
    ];
    expect(duplicatePromptNameIndex(rows, "AnadriyaQuarters", 1)).toBe(-1);
    expect(duplicatePromptNameIndex(rows, "#AnadriyaQuarters", 1)).toBe(-1);
    const patched = applyTimedPromptNameBindingPatch(
      rows,
      1,
      { prompt_name: "AnadriyaQuarters" },
      [korri, corridor],
    );
    expect(patched.error).toBeNull();
    expect(patched.rows[1].prompt_name).toBe("AnadriyaQuarters");
    expect(validateTimedPromptNameBindings(patched.rows)).toBeNull();
  });

  it("flags exact normalized Prompt Name collisions only", () => {
    const rows = [
      {
        binding_id: "bind-korri",
        prompt_name: "AnadriyaQuarters",
        type: "character" as const,
        tag: "@Korri",
      },
      {
        binding_id: "bind-ana",
        prompt_name: "Other",
        type: "character" as const,
        tag: "@Anadriya",
      },
    ];
    expect(normalizePromptNameKey("  AnadriyaQuarters ")).toBe("anadriyaquarters");
    expect(duplicatePromptNameIndex(rows, "anadriyaquarters", 1)).toBe(0);
    expect(duplicatePromptNameIndex(rows, "Anadriya", 1)).toBe(-1); // incomplete / different string
    const dup = applyTimedPromptNameBindingPatch(
      rows,
      1,
      { prompt_name: "AnadriyaQuarters" },
      [korri, anadriya],
    );
    expect(dup.error).toMatch(/already used/i);
    expect(validateTimedPromptNameBindings([
      { ...rows[0] },
      { ...rows[1], prompt_name: "AnadriyaQuarters" },
    ])).toMatch(/already used/i);
  });

  it("can skip duplicate validation when options.validateDuplicates is false", () => {
    const rows = [
      {
        binding_id: "bind-korri",
        prompt_name: "Same",
        type: "character" as const,
        tag: "@Korri",
      },
      {
        binding_id: "bind-ana",
        prompt_name: "Other",
        type: "character" as const,
        tag: "@Anadriya",
      },
    ];
    const skipped = applyTimedPromptNameBindingPatch(
      rows,
      1,
      { prompt_name: "Same" },
      [korri, anadriya],
      { validateDuplicates: false },
    );
    expect(skipped.error).toBeNull();
    expect(skipped.rows[1].prompt_name).toBe("Same");
  });

});
