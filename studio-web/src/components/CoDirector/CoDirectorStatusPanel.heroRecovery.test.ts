import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("CoDirectorStatusPanel hero recovery", () => {
  const src = readFileSync(new URL("./CoDirectorStatusPanel.tsx", import.meta.url), "utf8");

  it("shows Recovery Options next to the Blocked hero", () => {
    expect(src).toContain("codirector-status-hero-recovery");
    expect(src).toContain('summary?.band === "Blocked"');
    expect(src).toContain("Recovery Options");
  });

  it("enables Retry Issues when blockers exist even if a check is running", () => {
    expect(src).toContain("codirector-retry-issues");
    expect(src).toContain("statusChecking && blockers.length === 0");
  });

  it("does not mention canSend or Status-35 in this panel", () => {
    expect(src).not.toContain("canSend");
    expect(src).not.toContain("Status-35");
    expect(src).not.toContain("VideoChat3");
  });
});
