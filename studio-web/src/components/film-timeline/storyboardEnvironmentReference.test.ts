import { describe, expect, it } from "vitest";
import { groupReferenceOptions, type ReferenceOption } from "./referenceEntities";
import {
  resolveStoryboardEnvironment,
  storyboardEnvironmentSaves,
  type StoryboardWorkspaceLike,
} from "./storyboardEnvironmentReference";
import { publishableSceneAsset } from "../../filmTimeline/publishableSceneAsset";

const PROJECT = "project-a";
const FRAMES = [
  "a2a91531-bbc3-4861-afca-341bb642bcd6",
  "6a4c073c-5ff8-45b9-941c-4befd998e2da",
  "01a66d02-c541-466a-a909-bf7f4e38a6ef",
];

function workspace(overrides: Partial<StoryboardWorkspaceLike> = {}): StoryboardWorkspaceLike {
  return {
    document: {
      id: "board-1",
      projectId: PROJECT,
      title: "Storyboard",
      aspectRatio: "16:9",
      panelOrder: ["p1", "p2", "p3", "empty"],
    },
    panels: [
      { panelId: "p1", assetId: FRAMES[0] },
      { panelId: "p2", assetId: FRAMES[1] },
      { panelId: "p3", assetId: FRAMES[2] },
      { panelId: "empty", assetId: "" },
    ],
    ...overrides,
  };
}

describe("storyboard environment reference", () => {
  it("A — lists the current project's storyboard frames in order", () => {
    const resolved = resolveStoryboardEnvironment(PROJECT, workspace(), new Set(FRAMES));
    expect(resolved.ok).toBe(true);
    if (!resolved.ok) return;
    expect(resolved.candidate.documentId).toBe("board-1");
    expect(resolved.candidate.frames.map((frame) => frame.assetId)).toEqual(FRAMES);
  });

  it("B — refuses a storyboard from another project", () => {
    const foreign = workspace();
    foreign.document = { ...foreign.document!, projectId: "project-b" };
    expect(resolveStoryboardEnvironment(PROJECT, foreign, new Set(FRAMES))).toEqual({
      ok: false,
      reason: "OTHER_PROJECT",
      detail: "project-b",
    });
  });

  it("C — keeps the storyboard id with each ordered frame", () => {
    const resolved = resolveStoryboardEnvironment(PROJECT, workspace(), new Set(FRAMES));
    if (!resolved.ok) throw new Error(resolved.reason);
    const saves = storyboardEnvironmentSaves(resolved.candidate);
    expect(saves.map((row) => row.assetId)).toEqual(FRAMES);
    expect(saves.every((row) => row.type === "environment" && row.source === "storyboard:board-1")).toBe(true);
    expect(saves.map((row) => row.role)).toEqual(["frame:1", "frame:2", "frame:3"]);
  });

  it("D — selection is the authoritative environment reference payload", () => {
    const resolved = resolveStoryboardEnvironment(PROJECT, workspace(), new Set(FRAMES));
    if (!resolved.ok) throw new Error(resolved.reason);
    const [first] = storyboardEnvironmentSaves(resolved.candidate);
    expect(first.tag).toBe("Storyboard1");
    expect(first.label).toBe("Storyboard 1");
  });

  it("G — environment creator entities stay in their own group", () => {
    const sheet: ReferenceOption = {
      key: "environment:abode",
      assetId: "env-1",
      name: "Abode",
      defaultAlias: "Abode",
      group: "project",
      thumbAssetId: "env-1",
    };
    const board: ReferenceOption = {
      key: "storyboard:board-1",
      assetId: FRAMES[0],
      name: "Storyboard",
      defaultAlias: "Storyboard",
      group: "storyboard",
      thumbAssetId: FRAMES[0],
      storyboardId: "board-1",
      frames: FRAMES.map((assetId, index) => ({ assetId, panelId: `p${index}`, order: index + 1 })),
    };
    const groups = groupReferenceOptions([sheet, board], [], "environment");
    expect(groups.project.map((option) => option.name)).toEqual(["Abode"]);
    expect(groups.storyboard.map((option) => option.storyboardId)).toEqual(["board-1"]);
  });

  it("H — character options are not storyboard options", () => {
    const character: ReferenceOption = {
      key: "character:cade",
      assetId: "cade",
      name: "Cade",
      defaultAlias: "Cade",
      group: "project",
      thumbAssetId: "cade",
    };
    const groups = groupReferenceOptions([character], [], "character");
    expect(groups.storyboard).toEqual([]);
    expect(groups.project.map((option) => option.name)).toEqual(["Cade"]);
  });

  it("I — an empty storyboard does not invent a reference", () => {
    const empty = workspace({
      panels: [{ panelId: "empty", assetId: "" }],
      document: { id: "board-1", projectId: PROJECT, title: "Storyboard", panelOrder: ["empty"] },
    });
    expect(resolveStoryboardEnvironment(PROJECT, empty)).toEqual({ ok: false, reason: "EMPTY_STORYBOARD" });
    expect(resolveStoryboardEnvironment(PROJECT, { document: null, panels: [] })).toEqual({
      ok: false,
      reason: "NO_STORYBOARD",
    });
  });

  it("J — a missing library frame fails closed", () => {
    const resolved = resolveStoryboardEnvironment(PROJECT, workspace(), new Set([FRAMES[0], FRAMES[1]]));
    expect(resolved).toEqual({ ok: false, reason: "MISSING_FRAME", detail: FRAMES[2] });
  });
});

describe("publishable scene asset", () => {
  it("uses one completed clip as the finished scene", () => {
    expect(
      publishableSceneAsset({
        segments: [{ status: "completed", assetId: "video-1", trimInSec: 0, trimOutSec: null }],
        state: { stitchStatus: "stale", stitchAssetId: "" },
      }),
    ).toBe("video-1");
  });

  it("keeps a ready stitch ahead of a single clip", () => {
    expect(
      publishableSceneAsset({
        segments: [{ status: "completed", assetId: "video-1" }],
        state: { stitchStatus: "ready", stitchAssetId: "stitch-1" },
      }),
    ).toBe("stitch-1");
  });
});
