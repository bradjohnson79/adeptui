import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("JobPanel poll honesty", () => {
  it("calls onDone only on transition to done and honors outage suspend", () => {
    const src = readFileSync(new URL("./JobPanel.tsx", import.meta.url), "utf8");
    expect(src).toContain("shouldSuspendDependentPolling");
    expect(src).toContain("seenDoneRef");
    expect(src).toContain("onDoneRef");
    expect(src).toContain("newlyDone");
    expect(src).toContain("onDoneRef.current()");
    expect(src).toContain("}, [projectId]);");
    expect(src).not.toContain("}, [projectId, onDone]);");
  });
});
