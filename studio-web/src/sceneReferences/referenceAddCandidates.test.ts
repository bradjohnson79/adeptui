import { describe, expect, it } from "vitest";
import {
  collapseDuplicateIdentityCandidates,
  identityAliasKey,
  isAlreadyBound,
  type AddReferenceCandidate,
} from "./referenceAddCandidates";

function row(partial: Partial<AddReferenceCandidate> & Pick<AddReferenceCandidate, "assetId" | "alias">): AddReferenceCandidate {
  return {
    displayToken: `@${partial.alias}`,
    semanticType: "character",
    referenceType: "character",
    mediaKind: "image",
    scopeLabel: "Local",
    assetName: partial.alias,
    searchBlob: partial.alias.toLowerCase(),
    ...partial,
  };
}

describe("duplicate @ identity tags", () => {
  it("treats @Cade and @CadeCRS as one character", () => {
    expect(identityAliasKey("Cade")).toBe("cade");
    expect(identityAliasKey("CadeCRS")).toBe("cade");
    expect(identityAliasKey("Korri40YearsOld")).toBe("korri40yearsold");
  });

  it("keeps @CadeCRS and drops every other Cade view tag", () => {
    const collapsed = collapseDuplicateIdentityCandidates([
      row({ assetId: "front-a", alias: "Cade", assetName: "Cade Front.png" }),
      row({ assetId: "front-b", alias: "Cade", assetName: "Cade Front.png" }),
      row({ assetId: "side", alias: "Cade", assetName: "Cade Side.png" }),
      row({ assetId: "back", alias: "Cade", assetName: "Cade Back.png" }),
      row({ assetId: "threeq", alias: "Cade", assetName: "Cade 3-4.png" }),
      row({
        assetId: "crs",
        alias: "CadeCRS",
        displayToken: "@CadeCRS",
        assetName: "Cade CRS.png",
        searchBlob: "cadecrs cade crs.png",
      }),
      row({ assetId: "korri", alias: "Korri", displayToken: "@Korri" }),
    ]);
    const cade = collapsed.filter((item) => identityAliasKey(item.alias) === "cade");
    expect(cade.map((item) => item.displayToken)).toEqual(["@CadeCRS"]);
    expect(collapsed.some((item) => item.alias === "Korri")).toBe(true);
  });

  it("collapses identical view tags to one row when no sheet token exists", () => {
    const collapsed = collapseDuplicateIdentityCandidates([
      row({ assetId: "a", alias: "Korri" }),
      row({ assetId: "b", alias: "Korri" }),
    ]);
    expect(collapsed).toHaveLength(1);
    expect(collapsed[0].alias).toBe("Korri");
  });

  it("drops placeholder angle tags that belong to the same character as @CadeCRS", () => {
    const collapsed = collapseDuplicateIdentityCandidates([
      row({ assetId: "front", alias: "Cade", characterId: "cade-id" }),
      row({
        assetId: "crs",
        alias: "CadeCRS",
        displayToken: "@CadeCRS",
        assetName: "Cade CRS.png",
        characterId: "cade-id",
      }),
      row({
        assetId: "side",
        alias: "NewCharacter",
        displayToken: "@NewCharacter",
        assetName: "Cade Side.png",
        characterId: "cade-id",
      }),
    ]);
    expect(collapsed.map((item) => item.displayToken)).toEqual(["@CadeCRS"]);
  });

  it("treats a bound @CadeCRS as already covering @Cade", () => {
    expect(
      isAlreadyBound(
        { assetId: "front", alias: "Cade" },
        [{ assetId: "crs", alias: "CadeCRS" }],
      ),
    ).toBe(true);
  });
});
