import { describe, expect, it } from "vitest";
import {
  collectPromptBindingIds,
  resolveTimelineReference,
} from "./loadTimelineReferenceCatalog";

describe("loadTimelineReferenceCatalog helpers", () => {
  it("collects binding ids from prompt segments without using display names", () => {
    expect(
      collectPromptBindingIds([
        {
          reference_binding_ids: ["bind-a", ""],
          reference_name_bindings: [{ binding_id: "bind-b" }, { binding_id: "bind-a" }],
        },
      ]).sort(),
    ).toEqual(["bind-a", "bind-b"]);
  });

  it("resolves by binding id only", () => {
    const catalog = [
      { id: "bind-a", asset_id: "asset-a", reference_type: "prop", alias: "VentureSpaceship" },
      { id: "bind-b", asset_id: "asset-b", reference_type: "prop", alias: "CadeSStarfighter" },
    ];
    expect(resolveTimelineReference("bind-a", catalog)?.asset_id).toBe("asset-a");
    expect(resolveTimelineReference("VentureSpaceship", catalog)).toBeUndefined();
    expect(resolveTimelineReference("", catalog)).toBeUndefined();
  });
});
