import type { VoicePerformanceCapabilities, VoicePerformanceTake } from "../../contracts/voicePerformanceM410";
import { describe, expect, it } from "vitest";
import {
  dropPendingVoicePerformanceTakes,
  formatVoicePerformanceTakeStatus,
  mergeVoicePerformanceTakes,
  nextVoicePerformanceTakeNumber,
  pendingVoicePerformanceTakes,
  sortVoicePerformanceTakes,
  voicePerformanceBatchProgress,
  voicePerformanceCanGenerateTakes,
  voicePerformanceRuntimeNotice,
  voicePerformanceTakePercent,
} from "./voicePerformanceGenerate";

function take(partial: Partial<VoicePerformanceTake> & Pick<VoicePerformanceTake, "id" | "takeNumber">): VoicePerformanceTake {
  return {
    recordId: "rec-1",
    label: `Take ${partial.takeNumber}`,
    status: "completed",
    directionSnapshot: {},
    createdAt: "2026-09-17T00:00:00Z",
    updatedAt: "2026-09-17T00:00:00Z",
    ...partial,
  };
}

describe("voicePerformanceCanGenerateTakes", () => {
  it("keeps Generate Takes clickable while capabilities are still loading", () => {
    expect(
      voicePerformanceCanGenerateTakes({
        hasApprovedVoiceIdentity: true,
        capabilities: null,
      }),
    ).toBe(true);
  });

  it("blocks Generate Takes only after the runtime reports not ready", () => {
    expect(
      voicePerformanceCanGenerateTakes({
        hasApprovedVoiceIdentity: true,
        capabilities: { ready: false },
      }),
    ).toBe(false);
  });

  it("requires an approved voice identity", () => {
    expect(
      voicePerformanceCanGenerateTakes({
        hasApprovedVoiceIdentity: false,
        capabilities: { ready: true },
      }),
    ).toBe(false);
  });
});

describe("voicePerformanceRuntimeNotice", () => {
  it("does not claim the runtime is unavailable before capabilities load", () => {
    expect(voicePerformanceRuntimeNotice(null).kind).toBe("checking");
  });
});

describe("voicePerformanceTakePercent", () => {
  it("shows 100 when a take is ready", () => {
    expect(voicePerformanceTakePercent({ status: "completed" })).toBe(100);
    expect(voicePerformanceTakePercent({ status: "approved" })).toBe(100);
  });

  it("uses take-level completed/total instead of fabricated elapsed climb", () => {
    expect(voicePerformanceTakePercent({ generating: true, completed: 0, total: 4 })).toBe(0);
    expect(voicePerformanceTakePercent({ generating: true, completed: 1, total: 4 })).toBe(25);
    expect(voicePerformanceTakePercent({ generating: true, completed: 2, total: 4 })).toBe(50);
    expect(voicePerformanceTakePercent({ generating: true, elapsedMs: 8000 } as any)).toBe(0);
  });
});

describe("formatVoicePerformanceTakeStatus", () => {
  it("maps queued/running/completed/failed to product labels", () => {
    expect(formatVoicePerformanceTakeStatus("queued")).toBe("Queued");
    expect(formatVoicePerformanceTakeStatus("running")).toBe("Generating");
    expect(formatVoicePerformanceTakeStatus("completed")).toBe("Ready");
    expect(formatVoicePerformanceTakeStatus("failed")).toBe("Failed");
  });
});

describe("pendingVoicePerformanceTakes", () => {
  it("creates visible running/queued take cards while the worker is rendering", () => {
    const pending = pendingVoicePerformanceTakes({
      recordId: "rec-1",
      count: 4,
      startNumber: 1,
      labelStartNumber: 1,
      createdAt: "2026-09-17T00:00:00Z",
    });
    expect(pending).toHaveLength(4);
    expect(pending.map((item) => item.label)).toEqual(["Take 1", "Take 2", "Take 3", "Take 4"]);
    expect(pending[0].status).toBe("running");
    expect(pending[1].status).toBe("queued");
    expect(dropPendingVoicePerformanceTakes([...pending, take({ id: "take-real", takeNumber: 1 })])).toEqual([
      take({ id: "take-real", takeNumber: 1 }),
    ]);
  });
});

describe("mergeVoicePerformanceTakes", () => {
  it("registers newly generated takes even when the current record snapshot is empty", () => {
    const generated = [take({ id: "take-new", takeNumber: 1, audioAssetId: "asset-1" })];
    expect(mergeVoicePerformanceTakes([], generated)).toEqual(generated);
  });

  it("keeps earlier takes when a later generate-takes response returns only the new batch", () => {
    const existing = [take({ id: "take-1", takeNumber: 1, audioAssetId: "asset-1" })];
    const generated = [take({ id: "take-2", takeNumber: 2, audioAssetId: "asset-2" })];
    expect(mergeVoicePerformanceTakes(existing, generated).map((item) => item.id)).toEqual([
      "take-1",
      "take-2",
    ]);
  });

  it("replaces pending slots by takeNumber without reshuffling on async completion", () => {
    const pending = pendingVoicePerformanceTakes({
      recordId: "rec-1",
      count: 2,
      startNumber: 1,
      createdAt: "2026-09-17T00:00:00Z",
    });
    const firstReady = take({ id: "real-1", takeNumber: 1, status: "completed", audioAssetId: "a1" });
    const merged = mergeVoicePerformanceTakes(pending, [firstReady]);
    expect(merged.map((item) => item.takeNumber)).toEqual([1, 2]);
    expect(merged[0].id).toBe("real-1");
    expect(merged[0].status).toBe("completed");
    expect(isPending(merged[1])).toBe(true);
  });

  it("sorts by canonical takeNumber not completion time", () => {
    const lateFirst = take({ id: "b", takeNumber: 2, createdAt: "2026-09-17T00:00:01Z" });
    const earlySecond = take({ id: "a", takeNumber: 1, createdAt: "2026-09-17T00:00:09Z" });
    expect(sortVoicePerformanceTakes([lateFirst, earlySecond]).map((item) => item.id)).toEqual(["a", "b"]);
  });
});

describe("voicePerformanceBatchProgress", () => {
  it("reports take-level percent for a generating batch", () => {
    const takes = [
      take({ id: "1", takeNumber: 1, status: "completed" }),
      take({ id: "2", takeNumber: 2, status: "running" }),
      take({ id: "3", takeNumber: 3, status: "queued" }),
      take({ id: "4", takeNumber: 4, status: "queued" }),
    ];
    const progress = voicePerformanceBatchProgress({
      takes,
      expectedTotal: 4,
      batchStartNumber: 1,
      generating: true,
    });
    expect(progress.percent).toBe(25);
    expect(progress.label).toContain("Generating Take 2 of 4");
    expect(progress.source).toBe("take_level");
  });

  it("prefers honest server take-level progress when present", () => {
    const progress = voicePerformanceBatchProgress({
      takes: [],
      generating: true,
      serverProgress: {
        source: "take_level",
        completed: 2,
        total: 4,
        percent: 50,
        active: true,
        label: "Generating Take 3 of 4…",
      },
    });
    expect(progress.percent).toBe(50);
    expect(progress.label).toContain("3 of 4");
  });
});

describe("nextVoicePerformanceTakeNumber", () => {
  it("continues from the highest real take number", () => {
    expect(nextVoicePerformanceTakeNumber([take({ id: "1", takeNumber: 3 })])).toBe(4);
  });
});

function isPending(item: VoicePerformanceTake) {
  return String(item.id).startsWith("pending-take-");
}
