import { describe, expect, it } from "vitest";
import { normalizeErsError, stripHandlerError } from "./ersErrorMessage";

describe("normalizeErsError", () => {
  it("turns HANDLER_ERROR attribute miss into a short creator banner", () => {
    const raw = "HANDLER_ERROR: 'ImageGenerationPlan' object has no attribute 'prompt'";
    expect(normalizeErsError(raw)).toBe("ERS generation failed — ImageGenerationPlan has no prompt");
    expect(normalizeErsError(raw)).not.toContain("HANDLER_ERROR");
    expect(normalizeErsError(raw)).not.toContain("TypeError");
  });

  it("strips TypeError prefix and details so TypeError is not the only banner", () => {
    const raw = "HANDLER_ERROR: TypeError: 'ImageGenerationPlan' object has no attribute 'prompt'\n\n--- details ---\nTraceback (most recent call last):";
    expect(normalizeErsError(raw)).toBe("ERS generation failed — ImageGenerationPlan has no prompt");
    expect(normalizeErsError(raw)).not.toContain("TypeError");
    expect(normalizeErsError(raw)).not.toContain("Traceback");
  });

    it("maps attached-prop None x TypeError to a creator-readable reason", () => {
    const raw = "HANDLER_ERROR: TypeError: unsupported operand type(s) for -: 'NoneType' and 'float'";
    expect(normalizeErsError(raw)).toBe("ERS generation failed — an attached prop is missing a position");
    expect(normalizeErsError(raw)).not.toContain("TypeError");
    expect(normalizeErsError(raw)).not.toContain("HANDLER_ERROR");
  });

  it("strips TypeError so it is never the banner text", () => {
    expect(normalizeErsError("TypeError: boom")).toBe("ERS generation failed — boom");
    expect(normalizeErsError("TypeError: boom")).not.toContain("TypeError");
    expect(normalizeErsError("TypeError")).toBe("ERS generation failed");
  });

  it("keeps a short reason for other failures", () => {
    expect(normalizeErsError("HANDLER_ERROR: atlas asset missing")).toBe(
      "ERS generation failed — atlas asset missing",
    );
  });
});

describe("stripHandlerError", () => {
  it("peels HANDLER_ERROR and TypeError prefixes", () => {
    expect(stripHandlerError("HANDLER_ERROR: TypeError: nope")).toBe("nope");
  });
});
