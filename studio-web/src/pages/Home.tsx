import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import type { Project } from "../types";
import { PROJECT_TEMPLATES, type ProductionType } from "../dashboardImages";
import { StudioChrome } from "../components/dashboard/StudioChrome";
import { SystemStatusStrip } from "../components/dashboard/StudioChrome";
import { CinematicHero, CinematicEmptyState } from "../components/dashboard/CinematicHero";
import { NewProductionCard, ProjectTemplateCard } from "../components/dashboard/NewProductionCard";
import { ProjectCoverCard } from "../components/dashboard/ProjectCoverCard";
import {
  CoDirectorComposer,
  WorkspaceFeatureCard,
} from "../components/dashboard/DashboardCards";
import { dashboardImages } from "../dashboardImages";
import { useOpenCoDirector } from "../components/CoDirector";
import { loadRecentProjects, type EditorTab } from "../workspacePrefs";

type StatusFilter = "All" | "Active" | "Rendering" | "Complete";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [view, setView] = useState<"grid" | "list">("grid");
  const navigate = useNavigate();
  const openCoDirector = useOpenCoDirector();

  const mountedRef = useRef(true);
  const refreshAcRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      refreshAcRef.current?.abort();
    };
  }, []);

  const refresh = async () => {
    refreshAcRef.current?.abort();
    const ac = new AbortController();
    refreshAcRef.current = ac;
    try {
      const p = await api.listProjects({ signal: ac.signal });
      if (!mountedRef.current || ac.signal.aborted) return;
      setProjects(p);
    } catch (error) {
      if (isAbortError(error) || ac.signal.aborted || !mountedRef.current) return;
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current || ac.signal.aborted) return;
      }
      throw error;
    }
  };

  useEffect(() => {
    refresh().catch(async (error: unknown) => {
      if (isAbortError(error) || !mountedRef.current) return;
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current) return;
      }
      console.error(error);
    });
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return projects.filter((p) => {
      const status = p.status_label || "Active";
      if (statusFilter !== "All" && status !== statusFilter) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        (p.description || "").toLowerCase().includes(q) ||
        (p.tags_json || "").toLowerCase().includes(q)
      );
    });
  }, [projects, query, statusFilter]);

  const createWithDefaults = async (opts: {
    name: string;
    type: ProductionType;
    aspect?: string;
    resolution?: string;
    fps?: number | "auto";
    storyboard_style?: string;
  }) => {
    setBusy(true);
    try {
      const p = await api.createProject(opts.name);
      const tags = JSON.stringify([opts.type]);
      const defaults = JSON.stringify({
        production_type: opts.type,
        aspect: opts.aspect || "16:9",
        resolution: opts.resolution || "1080p",
        fps: opts.fps ?? "auto",
        storyboard_style: opts.storyboard_style || "Pencil storyboard",
      });
      await api.updateProject(p.id, {
        tags_json: tags,
        defaults_json: defaults,
        description: `${opts.type} production`,
      } as any);
      navigate(`/project/${p.id}`);
    } finally {
      setBusy(false);
    }
  };

  const exploreItems: {
    title: string;
    description: string;
    image: (typeof dashboardImages)[keyof typeof dashboardImages];
    tab: EditorTab;
  }[] = [
    { title: "Director", description: "Build timed prompts, camera direction, and model-ready sequences.", image: dashboardImages.director, tab: "director" },
    { title: "Editor", description: "Assemble approved sequences into complete scenes.", image: dashboardImages.director, tab: "editor" },
    { title: "Script / Storyboard", description: "Write scenes and board panels before you shoot.", image: dashboardImages.script, tab: "script" },
    { title: "Spatial Map", description: "Block cameras, characters, and continuity.", image: dashboardImages.spatial, tab: "spatial" },
    { title: "ImageGen", description: "Create stills, keyframes, and references.", image: dashboardImages.imagegen, tab: "imagegen" },
    { title: "Txt2Vid", description: "Generate motion clips from prompts.", image: dashboardImages.video, tab: "txt2vid" },
    {
      title: "Avatar Studio",
      description: "Talking characters, presenters, and guided lip sync from Character Profiles.",
      image: dashboardImages.avatar,
      tab: "avatar",
    },
    { title: "Library", description: "Browse assets, tags, and approved frames.", image: dashboardImages.library, tab: "library" },
  ];

  return (
    <div className="app-shell atmosphere">
      <StudioChrome
        variant="home"
        onOpenCoDirector={() => openCoDirector()}
        onSetup={async () => {
          // Setup Wizard is a ProjectEditor workspace, not a standalone route.
          const recent = loadRecentProjects().find((r) => projects.some((p) => p.id === r.id));
          let id = recent?.id ?? projects[0]?.id;
          if (!id) {
            setBusy(true);
            try {
              const p = await api.createProject("Untitled Project");
              id = p.id;
            } finally {
              setBusy(false);
            }
          }
          navigate(`/project/${id}?workspace=setup`);
        }}
      />
      <main className="studio-page">
        <CinematicHero
          onCreate={() => document.getElementById("new-production")?.scrollIntoView({ behavior: "smooth" })}
          onOpenExisting={() => document.getElementById("projects-library")?.scrollIntoView({ behavior: "smooth" })}
        />

        <NewProductionCard busy={busy} onCreate={createWithDefaults} />

        <section id="templates">
          <h2 className="section-heading">Project templates</h2>
          <p className="muted">Start with a production shape — no fake inventory, just defaults that fit the film.</p>
          <div className="template-grid">
            {PROJECT_TEMPLATES.map((t) => (
              <ProjectTemplateCard
                key={t.id}
                title={t.title}
                description={t.description}
                imageMotif={t.image.motif}
                imageSrc={t.image.src}
                imageAlt={t.image.alt}
                busy={busy}
                onUse={() =>
                  createWithDefaults({
                    name: t.title,
                    type: t.type,
                    ...t.defaults,
                  })
                }
              />
            ))}
          </div>
        </section>

        <section id="projects-library">
          <h2 className="section-heading">Projects</h2>
          <div className="library-toolbar">
            <input
              aria-label="Search projects"
              placeholder="Search projects…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="filter-chips" role="group" aria-label="Status filter">
              {(["All", "Active", "Rendering", "Complete"] as StatusFilter[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={statusFilter === s ? "primary" : ""}
                  onClick={() => setStatusFilter(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="view-toggle" role="group" aria-label="View mode">
              <button type="button" className={view === "grid" ? "primary" : ""} onClick={() => setView("grid")}>
                Grid
              </button>
              <button type="button" className={view === "list" ? "primary" : ""} onClick={() => setView("list")}>
                List
              </button>
            </div>
          </div>
          {!filtered.length ? (
            <CinematicEmptyState
              title="No projects yet"
              body="Create a production above or use a template to open your first command center."
              actionLabel="Create Project"
              onAction={() => document.getElementById("new-production")?.scrollIntoView({ behavior: "smooth" })}
            />
          ) : (
            <div className={`project-library-grid ${view}`}>
              {filtered.map((p) => (
                <ProjectCoverCard
                  key={p.id}
                  view={view}
                  project={{
                    id: p.id,
                    name: p.name,
                    description: p.description,
                    engine_default: p.engine_default,
                    updated_at: p.updated_at,
                    scene_count: p.scene_count ?? p.scenes?.length ?? 0,
                    asset_count: p.asset_count ?? p.assets?.length ?? 0,
                    render_pct: p.render_pct ?? 0,
                    status: p.status_label || "Active",
                    cover_url: p.cover_asset_id ? api.assetUrl(p.cover_asset_id) : null,
                    width: p.width,
                    height: p.height,
                  }}
                  onRename={async (id) => {
                    const next = window.prompt("Rename project", projects.find((x) => x.id === id)?.name || "");
                    if (!next?.trim()) return;
                    await api.updateProject(id, { name: next.trim() });
                    refresh();
                  }}
                  onDuplicate={async (id) => {
                    await api.duplicateProject(id);
                    refresh();
                  }}
                  onExport={async (id) => {
                    try {
                      await api.exportProject(id);
                      alert("Export job queued.");
                    } catch (e) {
                      alert(e instanceof Error ? e.message : String(e));
                    }
                  }}
                  onArchive={async (id) => {
                    if (!window.confirm("Archive this project? It will hide from the library.")) return;
                    await api.archiveProject(id, true);
                    refresh();
                  }}
                  onDelete={async (id) => {
                    if (!window.confirm("Delete this project permanently?")) return;
                    await api.deleteProject(id);
                    refresh();
                  }}
                />
              ))}
            </div>
          )}
        </section>

        <section id="explore">
          <h2 className="section-heading">Explore Adept UI</h2>
          <p className="muted">Open a workspace — creates a project first if you need one.</p>
          <div className="explore-grid">
            {exploreItems.map((item) => (
              <WorkspaceFeatureCard
                key={item.title}
                title={item.title}
                description={item.description}
                image={item.image}
                status="Continue"
                onContinue={async () => {
                  let id = projects[0]?.id;
                  if (!id) {
                    setBusy(true);
                    try {
                      const p = await api.createProject("Untitled Project");
                      id = p.id;
                    } finally {
                      setBusy(false);
                    }
                  }
                  navigate(`/project/${id}?tab=${item.tab}`);
                }}
              />
            ))}
          </div>
        </section>

        <div className="home-system-block dash-card">
          <h2 className="section-heading">System Status</h2>
          <SystemStatusStrip />
        </div>

        <CoDirectorComposer onSubmit={(text) => openCoDirector(text)} />
      </main>
    </div>
  );
}
