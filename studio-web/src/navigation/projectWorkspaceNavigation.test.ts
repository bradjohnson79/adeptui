import { describe, expect, it } from "vitest";
import {
  buildProjectWorkspaceLocation,
  openExpressStandardWorkspace,
  resolveHandoffSceneId,
} from "./projectWorkspaceNavigation";

const PROJECT = "beffd3d8-791d-4adf-9c4d-681ec9d4efb0";
const DIALOGUE = "ae8e5699-a5d8-4b9b-ad8e-0003d81d3639";

describe("project workspace handoff authority", () => {
  it("refuses to emit a location without a project id", () => {
    expect(buildProjectWorkspaceLocation({ projectId: "", tab: "timeline", sceneId: DIALOGUE })).toBeNull();
    expect(buildProjectWorkspaceLocation({ projectId: null, tab: "timeline" })).toBeNull();
  });

  it("preserves project + scene on Timeline Express → Standard", () => {
    expect(
      buildProjectWorkspaceLocation({
        projectId: PROJECT,
        tab: "timeline",
        sceneId: DIALOGUE,
      }),
    ).toEqual({
      pathname: `/project/${PROJECT}`,
      search: `?workspace=timeline&sceneId=${DIALOGUE}`,
    });
  });

  it("lets an explicit extra scene win over the bound scene", () => {
    expect(
      resolveHandoffSceneId({ sceneId: "walk" }, DIALOGUE),
    ).toBe("walk");
    expect(
      buildProjectWorkspaceLocation({
        projectId: PROJECT,
        tab: "timeline",
        sceneId: DIALOGUE,
        extra: { sceneId: "walk" },
      })?.search,
    ).toBe("?workspace=timeline&sceneId=walk");
  });

  it("sends retired Scene Creator Standard ids to the Image Generator with project and scene", () => {
    expect(
      buildProjectWorkspaceLocation({
        projectId: PROJECT,
        tab: "scenecreator",
        sceneId: DIALOGUE,
      }),
    ).toEqual({
      pathname: `/project/${PROJECT}`,
      search: `?workspace=imagegen&sceneId=${DIALOGUE}`,
    });
  });

  it("folds Text to Video, 1 Frame, and 3 Frame onto Timeline", () => {
    for (const tab of ["txt2vid", "one", "three", "text-to-video", "one-frame", "three-frame"]) {
      expect(
        buildProjectWorkspaceLocation({
          projectId: PROJECT,
          tab,
          sceneId: DIALOGUE,
        }),
      ).toEqual({
        pathname: `/project/${PROJECT}`,
        search: `?workspace=timeline&sceneId=${DIALOGUE}`,
      });
    }
  });

  it("forwards non-scene extras without dropping the project", () => {
    expect(
      buildProjectWorkspaceLocation({
        projectId: PROJECT,
        tab: "characters",
        sceneId: DIALOGUE,
        extra: { characterId: "korri" },
      }),
    ).toEqual({
      pathname: `/project/${PROJECT}`,
      search: `?workspace=characters&characterId=korri&sceneId=${DIALOGUE}`,
    });
  });

  it("keeps home as a bare project path", () => {
    expect(
      buildProjectWorkspaceLocation({
        projectId: PROJECT,
        tab: "home",
      }),
    ).toEqual({
      pathname: `/project/${PROJECT}`,
      search: "",
    });
  });

  it("passes scene identity through Express launchers", () => {
    const calls: Array<[string, Record<string, string> | undefined]> = [];
    openExpressStandardWorkspace((tab, extra) => calls.push([tab, extra]), "timeline", DIALOGUE);
    openExpressStandardWorkspace((tab, extra) => calls.push([tab, extra]), "scenecreator", DIALOGUE);
    expect(calls).toEqual([
      ["timeline", { sceneId: DIALOGUE }],
      ["scenecreator", { sceneId: DIALOGUE }],
    ]);
  });
});
