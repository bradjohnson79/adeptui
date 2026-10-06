/**
 * Recent Projects for the Production menu — server-canonical recency.
 *
 * Authority (no second project database): GET /api/projects returns non-archived
 * projects sorted by updated_at desc. Adept does not record a "last opened"
 * timestamp, so per the recency contract the fallback is last-modified
 * (updated_at). Rows render name + relative time; switching uses the canonical
 * navigate('/project/:id') flow — no project-loading logic lives here.
 */
import { relativeTime } from "../dashboardImages";

export const RECENT_PROJECTS_MAX = 5;

export type RecentProject = {
  id: string;
  name: string;
  updatedAt: string | null;
  /** Creator-facing relative label, e.g. "Just now" / "2h ago" / date. */
  whenLabel: string;
};

type ProjectListPayload = Array<{
  id: string;
  name: string;
  updated_at?: string | null;
  archived?: number | null;
}>;

/** Newest-first, max 5, archived/deleted filtered server-side already. */
export function toRecentProjects(projects: ProjectListPayload): RecentProject[] {
  return projects
    .filter((p) => !p.archived && p.id && p.name)
    .map((p) => ({
      id: p.id,
      name: p.name,
      updatedAt: p.updated_at ?? null,
      whenLabel: relativeTime(p.updated_at ?? undefined),
    }))
    .slice(0, RECENT_PROJECTS_MAX);
}
