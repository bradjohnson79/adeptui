import { describe, expect, it } from "vitest";
import {
  applyResolvedMediaClipLabels,
  extractQuotedDialogueFromPrompt,
  resolveMediaClipLabels,
  truncateClipFaceLabel,
} from "./mediaClipLabels";

const BATCH1 =
  'They speak these lines, each in their own voice, lips matching speech: Anadriya says, "That\'s it — Cade\'s down. Corridor\'s ours." Korri says, "Told you we\'d walk this one out."';
const BATCH2 =
  'Anadriya says, "Victory walk. Let them see us." Korri says, "Side by side, sis. Always."';

describe("mediaClipLabels", () => {
  it("truncates clip-face labels with ellipsis", () => {
    expect(truncateClipFaceLabel("short")).toBe("short");
    expect(truncateClipFaceLabel("A".repeat(40), 36).endsWith("…")).toBe(true);
    expect(truncateClipFaceLabel("A".repeat(40), 36).length).toBe(36);
  });

  it("extracts speaker+quoted dialogue from prompt without inventing", () => {
    const hits = extractQuotedDialogueFromPrompt(BATCH1, "Anadriya");
    expect(hits).toEqual([
      { speaker: "Anadriya", line: "That's it — Cade's down. Corridor's ours." },
    ]);
    expect(extractQuotedDialogueFromPrompt("no quotes here", "Anadriya")).toEqual([]);
  });

  it("uses metadata first for audio/sfx", () => {
    const r = resolveMediaClipLabels({
      kind: "sfx",
      clip: { label: "SFX corridor boots Omni — Batch1_VictoryA", asset_id: "a1" },
    });
    expect(r.sources.title).toBe("metadata");
    expect(r.title).toContain("SFX corridor boots");
    expect(r.label.length).toBeLessThanOrEqual(36);
  });

  it("falls back asset → filename and never fabricates when empty", () => {
    const empty = resolveMediaClipLabels({ kind: "audio", clip: {} });
    expect(empty.title).toBeNull();
    expect(empty.description).toBeNull();
    expect(empty.label).toBe("");
    expect(empty.sources.title).toBe("none");

    const fromFile = resolveMediaClipLabels({
      kind: "audio",
      clip: { label: "Audio" },
      asset: { filename: "victory_walk_bgm.wav" },
    });
    expect(fromFile.sources.title).toBe("filename");
    expect(fromFile.title).toBe("victory_walk_bgm");
  });

  it("resolves retake title from prompt when line empty (Scene 10 pattern)", () => {
    const r = resolveMediaClipLabels({
      kind: "lipsync",
      clip: {
        id: "4a3dccebe3",
        label: "Anadriya line",
        line: "",
        character_name: "Anadriya",
        audio_asset_id: "a37cb212-c49b-46cf-9d5f-dc4a17f4d927",
      },
      promptContext: { prompts: [BATCH1], clipStart: 0.1, clipLength: 2.8 },
    });
    expect(r.sources.title).toBe("prompt");
    expect(r.title).toBe("Anadriya: That's it — Cade's down. Corridor's ours.");
    expect(r.description || "").toContain("That's it — Cade's down. Corridor's ours.");
    expect(r.description || "").toContain("audio_asset_id=a37cb212-c49b-46cf-9d5f-dc4a17f4d927");
    expect(r.label.endsWith("…") || r.label.length <= 36).toBe(true);
  });

  it("prefers metadata line over prompt when both exist", () => {
    const r = resolveMediaClipLabels({
      kind: "lipsync",
      clip: {
        character_name: "Korri",
        line: "Stored line only",
        label: "Korri line",
      },
      promptContext: { prompts: [BATCH2] },
    });
    expect(r.sources.title).toBe("metadata");
    expect(r.title).toBe("Korri: Stored line only");
  });

  it("applyResolvedMediaClipLabels can backfill empty line from title", () => {
    const resolved = resolveMediaClipLabels({
      kind: "lipsync",
      clip: { character_name: "Korri", line: "", label: "Korri line" },
      promptContext: { prompts: [BATCH1] },
    });
    const next = applyResolvedMediaClipLabels(
      { character_name: "Korri", line: "", label: "Korri line" },
      resolved,
      { setLineFromTitle: true, speaker: "Korri" },
    );
    expect(next.line).toBe("Told you we'd walk this one out.");
    expect(next.title).toContain("Korri:");
  });

  it("job tier wins over prompt when metadata empty", () => {
    const r = resolveMediaClipLabels({
      kind: "audio",
      clip: {},
      job: { title: "Job bed — corridor" },
      promptContext: { prompts: [BATCH1] },
      asset: { filename: "x.wav" },
    });
    expect(r.sources.title).toBe("job");
    expect(r.title).toBe("Job bed — corridor");
  });
});
