import { describe, expect, it, vi, afterEach } from "vitest";
import { MagiEditorCommandStack } from "./MagiEditorCommandStack";

type Snapshot = { value: number };

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MagiEditorCommandStack (m1 A6)", () => {
  it("push + undo restores the before state", () => {
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("move", "Move clip", { value: 0 }, { value: 1 });
    const undone = stack.undo({ value: 1 });
    expect(undone).toEqual({ value: 0 });
    expect(stack.canUndo()).toBe(false);
    expect(stack.canRedo()).toBe(true);
  });

  it("undo + redo round-trips state", () => {
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("move", "Move clip", { value: 0 }, { value: 1 });
    stack.undo({ value: 1 });
    const redone = stack.redo({ value: 0 });
    expect(redone).toEqual({ value: 1 });
  });

  it("a fresh push clears the redo branch", () => {
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("move", "Move", { value: 0 }, { value: 1 });
    stack.undo({ value: 1 });
    expect(stack.canRedo()).toBe(true);
    stack.push("trim", "Trim", { value: 0 }, { value: 2 });
    expect(stack.canRedo()).toBe(false);
  });

  it("caps the undo stack at 100 entries (oldest dropped)", () => {
    const stack = new MagiEditorCommandStack<Snapshot>();
    for (let i = 0; i < 120; i += 1) {
      stack.push("edit", `Edit ${i}`, { value: i }, { value: i + 1 });
    }
    let current: Snapshot = { value: 120 };
    let steps = 0;
    while (stack.canUndo() && steps < 200) {
      const prev = stack.undo(current);
      if (!prev) break;
      current = prev;
      steps += 1;
    }
    expect(steps).toBe(100);
    expect(current).toEqual({ value: 20 });
  });

  it("coalesces overlay.text.update within 800ms window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1000);
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("overlay.text.update", "Update overlay", { value: 0 }, { value: 1 });
    vi.setSystemTime(1300); // 300ms later — inside the window.
    stack.push("overlay.text.update", "Update overlay", { value: 1 }, { value: 2 });
    expect(stack.canUndo()).toBe(true);
    const undone = stack.undo({ value: 2 });
    expect(undone).toEqual({ value: 0 });
    expect(stack.canUndo()).toBe(false);
  });

  it("does NOT coalesce overlay.text.update outside the 800ms window", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1000);
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("overlay.text.update", "Update overlay", { value: 0 }, { value: 1 });
    vi.setSystemTime(3000); // 2000ms later — outside the window.
    stack.push("overlay.text.update", "Update overlay", { value: 1 }, { value: 2 });
    const undone = stack.undo({ value: 2 });
    expect(undone).toEqual({ value: 1 });
    expect(stack.canUndo()).toBe(true);
  });

  it("does not coalesce non-text commands", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1000);
    const stack = new MagiEditorCommandStack<Snapshot>();
    stack.push("overlay.style.update", "Update overlay", { value: 0 }, { value: 1 });
    vi.setSystemTime(1300);
    stack.push("overlay.style.update", "Update overlay", { value: 1 }, { value: 2 });
    const undone = stack.undo({ value: 2 });
    expect(undone).toEqual({ value: 1 });
    expect(stack.canUndo()).toBe(true);
  });
});
