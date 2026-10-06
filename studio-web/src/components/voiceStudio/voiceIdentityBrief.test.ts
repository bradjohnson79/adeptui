import { describe, expect, it } from "vitest";
import {
  canApproveSelectedVoice,
  compileVoiceCloneGenerateBody,
  compileVoiceIdentityGenerateBody,
  pickNewestGeneratedSample,
  pickRestorableVoiceCandidates,
} from "./voiceIdentityBrief";

describe("compileVoiceIdentityGenerateBody", () => {
  it("sends the Voice Identity contract the generate API already understands", () => {
    const body = compileVoiceIdentityGenerateBody({
      sex: "female",
      age: "Young Adult 20-24",
      accent: "Neutral American",
      archetype: "Rebel",
      script: "Light circuitry, not tattoos.",
      promptDetails: "Playful teenage elf, sharp and teasing.",
      sampleCount: 4,
    });
    expect(body.candidateCount).toBe(4);
    expect(body.sampleCount).toBe(4);
    expect(body.testLine).toBe("Light circuitry, not tattoos.");
    expect(body.masterPrompt).toBe("Playful teenage elf, sharp and teasing.");
    expect((body.designBrief as { gender: string }).gender).toBe("Female");
    expect(body.method).toBe("design");
  });
});

describe("compileVoiceCloneGenerateBody", () => {
  it("does not send a transcript or prompt details, and honors the visible sample count", () => {
    const body = compileVoiceCloneGenerateBody({
      name: "Korri Clone",
      characterName: "Korri",
      referencePath: "C:/data/korri.mp3",
      referenceAssetId: "asset-1",
      testLine: "Light circuitry, not tattoos, doofus.",
      sampleCount: 1,
      consentConfirmed: true,
    });
    expect(body).not.toHaveProperty("transcript");
    expect(body).not.toHaveProperty("masterPrompt");
    expect(body).not.toHaveProperty("designBrief");
    expect(body).not.toHaveProperty("accent");
    expect(body).not.toHaveProperty("archetype");
    expect(body.candidateCount).toBe(1);
    expect(body.sampleCount).toBe(1);
    expect(body.test_line).toBe("Light circuitry, not tattoos, doofus.");
    expect(body.reference_asset_id).toBe("asset-1");
    const consent = body.consent as { consent_confirmed: boolean; synthetic_generation_allowed: boolean };
    expect(consent.consent_confirmed).toBe(true);
    expect(consent.synthetic_generation_allowed).toBe(true);
  });

  it("sends the clicked sample count even when it just changed to 4", () => {
    const body = compileVoiceCloneGenerateBody({
      name: "Korri Clone",
      characterName: "Korri",
      referencePath: "C:/data/korri.mp3",
      referenceAssetId: "asset-1",
      testLine: "I developed them with my sister in the Abode.",
      sampleCount: 4,
      consentConfirmed: true,
    });
    expect(body.candidateCount).toBe(4);
    expect(body.sampleCount).toBe(4);
  });
});

describe("canApproveSelectedVoice", () => {
  const samples = [
    { id: "sample-1", audioUrl: "/assets/a.wav" },
    { id: "sample-2", audioUrl: "/assets/b.wav" },
    { id: "sample-3", audioUrl: "/assets/c.wav" },
    { id: "sample-4", audioUrl: "/assets/d.wav" },
  ];

  it("enables approve for the selected generated sample even when a prior voice is already approved", () => {
    expect(
      canApproveSelectedVoice({
        selectedId: "sample-3",
        voiceId: "new-clone-profile",
        samples,
      }),
    ).toBe(true);
  });

  it("stays disabled when the selected sample has no audio", () => {
    expect(
      canApproveSelectedVoice({
        selectedId: "sample-3",
        voiceId: "new-clone-profile",
        samples: [{ id: "sample-3" }],
      }),
    ).toBe(false);
  });

  it("stays disabled without a generated voice id or selected candidate", () => {
    expect(canApproveSelectedVoice({ selectedId: "sample-3", voiceId: "", samples })).toBe(false);
    expect(canApproveSelectedVoice({ selectedId: "", voiceId: "new-clone-profile", samples })).toBe(false);
  });

  it("follows the selected candidate, never sample 1 by default", () => {
    expect(
      canApproveSelectedVoice({
        selectedId: "sample-2",
        voiceId: "new-clone-profile",
        samples,
      }),
    ).toBe(true);
    expect(samples.find((sample) => sample.id === "sample-2")?.audioUrl).toContain("b.wav");
  });
});

describe("pickRestorableVoiceCandidates", () => {
  it("restores the newest unapproved clone with playable assets, not an already approved profile", () => {
    const restored = pickRestorableVoiceCandidates([
      {
        id: "old-approved",
        approval_status: "approved",
        source_mode: "DESIGN",
        updated_at: "2026-09-01T20:00:00Z",
        candidates: [{ id: "stale", assetId: "asset-old" }],
      },
      {
        id: "older-clone",
        approval_status: "draft",
        source_mode: "CLONE",
        updated_at: "2026-09-01T21:00:00Z",
        candidates: [{ id: "c1", assetId: "asset-1" }],
      },
      {
        id: "latest-clone",
        approval_status: "draft",
        source_mode: "CLONE",
        updated_at: "2026-09-01T22:00:00Z",
        candidates: [
          { id: "s1", assetId: "a1" },
          { id: "s2", assetId: "a2" },
          { id: "s3", assetId: "a3" },
          { id: "s4", assetId: "a4" },
        ],
      },
    ]);
    expect(restored?.voiceId).toBe("latest-clone");
    expect(restored?.sourceMode).toBe("CLONE");
    expect(restored?.candidates).toHaveLength(4);
    expect(restored?.candidates[2]?.id).toBe("s3");
  });

  it("restores an unapproved Create New Voice design batch", () => {
    const restored = pickRestorableVoiceCandidates([
      {
        id: "design-draft",
        approval_status: "draft",
        source_mode: "DESIGN",
        updated_at: "2026-09-16T04:16:00Z",
        candidates: [
          { id: "d1", assetId: "a1" },
          { id: "d2", assetId: "a2" },
          { id: "d3", assetId: "a3" },
        ],
      },
    ]);
    expect(restored?.voiceId).toBe("design-draft");
    expect(restored?.sourceMode).toBe("DESIGN");
    expect(restored?.candidates).toHaveLength(3);
  });

  it("does not restore an older unapproved clone after a newer approved voice exists", () => {
    expect(
      pickRestorableVoiceCandidates([
        {
          id: "approved-clone",
          approval_status: "approved",
          source_mode: "CLONE",
          approved_at: "2026-09-02T02:20:20Z",
          updated_at: "2026-09-02T02:20:20Z",
          candidates: [{ id: "s3", assetId: "a3" }],
        },
        {
          id: "stale-clone",
          approval_status: "draft",
          source_mode: "CLONE",
          updated_at: "2026-09-02T02:07:53Z",
          candidates: [{ id: "old", assetId: "old-asset" }],
        },
      ]),
    ).toBeNull();
  });
});

describe("pickNewestGeneratedSample", () => {
  it("chooses the newest ElevenLabs sample and ignores saved local samples", () => {
    const picked = pickNewestGeneratedSample([
      {
        id: "old-local",
        status: "ready",
        assetId: "seven-seconds",
        voiceProfileId: "profile",
        provider: "qwen3-tts",
        name: "Sample 1",
        createdAt: "2026-10-01T00:00:00",
      },
      {
        id: "older-eleven",
        status: "ready",
        assetId: "earlier",
        voiceProfileId: "",
        provider: "elevenlabs",
        name: "Earlier",
        createdAt: "2026-10-04T16:35:00",
      },
      {
        id: "",
        status: "ready",
        assetId: "seventeen-seconds",
        voiceProfileId: "",
        provider: "elevenlabs",
        name: "Renkoka Final",
        createdAt: "2026-10-04T16:57:41",
      },
    ]);
    expect(picked?.assetId).toBe("seventeen-seconds");
  });
});

