import { Button } from "../ui/Button";
import type { DashboardImage } from "../../dashboardImages";

export function ProjectTemplateCard({
  id,
  title,
  description,
  image,
  meta,
  type,
  busy,
  selected,
  onUse,
}: {
  id: string;
  title: string;
  description: string;
  image: DashboardImage;
  meta?: string;
  type?: string;
  busy: boolean;
  selected?: boolean;
  onUse: () => void;
}) {
  return (
    <article
      className={`gs-template-card ${selected ? "is-selected" : ""}`}
      data-testid={`project-template-card-${id}`}
    >
      <div className="gs-template-card__media">
        <div
          className={`cinematic-media-fallback ${image.plate || "aurora-plate"} ${image.motif || ""}`.trim()}
          aria-hidden="true"
        />
        <img
          src={image.src}
          alt={image.alt || `${title} template — ${description}`}
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
        <div className="gs-template-card__lower-third">
          {type ? <span className="gs-template-card__lower-third-kicker">{type}</span> : null}
          <span className="gs-template-card__lower-third-title">{title}</span>
        </div>
      </div>
      <div className="gs-template-card__body">
        <h3>{title}</h3>
        <p>{description}</p>
        {meta ? <span className="gs-template-card__meta">{meta}</span> : null}
        <Button
          type="button"
          variant="primary"
          compact
          className="gs-template-card__cta"
          disabled={busy}
          data-testid={`use-template-${id}`}
          onClick={onUse}
        >
          Use Template
        </Button>
      </div>
    </article>
  );
}
