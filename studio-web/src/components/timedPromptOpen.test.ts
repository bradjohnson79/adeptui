import { afterEach, describe, expect, it, vi } from "vitest";
import {
  openTimedPromptAfterGesture,
  shouldIgnoreTimedPromptDismiss,
  timedPromptDismissGuardUntil,
} from "./timedPromptOpen";

describe("openTimedPromptAfterGesture", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not open during the double-click turn", () => {
    vi.useFakeTimers();
    const open = vi.fn();
    openTimedPromptAfterGesture(open, "prompt-1");
    expect(open).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(open).toHaveBeenCalledOnce();
    expect(open).toHaveBeenCalledWith("prompt-1");
  });

  it("ignores a blank id", () => {
    vi.useFakeTimers();
    const open = vi.fn();
    openTimedPromptAfterGesture(open, "  ");
    vi.runAllTimers();
    expect(open).not.toHaveBeenCalled();
  });

  it("ignores the opening click, then allows a later dismiss", () => {
    const now = 1_000;
    const until = timedPromptDismissGuardUntil(now);
    expect(shouldIgnoreTimedPromptDismiss(now + 10, until)).toBe(true);
    expect(shouldIgnoreTimedPromptDismiss(until, until)).toBe(false);
  });
});
