import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("Co-Director Express handoff page", () => {
  it("routes Standard destinations through the shared workspace location helper", () => {
    const src = readFileSync(new URL("./CoDirectorPage.tsx", import.meta.url), "utf8");
    expect(src).toContain("buildProjectWorkspaceLocation");
    expect(src).toContain("sceneId,");
    expect(src).not.toContain("pathname: `/project/${projectId}`");
  });
});
