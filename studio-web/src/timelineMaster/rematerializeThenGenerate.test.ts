import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  api: {
    directorTimelineRematerializeExecutionWindows: vi.fn(),
    directorTimelineNewSceneTake: vi.fn(),
    directorTimelineBeginExecutionRevision: vi.fn(),
    directorTimelineGenerateScene: vi.fn(),
  },
}));

import { api } from "../api";
import { rematerializeSceneExecutionWindows, rematerializeThenGenerateScene } from "./rematerializeThenGenerate";

describe("rematerializeThenGenerateScene", () => {
  beforeEach(() => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockReset();
    vi.mocked(api.directorTimelineNewSceneTake).mockReset();
    vi.mocked(api.directorTimelineBeginExecutionRevision).mockReset();
    vi.mocked(api.directorTimelineGenerateScene).mockReset();
  });

  it("rematerializes then generates without batchCount", async () => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockResolvedValue({ ok: true });
    vi.mocked(api.directorTimelineGenerateScene).mockResolvedValue({ ok: true, queued: 2 });
    const result = await rematerializeThenGenerateScene({
      projectId: "p1",
      sceneId: "s1",
      generatorId: "minimax-h3",
      durationSeconds: 12,
    });
    expect(api.directorTimelineRematerializeExecutionWindows).toHaveBeenCalledWith("p1", "s1", {
      generatorId: "minimax-h3",
      durationSeconds: 12,
    });
    expect(api.directorTimelineGenerateScene).toHaveBeenCalledWith("p1", "s1", {
      scope: "full",
      draftMode: undefined,
    });
    expect(result.ok).toBe(true);
    expect(api.directorTimelineNewSceneTake).not.toHaveBeenCalled();
    expect(api.directorTimelineBeginExecutionRevision).not.toHaveBeenCalled();
  });

  it("shows the saved windows before generate is submitted", async () => {
    const order: string[] = [];
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockImplementation(async () => {
      order.push("rematerialize");
      return { ok: true, master: { batchBlocks: [] } };
    });
    vi.mocked(api.directorTimelineGenerateScene).mockImplementation(async () => {
      order.push("generate");
      return { ok: true };
    });
    await rematerializeThenGenerateScene({
      projectId: "p1",
      sceneId: "s1",
      beforeGenerate: async () => {
        order.push("show");
      },
    });
    expect(order).toEqual(["rematerialize", "show", "generate"]);
  });

  it("mints SceneTake when rematerialize requires it, then retries", async () => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows)
      .mockResolvedValueOnce({
        ok: false,
        error: "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE",
        requiresNewSceneTake: true,
        currentSceneTakeId: "stk_old",
      })
      .mockResolvedValueOnce({ ok: true });
    vi.mocked(api.directorTimelineBeginExecutionRevision).mockResolvedValue({
      ok: true,
      currentSceneTakeId: "stk_new",
    });
    vi.mocked(api.directorTimelineGenerateScene).mockResolvedValue({ ok: true });
    await rematerializeThenGenerateScene({
      projectId: "p1",
      sceneId: "s1",
      generatorId: "ltx-2.5",
      durationSeconds: 20,
    });
    expect(api.directorTimelineBeginExecutionRevision).toHaveBeenCalledWith("p1", "s1", {
      reason: "generator_switch_window_topology_change",
    });
    expect(api.directorTimelineNewSceneTake).not.toHaveBeenCalled();
    expect(api.directorTimelineRematerializeExecutionWindows).toHaveBeenNthCalledWith(2, "p1", "s1", {
      generatorId: "ltx-2.5",
      durationSeconds: 20,
      allowSceneTakeId: "stk_new",
      previousSceneTakeId: "stk_old",
    });
  });

  it("resolves mint id from nested take.id", async () => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows)
      .mockResolvedValueOnce({
        ok: false,
        error: "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE",
        requiresNewSceneTake: true,
      })
      .mockResolvedValueOnce({ ok: true });
    vi.mocked(api.directorTimelineBeginExecutionRevision).mockResolvedValue({
      ok: true,
      take: { id: "stk_nested" },
    });
    const remat = await rematerializeSceneExecutionWindows({
      projectId: "p1",
      sceneId: "s1",
    });
    expect(remat.ok).toBe(true);
    expect(api.directorTimelineRematerializeExecutionWindows).toHaveBeenNthCalledWith(2, "p1", "s1", {
      generatorId: undefined,
      durationSeconds: undefined,
      allowSceneTakeId: "stk_nested",
      previousSceneTakeId: undefined,
    });
  });

  it("returns SCENE_TAKE_MINT_FAILED when mint has no id", async () => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockResolvedValueOnce({
      ok: false,
      error: "GENERATOR_SWITCH_REQUIRES_NEW_SCENE_TAKE",
      requiresNewSceneTake: true,
    });
    vi.mocked(api.directorTimelineBeginExecutionRevision).mockResolvedValue({ ok: true });
    const remat = await rematerializeSceneExecutionWindows({
      projectId: "p1",
      sceneId: "s1",
    });
    expect(remat.ok).toBe(false);
    expect(remat.error).toBe("SCENE_TAKE_MINT_FAILED");
  });

  it("rematerialize-only does not queue generate", async () => {
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockResolvedValue({ ok: true });
    const result = await rematerializeSceneExecutionWindows({
      projectId: "p1",
      sceneId: "s1",
      generatorId: "minimax-h3",
      durationSeconds: 30,
    });
    expect(result.ok).toBe(true);
    expect(api.directorTimelineRematerializeExecutionWindows).toHaveBeenCalledWith("p1", "s1", {
      generatorId: "minimax-h3",
      durationSeconds: 30,
    });
    expect(api.directorTimelineGenerateScene).not.toHaveBeenCalled();
  });
});
