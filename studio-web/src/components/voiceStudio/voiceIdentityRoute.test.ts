import { describe, expect, it } from "vitest";
import { voiceIdentityAction } from "./voiceIdentityRoute";

describe("Voice Identity method routing", () => {
  it("routes Design / Clone to existing APIs", () => {
    expect(voiceIdentityAction("create")).toBe("design");
    expect(voiceIdentityAction("clone")).toBe("clone");
    expect(voiceIdentityAction("existing")).toBe("none");
    expect(voiceIdentityAction(null)).toBe("none");
  });
});
