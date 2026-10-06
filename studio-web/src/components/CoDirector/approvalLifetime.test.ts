import { describe, expect, it } from "vitest";
import { STALE_APPROVAL_COPY, approvalCardIsActionable } from "./approvalLifetime";

describe("approval card lifetime", () => {
  it("keeps a fresh proposal actionable across repeat reads", () => {
    const proposal = { status: "pending", isStale: false };
    expect(approvalCardIsActionable(proposal)).toBe(true);
    expect(approvalCardIsActionable(proposal)).toBe(true);
    expect(STALE_APPROVAL_COPY.includes("proposal")).toBe(false);
  });

  it("hides actions after a real stale flag, rejection, or completion", () => {
    expect(approvalCardIsActionable({ status: "pending", isStale: true })).toBe(false);
    expect(approvalCardIsActionable({ status: "stale", isStale: true })).toBe(false);
    expect(approvalCardIsActionable({ status: "rejected", isStale: false })).toBe(false);
    expect(approvalCardIsActionable({ status: "completed", isStale: false })).toBe(false);
    expect(approvalCardIsActionable({ status: "revision_requested", isStale: false })).toBe(true);
  });
});
