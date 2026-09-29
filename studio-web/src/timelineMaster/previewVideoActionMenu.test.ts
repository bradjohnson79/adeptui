import { describe, expect, it } from "vitest";
import { shouldShowPreviewVideoMenu } from "./previewVideoActionMenu";
import type { PreviewComposition } from "../components/timeline-master/TimelinePreviewComposer";

const videoFrame: PreviewComposition = {
  kind: "timeline_frame",
  visualSrc: "/media/clip.mp4",
  mediaKind: "video",
  promptText: "Korri walks",
  promptLabel: "Batch 1",
  batchId: "b1",
  batchLocalTime: 0,
  visualLocalTime: 0,
};

const imageFrame: PreviewComposition = { ...videoFrame, mediaKind: "image", visualSrc: "/media/still.png" };

describe("shouldShowPreviewVideoMenu", () => {
  it("shows when the Preview Monitor is displaying Timeline video", () => {
    expect(shouldShowPreviewVideoMenu({ sceneMode: "video_finishing", composition: videoFrame })).toBe(true);
    expect(shouldShowPreviewVideoMenu({ sceneMode: "image_planning", composition: videoFrame })).toBe(true);
    expect(
      shouldShowPreviewVideoMenu({
        sceneMode: "video_finishing",
        composition: { kind: "final_output", src: "/out.mp4", mediaKind: "video" },
      }),
    ).toBe(true);
  });

  it("shows when a generated take exists at the playhead even without video composition", () => {
    expect(
      shouldShowPreviewVideoMenu({
        sceneMode: "video_finishing",
        composition: { kind: "idle" },
        hasGeneratedTakeAtPlayhead: true,
      }),
    ).toBe(true);
  });

  it("stays available for stills, library, and idle", () => {
    expect(shouldShowPreviewVideoMenu({ sceneMode: "video_finishing", composition: imageFrame })).toBe(true);
    expect(
      shouldShowPreviewVideoMenu({
        sceneMode: "video_finishing",
        composition: { kind: "final_output", src: "/out.png", mediaKind: "image" },
      }),
    ).toBe(true);
    expect(
      shouldShowPreviewVideoMenu({
        sceneMode: "video_finishing",
        composition: {
          kind: "library",
          asset: { id: "a", kind: "video" } as never,
          src: "/lib.mp4",
          mediaKind: "video",
        },
      }),
    ).toBe(true);
    expect(shouldShowPreviewVideoMenu({ sceneMode: "video_finishing", composition: { kind: "idle" } })).toBe(true);
  });
});
