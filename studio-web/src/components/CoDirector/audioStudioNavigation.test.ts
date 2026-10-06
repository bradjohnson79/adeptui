import { describe, expect, it } from "vitest";
import {
  audioStudioTabFromResult,
  audioStudioWorkspacePath,
  flattenToolHandoff,
  resolveAudioStudioNavigation,
  shouldOpenAudioStudio,
} from "./audioStudioNavigation";

const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";

describe("audioStudioNavigation", () => {
  it("opens from uiAction even when the tool id is a sibling opener", () => {
    expect(shouldOpenAudioStudio("voice_environment.open_audio_studio", { uiAction: "open_audio_studio" })).toBe(true);
    expect(shouldOpenAudioStudio("audio.open_studio", {})).toBe(true);
    expect(shouldOpenAudioStudio("timeline.focus_ui", {})).toBe(false);
  });

  it("prefers the tool workspaceUrl and does not invent a second store", () => {
    const url = resolveAudioStudioNavigation(PROJECT, "audio.open_studio", {
      uiAction: "open_audio_studio",
      audioTab: "ambience",
      workspaceUrl: `/project/${PROJECT}?workspace=audiostudio&audioTab=ambience`,
    });
    expect(url).toBe(`/project/${PROJECT}?workspace=audiostudio&audioTab=ambience`);
  });

  it("builds a Music path when the model omitted workspaceUrl", () => {
    expect(resolveAudioStudioNavigation(PROJECT, "audio.open_studio", { uiAction: "open_audio_studio" })).toBe(
      `/project/${PROJECT}?workspace=audiostudio&audioTab=music`,
    );
    expect(audioStudioTabFromResult({ audioTab: "sound effects" })).toBe("sfx");
    expect(audioStudioWorkspacePath(PROJECT, "library")).toContain("audioTab=library");
  });

  it("lifts nested read-tool data so Audio Studio still opens", () => {
    const enveloped = {
      status: "success",
      toolId: "audio.open_studio",
      data: {
        uiAction: "open_audio_studio",
        audioTab: "sfx",
        workspaceUrl: `/project/${PROJECT}?workspace=audiostudio&audioTab=sfx`,
        projectId: PROJECT,
      },
    };
    expect(flattenToolHandoff(enveloped).uiAction).toBe("open_audio_studio");
    expect(resolveAudioStudioNavigation(PROJECT, "audio.open_studio", enveloped)).toBe(
      `/project/${PROJECT}?workspace=audiostudio&audioTab=sfx`,
    );
  });
});
