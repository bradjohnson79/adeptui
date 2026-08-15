import { describe, expect, it } from "vitest";
import { shortJobMessage } from "./shortJobMessage";

describe("shortJobMessage", () => {
  it("strips --- details --- traceback and keeps the short summary", () => {
    const raw = "ComfyUI prompt failed\n\n--- details ---\nTraceback (most recent call last):\n  File \"queue_worker.py\", line 1";
    expect(shortJobMessage(raw)).toBe("ComfyUI prompt failed");
    expect(shortJobMessage(raw)).not.toContain("details");
    expect(shortJobMessage(raw)).not.toContain("Traceback");
  });

  it("returns a trimmed message when there is no details strip", () => {
    expect(shortJobMessage("  Kie createTask failed for nano-banana  ")).toBe(
      "Kie createTask failed for nano-banana",
    );
  });
});
