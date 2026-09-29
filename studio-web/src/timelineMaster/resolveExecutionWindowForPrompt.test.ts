import { describe, expect, it } from "vitest";
import { resolveExecutionWindowForPrompt } from "./resolveExecutionWindowForPrompt";
import type { BatchBlock } from "./contracts";

function batch(id: string, order: number, planned: number): BatchBlock {
  return {
    id,
    order,
    label: id,
    status: "Ready",
    duration: { plannedDuration: planned },
    promptSegments: [],
    candidateVersions: [],
    references: [],
  } as unknown as BatchBlock;
}

describe("resolveExecutionWindowForPrompt", () => {
  const windows = [batch("w1", 0, 15), batch("w2", 1, 15)];

  it("binds 0-18 prompt to first window by start-containment", () => {
    expect(resolveExecutionWindowForPrompt(windows, { start: 0, length: 18 })?.id).toBe("w1");
  });

  it("binds 16-30 prompt to second window", () => {
    expect(resolveExecutionWindowForPrompt(windows, { start: 16, length: 14 })?.id).toBe("w2");
  });

  it("binds a 0-45 scene prompt to window 1, never midpoint window 2", () => {
    const three = [batch("w1", 0, 15), batch("w2", 1, 15), batch("w3", 2, 15)];
    expect(resolveExecutionWindowForPrompt(three, { start: 0, length: 45 })?.id).toBe("w1");
  });

  it("returns null when no batches", () => {
    expect(resolveExecutionWindowForPrompt([], { start: 0, length: 2 })).toBeNull();
  });
});
