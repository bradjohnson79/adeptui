import { describe, expect, it } from "vitest";
import {
  WORKSPACES,
  commandPaletteWorkspaces,
  coDirectorProjectPath,
  isStandaloneBibleWorkspace,
  resolveWorkspace,
  workspacesForMenu,
} from "./workspaces";

describe("Production Bible user destinations", () => {
  it("keeps bible resolvable, then hidden from menus and search", () => {
    expect(resolveWorkspace("bible")).toBe("bible");
    expect(resolveWorkspace("production-bible")).toBe("bible");
    expect(WORKSPACES.bible.menuHidden).toBe(true);
    expect(WORKSPACES.bible.commandPalette).toBe(false);
    expect(workspacesForMenu("production")).not.toContain("bible");
    expect(commandPaletteWorkspaces()).not.toContain("bible");
  });

  it("redirects standalone bible visits to Co-Director for the same project", () => {
    expect(isStandaloneBibleWorkspace("bible")).toBe(true);
    expect(isStandaloneBibleWorkspace("characters")).toBe(false);
    expect(coDirectorProjectPath("2347bf46-3762-4763-86c5-4a6032522278")).toBe(
      "/co-director?projectId=2347bf46-3762-4763-86c5-4a6032522278",
    );
  });
});
