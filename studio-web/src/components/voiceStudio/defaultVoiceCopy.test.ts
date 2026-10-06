import { describe, expect, it } from "vitest";
import {
  approveReplacementNote,
  approvedDefaultVoiceMessage,
  approvedVoiceBannerSubtitle,
  approvedVoiceBannerTitle,
  approvedVoiceVersionLabel,
  noApprovedDefaultVoiceMessage,
} from "./defaultVoiceCopy";

describe("default voice copy", () => {
  it("names the character on approval", () => {
    expect(approvedDefaultVoiceMessage("Korri")).toBe(
      "Approved. This is now Korri's default voice throughout Adept UI.",
    );
  });

  it("is honest when a character has no approved voice", () => {
    expect(noApprovedDefaultVoiceMessage("Anadriya")).toBe(
      "Anadriya has no voice currently assigned.",
    );
  });

  it("uses the VoiceProfile name, not a generic Voice suffix", () => {
    expect(approvedVoiceBannerTitle("Korri Clone", "Korri")).toBe("Approved Voice — Korri Clone");
    expect(approvedVoiceBannerSubtitle()).toBe("Default voice across Adept UI");
  });

  it("explains replacement without an error state", () => {
    expect(approveReplacementNote("Cade O'Connor")).toBe(
      "Approving a new sample will make it Cade O'Connor's current voice. The previous approved voice will remain in version history.",
    );
    expect(approvedVoiceVersionLabel(2)).toBe("v2");
    expect(approvedVoiceVersionLabel("")).toBe("");
  });
});
