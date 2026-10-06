import fs from "node:fs";
import { describe, expect, it } from "vitest";

const studio = fs.readFileSync(new URL("./ScriptwriterStudio.tsx", import.meta.url), "utf8");

describe("Script Writer Story is native — no Co-Director navigation loop", () => {
  it("Story tab switches the local view instead of opening Co-Director", () => {
    expect(studio).toContain('setView("story")');
    expect(studio).toContain("data-testid=\"scriptwriter-story\"");
    expect(studio).not.toMatch(/contentTab=story/);
    expect(studio).not.toMatch(/navigate\(`\/co-director/);
    expect(studio).toContain("StoryDocumentEditor");
  });

  it("keeps Script and Story on the same studio surface", () => {
    expect(studio).toContain('view === "script"');
    expect(studio).toContain('view === "story"');
    expect(studio).toContain("StoryDocumentEditor");
    expect(studio).toContain('data-testid="scriptwriter-story"');
  });
});
