import { beforeEach, describe, expect, it } from "vitest";
import { previousEligibleProject, projectsHeroSummary } from "./CreateProjectCard";
import { pushRecentProject } from "../../workspacePrefs";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, String(value));
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => store.clear(),
    },
  });
});

describe("projects hero", () => {
  it("summarizes the live productions and names the active one", () => {
    expect(projectsHeroSummary([], null)).toMatch(/No productions yet/);
    expect(
      projectsHeroSummary(
        [
          { status_label: "Active" },
          { status_label: "Rendering" },
          { archived: 1, status_label: "Complete" },
        ],
        "CD Timeline Recert",
      ),
    ).toBe("2 productions, 1 rendering. CD Timeline Recert is the active project.");
  });

  it("uses the earlier recent project, then the next updated project", () => {
    pushRecentProject("active", "Active");
    pushRecentProject("older", "Older");
    const projects = [
      { id: "active", name: "Active", updated_at: "2026-10-05T00:00:00Z" },
      { id: "older", name: "Older", updated_at: "2026-10-01T00:00:00Z" },
      { id: "newest", name: "Newest", updated_at: "2026-10-04T00:00:00Z" },
    ];
    expect(previousEligibleProject(projects, "active")?.id).toBe("older");
    expect(previousEligibleProject(projects.filter((project) => project.id !== "older"), "active")?.id).toBe("newest");
    expect(previousEligibleProject([{ id: "only", name: "Only", updated_at: "2026-10-05T00:00:00Z" }], "only")).toBeNull();
  });
});
