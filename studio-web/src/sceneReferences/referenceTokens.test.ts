import { describe, expect, it } from "vitest";
import {
  bindingAcceptedOnTrack,
  chipLabel,
  displayToken,
  formatAutocompleteRow,
  inferSemanticReferenceType,
  mediaKindForReferenceType,
  normalizePromptTags,
  normalizeTimelineReference,
  parseTokenQuery,
  roleLabelForBinding,
  sanitizeAlias,
  semanticTypeFromPrefix,
  semanticTypeFromSheetPattern,
  sortBindingsForTrack,
  tokenSummary,
  typeLabel,
} from "./referenceTokens.ts";

describe("referenceTokens", () => {
  it("sanitizeAlias strips prefix and spaces", () => {
    expect(sanitizeAlias("*Korri Pose Video")).toBe("KorriPoseVideo");
    expect(sanitizeAlias("@Korri")).toBe("Korri");
    expect(sanitizeAlias("#Schnick Counter")).toBe("SchnickCounter");
  });

  it("displayToken uses typed prefixes", () => {
    expect(displayToken("Korri", "entity", "character")).toBe("@Korri");
    expect(displayToken("VentureCorridorScene", "image", "environment")).toBe("#VentureCorridorScene");
    expect(displayToken("CoffeeMug", "entity", "prop")).toBe("%CoffeeMug");
    expect(displayToken("KorriPoseVideo", "video", "video")).toBe("*KorriPoseVideo");
    expect(displayToken("MoodBoardStill", "image", "generic_image")).toBe("~MoodBoardStill");
  });

  it("generic image sigil ~ round-trips through parse and strip", () => {
    expect(parseTokenQuery("~Mood").prefix).toBe("~");
    expect(parseTokenQuery("~Mood").query).toBe("Mood");
    expect(sanitizeAlias("~MoodBoardStill")).toBe("MoodBoardStill");
    expect(typeLabel("generic_image")).toBe("Image Reference");
  });

  it("autocomplete rows include token and type", () => {
    expect(
      formatAutocompleteRow({
        id: "1",
        asset_id: "a",
        alias: "KorriPoseVideo",
        media_kind: "video",
        reference_type: "video",
        duration_sec: 4.8,
      }),
    ).toMatch(/^\*KorriPoseVideo/);
    expect(
      formatAutocompleteRow({
        id: "2",
        asset_id: "b",
        alias: "Korri",
        media_kind: "entity",
        reference_type: "character",
      }),
    ).toMatch(/^@Korri/);
  });

  it("prop creator prompt text does not classify a prop tag as an environment", () => {
    expect(
      semanticTypeFromSheetPattern(
        "prop_schnickcoffeethermos_c1 no environment scene",
      ),
    ).toBe("prop");
  });

  it("prop sheet tagged prop_ stays a prop when reference_type was stamped environment", () => {
    const thermos = normalizeTimelineReference({
      reference_type: "environment",
      media_kind: "image",
      alias: "SchnickCoffeeThermos",
      display_token: "#SchnickCoffeeThermos",
      asset_name: "prop_schnick-coffee-thermos_c1",
      reference_roles: ["prop"],
    });
    expect(thermos.timedPromptType).toBe("prop");
    expect(thermos.prefix).toBe("%");
    expect(thermos.tag).toBe("%SchnickCoffeeThermos");
  });

  it("wrong type is rejected per track", () => {
    const video = {
      id: "v",
      asset_id: "vid",
      alias: "KorriPoseVideo",
      media_kind: "video" as const,
      reference_type: "video",
    };
    const image = {
      id: "i",
      asset_id: "img",
      alias: "SchnickCounterWide",
      media_kind: "image" as const,
      reference_type: "image",
    };
    expect(bindingAcceptedOnTrack(video, "videoReference")).toBe(true);
    expect(bindingAcceptedOnTrack(image, "videoReference")).toBe(false);
    expect(bindingAcceptedOnTrack(video, "imageReference")).toBe(false);
    expect(bindingAcceptedOnTrack(image, "imageReference")).toBe(true);
    expect(bindingAcceptedOnTrack(video, "prompt")).toBe(true);
    expect(bindingAcceptedOnTrack(image, "prompt")).toBe(true);
    expect(bindingAcceptedOnTrack(video, "camera")).toBe(true);
    expect(bindingAcceptedOnTrack(image, "camera")).toBe(false);
    expect(parseTokenQuery("*Kor").prefix).toBe("*");
    expect(parseTokenQuery("%Coffee").prefix).toBe("%");
  });

  it("token summary stays compact and flags missing bindings", () => {
    const korri = {
      id: "k",
      asset_id: "ak",
      alias: "Korri",
      media_kind: "entity" as const,
      reference_type: "character",
    };
    const bar = {
      id: "b",
      asset_id: "ab",
      alias: "Bar",
      media_kind: "image" as const,
      reference_type: "image",
    };
    expect(tokenSummary(["k", "b", "missing", "x", "y"], [korri, bar])).toBe("@Korri #Bar Broken Reference +2");
  });

  it("camera autocomplete lists characters before videos", () => {
    const video = {
      id: "v",
      asset_id: "vid",
      alias: "Macarena",
      media_kind: "video" as const,
      reference_type: "video",
    };
    const korri = {
      id: "k",
      asset_id: "ak",
      alias: "Korri",
      media_kind: "entity" as const,
      reference_type: "character",
    };
    const cup = {
      id: "p",
      asset_id: "ap",
      alias: "Cup",
      media_kind: "entity" as const,
      reference_type: "prop",
    };
    const sorted = sortBindingsForTrack([video, cup, korri], "camera");
    expect(sorted.map((item) => item.alias)).toEqual(["Korri", "Cup", "Macarena"]);
  });

  it("typeLabel returns human-readable role names, not abbreviations", () => {
    expect(typeLabel("character")).toBe("Character");
    expect(typeLabel("environment")).toBe("Environment");
    expect(typeLabel("prop")).toBe("Prop");
    expect(typeLabel("wardrobe")).toBe("Wardrobe");
    expect(typeLabel("creature")).toBe("Creature");
    expect(typeLabel("scene_frame")).toBe("Scene Frame");
    expect(typeLabel("video", "video")).toBe("Video");
    expect(typeLabel("image", "image")).toBe("Image");
  });

  it("chipLabel returns canonical tag without CRS/ERS/PRS suffix", () => {
    expect(
      chipLabel({
        id: "1",
        asset_id: "a",
        alias: "Addex",
        media_kind: "entity",
        reference_type: "character",
      }),
    ).toBe("@Addex");
    expect(
      chipLabel({
        id: "2",
        asset_id: "b",
        alias: "Place",
        media_kind: "image",
        reference_type: "environment",
      }),
    ).toBe("#Place");
    expect(
      chipLabel({
        id: "3",
        asset_id: "c",
        alias: "Mug",
        media_kind: "entity",
        reference_type: "prop",
      }),
    ).toBe("%Mug");
  });

  it("normalizePromptTags strips CRS suffix from legacy @-tags", () => {
    expect(normalizePromptTags("@KorriCRS walks beside @AddexCRS")).toBe("@Korri walks beside @Addex");
    expect(normalizePromptTags("@KorriERS and #PlaceERS")).toBe("@Korri and #Place");
    expect(normalizePromptTags("@Addex walks beside @Korri40YearsOld")).toBe("@Addex walks beside @Korri40YearsOld");
  });

  it("normalizePromptTags maps to canonical display_token when bindings provided", () => {
    const bindings = [
      {
        id: "k",
        asset_id: "ak",
        alias: "Korri40YearsOld",
        media_kind: "entity" as const,
        reference_type: "character",
        display_token: "@Korri40YearsOld",
      },
      {
        id: "a",
        asset_id: "aa",
        alias: "Addex",
        media_kind: "entity" as const,
        reference_type: "character",
        display_token: "@Addex",
      },
    ];
    expect(normalizePromptTags("@KorriCRS walks beside @AddexCRS", bindings)).toBe(
      "@Korri40YearsOld walks beside @Addex",
    );
  });

  it("normalizePromptTags handles empty and no-tag text", () => {
    expect(normalizePromptTags("")).toBe("");
    expect(normalizePromptTags("No tags here")).toBe("No tags here");
  });

  it("semantic prefix and sheet-pattern inference for attach", () => {
    expect(semanticTypeFromPrefix("#CodirectorErs")).toBe("environment");
    expect(semanticTypeFromPrefix("@Anadriya")).toBe("character");
    expect(semanticTypeFromPrefix("%CoffeeMug")).toBe("prop");
    expect(semanticTypeFromPrefix("~Mood")).toBeNull();
    expect(semanticTypeFromSheetPattern("CodirectorErs")).toBe("environment");
    expect(semanticTypeFromSheetPattern("HeroCRS")).toBe("character");
    expect(semanticTypeFromSheetPattern("MugPRS")).toBe("prop");
    expect(
      inferSemanticReferenceType({ tag: "CodirectorErs", filename: "codirector_ers.png", mediaKind: "image" }),
    ).toBe("environment");
    expect(inferSemanticReferenceType({ tag: "#VentureHall", mediaKind: "image" })).toBe("environment");
    expect(
      inferSemanticReferenceType({ tag: "Anadriya", filename: "anadriya_crs.png", mediaKind: "image" }),
    ).toBe("character");
    expect(inferSemanticReferenceType({ tag: "MoodBoardStill", mediaKind: "image" })).toBe("image");
    expect(inferSemanticReferenceType({ tag: "WalkCycle", mediaKind: "video" })).toBe("video");
    expect(
      inferSemanticReferenceType({
        tag: "Hall",
        mediaKind: "image",
        referenceType: "environment",
      }),
    ).toBe("environment");
  });

  it("image media_kind + reference_type image + display_token #Foo is environment-shaped chip", () => {
    expect(
      chipLabel({
        id: "1",
        asset_id: "a",
        alias: "CodirectorErs",
        media_kind: "image",
        reference_type: "environment",
      }),
    ).toBe("#CodirectorErs");
    expect(displayToken("Foo", "image", "image")).toBe("#Foo");
    expect(displayToken("Foo", "image", "environment")).toBe("#Foo");
  });

  it("normalizeTimelineReference: mediaType image never overrides #/@/% semantics", () => {
    const ers = normalizeTimelineReference({
      alias: "CodirectorErs3d90b410Sheet",
      media_kind: "image",
      reference_type: "image",
      display_token: "#CodirectorErs3d90b410Sheet",
    });
    expect(ers.semanticType).toBe("environment");
    expect(ers.timedPromptType).toBe("environment");
    expect(ers.tag).toBe("#CodirectorErs3d90b410Sheet");
    expect(
      roleLabelForBinding({
        alias: "CodirectorErs3d90b410Sheet",
        media_kind: "image",
        reference_type: "image",
        display_token: "#CodirectorErs3d90b410Sheet",
      }),
    ).toBe("Environment");

    expect(
      normalizeTimelineReference({
        alias: "TestProp",
        media_kind: "image",
        reference_type: "image",
        display_token: "%TestProp",
      }).timedPromptType,
    ).toBe("prop");

    expect(
      normalizeTimelineReference({
        alias: "Anadriya",
        media_kind: "entity",
        reference_type: "character",
        display_token: "@Anadriya",
      }).timedPromptType,
    ).toBe("character");
  });

  it("normalizeTimelineReference: sheet pattern recovers CodirectorErs without display_token prefix", () => {
    const ers = normalizeTimelineReference({
      alias: "CodirectorErs3d90b410Sheet",
      media_kind: "image",
      reference_type: "image",
    });
    expect(ers.timedPromptType).toBe("environment");
    expect(mediaKindForReferenceType("environment", "image")).toBe("image");
    expect(mediaKindForReferenceType("character", "image")).toBe("entity");
    expect(mediaKindForReferenceType("prop", "image")).toBe("entity");
  });

});
