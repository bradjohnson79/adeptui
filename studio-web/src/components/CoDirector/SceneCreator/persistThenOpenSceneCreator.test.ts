import { describe, expect, it, vi } from "vitest";

vi.mock("../../../api", () => ({
  api: {
    sceneCreator: {
      productionHandoff: vi.fn(),
    },
  },
}));

import { api } from "../../../api";
import { persistThenOpenSceneCreator } from "./persistThenOpenSceneCreator";

describe("persistThenOpenSceneCreator", () => {
  it("navigates only after a successful persist, using server IDs", async () => {
    const order: string[] = [];
    vi.mocked(api.sceneCreator.productionHandoff).mockImplementation(async () => {
      order.push("persist");
      return {
        sceneId: "scene-server",
        sheetId: "sheet-server",
        handoffId: "handoff-1",
        revision: 1,
        selectedProfileId: "handoff-1",
        ersPackageId: "pkg-1",
        ersLibraryAssetId: "ers-lib",
        spatialMapId: "map-1",
      };
    });
    const onGoTab = vi.fn((tab: string) => {
      order.push(`nav:${tab}`);
    });
    await persistThenOpenSceneCreator({
      projectId: "proj-1",
      sceneId: "guess",
      onGoTab,
    });
    expect(order).toEqual(["persist", "nav:scenecreator"]);
    expect(onGoTab).toHaveBeenCalledWith("scenecreator", {
      scene_id: "scene-server",
      sheet_id: "sheet-server",
      spatialProfileId: "handoff-1",
      handoffId: "handoff-1",
    });
  });

  it("does not navigate when persist fails", async () => {
    vi.mocked(api.sceneCreator.productionHandoff).mockRejectedValue(new Error("persist failed"));
    const onGoTab = vi.fn();
    await expect(
      persistThenOpenSceneCreator({ projectId: "proj-1", onGoTab }),
    ).rejects.toThrow("persist failed");
    expect(onGoTab).not.toHaveBeenCalled();
  });
});
