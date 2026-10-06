import type { Project } from "../../types";
import { loadRecentProjects } from "../../workspacePrefs";
import { Button } from "../ui/Button";

export function previousEligibleProject(
  projects: Array<Pick<Project, "id" | "name" | "archived" | "updated_at">>,
  activeId: string | null,
): Pick<Project, "id" | "name" | "archived" | "updated_at"> | null {
  const eligible = projects.filter((project) => !project.archived && project.id);
  if (!activeId) return null;
  const fromRecent = loadRecentProjects().find(
    (item) => item.id !== activeId && eligible.some((project) => project.id === item.id),
  );
  if (fromRecent) return eligible.find((project) => project.id === fromRecent.id) || null;
  const ordered = [...eligible].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
  return ordered.find((project) => project.id !== activeId) || null;
}

export function projectsHeroSummary(
  projects: Array<Pick<Project, "archived" | "status_label">>,
  activeName?: string | null,
): string {
  const live = projects.filter((project) => !project.archived);
  const count = live.length;
  if (!count) return "No productions yet. Create one and it will show up here.";
  const noun = count === 1 ? "production" : "productions";
  const rendering = live.filter((project) => /render/i.test(project.status_label || "")).length;
  const complete = live.filter((project) => /complete/i.test(project.status_label || "")).length;
  const detail = [
    rendering ? `${rendering} rendering` : "",
    complete ? `${complete} complete` : "",
  ].filter(Boolean);
  const lead = `${count} ${noun}${detail.length ? `, ${detail.join(", ")}` : ""}.`;
  return activeName ? `${lead} ${activeName} is the active project.` : lead;
}

export function CreateProjectCard({
  busy,
  onOpen,
  projects,
  activeProjectName,
  previousProjectName,
  onOpenActive,
  onOpenPrevious,
}: {
  busy: boolean;
  onOpen: () => void;
  projects: Array<Pick<Project, "archived" | "status_label">>;
  activeProjectName?: string | null;
  previousProjectName?: string | null;
  onOpenActive?: () => void;
  onOpenPrevious?: () => void;
}) {
  return (
    <div className="glass-section gs-projects-hero" data-testid="projects-hero">
      <div className="gs-projects-hero__top">
        <div className="gs-projects-hero__copy">
          <h2 id="projects-heading">Projects</h2>
          <p className="gs-projects-hero__summary" data-testid="projects-hero-summary">
            {projectsHeroSummary(projects, activeProjectName)}
          </p>
        </div>
        <Button
          type="button"
          variant="primary"
          data-testid="create-project-open"
          disabled={busy}
          onClick={onOpen}
        >
          + Create Project
        </Button>
      </div>
      <div className="gs-projects-hero__pair">
        <div className="gs-projects-hero__slot" data-testid="home-active-project-banner">
          <p className="gs-projects-hero__label">Active project</p>
          <div className="gs-projects-hero__row">
            <strong data-testid="home-active-project-name">{activeProjectName || "None yet"}</strong>
            {activeProjectName && onOpenActive ? (
              <Button type="button" variant="ghost" compact onClick={onOpenActive}>
                Continue
              </Button>
            ) : null}
          </div>
        </div>
        <div className="gs-projects-hero__slot" data-testid="home-previous-project">
          <p className="gs-projects-hero__label">Previous project</p>
          <div className="gs-projects-hero__row">
            <strong data-testid="home-previous-project-name">{previousProjectName || "None yet"}</strong>
            {previousProjectName && onOpenPrevious ? (
              <Button type="button" variant="ghost" compact data-testid="home-previous-project-open" onClick={onOpenPrevious}>
                Open
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
