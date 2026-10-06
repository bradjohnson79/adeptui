import { describe, expect, it } from "vitest";
import type { Asset } from "../../types";
import { assetsForReferenceTab, referencePresentation } from "./referenceRole";
import { libraryAfterClassification, mergeLibraryPage, upsertClassifiedAsset } from "./referenceLibrary";

function asset(partial: Partial<Asset>): Asset {
  return {
    id: "asset-1",
    project_id: "project-1",
    tag: "Renkoka-sample",
    kind: "image",
    filename: "Renkoka sample.png",
    path: "",
    comfy_name: "",
    created_at: "",
    ...partial,
  };
}

describe("library classification wiring", () => {
  it("A: none to Character lands in the shared list and the Character tab", () => {
    const page = [asset({ id: "other", tag: "other" })];
    const classified = asset({
      id: "sample",
      effectiveReferenceRole: "character",
      referenceRoleSource: "explicit",
    });
    const next = libraryAfterClassification(page, classified, true);
    expect(referencePresentation(next.find((item) => item.id === "sample")!).badge).toBe("Character");
    expect(referencePresentation(next.find((item) => item.id === "sample")!).offersRemoveReference).toBe(true);
    expect(assetsForReferenceTab(next, "character").map((item) => item.id)).toEqual(["sample"]);
    expect(assetsForReferenceTab(next, "prop")).toEqual([]);
  });

  it("B: Character to Prop leaves Character and enters Prop", () => {
    const current = [
      asset({
        id: "sample",
        effectiveReferenceRole: "character",
        referenceRoleSource: "explicit",
      }),
    ];
    const next = libraryAfterClassification(
      current,
      asset({ id: "sample", effectiveReferenceRole: "prop", referenceRoleSource: "explicit" }),
      true,
    );
    expect(referencePresentation(next[0]).badge).toBe("Prop");
    expect(assetsForReferenceTab(next, "character")).toEqual([]);
    expect(assetsForReferenceTab(next, "prop").map((item) => item.id)).toEqual(["sample"]);
  });

  it("C: Prop to none removes every image tab and the green role", () => {
    const current = [
      asset({ id: "sample", effectiveReferenceRole: "prop", referenceRoleSource: "explicit" }),
    ];
    const next = libraryAfterClassification(
      current,
      asset({ id: "sample", effectiveReferenceRole: null, referenceRoleSource: "none" }),
      true,
    );
    const view = referencePresentation(next[0]);
    expect(view.badge).toBeNull();
    expect(view.menuLabel).toBe("Reference As");
    expect(assetsForReferenceTab(next, "character")).toEqual([]);
    expect(assetsForReferenceTab(next, "prop")).toEqual([]);
    expect(assetsForReferenceTab(next, "environment")).toEqual([]);
  });

  it("D: a failed classification preserves the previous role", () => {
    const current = [
      asset({ id: "sample", effectiveReferenceRole: "character", referenceRoleSource: "explicit" }),
    ];
    const next = libraryAfterClassification(current, null, false);
    expect(next).toBe(current);
    expect(referencePresentation(next[0]).badge).toBe("Character");
  });

  it("F: an off-page tray asset stays in the modal list after a page refresh", () => {
    const classified = asset({
      id: "sample",
      effectiveReferenceRole: "environment",
      referenceRoleSource: "explicit",
    });
    const withRole = upsertClassifiedAsset([asset({ id: "page-only" })], classified);
    const refreshed = mergeLibraryPage(withRole, [asset({ id: "page-only", filename: "newer.png" })]);
    expect(assetsForReferenceTab(refreshed, "environment").map((item) => item.id)).toEqual(["sample"]);
    expect(refreshed.find((item) => item.id === "page-only")?.filename).toBe("newer.png");
  });

  it("G: a saved character shows the green role and not Remove Reference", () => {
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
  });

  it("H: an override shows the new role and Reset to Saved Role", () => {
    const view = referencePresentation(
      asset({
        effectiveReferenceRole: "environment",
        referenceRoleSource: "override",
        creatorReferenceRole: "character",
      }),
    );
    expect(view.badge).toBe("Environment");
    expect(view.note).toBe("Override of Saved Character");
    expect(view.offersResetToSavedRole).toBe(true);
    expect(view.offersRemoveReference).toBe(false);
  });
});
