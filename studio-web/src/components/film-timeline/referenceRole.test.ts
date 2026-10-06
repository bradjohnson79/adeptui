import { describe, expect, it } from "vitest";
import type { Asset } from "../../types";
import { assetsForReferenceTab, explicitLibraryAssetsForTab, referencePresentation } from "./referenceRole";
import { groupReferenceOptions, type ReferenceOption } from "./referenceEntities";

function asset(partial: Partial<Asset>): Asset {
  return {
    id: "asset-1",
    project_id: "project-1",
    tag: "",
    kind: "image",
    filename: "character_sheet_front.png",
    path: "",
    comfy_name: "",
    created_at: "",
    ...partial,
  };
}

describe("referencePresentation", () => {
  it("F: a saved character with no override does not offer Remove Reference", () => {
    const view = referencePresentation(
      asset({
        effectiveReferenceRole: "character",
        referenceRoleSource: "creator",
        creatorReferenceRole: "character",
      }),
    );
    expect(view.badge).toBe("Character");
    expect(view.note).toBe("Saved Character");
    expect(view.offersRemoveReference).toBe(false);
    expect(view.options.map((option) => option.label)).not.toContain("Remove Reference");
    expect(view.options.map((option) => option.approvedAs)).toEqual(["prop", "environment"]);
  });

  it("G: a manually classified character offers Remove Reference", () => {
    const view = referencePresentation(
      asset({
        effectiveReferenceRole: "character",
        referenceRoleSource: "explicit",
        creatorReferenceRole: null,
      }),
    );
    expect(view.offersRemoveReference).toBe(true);
    const remove = view.options.find((option) => option.label === "Remove Reference");
    expect(remove?.approvedAs).toBeNull();
  });

  it("labels a creator override as Reset to Saved Role", () => {
    const view = referencePresentation(
      asset({
        effectiveReferenceRole: "prop",
        referenceRoleSource: "override",
        creatorReferenceRole: "character",
      }),
    );
    expect(view.badge).toBe("Prop");
    expect(view.note).toBe("Override of Saved Character");
    expect(view.offersRemoveReference).toBe(false);
    expect(view.offersResetToSavedRole).toBe(true);
    expect(view.options.map((option) => option.label)).toContain("Reset to Saved Role");
    expect(view.options.map((option) => option.label)).not.toContain("Remove Reference");
  });

  it("does not infer a role from a character-looking filename", () => {
    const view = referencePresentation(asset({ filename: "seg_01_head.png" }));
    expect(view.effectiveRole).toBeNull();
    expect(view.menuLabel).toBe("Reference As");
    expect(assetsForReferenceTab([asset({ filename: "seg_01_head.png" })], "character")).toEqual([]);
  });
});

describe("assetsForReferenceTab", () => {
  it("keeps each image on the server role only", () => {
    const rows = [
      asset({ id: "none", filename: "imagen_edit.png" }),
      asset({ id: "char", effectiveReferenceRole: "character", referenceRoleSource: "explicit" }),
      asset({ id: "prop", effectiveReferenceRole: "prop", referenceRoleSource: "explicit" }),
      asset({ id: "frame", effectiveReferenceRole: null, referenceRoleSource: "none", prompt_meta_json: '{"approvedAs":"scene_frame"}' }),
      asset({ id: "clip", kind: "video", filename: "plate.mp4", effectiveReferenceRole: "video", referenceRoleSource: "media" }),
    ];
    expect(assetsForReferenceTab(rows, "character").map((item) => item.id)).toEqual(["char"]);
    expect(assetsForReferenceTab(rows, "prop").map((item) => item.id)).toEqual(["prop"]);
    expect(assetsForReferenceTab(rows, "environment")).toEqual([]);
    expect(assetsForReferenceTab(rows, "video").map((item) => item.id)).toEqual(["clip"]);
  });
});

describe("explicitLibraryAssetsForTab", () => {
  it("excludes a saved character's raw hero image (creator source)", () => {
    // Renkoka Front: the hero still of the saved Character entity. It must NOT
    // appear as a standalone library Character choice — the ENTITY does.
    const rows = [
      asset({ id: "hero", filename: "Renkoka Front.png", effectiveReferenceRole: "character", referenceRoleSource: "creator", creatorReferenceRole: "character" }),
      asset({ id: "crs", tag: "Renkoka-CRS", filename: "Renkoka CRS.png", effectiveReferenceRole: "character", referenceRoleSource: "explicit" }),
    ];
    expect(explicitLibraryAssetsForTab(rows, "character").map((item) => item.id)).toEqual(["crs"]);
  });

  it("keeps an explicit override as a library choice", () => {
    const rows = [
      asset({ id: "ovr", effectiveReferenceRole: "prop", referenceRoleSource: "override", creatorReferenceRole: "character" }),
    ];
    expect(explicitLibraryAssetsForTab(rows, "prop").map((item) => item.id)).toEqual(["ovr"]);
  });
});

describe("groupReferenceOptions", () => {
  function entity(partial: Partial<ReferenceOption>): ReferenceOption {
    const base: ReferenceOption = {
      key: "character:x",
      assetId: "a",
      name: "X",
      defaultAlias: "X",
      group: "project",
      thumbAssetId: "a",
      ...partial,
    };
    // Mirror production: defaultAlias follows the entity name unless overridden.
    if (partial.name !== undefined && partial.defaultAlias === undefined) base.defaultAlias = partial.name;
    return base;
  }

  it("groups project / global / library and suppresses the entity bind asset from library", () => {
    const entities = [
      entity({ key: "character:renkoka", assetId: "hero-1", name: "Renkoka", group: "global" }),
      entity({ key: "character:cade", assetId: "hero-2", name: "Cade", group: "global" }),
    ];
    const library = [
      asset({ id: "hero-1", filename: "Renkoka Front.png", effectiveReferenceRole: "character", referenceRoleSource: "creator" }),
      asset({ id: "crs-1", tag: "Renkoka-CRS", filename: "Renkoka CRS.png", effectiveReferenceRole: "character", referenceRoleSource: "explicit" }),
    ];
    const groups = groupReferenceOptions(entities, library, "character");
    expect(groups.project).toEqual([]);
    expect(groups.global.map((option) => option.name)).toEqual(["Cade", "Renkoka"]);
    // The entity bind asset (hero-1) is suppressed; only the explicit CRS remains.
    expect(groups.library.map((option) => option.name)).toEqual(["Renkoka-CRS"]);
    expect(groups.library[0].assetId).toBe("crs-1");
  });

  it("defaults the alias from the entity name", () => {
    const groups = groupReferenceOptions(
      [entity({ key: "environment:abode", assetId: "env-1", name: "Abode", group: "project" })],
      [],
      "environment",
    );
    expect(groups.project[0].defaultAlias).toBe("Abode");
  });
});
