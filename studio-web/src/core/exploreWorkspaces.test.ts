import { describe, expect, it } from "vitest";
import { EXPLORE_WORKSPACE_IDS, getExploreWorkspaceCards } from "./exploreWorkspaces";
import { WORKSPACES } from "./workspaces";

const CANONICAL_TITLES = [
  "Image Generation",
  "Character Creator",
  "Prop Creator",
  "Environment Creator",
  "Storyboard",
  "Scriptwriter",
  "Voice Studio",
  "Audio Studio",
] as const;

describe("Explore Adept UI roster", () => {
  it("lists creator studios without the retired video destinations", () => {
    expect(EXPLORE_WORKSPACE_IDS).toEqual([
      "imagegen",
      "characters",
      "propcreator",
      "environmentcreator",
      "script",
      "scriptwriter",
      "voicestudio",
      "audiostudio",
    ]);
    const cards = getExploreWorkspaceCards();
    expect(cards).toHaveLength(8);
    expect(cards.map((card) => card.id)).not.toContain("txt2vid");
    expect(cards.map((card) => card.id)).not.toContain("one");
    expect(cards.map((card) => card.id)).not.toContain("three");
    expect(cards.map((card) => card.label)).toEqual([...CANONICAL_TITLES]);
    expect(cards.map((card) => card.id)).not.toContain("library");
  });

  it("omits Timeline and MAGI from Explore only", () => {
    const ids = getExploreWorkspaceCards().map((card) => card.id);
    expect(ids).not.toContain("timeline");
    expect(ids).not.toContain("magi");
    expect(WORKSPACES.timeline).toBeDefined();
    expect(WORKSPACES.magi).toBeDefined();
  });

  it("routes every card to an existing WORKSPACES id with themed artwork", () => {
    for (const card of getExploreWorkspaceCards()) {
      expect(WORKSPACES[card.workspace]).toBeDefined();
      expect(card.image.src).toMatch(/\.(jpg|jpeg|webp)$/i);
      expect(card.image.alt.trim().length).toBeGreaterThan(0);
      expect(card.description.length).toBeLessThanOrEqual(80);
    }
  });
});
