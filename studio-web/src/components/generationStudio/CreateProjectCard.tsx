import { Button } from "../ui/Button";
import { ProjectTemplateCarousel } from "./ProjectTemplateCarousel";
import { GlassSection } from "./GlassSection";
import { dashboardImages } from "../../dashboardImages";

export function CreateProjectCard({
  busy,
  onOpen,
  activeProjectName,
  onOpenActive,
}: {
  busy: boolean;
  onOpen: () => void;
  activeProjectName?: string | null;
  onOpenActive?: () => void;
}) {
  const cover = dashboardImages.createProject;

  return (
    <div className="glass-section gs-create-card" data-testid="create-project-card">
      <div className="gs-create-card__media" aria-hidden={false}>
        <div className={`gs-create-card__fallback ${cover.plate} ${cover.motif}`} aria-hidden="true" />
        <img src={cover.src} alt={cover.alt} loading="lazy" />
        <div className="gs-create-card__scrim" aria-hidden="true" />
      </div>
      <div className="gs-create-card__content">
        <h2>Create a Project</h2>
        <p className="muted">Start a blank project and build your production from the ground up.</p>
        <Button
          type="button"
          variant="primary"
          data-testid="create-project-open"
          disabled={busy}
          onClick={onOpen}
        >
          + Create Project
        </Button>
        {activeProjectName ? (
          <div className="gs-create-card__active" data-testid="home-active-project-banner">
            <p className="gs-create-card__active-label">Active project</p>
            <div className="gs-create-card__active-row">
              <strong data-testid="home-active-project-name">{activeProjectName}</strong>
              {onOpenActive ? (
                <Button type="button" variant="ghost" compact onClick={onOpenActive}>
                  Continue
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function BrowseTemplatesCard({
  onSelectTemplate,
}: {
  onSelectTemplate: (templateId: string) => void;
}) {
  return (
    <GlassSection
      className="gs-browse-card"
      title="Browse Templates"
      description="Preview production shapes and open a template to start."
      testId="browse-templates-card"
    >
      <ProjectTemplateCarousel onSelect={onSelectTemplate} />
    </GlassSection>
  );
}
