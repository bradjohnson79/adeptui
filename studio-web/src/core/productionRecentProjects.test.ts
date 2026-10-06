import { describe, expect, it } from "vitest";
import { toRecentProjects, RECENT_PROJECTS_MAX } from "./productionRecentProjects";

function project(id: string, name: string, updated_at: string, archived?: number) {
  return { id, name, updated_at, ...(archived ? { archived } : {}) };
}

describe("Recent Projects (Production menu)", () => {
  it("maps server projects newest-first (server order preserved), max 5", () => {
    const projects = Array.from({ length: 7 }, (_, i) =>
      project(`p${i}`, `Project ${i}`, `2026-09-0${i + 1}T12:00:00Z`),
    );
    const recent = toRecentProjects(projects);
    expect(recent).toHaveLength(RECENT_PROJECTS_MAX);
    expect(recent[0].id).toBe("p0");
    expect(recent[0].name).toBe("Project 0");
    expect(recent[4].id).toBe("p4");
  });

  it("excludes archived projects", () => {
    const projects = [
      project("a", "Active", "2026-09-10T12:00:00Z"),
      project("b", "Archived", "2026-09-11T12:00:00Z", 1),
    ];
    const recent = toRecentProjects(projects);
    expect(recent.map((r) => r.id)).toEqual(["a"]);
  });

  it("excludes entries without id or name", () => {
    const recent = toRecentProjects([
      { id: "ok", name: "OK", updated_at: "2026-09-10T12:00:00Z" },
      { name: "No id", updated_at: "2026-09-10T12:00:00Z" },
      { id: "no-name", updated_at: "2026-09-10T12:00:00Z" },
    ]);
    expect(recent.map((r) => r.id)).toEqual(["ok"]);
  });

  it("renders relative time labels from updated_at (recency authority: last modified)", () => {
    const now = Date.now();
    const minutesAgo = new Date(now - 5 * 60 * 1000).toISOString();
    const daysAgo = new Date(now - 3 * 86400 * 1000).toISOString();
    const [fresh, older] = toRecentProjects([
      project("fresh", "Fresh", minutesAgo),
      project("older", "Older", daysAgo),
    ]);
    expect(fresh.whenLabel).toBe("5m ago");
    expect(older.whenLabel).toBe("3d ago");
  });

  it("handles missing updated_at gracefully", () => {
    const [row] = toRecentProjects([{ id: "x", name: "X" }]);
    expect(row.updatedAt).toBeNull();
    expect(row.whenLabel).toBe("—");
  });

  it("supports fewer than five projects (shows only those that exist)", () => {
    const recent = toRecentProjects([project("only", "Only One", "2026-09-10T12:00:00Z")]);
    expect(recent).toHaveLength(1);
  });

  it("empty list renders as empty (no placeholders)", () => {
    expect(toRecentProjects([])).toEqual([]);
  });
});
