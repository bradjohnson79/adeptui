import { describe, expect, it } from "vitest";
import { libraryFolderVisible, sidebarFoldersForType, type LibraryFolderNode } from "./libraryNav";

const TREE: LibraryFolderNode[] = [
  {
    systemKey: "video",
    displayName: "Video",
    children: [
      { systemKey: "video.generated", displayName: "Generated" },
      { systemKey: "video.renders", displayName: "Renders" },
    ],
  },
  {
    systemKey: "audio",
    displayName: "Audio",
    children: [
      { systemKey: "audio.music", displayName: "Music" },
      { systemKey: "audio.music_track", displayName: "Music Track" },
      { systemKey: "audio.sfx", displayName: "SFX" },
      { systemKey: "audio.foley", displayName: "Foley" },
    ],
  },
  {
    systemKey: "three_d",
    displayName: "3D (Coming in Version 1.2)",
    children: [{ systemKey: "three_d.characters", displayName: "Characters" }],
  },
  {
    systemKey: "templates_presets",
    displayName: "Templates and Presets",
    children: [{ systemKey: "templates_presets.look_presets", displayName: "Look Presets" }],
  },
  { systemKey: "storyboards", displayName: "Storyboards" },
];

describe("library folder visibility", () => {
  it("hides preset shelves and deferred 3D destinations", () => {
    expect(libraryFolderVisible("templates_presets", "Templates and Presets")).toBe(false);
    expect(libraryFolderVisible("templates_presets.camera_presets", "Camera Presets")).toBe(false);
    expect(libraryFolderVisible("three_d", "3D (Coming in Version 1.2)")).toBe(false);
    expect(libraryFolderVisible("characters.three_d", "3D (Coming in Version 1.2)")).toBe(false);
  });

  it("hides audio labels that have no placement owner", () => {
    expect(libraryFolderVisible("audio.music_track", "Music Track")).toBe(false);
    expect(libraryFolderVisible("audio.music", "Music")).toBe(true);
    expect(libraryFolderVisible("audio.foley", "Foley")).toBe(true);
  });

  it("shows only the video group when the Video type is selected", () => {
    const shown = sidebarFoldersForType(TREE, "video");
    expect(shown.map((folder) => folder.displayName)).toEqual(["Video"]);
    expect(shown[0].children?.map((child) => child.displayName)).toEqual(["Generated", "Renders"]);
  });
});
