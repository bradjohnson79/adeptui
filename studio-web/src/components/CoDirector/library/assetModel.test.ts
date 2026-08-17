import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * assetModel — pure-logic unit tests for resolveAssetUrl / getCardPreviewUrl,
 * approval-badge parsing (CDX-017) and entity-name resolution (CDX-071).
 *
 * apiUrl() reads VITE_API_BASE at module load time, so we mock the apiBase
 * module to deterministically control the resolved base in each case.
 */

const MOCK_BASE = "https://api-beta.adeptui.org";

vi.mock("../../../runtime/apiBase", () => ({
  apiUrl: (path: string): string =>
    MOCK_BASE && path.startsWith("/") ? MOCK_BASE + path : path,
}));

import {
  buildEntityNameMap,
  flattenTreeFolders,
  getApprovalBadge,
  getAssetAssociationLabel,
  getCardPreviewUrl,
  parseAssetLabels,
  resolveAssetUrl,
  resolveLinkedEntityName,
  type LibraryFolderNode,
} from "./assetModel";

describe("resolveAssetUrl", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("resolves a relative /api path against the configured API_BASE", () => {
    expect(resolveAssetUrl("/api/assets/abc/thumb")).toBe(
      MOCK_BASE + "/api/assets/abc/thumb",
    );
  });

  it("returns a relative path unchanged when API_BASE is empty", async () => {
    vi.doMock("../../../runtime/apiBase", () => ({
      apiUrl: (path: string): string => path,
    }));
    const mod = await import("./assetModel");
    expect(mod.resolveAssetUrl("/api/assets/abc/thumb")).toBe(
      "/api/assets/abc/thumb",
    );
  });

  it("returns absolute https URLs unchanged", () => {
    expect(resolveAssetUrl("https://example.com/img.png")).toBe(
      "https://example.com/img.png",
    );
  });

  it("returns absolute http URLs unchanged", () => {
    expect(resolveAssetUrl("http://example.com/img.png")).toBe(
      "http://example.com/img.png",
    );
  });

  it("returns protocol-relative URLs unchanged", () => {
    expect(resolveAssetUrl("//example.com/img.png")).toBe(
      "//example.com/img.png",
    );
  });

  it("returns data: URIs unchanged", () => {
    const uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==";
    expect(resolveAssetUrl(uri)).toBe(uri);
  });

  it("returns undefined for undefined input", () => {
    expect(resolveAssetUrl(undefined)).toBeUndefined();
  });

  it("treats empty string as no URL (returns undefined)", () => {
    expect(resolveAssetUrl("")).toBeUndefined();
  });
});

describe("getCardPreviewUrl", () => {
  it("resolves thumb_url through resolveAssetUrl", () => {
    expect(
      getCardPreviewUrl({ id: "abc", thumb_url: "/api/assets/abc/thumb" }),
    ).toBe(MOCK_BASE + "/api/assets/abc/thumb");
  });

  it("resolves preview_url through resolveAssetUrl when no thumb_url", () => {
    expect(
      getCardPreviewUrl({ id: "abc", preview_url: "/api/assets/abc/preview" }),
    ).toBe(MOCK_BASE + "/api/assets/abc/preview");
  });

  it("resolves previewUrl (camelCase) through resolveAssetUrl", () => {
    expect(
      getCardPreviewUrl({ id: "abc", previewUrl: "/api/assets/abc/preview" }),
    ).toBe(MOCK_BASE + "/api/assets/abc/preview");
  });

  it("prefers thumb_url over preview_url", () => {
    expect(
      getCardPreviewUrl({
        id: "abc",
        thumb_url: "/api/assets/abc/thumb",
        preview_url: "/api/assets/abc/preview",
      }),
    ).toBe(MOCK_BASE + "/api/assets/abc/thumb");
  });

  it("passes absolute thumb_url through unchanged", () => {
    expect(
      getCardPreviewUrl({ id: "abc", thumb_url: "https://cdn.example.com/x.png" }),
    ).toBe("https://cdn.example.com/x.png");
  });

  it("passes data: thumb_url through unchanged", () => {
    const uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==";
    expect(getCardPreviewUrl({ id: "abc", thumb_url: uri })).toBe(uri);
  });

  it("returns undefined when no thumb/preview and not an image", () => {
    expect(getCardPreviewUrl({ id: "abc", kind: "video" })).toBeUndefined();
  });
});

describe("parseAssetLabels", () => {
  it("parses a JSON-string label array", () => {
    expect(
      parseAssetLabels({ id: "a", labels_json: '["approved_prop","scene_shot"]' }),
    ).toEqual(["approved_prop", "scene_shot"]);
  });

  it("returns [] when labels_json is missing", () => {
    expect(parseAssetLabels({ id: "a" })).toEqual([]);
  });

  it("returns [] on malformed JSON", () => {
    expect(parseAssetLabels({ id: "a", labels_json: "not-json" })).toEqual([]);
  });

  it("returns [] when labels_json is not an array", () => {
    expect(parseAssetLabels({ id: "a", labels_json: '{"x":1}' })).toEqual([]);
  });

  it("coerces entries to strings and drops empties", () => {
    expect(parseAssetLabels({ id: "a", labels_json: '[42,"", "x"]' })).toEqual(["42", "x"]);
  });
});

describe("getApprovalBadge (CDX-017)", () => {
  it("returns Approved Prop when labels_json carries approved_prop", () => {
    expect(getApprovalBadge({ id: "a", labels_json: '["approved_prop"]' })).toEqual({
      label: "Approved Prop",
    });
  });

  it("returns Approved Take when labels_json carries approved_take", () => {
    expect(
      getApprovalBadge({ id: "a", labels_json: '["scene_shot","approved_take"]' }),
    ).toEqual({ label: "Approved Take" });
  });

  it("returns Approved for snake_case production_approval=approved", () => {
    expect(getApprovalBadge({ id: "a", production_approval: "approved" })).toEqual({
      label: "Approved",
    });
  });

  it("returns Approved for camelCase productionApproval=approved", () => {
    expect(getApprovalBadge({ id: "a", productionApproval: "approved" })).toEqual({
      label: "Approved",
    });
  });

  it("is case-insensitive on the approval value", () => {
    expect(getApprovalBadge({ id: "a", production_approval: "APPROVED" })).toEqual({
      label: "Approved",
    });
  });

  it("returns null when nothing is approved", () => {
    expect(getApprovalBadge({ id: "a" })).toBeNull();
    expect(getApprovalBadge({ id: "a", production_approval: "rejected" })).toBeNull();
    expect(getApprovalBadge({ id: "a", production_approval: "none" })).toBeNull();
    expect(getApprovalBadge({ id: "a", labels_json: '["scene_shot"]' })).toBeNull();
  });
});

describe("flattenTreeFolders / buildEntityNameMap", () => {
  const tree: LibraryFolderNode[] = [
    {
      folderId: "sys:characters",
      displayName: "Characters",
      systemKey: "characters",
      children: [
        {
          folderId: "f-char-1",
          displayName: "Anadriya",
          entityType: "character",
          entityId: "char-1",
          entityName: "Anadriya",
          children: [
            {
              folderId: "f-char-1-id",
              displayName: "Identity References",
              systemKey: "characters.identity_references",
              entityType: "character",
              entityId: "char-1",
              entityName: "Anadriya",
            },
          ],
        },
      ],
    },
    { folderId: "sys:video", displayName: "Video", systemKey: "video" },
  ];

  it("flattens a nested tree in pre-order", () => {
    const flat = flattenTreeFolders(tree);
    expect(flat.map((f) => f.folderId)).toEqual([
      "sys:characters",
      "f-char-1",
      "f-char-1-id",
      "sys:video",
    ]);
  });

  it("returns [] for empty/undefined trees", () => {
    expect(flattenTreeFolders(undefined)).toEqual([]);
    expect(flattenTreeFolders([])).toEqual([]);
  });

  it("maps entityId → entityName, including duplicated entity folders", () => {
    const map = buildEntityNameMap(tree);
    expect(map.get("char-1")).toBe("Anadriya");
    expect(map.size).toBe(1);
  });
});

describe("resolveLinkedEntityName (CDX-071)", () => {
  const tree: LibraryFolderNode[] = [
    {
      folderId: "sys:characters",
      displayName: "Characters",
      systemKey: "characters",
      children: [
        {
          folderId: "f-char-1",
          displayName: "Anadriya",
          entityType: "character",
          entityId: "char-1",
          entityName: "Anadriya",
        },
      ],
    },
    {
      folderId: "sys:props",
      displayName: "Props",
      systemKey: "props",
      children: [
        {
          folderId: "f-prop-1",
          displayName: "Sword of Dawn",
          entityType: "prop",
          entityId: "prop-1",
          entityName: "Sword of Dawn",
        },
      ],
    },
  ];

  it("resolves character name from the folder tree", () => {
    expect(
      resolveLinkedEntityName({ id: "a", characterId: "char-1" }, tree, "character"),
    ).toBe("Anadriya");
  });

  it("resolves prop name from the folder tree", () => {
    expect(resolveLinkedEntityName({ id: "a", propId: "prop-1" }, tree, "prop")).toBe(
      "Sword of Dawn",
    );
  });

  it("falls back to the libraryPath entity segment when the id is unknown", () => {
    expect(
      resolveLinkedEntityName(
        { id: "a", characterId: "unknown-char", libraryPath: "Characters/Aria/Identity References" },
        tree,
        "character",
      ),
    ).toBe("Aria");
  });

  it("returns null when the entity id is missing", () => {
    expect(resolveLinkedEntityName({ id: "a" }, tree, "character")).toBeNull();
    expect(resolveLinkedEntityName({ id: "a", characterId: null }, tree, "scene")).toBeNull();
  });

  it("returns null when nothing resolves (never a raw UUID)", () => {
    expect(
      resolveLinkedEntityName({ id: "a", characterId: "unknown-char" }, tree, "character"),
    ).toBeNull();
  });

  it("resolves scene type via sceneId", () => {
    const scenes: LibraryFolderNode[] = [
      {
        folderId: "f-scene-1",
        displayName: "Courtyard",
        entityType: "scene",
        entityId: "scene-1",
        entityName: "Courtyard",
      },
    ];
    expect(
      resolveLinkedEntityName({ id: "a", sceneId: "scene-1" }, scenes, "scene"),
    ).toBe("Courtyard");
  });
});

describe("getAssetAssociationLabel (CDX-071)", () => {
  const tree: LibraryFolderNode[] = [
    {
      folderId: "sys:characters",
      displayName: "Characters",
      systemKey: "characters",
      children: [
        {
          folderId: "f-char-1",
          displayName: "Anadriya",
          entityType: "character",
          entityId: "char-1",
          entityName: "Anadriya",
        },
      ],
    },
  ];

  it("shows resolved entity names when known", () => {
    expect(
      getAssetAssociationLabel({ id: "a", characterId: "char-1" }, tree),
    ).toBe("Character · Anadriya");
  });

  it("shows a bare entity kind when the id is present but unresolvable", () => {
    expect(
      getAssetAssociationLabel({ id: "a", characterId: "unknown-id" }, tree),
    ).toBe("Character");
  });

  it("joins multiple associations", () => {
    expect(
      getAssetAssociationLabel({ id: "a", characterId: "char-1", sceneId: "scene-9" }, tree),
    ).toBe("Character · Anadriya · Scene");
  });

  it("falls back to the last libraryPath segment when no entity ids exist", () => {
    expect(
      getAssetAssociationLabel({ id: "a", libraryPath: "Uploads/Storyboard-Images" }, tree),
    ).toBe("Storyboard Images");
  });

  it("returns an empty string for an asset with no associations", () => {
    expect(getAssetAssociationLabel({ id: "a" }, tree)).toBe("");
  });
});
