import { useEffect, useMemo, useState } from "react";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";
import { loadLastWorkspace } from "../workspacePrefs";
import { dashboardImages, relativeTime } from "../dashboardImages";
import { CinematicEmptyState } from "./dashboard/CinematicHero";
import {
  ActivityFeed,
  CoDirectorBriefing,
  ContinueProductionCard,
  ProductionHealthPanel,
  ProductionStatCard,
  RecentAssetCard,
  RenderJobCard,
  WorkspaceFeatureCard,
} from "./dashboard/DashboardCards";

const TAB_LABELS: Partial<Record<EditorTab, string>> = {
  director: "Director",
  editor: "Editor",
  audiostudio: "Audio Studio",
  script: "Script / Storyboard",
  spatial: "Spatial Map",
  imagegen: "ImageGen",
  txt2vid: "Txt2Vid",
  library: "Library",
  mastersheet: "Scene Master Sheet",
  avatar: "Avatar Studio",
  home: "Project Home",
};

export function ProjectHome({
  project,
  onGo,
  onRefresh,
  onAskCoDirector,
}: {
  project: Project;
  onGo: (tab: EditorTab) => void;
  onRefresh: () => Promise<void>;
  onAskCoDirector?: (prompt?: string) => void;
}) {
  const [dash, setDash] = useState<any>(null);

  useEffect(() => {
    const ac = new AbortController();
    api
      .projectDashboard(project.id, { signal: ac.signal })
      .then((next) => {
        if (!ac.signal.aborted) setDash(next);
      })
      .catch(async (error: unknown) => {
        if (isAbortError(error) || ac.signal.aborted) return;
        if (isNavigationFetchFailure(error)) {
          await new Promise((resolve) => window.setTimeout(resolve, 0));
          if (ac.signal.aborted) return;
        }
        console.error(error);
      });
    return () => ac.abort();
  }, [project.id, project.updated_at]);

  const counts = dash?.counts || {};
  const progress = dash?.progress || { pct: 0 };
  const coverUrl = dash?.cover_asset_id ? api.assetUrl(dash.cover_asset_id) : null;
  const lastTab = loadLastWorkspace(project.id) || "director";
  const lastLabel = TAB_LABELS[lastTab] || "Director";
  const status = project.status_label || "Active";

  const suggestionItems = useMemo(() => {
    const raw = dash?.suggestions || [];
    return raw.map((s: any, i: number) => ({
      id: String(s.id || i),
      text: String(s.text || s.message || JSON.stringify(s)),
    }));
  }, [dash]);

  const activityItems = useMemo(() => {
    const raw = dash?.activity || [];
    return raw.map((a: any) => ({
      id: String(a.id),
      when: relativeTime(a.when),
      text: String(a.text || a.message || a.kind),
    }));
  }, [dash]);

  const workspaces: {
    title: string;
    description: string;
    image: (typeof dashboardImages)[keyof typeof dashboardImages];
    tab: EditorTab;
  }[] = [
    { title: "Director", description: "Build timed prompts, camera direction, and model-ready sequences.", image: dashboardImages.director, tab: "director" },
    { title: "Editor", description: "Assemble approved sequences into complete scenes.", image: dashboardImages.director, tab: "editor" },
    { title: "Script / Storyboard", description: "Write scenes and board panels.", image: dashboardImages.script, tab: "script" },
    { title: "Spatial Map", description: "Block cameras and continuity.", image: dashboardImages.spatial, tab: "spatial" },
    { title: "ImageGen", description: "Stills, keyframes, references.", image: dashboardImages.imagegen, tab: "imagegen" },
    { title: "Txt2Vid", description: "Motion clips from prompts.", image: dashboardImages.video, tab: "txt2vid" },
    {
      title: "Avatar Studio",
      description: "Talking portraits and cinematic dialogue with lip sync.",
      image: dashboardImages.avatar,
      tab: "avatar",
    },
    { title: "Library", description: "Assets and approved frames.", image: dashboardImages.library, tab: "library" },
  ];

  const continueBullets = [
    dash?.last_scene_name ? `Last scene: ${dash.last_scene_name}` : "No scenes yet — start in Script or ImageGen.",
    suggestionItems[0]?.text || "Ask Co-Director for the next production step.",
    `${progress.scenes_with_output || 0}/${progress.scenes_total || 0} scenes with output`,
  ];

  return (
    <div className="studio-page project-dashboard">
      <section className="project-dash-hero" aria-label={`${project.name} cover`}>
        <div className="cinematic-media motif-set">
          <div className="cinematic-media-fallback" aria-hidden="true" />
          {coverUrl && (
            <img
              src={coverUrl}
              alt=""
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = "none";
              }}
            />
          )}
          <div className="cinematic-media-overlay" />
        </div>
        <div className="project-dash-hero-inner">
          <span className="status-badge">{status}</span>
          <h1>{project.name}</h1>
          <p>{project.description || "Production command center"}</p>
          <div className="progress-strip" aria-label={`Timeline progress ${progress.pct || 0}%`}>
            <div className="progress-strip-fill" style={{ width: `${progress.pct || 0}%` }} />
          </div>
          <p className="scene-meta" style={{ color: "rgba(255,255,255,0.85)" }}>
            Scenes rendered {progress.scenes_with_output || 0}/{progress.scenes_total || 0}
          </p>
          <div className="project-dash-actions">
            <button type="button" className="primary" onClick={() => onGo(lastTab === "home" ? "director" : lastTab)}>
              Continue Production
            </button>
            <button type="button" onClick={() => onAskCoDirector?.("What should we do next on this production?")}>
              Ask Co-Director
            </button>
            <button type="button" onClick={() => onGo("director")}>
              View Timeline
            </button>
          </div>
        </div>
      </section>

      <div className="stat-row">
        <ProductionStatCard value={counts.scenes ?? project.scenes?.length ?? 0} label="Scenes" />
        <ProductionStatCard value={counts.assets ?? project.assets?.length ?? 0} label="Assets" />
        <ProductionStatCard value={counts.images ?? "—"} label="Images" />
        <ProductionStatCard value={counts.videos ?? "—"} label="Videos" />
        <ProductionStatCard value={`${progress.pct || 0}%`} label="Timeline" highlight />
      </div>

      <ContinueProductionCard
        title={lastLabel}
        subtitle={`Resume in ${lastLabel}${dash?.last_scene_name ? ` · ${dash.last_scene_name}` : ""}`}
        bullets={continueBullets}
        onContinue={() => onGo(lastTab === "home" ? "director" : lastTab)}
        imageSrc={coverUrl}
      />

      <div className="project-dash-grid">
        <CoDirectorBriefing
          items={suggestionItems}
          onAsk={() => onAskCoDirector?.()}
          onPrimary={() => onGo("imagegen")}
          primaryLabel="Generate"
        />
        <ProductionHealthPanel items={dash?.health || []} onReview={() => onGo("settings")} />
      </div>

      <h2 className="section-heading">Workspaces</h2>
      <div className="workspace-feature-grid">
        {workspaces.map((w) => (
          <WorkspaceFeatureCard
            key={w.title}
            title={w.title}
            description={w.description}
            image={w.image}
            status="Continue"
            onContinue={() => onGo(w.tab)}
          />
        ))}
      </div>

      <div className="project-dash-grid">
        <section className="dash-card">
          <h2>Recent assets</h2>
          {!dash?.recent_assets?.length ? (
            <CinematicEmptyState
              title="No assets yet"
              body="Generate stills or import references — they’ll show up here."
              actionLabel="Open ImageGen"
              onAction={() => onGo("imagegen")}
            />
          ) : (
            <div className="recent-assets-strip">
              {dash.recent_assets.map((a: any) => (
                <RecentAssetCard
                  key={a.id}
                  name={a.tag || a.filename || "Asset"}
                  kind={a.kind || "file"}
                  thumb={a.id ? api.assetUrl(a.id) : undefined}
                  meta={a.kind}
                  onOpen={() => onGo("library")}
                />
              ))}
            </div>
          )}
        </section>
        <section className="dash-card">
          <h2>Render jobs</h2>
          {!dash?.recent_jobs?.length ? (
            <CinematicEmptyState
              title="No jobs yet"
              body="Queue a render from Director, ImageGen, or Txt2Vid."
              actionLabel="Open Director"
              onAction={() => onGo("director")}
            />
          ) : (
            <div className="render-jobs-panel">
              {dash.recent_jobs.slice(0, 5).map((j: any) => (
                <RenderJobCard
                  key={j.id}
                  title={j.kind}
                  status={j.status}
                  progress={typeof j.progress === "number" ? j.progress : 0}
                  message={j.message}
                  onOpen={() => onGo("director")}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      <div className="project-dash-grid">
        <ActivityFeed items={activityItems} />
        <section className="dash-card">
          <h2>Scene Master Sheets</h2>
          <p className="muted" style={{ marginBottom: "0.75rem" }}>
            Structured whole-scene packages — what exists in the scene (not a collage).
          </p>
          <button type="button" className="primary" onClick={() => onGo("mastersheet")}>
            Open Scene Master Sheet
          </button>
          <button type="button" style={{ marginLeft: "0.4rem" }} onClick={() => onGo("library")}>
            Browse in Library
          </button>
        </section>
      </div>

      <p className="scene-meta" style={{ marginTop: "1rem" }}>
        Updated {relativeTime(project.updated_at)} · refresh after generates
        <button type="button" className="ghost" style={{ marginLeft: 8 }} onClick={() => void onRefresh()}>
          Refresh
        </button>
      </p>
    </div>
  );
}
