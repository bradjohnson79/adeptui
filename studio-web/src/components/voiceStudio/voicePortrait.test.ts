import { describe, expect, it } from "vitest";
import { choosePortraitAssetId } from "./voicePortrait";

describe("choosePortraitAssetId", () => {
  it("prefers canonical approved hero_identity over a draft reference image", () => {
    const id = choosePortraitAssetId([
      { asset_id: "draft", reference_role: "reference_image", canonical: false, approval_status: "draft" },
      { asset_id: "hero", reference_role: "hero_identity", canonical: true, approval_status: "approved" },
    ]);
    expect(id).toBe("hero");
  });

  it("reads camelCase assetId when snake_case is missing", () => {
    expect(choosePortraitAssetId([{ assetId: "from-camel", reference_role: "hero_portrait" }])).toBe("from-camel");
  });

  it("falls back to a generic reference image", () => {
    expect(choosePortraitAssetId([{ asset_id: "ref", reference_role: "reference_image" }])).toBe("ref");
  });
});
