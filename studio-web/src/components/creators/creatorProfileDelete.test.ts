import { describe, expect, it } from "vitest";
import { buildDeleteCopy, isGlobalDirty } from "./creatorProfileDelete";
import type { CreatorDeletePreview } from "./creatorProfileDelete";

function preview(over: Partial<CreatorDeletePreview> = {}): CreatorDeletePreview {
  return {
    entityType: "character",
    entityId: "c1",
    name: "Korri",
    isGlobal: false,
    owningProjectId: "p1",
    usage: [],
    usageCount: 0,
    projectCount: 0,
    libraryAssetsKept: true,
    canDelete: true,
    ...over,
  };
}

describe("buildDeleteCopy", () => {
  it("uses local language and primary label for a project-scoped profile", () => {
    const copy = buildDeleteCopy("character", preview({ isGlobal: false, name: "Anadriya" }));
    expect(copy.title).toBe("Delete Anadriya?");
    expect(copy.body).toContain("local Character profile");
    expect(copy.body).toContain("This action cannot be undone.");
    expect(copy.primaryLabel).toBe("Delete Character");
  });

  it("uses global language and primary label for a global profile", () => {
    const copy = buildDeleteCopy("prop", preview({ entityType: "prop", isGlobal: true, name: "Lantern" }));
    expect(copy.title).toBe("Delete Lantern?");
    expect(copy.body).toContain("Global Prop profile");
    expect(copy.body).toContain("every project currently using this Global profile");
    expect(copy.primaryLabel).toBe("Delete Global Prop");
  });

  it("summarizes usage across one project", () => {
    const copy = buildDeleteCopy(
      "environment",
      preview({
        entityType: "environment",
        isGlobal: false,
        usageCount: 3,
        projectCount: 1,
        usage: [{ projectId: "p1", projectName: "Pilot", kind: "scene", label: "Corridor" }],
      }),
    );
    expect(copy.usageSummary).toMatch(/referenced by 3 scenes across 1 project/);
    expect(copy.body).toContain(copy.usageSummary);
  });

  it("summarizes global cross-project usage", () => {
    const copy = buildDeleteCopy(
      "character",
      preview({
        isGlobal: true,
        usageCount: 1,
        projectCount: 2,
        usage: [
          { projectId: "p1", projectName: "Pilot", kind: "scene" },
          { projectId: "p2", projectName: "Trailer", kind: "scene" },
        ],
      }),
    );
    expect(copy.usageSummary).toMatch(/referenced by 1 scene across 2 projects/);
    expect(copy.usageSummary).toContain("It will disappear from every project that uses it.");
  });

  it("falls back to a generic name when the preview has none", () => {
    const copy = buildDeleteCopy("prop", preview({ entityType: "prop", name: "" }));
    expect(copy.title).toBe("Delete this prop?");
  });
});

describe("isGlobalDirty", () => {
  it("detects a changed global flag", () => {
    expect(isGlobalDirty(false, true)).toBe(true);
    expect(isGlobalDirty(true, false)).toBe(true);
  });

  it("returns false when the global flag is unchanged", () => {
    expect(isGlobalDirty(false, false)).toBe(false);
    expect(isGlobalDirty(true, true)).toBe(false);
  });
});
