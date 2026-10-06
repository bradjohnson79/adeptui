import { describe, expect, it } from "vitest";

describe("Prop Creator delete confirmation wiring", () => {
  it("exposes a delete-preview endpoint on the prop creator API", async () => {
    const fs = await import("node:fs");
    const api = fs.readFileSync(new URL("../../../api.ts", import.meta.url), "utf8");
    expect(api).toContain("deletePreview: (projectId: string, propId: string) =>");
    expect(api).toContain("/props/${encodeURIComponent(propId)}/delete-preview");
  });

  it("puts a Delete button in the Saved Prop block", async () => {
    const fs = await import("node:fs");
    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    const savedPropBlock = core.slice(core.indexOf("function SavedPropBlock"), core.indexOf("function NameStyleBlock"));
    expect(savedPropBlock).toContain('data-testid="prop-creator-delete"');
    expect(savedPropBlock).toContain("() => onDelete?.()");
  });

  it("wires the modal through the core and renders it for both standard and advanced tabs", async () => {
    const fs = await import("node:fs");
    const core = fs.readFileSync(new URL("./PropCreatorCore.tsx", import.meta.url), "utf8");
    expect(core).toContain("CreatorProfileDeleteModal");
    expect(core).toContain('entityType="prop"');
    expect(core).toContain("const [deletePreview, setDeletePreview]");
    expect(core).toContain("const [deleteModalOpen, setDeleteModalOpen]");
  });

  it("usePropCreator.remove no longer uses window.confirm", async () => {
    const fs = await import("node:fs");
    const hook = fs.readFileSync(new URL("./usePropCreator.ts", import.meta.url), "utf8");
    expect(hook).not.toMatch(/window\.confirm/);
  });

  it("usePropCreator.remove accepts confirmCrossProject and passes it to the API", async () => {
    const fs = await import("node:fs");
    const hook = fs.readFileSync(new URL("./usePropCreator.ts", import.meta.url), "utf8");
    expect(hook).toMatch(/remove = useCallback\(async \(opts\?: \{ confirmCrossProject\?: boolean \}\): Promise<boolean>/);
    expect(hook).toContain("propCreatorApi.delete(projectId, prop.id, opts?.confirmCrossProject ?? false)");
  });

  it("propCreatorApi.delete accepts confirmCrossProject and deletePreview is wired", async () => {
    const fs = await import("node:fs");
    const apiLayer = fs.readFileSync(new URL("./propCreatorApi.ts", import.meta.url), "utf8");
    expect(apiLayer).toContain("delete: (projectId: string, propId: string, confirmCrossProject?: boolean)");
    expect(apiLayer).toContain("deletePreview: (projectId: string, propId: string)");
  });
});
