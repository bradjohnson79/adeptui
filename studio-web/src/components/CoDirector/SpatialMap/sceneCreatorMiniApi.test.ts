import { describe, expect, it } from "vitest";
import {
  activeMiniCameras,
  miniOutputCount,
  miniResultSelectable,
  miniResultState,
  resolveReadyMiniGenerator,
  type MiniResult,
} from "./sceneCreatorMiniApi";
import type { SpatialMapDocument } from "./types";

describe("Scene Creator Mini output math", () => {
  it("is two images per active camera, capped at eight", () => {
    expect(miniOutputCount(0)).toBe(0);
    expect(miniOutputCount(1)).toBe(2);
    expect(miniOutputCount(2)).toBe(4);
    expect(miniOutputCount(3)).toBe(6);
    expect(miniOutputCount(4)).toBe(8);
    expect(miniOutputCount(12)).toBe(8);
  });

  it("ignores unplaced and hidden cameras", () => {
    const document = {
      cameras: [
        { id: "1", cameraSlot: 0, gridRow: 2, gridColumn: 2, visible: true, label: "C1" },
        { id: "2", cameraSlot: 1, gridRow: -1, gridColumn: -1, visible: true, label: "C2" },
        { id: "3", cameraSlot: 2, gridRow: 4, gridColumn: 4, visible: false, label: "C3" },
        { id: "4", cameraSlot: 3, gridRow: 7, gridColumn: 6, visible: true, label: "C4" },
      ],
    } as unknown as SpatialMapDocument;
    const active = activeMiniCameras(document);
    expect(active.map((c) => c.label)).toEqual(["C1", "C4"]);
    expect(miniOutputCount(active.length)).toBe(4);
  });

  it("does not keep a disabled generator selected", () => {
    expect(resolveReadyMiniGenerator("qwen2512", false, true)).toBe("gpt-image-2");
    expect(resolveReadyMiniGenerator("gpt-image-2", true, false)).toBe("qwen2512");
    expect(resolveReadyMiniGenerator("qwen2512", true, true)).toBe("qwen2512");
  });
});

describe("Mini candidate validation states", () => {
  function result(partial: Partial<MiniResult>): MiniResult {
    return { id: "r", cameraId: "c", cameraLabel: "C2", variation: "A", jobId: "j", status: "complete", ...partial };
  }

  it("maps job + validation states to product states", () => {
    expect(miniResultState(result({ status: "queued" }))).toBe("generating");
    expect(miniResultState(result({ status: "generating" }))).toBe("generating");
    expect(miniResultState(result({ status: "complete" }))).toBe("validating");
    expect(miniResultState(result({ status: "complete", validation: { state: "validating" } }))).toBe("validating");
    expect(miniResultState(result({ status: "complete", validation: { state: "pass" } }))).toBe("pass");
    expect(miniResultState(result({ status: "complete", validation: { state: "continuity_failed" } }))).toBe("continuity_failed");
    expect(miniResultState(result({ status: "failed" }))).toBe("generation_failed");
    expect(miniResultState(result({ status: "complete", validation: { state: "validation_unavailable" } }))).toBe("validation_unavailable");
  });

  it("only PASS-validated candidates are selectable", () => {
    const pass = result({ validation: { state: "pass" }, assetId: "a" });
    expect(miniResultSelectable(pass)).toBe(true);
    expect(miniResultSelectable(result({ status: "complete" }))).toBe(false);
    expect(miniResultSelectable(result({ status: "complete", validation: { state: "continuity_failed" }, assetId: "a" }))).toBe(false);
    expect(miniResultSelectable(result({ status: "failed" }))).toBe(false);
    expect(miniResultSelectable({ ...pass, inLibrary: true })).toBe(false);
    expect(miniResultSelectable(result({ status: "complete", validation: { state: "pass" } }))).toBe(false); // no asset
  });
});

