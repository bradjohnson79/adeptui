import { describe, expect, it } from "vitest";
import {
  defaultStoryTitle,
  escapeHtml,
  isBlankStoryHtml,
  looksLikeHtml,
  pickPrimaryStoryEntry,
  toEditorHtml,
  type CanonicalStoryEntry,
} from "./canonicalStory";

function entry(partial: Partial<CanonicalStoryEntry>): CanonicalStoryEntry {
  return {
    id: "e1",
    projectId: "p1",
    title: "Story",
    entryType: "project_story",
    logline: "",
    shortSummary: "",
    longSummary: "",
    sortOrder: 0,
    createdAt: "",
    updatedAt: "",
    ...partial,
  };
}

describe("canonical story helpers", () => {
  it("prefers the project_story entry as the shared document", () => {
    const primary = pickPrimaryStoryEntry([
      entry({ id: "ep", entryType: "episode", title: "Ep 1" }),
      entry({ id: "main", entryType: "project_story", title: "The Venture — Story" }),
    ]);
    expect(primary?.id).toBe("main");
  });

  it("falls back to the first entry when no project_story exists", () => {
    const only = pickPrimaryStoryEntry([entry({ id: "only", entryType: "chapter" })]);
    expect(only && only.id).toBe("only");
    expect(pickPrimaryStoryEntry([])).toBeNull();
  });

  it("wraps plain Express text as paragraphs and keeps existing HTML", () => {
    expect(toEditorHtml("Synopsis.\n\nTreatment.")).toBe("<p>Synopsis.</p><p>Treatment.</p>");
    expect(toEditorHtml("<h2>Arcs</h2><p>Korri and Anadriya.</p>")).toBe(
      "<h2>Arcs</h2><p>Korri and Anadriya.</p>",
    );
    expect(toEditorHtml("")).toBe("<p></p>");
    expect(looksLikeHtml("<p>Hi</p>")).toBe(true);
    expect(looksLikeHtml("just text")).toBe(false);
    expect(escapeHtml("<x>")).toBe("&lt;x&gt;");
  });

  it("treats empty markup as a blank story document", () => {
    expect(isBlankStoryHtml("<p></p>")).toBe(true);
    expect(isBlankStoryHtml("<p>Korri stays.</p>")).toBe(false);
  });

  it("names the story document from the project without inventing a second project", () => {
    expect(defaultStoryTitle("The Venture")).toBe("The Venture — Story");
    expect(defaultStoryTitle("")).toBe("Untitled — Story");
  });
});
