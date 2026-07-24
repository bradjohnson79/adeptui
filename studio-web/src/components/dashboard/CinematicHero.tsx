import type { ReactNode } from "react";
import type { DashboardImage } from "../../dashboardImages";

export function CinematicMedia({
  image,
  className = "",
  children,
}: {
  image: DashboardImage;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div className={`cinematic-media ${image.motif} ${className}`} role="img" aria-label={image.alt}>
      <div className="cinematic-media-fallback" aria-hidden="true" />
      <img
        src={image.src}
        alt=""
        className="cinematic-media-img"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
        }}
      />
      <div className="cinematic-media-overlay" aria-hidden="true" />
      {children}
    </div>
  );
}

export function CinematicEmptyState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="cinematic-empty">
      <div className="cinematic-empty-icon" aria-hidden="true" />
      <h3>{title}</h3>
      <p>{body}</p>
      {actionLabel && onAction && (
        <button type="button" className="primary" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function CinematicHero({
  onCreate,
  onOpenExisting,
}: {
  onCreate: () => void;
  onOpenExisting: () => void;
}) {
  return (
    <section className="cinematic-hero">
      <div className="cinematic-hero-copy">
        <p className="eyebrow">Build your next film</p>
        <h1>Direct local AI video.</h1>
        <p className="lede">
          From script and storyboard to spatial blocking and final timeline — a filmmaking OS, not a node
          graph.
        </p>
        <div className="hero-cta-row">
          <button type="button" className="primary" onClick={onCreate}>
            Create New Project
          </button>
          <button type="button" onClick={onOpenExisting}>
            Open Existing Project
          </button>
        </div>
        <div className="hero-chips" aria-label="Pipeline stages">
          {["Script", "Storyboard", "Spatial Map", "ImageGen", "Director"].map((c) => (
            <span key={c} className="pill">
              {c}
            </span>
          ))}
        </div>
      </div>
      <CinematicMedia image={{ src: "/images/dashboard/hero-film-set.jpg", alt: "Film set", motif: "motif-set" }} className="cinematic-hero-media">
        <span className="hero-media-caption">Production on set</span>
      </CinematicMedia>
    </section>
  );
}
