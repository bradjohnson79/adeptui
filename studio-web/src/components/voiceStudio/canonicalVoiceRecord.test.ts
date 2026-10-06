import { describe, expect, it } from "vitest";
import { pickCanonicalVoiceRecord } from "./canonicalVoiceRecord";

describe("pickCanonicalVoiceRecord", () => {
  const records = [
    { characterId: "korri", voiceIdentityId: "old-draft", approvedTakeId: "t-old", updatedAt: "2026-09-02T03:00:00Z" },
    { characterId: "korri", voiceIdentityId: "approved-clone", approvedTakeId: "", updatedAt: "2026-09-02T04:00:00Z" },
    { characterId: "korri", voiceIdentityId: "approved-clone", approvedTakeId: "t-new", updatedAt: "2026-09-02T02:00:00Z" },
    { characterId: "anadriya", voiceIdentityId: "approved-clone", approvedTakeId: "t-other", updatedAt: "2026-09-02T05:00:00Z" },
  ];

  it("never falls back to another character or a stale voice identity", () => {
    expect(pickCanonicalVoiceRecord(records, "korri", "approved-clone")?.voiceIdentityId).toBe("approved-clone");
    expect(pickCanonicalVoiceRecord(records, "korri", "missing")).toBeNull();
    expect(pickCanonicalVoiceRecord(records, "anadriya", "old-draft")).toBeNull();
  });

  it("can require an approved take without stealing another voice's record", () => {
    const chosen = pickCanonicalVoiceRecord(records, "korri", "approved-clone", { requireApprovedTake: true });
    expect(chosen?.approvedTakeId).toBe("t-new");
    expect(pickCanonicalVoiceRecord(records, "korri", "old-draft", { requireApprovedTake: true })?.approvedTakeId).toBe("t-old");
  });
});
