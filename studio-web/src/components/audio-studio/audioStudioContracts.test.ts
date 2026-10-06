import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

describe("Audio Studio surface contracts", () => {
  it("keeps four shared surfaces and reuses Library plus generate/approve/place", () => {
    const workspace = readFileSync(fileURLToPath(new URL("./AudioStudioWorkspace.tsx", import.meta.url)), "utf8");
    expect(workspace).toContain('id: "music"');
    expect(workspace).toContain('id: "sfx"');
    expect(workspace).toContain('id: "ambience"');
    expect(workspace).toContain('id: "library"');
    expect(workspace).toContain("audioStudioGenerate");
    expect(workspace).toContain("audioStudioApproveCandidate");
    expect(workspace).not.toContain("Add to Timeline");
    expect(workspace).toContain("api.library");
    const place = readFileSync(fileURLToPath(new URL("../../filmTimeline/addToTimeline.ts", import.meta.url)), "utf8");
    expect(place).toContain("export function addToTimeline");
    expect(workspace).not.toContain("VoiceCreatorProfile");
  });

  it("does not fall back leftover Library clips as generated takes", () => {
    const candidates = readFileSync(fileURLToPath(new URL("./audioStudioCandidates.ts", import.meta.url)), "utf8");
    expect(candidates).not.toContain("fallbackAssets");
  });
});
