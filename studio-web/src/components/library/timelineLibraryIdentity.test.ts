import { describe, expect, it } from "vitest";
import {
  assetMatchesLibrarySearch,
  buildCharacterNameMap,
  timelineLibraryIdentity,
} from "./timelineLibraryIdentity";

const NAMES = buildCharacterNameMap([
  { id: "4c1c0bc8-a771-4998-b652-5d549b2a2b8d", name: "Anadriya" },
  { id: "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed", name: "Korri" },
]);

describe("timelineLibraryIdentity", () => {
  it("maps character-name ids and 8-character prefixes", () => {
    expect(NAMES["4c1c0bc8-a771-4998-b652-5d549b2a2b8d"]).toBe("Anadriya");
    expect(NAMES["4c1c0bc8"]).toBe("Anadriya");
    expect(NAMES["4a2e9cbe"]).toBe("Korri");
  });

  it("identifies character sheets by existing characterId instead of @character_sheet", () => {
    const anadriya = timelineLibraryIdentity(
      {
        tag: "character_sheet",
        filename: "character_sheet_4c1c0bc8_c1_22430609.png",
        kind: "image",
        labels_json: '["character_sheet","composed","candidate_1"]',
        prompt_meta_json: JSON.stringify({
          objective: "character_sheet_composed",
          characterId: "4c1c0bc8-a771-4998-b652-5d549b2a2b8d",
        }),
      },
      { characterNames: NAMES },
    );
    const korri = timelineLibraryIdentity(
      {
        tag: "character_sheet",
        filename: "character_sheet_4a2e9cbe_c1_0ed74c11.png",
        kind: "image",
        labels_json: '["character_sheet","composed","candidate_1"]',
        prompt_meta_json: JSON.stringify({
          objective: "character_sheet_composed",
          characterId: "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed",
        }),
      },
      { characterNames: NAMES },
    );
    expect(anadriya.title).toBe("@Anadriya");
    expect(korri.title).toBe("@Korri");
    expect(anadriya.title).not.toBe(korri.title);
    expect(anadriya.context).toContain("Character sheet");
    expect(anadriya.tooltip).toContain("character_sheet_4c1c0bc8_c1_22430609.png");
  });

  it("keeps a Prop Creator still as a prop when the prompt says no environment scene", () => {
    const identity = timelineLibraryIdentity({
      tag: "prop_schnickcoffeethermos_c1",
      filename: "imagegen_edit.png",
      kind: "image",
      labels_json: '["approved_prop","prop_view"]',
      prompt_meta_json: JSON.stringify({
        prompt: "No character holding the prop, no environment scene",
        purpose: "project prop",
      }),
    });
    expect(identity.sheetKind).toBe("prs");
    expect(identity.title.startsWith("%")).toBe(true);
  });

  it("uses the character profile name instead of a New Character placeholder", () => {
    const identity = timelineLibraryIdentity(
      {
        tag: "New Character — Side",
        filename: "Cade Side.png",
        kind: "image",
        prompt_meta_json: JSON.stringify({
          characterId: "93145921-28cb-46d1-86fc-28c213192a42",
          characterName: "New Character",
          role: "character_angle",
        }),
      },
      {
        characterNames: { "93145921-28cb-46d1-86fc-28c213192a42": "Cade" },
      },
    );
    expect(identity.title).toBe("Cade");
  });

  it("uses a human identity filename when no profile map is present", () => {
    const identity = timelineLibraryIdentity({
      tag: "character_reference",
      filename: "Anadriya Front.png",
      kind: "image",
      labels_json: "[]",
      prompt_meta_json: JSON.stringify({
        library: {
          libraryPath: "Project/Characters/Identity References",
          classification: { category: "characters", subtype: "identity_references" },
        },
      }),
    });
    expect(identity.title).toBe("@Anadriya");
    expect(identity.context).toContain("Identity");
  });

  it("resolves a sheet name from a related identity filename", () => {
    const identity = timelineLibraryIdentity(
      {
        id: "sheet-1",
        tag: "character_sheet",
        filename: "character_sheet_4c1c0bc8_c1_22430609.png",
        kind: "image",
        labels_json: '["character_sheet"]',
        prompt_meta_json: JSON.stringify({
          characterId: "4c1c0bc8-a771-4998-b652-5d549b2a2b8d",
          sourceAssetIds: ["front-1"],
        }),
      },
      {
        relatedAssets: [{ id: "front-1", filename: "Anadriya Front.png", tag: "character_reference" }],
      },
    );
    expect(identity.title).toBe("@Anadriya");
  });

  it("keeps environment tags as # tokens and does not promote machine filenames", () => {
    const place = timelineLibraryIdentity({
      tag: "Venture-Corridor-scene",
      filename: "Venture Corridor scene.png",
      kind: "image",
    });
    expect(place.title).toBe("#VentureCorridorScene");
    expect(place.context).toMatch(/Environment|ERS/);

    const generated = timelineLibraryIdentity({
      tag: "codirector_image_generate_4bdc4259",
      filename: "imagegen_fal_be64469b.png",
      kind: "image",
    });
    expect(generated.title).toBe("Image");
    expect(generated.tooltip).toContain("imagegen_fal_be64469b.png");
  });

  it("matches search against character name, not only the raw tag", () => {
    const asset = {
      tag: "character_sheet",
      filename: "character_sheet_4a2e9cbe_c1_0ed74c11.png",
      kind: "image",
      prompt_meta_json: JSON.stringify({ characterId: "4a2e9cbe-e1e0-4d87-a411-6a8851b2f0ed" }),
    };
    const identity = timelineLibraryIdentity(asset, { characterNames: NAMES });
    expect(assetMatchesLibrarySearch(asset, "korri", identity)).toBe(true);
    expect(assetMatchesLibrarySearch(asset, "character_sheet", identity)).toBe(true);
    expect(assetMatchesLibrarySearch(asset, "anadriya", identity)).toBe(false);
  });
});
