import { describe, expect, it } from "vitest";
import {
  EMPTY_RUNTIME_MONITOR,
  isPreviewEvent,
  isTerminalEvent,
  reduceRuntimeEvent,
  type GeneratorRuntimeEvent,
} from "./events";

function event(partial: Partial<GeneratorRuntimeEvent>): GeneratorRuntimeEvent {
  return {
    executionId: "ex-1",
    jobId: "job-1",
    provider: "local-comfy",
    modelId: "minimax-h3",
    eventType: "PROGRESS",
    createdAt: "2026-09-07T00:00:00Z",
    ...partial,
  };
}

describe("generator runtime events", () => {
  it("reduces preview frames and ignores a different job", () => {
    const first = reduceRuntimeEvent(
      EMPTY_RUNTIME_MONITOR,
      event({
        eventType: "PREVIEW_FRAME",
        preview: {
          url: "/media/a.jpg",
          mimeType: "image/jpeg",
          timestamp: "2026-09-07T00:00:00Z",
          sequence: 1,
          draft: true,
        },
      }),
    );
    expect(isPreviewEvent(event({ eventType: "PREVIEW_FRAME" }))).toBe(true);
    expect(first.previewSequence).toBe(1);
    const other = reduceRuntimeEvent(
      first,
      event({
        jobId: "job-2",
        eventType: "PREVIEW_FRAME",
        preview: {
          url: "/media/b.jpg",
          mimeType: "image/jpeg",
          timestamp: "2026-09-07T00:00:01Z",
          sequence: 1,
          draft: true,
        },
      }),
    );
    expect(other.previewUrl).toBe("/media/a.jpg");
  });

  it("keeps cancel-rejected non-terminal so the job can continue", () => {
    expect(isTerminalEvent(event({ eventType: "CANCEL_REJECTED" }))).toBe(false);
    expect(isTerminalEvent(event({ eventType: "CANCELLED" }))).toBe(true);
  });
});
