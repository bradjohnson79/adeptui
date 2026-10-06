import { describe, expect, it } from "vitest";
import { overlayLiveTimeline, type TimelineBoardView } from "./DirectorTracks";

function view(partial: Partial<TimelineBoardView>): TimelineBoardView {
  return partial as TimelineBoardView;
}

describe("overlayLiveTimeline keeps Library tray membership", () => {
  it("keeps staged library ids when a master reload omits them", () => {
    const live = view({ promptSegments: [], library_asset_ids: undefined });
    const memory = view({ promptSegments: [], library_asset_ids: ["img-1"] });
    const merged = overlayLiveTimeline(live, memory);
    expect(merged.library_asset_ids).toEqual(["img-1"]);
  });

  it("keeps an explicit empty tray after the creator removes the last image", () => {
    const live = view({ promptSegments: [], library_asset_ids: ["img-1"] });
    const memory = view({ promptSegments: [], library_asset_ids: [] });
    const merged = overlayLiveTimeline(live, memory);
    expect(merged.library_asset_ids).toEqual([]);
  });
});
