import { describe, expect, it } from "vitest";
import { CONTENT_NAV } from "../navEntries";

describe("Voice Creator Express contracts", () => {
  it("places Voice Creator immediately after Character Creator and before Prop Creator", () => {
    const tabs = CONTENT_NAV.filter((item) => item.kind === "tab").map((item) => item.id);
    expect(tabs.indexOf("voice_creator")).toBe(tabs.indexOf("characters") + 1);
    expect(tabs.indexOf("prop_creator")).toBe(tabs.indexOf("voice_creator") + 1);
    const entry = CONTENT_NAV.find((item) => item.kind === "tab" && item.id === "voice_creator");
    expect(entry && entry.kind === "tab" ? entry.label : "").toBe("Voice Creator");
  });

  it("reuses Voice Identity instead of inventing a second voice system", async () => {
    const fs = await import("node:fs");
    const panel = fs.readFileSync(new URL("./VoiceCreatorPanel.tsx", import.meta.url), "utf8");
    const identity = fs.readFileSync(new URL("../../voiceStudio/VoiceIdentityPanel.tsx", import.meta.url), "utf8");
    expect(panel).toContain('variant="express"');
    expect(panel).toContain("VoiceIdentityPanel");
    expect(panel).not.toContain("VoiceCreatorProfile");
    expect(panel).not.toContain("approveCharacterVoiceCandidate");
    expect(identity).toContain("approveCharacterVoiceCandidate");
    expect(identity).toContain("approvedDefaultVoiceMessage");
    expect(identity).toContain('data-testid="voice-provider"');
    expect(identity).toContain('label="Voice Provider"');
    expect(identity).toContain("ElevenLabsVoiceWorkflow");
    expect(identity).toContain('method === "elevenlabs"');
  });
});
