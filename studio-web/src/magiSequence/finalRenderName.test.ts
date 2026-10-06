import { describe, expect, it } from "vitest";
import {
  FINAL_VIDEO_NAME_CONFLICT,
  FINAL_VIDEO_NAME_EMPTY,
  finalVideoNameMessage,
  normalizeFinalVideoName,
  suggestedFinalVideoName,
} from "./finalRenderName";

describe("MAGI final video name", () => {
  it("keeps the readable title and adds one mp4 extension", () => {
    expect(normalizeFinalVideoName("  Renkoka Final Scene  ")).toEqual({
      title: "Renkoka Final Scene",
      filename: "Renkoka Final Scene.mp4",
    });
    expect(normalizeFinalVideoName("Renkoka Final Scene.mp4")).toEqual({
      title: "Renkoka Final Scene",
      filename: "Renkoka Final Scene.mp4",
    });
    expect(normalizeFinalVideoName("scene.mp4.mp4")?.filename).toBe("scene.mp4");
  });

  it("rejects an empty name and filesystem characters", () => {
    expect(finalVideoNameMessage("   ", [])).toBe(FINAL_VIDEO_NAME_EMPTY);
    expect(normalizeFinalVideoName("Renkoka/Final")).toBeNull();
    expect(finalVideoNameMessage("Renkoka/Final", [])).toMatch(/character/i);
  });

  it("uses the scene name as the suggested title", () => {
    expect(suggestedFinalVideoName("Scene 1", "Korri")).toBe("Scene 1 Final");
    expect(suggestedFinalVideoName("Scene 1 Final", "Korri")).toBe("Scene 1 Final");
    expect(suggestedFinalVideoName("", "Korri")).toBe("Korri Final");
  });

  it("blocks a library title or file that already uses the name", () => {
    const assets = [{ tag: "Renkoka Final Scene", filename: "magi_final_render_old.mp4" }];
    expect(finalVideoNameMessage("Renkoka Final Scene", assets)).toBe(FINAL_VIDEO_NAME_CONFLICT);
    expect(finalVideoNameMessage("Other Cut", [{ tag: "magi_final", filename: "Other Cut.mp4" }])).toBe(
      FINAL_VIDEO_NAME_CONFLICT,
    );
    expect(finalVideoNameMessage("Other Cut", [{ tag: "magi_final", filename: "magi_final_render_old.mp4" }])).toBeNull();
  });
});
