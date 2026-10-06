import { describe, expect, it } from "vitest";
import { flattenStudioApiDetail } from "./api";

describe("flattenStudioApiDetail", () => {
  it("unwraps MAGI published-master envelopes", () => {
    const flat = flattenStudioApiDetail({
      error: {
        code: "PUBLISHED_MASTER_REQUIRED",
        message: "This scene has no published master. Publish the scene on Timeline first.",
        fields: { sceneId: "scene-1" },
      },
    });
    expect(flat).toMatchObject({
      code: "PUBLISHED_MASTER_REQUIRED",
      message: "This scene has no published master. Publish the scene on Timeline first.",
    });
    expect((flat as { details?: { sceneId?: string } }).details?.sceneId).toBe("scene-1");
  });

  it("keeps flat Co-Director details", () => {
    const flat = flattenStudioApiDetail({
      code: "TOOL_NOT_FOUND",
      message: "Unknown tool.",
    });
    expect(flat).toMatchObject({ code: "TOOL_NOT_FOUND", message: "Unknown tool." });
  });
});
