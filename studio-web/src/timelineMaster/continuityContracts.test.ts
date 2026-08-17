import { describe, expect, it } from "vitest";
import { CURRENT_CONTINUITY_CONTEXT_VERSION } from "./contracts";

describe("timeline continuity contracts", () => {
  it("freezes contextVersion at 1", () => {
    expect(CURRENT_CONTINUITY_CONTEXT_VERSION).toBe(1);
  });
});
