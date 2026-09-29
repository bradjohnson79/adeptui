import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({
  api: {
    updateScene: vi.fn(),
    directorTimelineRematerializeExecutionWindows: vi.fn(),
    directorTimelineNewSceneTake: vi.fn(),
    directorTimelineGenerateScene: vi.fn(),
  },
}));

import { api } from "../api";
import { persistCanonicalSceneDuration } from "./persistSceneDuration";

describe("persistCanonicalSceneDuration", () => {
  beforeEach(() => {
    vi.mocked(api.updateScene).mockReset();
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockReset();
    vi.mocked(api.directorTimelineGenerateScene).mockReset();
    vi.mocked(api.updateScene).mockResolvedValue({});
    vi.mocked(api.directorTimelineRematerializeExecutionWindows).mockResolvedValue({ ok: true });
  });

  it("writes Scene duration, syncs Timeline duration, rematerializes, and does not generate", async () => {
    const mutateTimeline = vi.fn(async (mutator: (current: { duration_sec: number }) => { duration_sec: number }) => {
      expect(mutator({ duration_sec: 15 }).duration_sec).toBe(30);
    });
    const result = await persistCanonicalSceneDuration({
      projectId: "p1",
      sceneId: "s1",
      durationSec: 30,
      generatorId: "minimax-h3",
      mutateTimeline: mutateTimeline as never,
    });
    expect(result.ok).toBe(true);
    expect(api.updateScene).toHaveBeenCalledWith("p1", "s1", { duration_sec: 30 });
    expect(mutateTimeline).toHaveBeenCalled();
    expect(api.directorTimelineRematerializeExecutionWindows).toHaveBeenCalledWith("p1", "s1", {
      generatorId: "minimax-h3",
      durationSeconds: 30,
    });
    expect(api.directorTimelineGenerateScene).not.toHaveBeenCalled();
  });
});
