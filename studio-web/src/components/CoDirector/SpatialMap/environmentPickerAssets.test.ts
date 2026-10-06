import { describe, expect, it, vi } from "vitest";
import type { LibraryAsset } from "../library/assetModel";
import {
  ENVIRONMENT_PICKER_PAGE_SIZE,
  loadEnvironmentPickerImages,
  matchEnvironmentPickerQuery,
  rankEnvironmentPickerAssets,
} from "./environmentPickerAssets";

function image(partial: Partial<LibraryAsset> & { id: string }): LibraryAsset {
  return {
    kind: "image",
    ...partial,
  };
}

describe("environment picker assets", () => {
  it("ranks scene backgrounds above recent generated stills", () => {
    const generated = image({ id: "gen", filename: "continuity_last_frame.png", tag: "continuity_last_frame" });
    const corridor = image({
      id: "2b1f1901-af59-4368-b1ef-64175a8d1a23",
      filename: "Venture Corridor scene.png",
      tag: "Venture-Corridor-scene",
      libraryPath: "Project/Scenes/Backgrounds",
      classification: { target_folder: "scenes.backgrounds", subtype: "backgrounds" },
    });
    const ranked = rankEnvironmentPickerAssets([generated, corridor]);
    expect(ranked[0]?.id).toBe(corridor.id);
  });

  it("matches the Venture corridor by filename, tag, or library path", () => {
    const corridor = image({
      id: "corridor",
      filename: "Venture Corridor scene.png",
      tag: "Venture-Corridor-scene",
      libraryPath: "Project/Scenes/Backgrounds",
    });
    expect(matchEnvironmentPickerQuery(corridor, "Venture")).toBe(true);
    expect(matchEnvironmentPickerQuery(corridor, "backgrounds")).toBe(true);
    expect(matchEnvironmentPickerQuery(corridor, "gravel")).toBe(false);
  });

  it("pages past the newest mixed Library rows so older images remain reachable", async () => {
    const corridor = image({
      id: "corridor",
      filename: "Venture Corridor scene.png",
      tag: "Venture-Corridor-scene",
      classification: { target_folder: "scenes.backgrounds" },
    });
    const loader = vi.fn(async (_projectId: string, opts: { offset: number; limit: number }) => {
      if (opts.offset === 0) {
        return {
          items: Array.from({ length: opts.limit }, (_, i) => ({
            id: `audio-${i}`,
            kind: "audio",
            filename: `clone_${i}.wav`,
          })),
          totalMatches: opts.limit + 1,
        };
      }
      return { items: [corridor], totalMatches: opts.limit + 1 };
    });

    const images = await loadEnvironmentPickerImages(loader, "project-1");
    expect(loader).toHaveBeenCalledTimes(2);
    expect(loader.mock.calls[0]?.[1]).toMatchObject({
      limit: ENVIRONMENT_PICKER_PAGE_SIZE,
      offset: 0,
    });
    expect(images.map((row) => row.id)).toEqual(["corridor"]);
  });
});
