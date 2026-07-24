import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { relativeTime } from "../../dashboardImages";

export type ProjectCardModel = {
  id: string;
  name: string;
  description?: string;
  engine_default?: string;
  updated_at?: string;
  scene_count?: number;
  asset_count?: number;
  render_pct?: number;
  status?: string;
  cover_url?: string | null;
  width?: number;
  height?: number;
};

export function ProjectCoverCard({
  project,
  view = "grid",
  onRename,
  onDuplicate,
  onExport,
  onArchive,
  onDelete,
}: {
  project: ProjectCardModel;
  view?: "grid" | "list";
  onRename: (id: string) => void;
  onDuplicate: (id: string) => void;
  onExport: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const pct = Math.max(0, Math.min(100, project.render_pct ?? 0));
  const status = project.status || "Active";

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  return (
    <article className={`dash-card project-cover-card ${view}`}>
      <Link to={`/project/${project.id}`} className="project-cover-link" aria-label={`Open ${project.name}`}>
        <div className={`cinematic-media motif-set project-cover-media`}>
          <div className="cinematic-media-fallback" aria-hidden="true" />
          {project.cover_url && (
            <img
              src={project.cover_url}
              alt=""
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div className="cinematic-media-overlay" />
          <span className={`status-badge top-badge ${status === "Rendering" ? "warn" : status === "Complete" ? "ok" : ""}`}>
            {status}
          </span>
        </div>
      </Link>
      <div className="project-cover-body">
        <h3>{project.name}</h3>
        <p className="muted">
          {project.description?.slice(0, 80) || `${project.width || 1280}×${project.height || 720}`}
        </p>
        <p className="scene-meta">
          {project.scene_count ?? 0} scenes · {project.asset_count ?? 0} assets ·{" "}
          {(project.engine_default || "ltx").toUpperCase()}
        </p>
        <div className="progress-strip" aria-label={`Render progress ${pct}%`}>
          <div className="progress-strip-fill" style={{ width: `${pct}%` }} />
        </div>
        <p className="scene-meta">Updated {relativeTime(project.updated_at)}</p>
        <div className="row project-cover-actions">
          <Link to={`/project/${project.id}`}>
            <button type="button" className="primary">
              Continue
            </button>
          </Link>
          <div className="overflow-wrap" ref={menuRef}>
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={`More actions for ${project.name}`}
              onClick={() => setMenuOpen((v) => !v)}
            >
              •••
            </button>
            {menuOpen && (
              <div className="overflow-menu" role="menu">
                <Link to={`/project/${project.id}`} role="menuitem">
                  Open
                </Link>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onRename(project.id); }}>
                  Rename
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDuplicate(project.id); }}>
                  Duplicate
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onExport(project.id); }}>
                  Export
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onArchive(project.id); }}>
                  Archive
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="danger"
                  onClick={() => {
                    setMenuOpen(false);
                    onDelete(project.id);
                  }}
                >
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
