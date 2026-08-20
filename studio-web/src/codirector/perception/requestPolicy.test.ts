import { describe, expect, it } from "vitest";
import {
  creatorPerceptionMessage,
  PERCEPTION_REQUEST_MS,
  SCENE_REVIEW_START_FAILED,
  SMART_SELECT_PAINT,
} from "./requestPolicy";

describe("perception request policy", () => {
  it("uses one shared timeout", () => {
    expect(PERCEPTION_REQUEST_MS).toBe(45_000);
  });

  it("hides raw runtime text", () => {
    expect(creatorPerceptionMessage(new Error("RuntimeError: boom"), SCENE_REVIEW_START_FAILED)).toBe(
      SCENE_REVIEW_START_FAILED,
    );
    expect(creatorPerceptionMessage(new DOMException("Aborted", "AbortError"), SCENE_REVIEW_START_FAILED)).toBe(
      SCENE_REVIEW_START_FAILED,
    );
    expect(creatorPerceptionMessage(new Error("Studio API is currently unavailable."), SCENE_REVIEW_START_FAILED)).toBe(
      "Studio API is currently unavailable.",
    );
    expect(creatorPerceptionMessage(new Error("subprocess failed"), SMART_SELECT_PAINT)).toBe(SMART_SELECT_PAINT);
  });
});
