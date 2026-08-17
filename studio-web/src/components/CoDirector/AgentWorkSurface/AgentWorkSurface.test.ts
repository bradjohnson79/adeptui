import { describe, expect, it, vi } from "vitest";

// The component itself needs a DOM render harness, which this repo does not
// ship (no jsdom/RTL — see sibling test comments). These node-env tests cover
// the extractable pure honesty logic the component actually uses.
vi.mock("../../../api", () => ({
  api: {
    advanceExecution: vi.fn(),
    regenerateFrame: vi.fn(),
    cancelExecution: vi.fn(),
  },
}));
vi.mock("../CoDirectorSession", () => ({
  useCoDirectorSession: () => ({ uiContext: {}, activeExecution: null, setActiveExecution: vi.fn() }),
}));
vi.mock("../SceneCreator/persistThenOpenSceneCreator", () => ({
  persistThenOpenSceneCreator: vi.fn(),
}));

import { REGENERATE_FAILED_MESSAGE, pollPausedFor } from "./AgentWorkSurface";
import { NORMAL_WORK_SURFACE, isAgentWork } from "./types";
import type { WorkSurfaceState } from "./types";

const livePack: WorkSurfaceState = {
  mode: "agent_work",
  execution_id: "e1",
  capability: "ers.generate",
  surface_type: "ers_generation",
  status: "running",
  progress: 0.5,
  focused_artifact_ids: [],
  child_jobs: [],
  result_asset_ids: [],
  collection_id: null,
  error: null,
  project_id: "p1",
};

const terminalPack: WorkSurfaceState = { ...livePack, status: "completed" };

describe("FE-007 poll-expiration honesty", () => {
  it("does not pause while the poll budget has headroom", () => {
    expect(pollPausedFor(livePack, 79)).toBe(false);
  });

  it("pauses exactly when the budget is spent while work may still run", () => {
    expect(pollPausedFor(livePack, 80)).toBe(true);
  });

  it("never reports paused for a terminal execution (job is done/failed, not paused)", () => {
    expect(pollPausedFor(terminalPack, 80)).toBe(false);
    expect(pollPausedFor(null, 80)).toBe(false);
  });

  it("respects an explicit budget", () => {
    expect(pollPausedFor(livePack, 4, 5)).toBe(false);
    expect(pollPausedFor(livePack, 5, 5)).toBe(true);
  });
});

describe("FE-007 regenerate failure copy", () => {
  it("is honest: says regeneration failed and the existing look was not changed", () => {
    const msg = REGENERATE_FAILED_MESSAGE.toLowerCase();
    expect(msg).toContain("regeneration failed");
    expect(msg).toContain("not changed");
    expect(msg).not.toContain("completed");
    expect(msg).not.toContain("regenerated");
  });
});

describe("CDX-092 focused_artifact_ids contract truth", () => {
  it("does not require the fabricated focused_artifact_ids field (backend has no such concept)", () => {
    // A valid agent-work surface state must be expressible WITHOUT
    // focused_artifact_ids — the backend ExecutionPlan never emits it.
    const state: WorkSurfaceState = {
      mode: "agent_work",
      execution_id: "e2",
      capability: "script.propose_edit",
      surface_type: "script_operation",
      status: "completed",
      progress: 1,
      child_jobs: [],
      result_asset_ids: ["asset-1"],
    };
    expect(state.focused_artifact_ids).toBeUndefined();
    expect(state.result_asset_ids).toEqual(["asset-1"]);
    expect(isAgentWork(state)).toBe(true);
  });

  it("empty state no longer claims focused artifacts", () => {
    expect(NORMAL_WORK_SURFACE.focused_artifact_ids).toBeUndefined();
    expect(NORMAL_WORK_SURFACE.result_asset_ids).toEqual([]);
  });
});
