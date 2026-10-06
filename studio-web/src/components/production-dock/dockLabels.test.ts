import { describe, expect, it } from "vitest";
import {
  formatAudioDockPillLabel,
  formatAudioStudioProviderPill,
  formatAudioMenuRowLabel,
} from "./dockLabels";

describe("formatAudioStudioProviderPill", () => {
  it("maps elevenlabs source to API — ElevenLabs", () => {
    expect(formatAudioStudioProviderPill("elevenlabs")).toBe("ElevenLabs API");
    expect(formatAudioStudioProviderPill("api")).toBe("ElevenLabs API");
  });

  it("maps local source to Local (never ACE-Step)", () => {
    expect(formatAudioStudioProviderPill("local")).toBe("Local");
    expect(formatAudioStudioProviderPill("local", "ACE-Step (Local)")).toBe("Local");
  });

  it("prefers short ElevenLabs displayName from health", () => {
    expect(formatAudioStudioProviderPill("elevenlabs", "ElevenLabs API")).toBe("ElevenLabs API");
  });
});

describe("formatAudioDockPillLabel (legacy collapse)", () => {
  it("never returns ACE-Step model chrome", () => {
    expect(
      formatAudioDockPillLabel({
        id: "ace-step-local",
        label: "ACE-Step (Local)",
        locality: "local",
      }),
    ).toBe("Local");
  });

  it("does not label fal as ElevenLabs", () => {
    expect(
      formatAudioDockPillLabel({
        id: "audio-fal",
        label: "Hosted Audio — fal.ai",
        locality: "hosted",
        providerId: "fal",
      }),
    ).toBe("Local");
  });
});

describe("formatAudioMenuRowLabel", () => {
  it("labels the ElevenLabs provider directly", () => {
    expect(
      formatAudioMenuRowLabel({
        id: "audio-elevenlabs",
        locality: "hosted",
        providerId: "elevenlabs",
      }),
    ).toBe("ElevenLabs API");
  });

  it("does not label fal as ElevenLabs", () => {
    expect(
      formatAudioMenuRowLabel({
        id: "audio-fal",
        locality: "hosted",
        providerId: "fal",
      }),
    ).toBe("Audio");
  });
});
