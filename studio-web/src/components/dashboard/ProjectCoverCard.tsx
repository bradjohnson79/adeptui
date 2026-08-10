import { useEffect, useRef, useState } from "react";
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
  cover_kind?: "image" | "video" | null;
  width?: number;
  height?: number;
  password_protected?: boolean;
  password_locked?: boolean;
};

const COVER_MOTIFS = [
  {
    key: "clapboard",
    src: "/images/ui/motifs/cover-clapboard.svg",
    alt: "Film clapboard on a teal and amber cinematic gradient",
    plate: "motif-set",
  },
  {
    key: "camera",
    src: "/images/ui/motifs/cover-camera.svg",
    alt: "Cinema camera on a deep blue and teal cinematic gradient",
    plate: "motif-director",
  },
  {
    key: "screenplay",
    src: "/images/ui/motifs/cover-screenplay.jpg",
    alt: "Screenplay title page on a warm cinematic gradient",
    plate: "motif-script",
  },
] as const;

function motifForProject(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return COVER_MOTIFS[hash % COVER_MOTIFS.length];
}

export function ProjectCoverCard({
  project,
  view = "grid",
  active = false,
  onOpen,
  onRename,
  onDuplicate,
  onExport,
  onPasswordProtect,
  onManagePassword,
  onLockNow,
  onArchive,
  onDelete,
}: {
  project: ProjectCardModel;
  view?: "grid" | "list";
  active?: boolean;
  onOpen: (id: string) => void;
  onRename: (id: string) => void;
  onDuplicate: (id: string) => void;
  onExport: (id: string) => void;
  onPasswordProtect: (id: string) => void;
  onManagePassword: (id: string) => void;
  onLockNow?: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [coverFailed, setCoverFailed] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const pct = Math.max(0, Math.min(100, project.render_pct ?? 0));
  const status = project.status || "Active";
  const motif = motifForProject(project.id);
  const protectedProj = Boolean(project.password_protected);
  const locked = Boolean(project.password_locked);
  const showMotif = locked || !project.cover_url || coverFailed;
  const isVideo = project.cover_kind === "video";

  useEffect(() => {
    setCoverFailed(false);
  }, [project.cover_url]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  return (
    <article
      className={`dash-card project-cover-card ${view} ${active ? "active" : ""}`}
      data-testid={`project-card-${project.id}`}
      data-active-project={active ? "true" : "false"}
      data-password-protected={protectedProj ? "true" : "false"}
      data-password-locked={locked ? "true" : "false"}
    >
      <button
        type="button"
        className="project-cover-link"
        aria-label={locked ? `Unlock ${project.name}` : `Open ${project.name}`}
        onClick={() => onOpen(project.id)}
        style={{ display: "block", width: "100%", border: 0, padding: 0, background: "transparent", cursor: "pointer", textAlign: "left" }}
      >
        <div className={`cinematic-media ${motif.plate} project-cover-media`}>
          <div className="cinematic-media-fallback" aria-hidden="true" />
          {showMotif ? (
            <img src={motif.src} alt={motif.alt} className="project-cover-motif" loading="lazy" />
          ) : isVideo ? (
            <video
              className="project-cover-motif"
              src={project.cover_url!}
              muted
              playsInline
              loop
              autoPlay
              preload="metadata"
              aria-label={`Video still for ${project.name}`}
              onError={() => setCoverFailed(true)}
            />
          ) : (
            <img
              src={project.cover_url!}
              alt={`Cover image for ${project.name}`}
              loading="lazy"
              onError={() => setCoverFailed(true)}
            />
          )}
          <div className="cinematic-media-overlay" />
          <span className={`status-badge top-badge ${status === "Rendering" ? "warn" : status === "Complete" ? "ok" : ""}`}>
            {status}
          </span>
          {protectedProj && (
            <span className="status-badge" data-testid="project-lock-badge" style={{ left: "0.5rem", right: "auto", top: "0.5rem" }}>
              🔒 Password Protected
            </span>
          )}
        </div>
      </button>
      <div className="project-cover-body">
        {active ? (
          <span className="project-cover-active-badge" data-testid="project-active-badge">
            Active Project
          </span>
        ) : null}
        <h3>{project.name}</h3>
        <p className="muted">
          {locked
            ? "Protected project"
            : project.description?.slice(0, 80) || `${project.width || 1280}×${project.height || 720}`}
        </p>
        <p className="scene-meta">
          {locked
            ? `${(project.engine_default || "minimax-h3").toUpperCase()} · protected`
            : `${project.scene_count ?? 0} scenes · ${project.asset_count ?? 0} assets · ${(project.engine_default || "minimax-h3").toUpperCase()}`}
        </p>
        {!locked && (
          <div
            className="progress-strip"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-label={`Render progress ${pct}%`}
          >
            <div className="progress-strip-fill" style={{ width: `${pct}%` }} aria-hidden="true" />
          </div>
        )}
        <p className="scene-meta">Updated {relativeTime(project.updated_at)}</p>
        <div className="row project-cover-actions">
          <button type="button" className="primary" data-testid="project-continue" onClick={() => onOpen(project.id)}>
            {locked ? "Unlock" : "Continue"}
          </button>
          <div className="overflow-wrap" ref={menuRef}>
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={`More actions for ${project.name}`}
              data-testid="project-menu-button"
              onClick={() => setMenuOpen((v) => !v)}
            >
              •••
            </button>
            {menuOpen && (
              <div className="overflow-menu" role="menu" data-testid="project-overflow-menu">
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onOpen(project.id); }}>
                  Open
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onRename(project.id); }}>
                  Rename
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onDuplicate(project.id); }}>
                  Duplicate
                </button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onExport(project.id); }}>
                  Export
                </button>
                {protectedProj ? (
                  <>
                    <button
                      type="button"
                      role="menuitem"
                      data-testid="project-menu-manage-password"
                      onClick={() => {
                        setMenuOpen(false);
                        onManagePassword(project.id);
                      }}
                    >
                      Manage Password Protection
                    </button>
                    {onLockNow && (
                      <button
                        type="button"
                        role="menuitem"
                        data-testid="project-menu-lock-now"
                        onClick={() => {
                          setMenuOpen(false);
                          onLockNow(project.id);
                        }}
                      >
                        Lock Project Now
                      </button>
                    )}
                  </>
                ) : (
                  <button
                    type="button"
                    role="menuitem"
                    data-testid="project-menu-password-protect"
                    onClick={() => {
                      setMenuOpen(false);
                      onPasswordProtect(project.id);
                    }}
                  >
                    Password Protect
                  </button>
                )}
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onArchive(project.id); }}>
                  Archive
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="danger"
                  data-testid="project-menu-delete"
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
