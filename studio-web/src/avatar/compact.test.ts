import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  AVATAR_ASPECT_RATIOS,
  AVATAR_COMPACT_MAIN_TESTIDS,
  AVATAR_EXCLUDED_GENERATOR_IDS,
  AVATAR_GENERATOR_IDS,
  compiledDialogueFromConversation,
  conversationTurnsInOrder,
  defaultSpeakers,
  hydrateCompactSession,
  isListedAvatarGenerator,
  speakerLabel,
} from "./compact";
import { emptyAvatarSession } from "./types";

const panelSource = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../components/AvatarStudioCreatePanel.tsx"),
  "utf8",
);
const mainSource = panelSource.split('data-testid="avatar-advanced-panel"')[0] || panelSource;

describe("Avatar compact MAIN path", () => {
  it("keeps required creator decisions on MAIN", () => {
    for (const testId of AVATAR_COMPACT_MAIN_TESTIDS) {
      expect(mainSource).toContain(`data-testid="${testId}"`);
    }
  });

  it("does not keep style, framing, or background card grids on MAIN", () => {
    expect(mainSource).not.toContain("avatar-mode-cards");
    expect(mainSource).not.toContain("STYLE_CARDS.map");
    expect(mainSource).not.toContain("FRAMING_CARDS.map");
    expect(mainSource).not.toContain("BACKGROUND_CARDS.map");
    expect(mainSource).not.toContain("avatar-card-grid");
    expect(panelSource).toContain("avatar-style-select");
    expect(panelSource).toContain("avatar-framing-select");
    expect(panelSource).toContain("avatar-background-select");
    expect(panelSource).toContain("LoRASelector");
  });

  it("lists only talking-head generators and excludes H3, LTX, and EchoMimic", () => {
    expect([...AVATAR_GENERATOR_IDS]).toEqual(["infinitetalk-local", "longcat-video-avatar-1-5-local"]);
    for (const id of AVATAR_EXCLUDED_GENERATOR_IDS) {
      expect(isListedAvatarGenerator(id)).toBe(false);
      expect(mainSource).not.toContain(id);
    }
    expect(mainSource).not.toContain("minimax");
    expect(mainSource).not.toContain("ltx_2_5");
  });

  it("includes aspect options", () => {
    expect([...AVATAR_ASPECT_RATIOS]).toEqual(["1:1", "4:5", "3:2", "16:9", "9:16", "21:9"]);
    expect(panelSource).toContain("avatar-aspect");
  });
});

describe("speaker labels and conversation isolation", () => {
  it("uses Person 1 / Person 2 when no character is bound", () => {
    const speakers = defaultSpeakers(emptyAvatarSession("proj-1"));
    expect(speakerLabel(speakers[0], 1)).toBe("Person 1");
    expect(speakerLabel(undefined, 2)).toBe("Person 2");
    expect(panelSource).toContain('<option value="person-1">Person 1</option>');
    expect(panelSource).toContain('<option value="person-2">Person 2</option>');
  });

  it("keeps Speaker A and Speaker B dialogue isolated in A then B order", () => {
    const session = hydrateCompactSession(emptyAvatarSession("proj-1"));
    session.mode_kind = "conversation";
    session.speakers = [
      { id: "speaker-a", label: "Person 1" },
      { id: "speaker-b", label: "Person 2" },
    ];
    session.conversation = {
      order: "a_then_b",
      turns: [
        { speakerId: "speaker-a", dialogue: "Korri opens the shop." },
        { speakerId: "speaker-b", dialogue: "Anadriya answers the counter." },
      ],
    };
    const turns = conversationTurnsInOrder(session.conversation);
    expect(turns.map((turn) => turn.dialogue)).toEqual([
      "Korri opens the shop.",
      "Anadriya answers the counter.",
    ]);
    expect(compiledDialogueFromConversation(session)).toContain("Korri opens the shop.");
    expect(compiledDialogueFromConversation(session)).toContain("Anadriya answers the counter.");
  });

  it("reverses speaking order for B then A without mixing lines", () => {
    const turns = conversationTurnsInOrder({
      order: "b_then_a",
      turns: [
        { speakerId: "speaker-a", dialogue: "A line" },
        { speakerId: "speaker-b", dialogue: "B line" },
      ],
    });
    expect(turns.map((turn) => `${turn.speakerId}:${turn.dialogue}`)).toEqual(["speaker-b:B line", "speaker-a:A line"]);
  });

  it("hydrates aspect and replaces leftover LTX model ids", () => {
    const session = emptyAvatarSession("proj-1");
    session.model_id = "ltx_2_5_distilled";
    session.look.aspect = "16:9";
    const next = hydrateCompactSession(session);
    expect(next.model_id).toBe("infinitetalk-local");
    expect(next.look.aspect).toBe("16:9");
    expect(next.camera.aspect).toBe("16:9");
    expect(next.source_kind).toBe("character");
  });
});
