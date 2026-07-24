import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import type { Project } from "../types";
import { CoDirectorProvider } from "../core/CoDirectorContext";
import { workspaceLabel } from "../core/workspaces";
import { Timeline } from "../components/Timeline";
import { AssetTray, PromptComposer } from "../components/AssetTray";
import { AdvancedPanel, JobPanel } from "../components/JobPanel";
import { GpuVramPanel } from "../components/GpuVramPanel";
import { SpatialSceneWorkspace } from "../components/SpatialSceneWorkspace";
import { ScriptStoryboardWorkspace } from "../components/ScriptStoryboardWorkspace";
import { useBindCoDirectorWorkspace, useOpenCoDirector } from "../components/CoDirector";
import { ImageToolsPanel } from "../components/ImageTools";
import { DirectorTracks } from "../components/DirectorTracks";
import { OneFramePanel, ThreeFramePanel } from "../components/FrameModes";
import { DirectorSelectionProvider, useDirectorSelection } from "../components/DirectorSelectionContext";
import { ContextInspector } from "../components/ContextInspector";
import { GenerateTimelinePanel } from "../components/GenerateTimelinePanel";
import { LipSyncTracksPanel } from "../components/LipSyncTracks";
import { SetupWizardPanel } from "../components/SetupWizard";
import { ProfilesWorkspace } from "../components/ProfilesWorkspace";
import { LivePreviewMonitor } from "../components/LivePreviewMonitor";
import { ProjectMenu } from "../components/ProjectMenu";
import { ProjectHome } from "../components/ProjectHome";
import { ProjectSettings } from "../components/ProjectSettings";
import { Txt2VidPanel } from "../components/Txt2VidPanel";
import { ImageGenPanel } from "../components/ImageGenPanel";
import { LibraryPanel } from "../components/LibraryPanel";
import { MarketplacePanel } from "../components/MarketplacePanel";
import { SceneMasterSheetWorkspace } from "../components/SceneMasterSheetWorkspace";
import { AvatarStudioWorkspace } from "../components/AvatarStudioWorkspace";
import { EditorWorkspace, readEditorialContext } from "../components/EditorWorkspace";
import { AudioStudioWorkspace } from "../components/AudioStudioWorkspace";
import { ProductionBibleWorkspace } from "../components/ProductionBibleWorkspace";
import { StudioChrome as AppStudioChrome } from "../components/dashboard/StudioChrome";
import { continuityLockedCount } from "../directorSelection";
import {
  type EditorTab,
  loadLastWorkspace,
  pushRecentProject,
  resolveWorkspace,
  saveLastWorkspace,
} from "../workspacePrefs";

function DirectorWorkspaceShell({
  project,
  selectedScene,
  setSelectedScene,
  tab,
  refresh,
  onGoEditor,
}: {
  project: Project;
  selectedScene?: string;
  setSelectedScene: (id: string) => void;
  tab: "one" | "three" | "director";
  refresh: () => Promise<void>;
  onGoEditor?: () => void;
}) {
  const { workspaceTab, setWorkspaceTab, setSelection, clearSelection } = useDirectorSelection();
  const [centerView, setCenterView] = useState<"monitor" | "tracks">(() => {
    try {
      const v = localStorage.getItem("adept_director_center_view");
      return v === "tracks" ? "tracks" : "monitor";
    } catch {
      return "monitor";
    }
  });
  const [editorialNote, setEditorialNote] = useState<string | null>(null);
  const selected = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
  const cont = continuityLockedCount(selected?.continuity_json);
  const sceneW = selected?.width || project.width;
  const sceneH = selected?.height || project.height;
  const sceneFps =
    selected?.fps_mode && selected.fps_mode !== "auto" && selected.fps
      ? selected.fps
      : project.fps;

  useEffect(() => {
    try {
      localStorage.setItem("adept_director_center_view", centerView);
    } catch {
      /* ignore */
    }
  }, [centerView]);

  useEffect(() => {
    const ctx = readEditorialContext();
    if (!ctx) {
      setEditorialNote(null);
      return;
    }
    const bits = [
      ctx.needed_duration_sec != null ? `${ctx.needed_duration_sec}s needed` : null,
      ctx.prev_clip_label ? `after “${ctx.prev_clip_label}”` : null,
      ctx.next_clip_label ? `before “${ctx.next_clip_label}”` : null,
      ctx.screen_direction || null,
      ctx.required_ending ? `ending: ${ctx.required_ending}` : null,
    ].filter(Boolean);
    setEditorialNote(bits.length ? `Editorial context: ${bits.join(" · ")}` : "Editorial context loaded for replacement");
  }, [selectedScene, tab]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) {
        return;
      }
      if (e.key === "Escape") clearSelection();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearSelection]);

  const showToggle = tab === "director";
  const showMonitor = !showToggle || centerView === "monitor";
  const showTracks = showToggle && centerView === "tracks";

  return (
    <div className="director-shell">
      <aside className="shell-pane shell-left">
        <AssetTray project={project} onChange={refresh} />
        <Timeline
          project={project}
          selectedId={selectedScene}
          onSelect={(id) => {
            setSelectedScene(id);
            setSelection({ kind: "scene", id });
          }}
          onChange={refresh}
        />
        <AdvancedPanel project={project} onChange={refresh} />
      </aside>

      <main className={`shell-pane shell-main ${showToggle ? "shell-main-switched" : ""}`}>
        {showToggle && (
          <div className="director-view-toggle" role="group" aria-label="Director center view">
            <button
              type="button"
              className={centerView === "monitor" ? "primary" : ""}
              aria-pressed={centerView === "monitor"}
              onClick={() => setCenterView("monitor")}
            >
              Director Monitor
            </button>
            <button
              type="button"
              className={centerView === "tracks" ? "primary" : ""}
              aria-pressed={centerView === "tracks"}
              onClick={() => setCenterView("tracks")}
            >
              Prompt Timeline
            </button>
          </div>
        )}

        {editorialNote && tab === "director" && (
          <div className="pill" style={{ margin: "0.5rem 1rem" }}>
            {editorialNote}
          </div>
        )}

        {showMonitor && (
          <div className="director-center-pane director-monitor-pane">
            {tab === "director" && (
              <p className="scene-meta" style={{ margin: "0 0 0.35rem", letterSpacing: "0.04em", textTransform: "uppercase", fontSize: "0.7rem" }}>
                Prompt Timeline · Monitor
              </p>
            )}
            <LivePreviewMonitor project={project} scene={selected} />
            {tab === "director" && selected && (
              <div className="timeline-header-badges">
                <span className="pill">{selected.name}</span>
                <span className="pill">{selected.engine === "auto" ? "Auto" : selected.engine}</span>
                <span className="pill">{selected.duration_sec}s</span>
                <span className="pill">{selected.aspect_ratio || "16:9"}</span>
                <span className="pill">
                  {sceneW}×{sceneH}
                </span>
                <span className="pill">
                  {selected.fps_mode === "auto" ? "Auto fps" : `${sceneFps} fps`}
                </span>
                <span className="pill">{project.vram_gb || 32} GB</span>
                <span className="pill">
                  Continuity {cont.locked}/{cont.total}
                </span>
              </div>
            )}
            {tab === "director" && selected && (selected.output_path || selected.lipsync_output_path) && (
              <div className="row-actions" style={{ margin: "0.5rem 0", flexWrap: "wrap" }}>
                <span className="scene-meta">Send to Editor</span>
                <button
                  type="button"
                  className="primary"
                  onClick={async () => {
                    const seq = await api.directorSequenceFromScene(project.id, {
                      scene_id: selected.id,
                      name: `${selected.name} · Monitor shot`,
                      status: "approved",
                      include_audio: true,
                    });
                    await api.patchDirectorSequence(project.id, seq.id, { approve: true });
                    await api.sendDirectorToEditor(project.id, seq.id, {
                      track: "video",
                      include_audio: true,
                      label: seq.name,
                    });
                    onGoEditor?.();
                  }}
                >
                  Current shot / approved variation
                </button>
              </div>
            )}
            {tab === "one" && <OneFramePanel project={project} scene={selected} onChange={refresh} />}
            {tab === "three" && <ThreeFramePanel project={project} scene={selected} onChange={refresh} />}
            {tab !== "director" && (
              <PromptComposer project={project} sceneId={selectedScene} onChange={refresh} />
            )}
          </div>
        )}

        {showTracks && (
          <div className="director-center-pane director-tracks-pane">
            <div className="workspace-tabs" role="tablist">
              {(
                [
                  ["timeline", "Timeline"],
                  ["prompt", "Prompt"],
                  ["lipsync", "Lip Sync"],
                  ["settings", "Scene Settings"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={workspaceTab === id}
                  className={workspaceTab === id ? "primary" : ""}
                  onClick={() => setWorkspaceTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>

            {(workspaceTab === "timeline" || workspaceTab === "prompt") && (
              <DirectorTracks
                project={project}
                scene={selected}
                onChange={refresh}
                viewMode={workspaceTab === "prompt" ? "prompt" : "tracks"}
                onGoEditor={onGoEditor}
              />
            )}
            {workspaceTab === "lipsync" && selected && (
              <LipSyncTracksPanel project={project} scene={selected} onChange={onChangeSafe(refresh)} />
            )}
            {workspaceTab === "settings" && (
              <PromptComposer project={project} sceneId={selectedScene} onChange={refresh} showContinuity />
            )}
          </div>
        )}
      </main>

      <aside className="shell-pane shell-right">
        <ContextInspector project={project} scene={selected} onChange={refresh} />
        <JobPanel projectId={project.id} onDone={refresh} />
        <GpuVramPanel project={project} onChange={refresh} />
      </aside>
    </div>
  );
}

function onChangeSafe(refresh: () => Promise<void>) {
  return () => {
    void refresh();
  };
}

export default function ProjectEditor() {
  const { id } = useParams();
  const { search: locationSearch } = useLocation();
  const [project, setProject] = useState<Project | null>(null);
  const [selectedScene, setSelectedScene] = useState<string>();
  const [tab, setTab] = useState<EditorTab>("home");
  const [workspaceProjectId, setWorkspaceProjectId] = useState<string>();
  const [menuOpen, setMenuOpen] = useState(false);
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);
  const [search, setSearch] = useState("");
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

  const refresh = useCallback(async () => {
    if (!id) return;
    refreshAcRef.current?.abort();
    const ac = new AbortController();
    refreshAcRef.current = ac;
    try {
      const p = await api.getProject(id, { signal: ac.signal });
      if (!mountedRef.current || ac.signal.aborted) return;
      setProject(p);
      setSelectedScene((prev) => prev || p.scenes[0]?.id);
      pushRecentProject(p.id, p.name);
    } catch (error) {
      if (isAbortError(error) || ac.signal.aborted || !mountedRef.current) return;
      // Navigation can reject as TypeError before React cleanup aborts the signal.
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current || ac.signal.aborted) return;
      }
      throw error;
    }
  }, [id]);

  useEffect(() => {
    refresh().catch(async (error: unknown) => {
      if (isAbortError(error) || !mountedRef.current) return;
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current) return;
      }
      console.error(error);
    });
  }, [refresh]);

  useEffect(() => {
    if (!id) return;
    const query = new URLSearchParams(locationSearch);
    const requested = resolveWorkspace(query.get("workspace") ?? query.get("tab"));
    const last = loadLastWorkspace(id);
    // First open / no history → Project Home
    setTab(requested || last || "home");
    setWorkspaceProjectId(id);
  }, [id, locationSearch]);

  useEffect(() => {
    if (!id || workspaceProjectId !== id) return;
    saveLastWorkspace(id, tab);
  }, [id, tab, workspaceProjectId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) {
        return;
      }
      if (e.key === "Escape") {
        setMenuOpen(false);
        setProjectMenuOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!project) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            Adept <span>UI Generation Studio</span>
          </div>
        </header>
        <p className="empty">Loading project…</p>
      </div>
    );
  }

  const applyPrompt = async (prompt: string) => {
    const scene = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
    if (!scene) return;
    await api.updateScene(project.id, scene.id, { ...scene, prompt });
    await refresh();
  };

  const go = (next: string) => {
    const resolved = resolveWorkspace(next);
    if (!resolved) return;
    setTab(resolved);
    setMenuOpen(false);
    setProjectMenuOpen(false);
  };

  const showDirectorShell = tab === "one" || tab === "three" || tab === "director";
  // Viewport-locked shell only for multi-pane app layouts; document pages use native window scroll.
  const lockViewportShell = showDirectorShell || tab === "spatial";

  const runSearch = () => {
    const q = search.trim().toLowerCase();
    if (!q) return;
    if (q.includes("image")) go("imagegen");
    else if (q.includes("txt") || q.includes("text")) go("txt2vid");
    else if (q.includes("director")) go("director");
    else if (q.includes("editor") || q.includes("assemble")) go("editor");
    else if (q.includes("audio")) go("audiostudio");
    else if (q.includes("bible")) go("bible");
    else if (q.includes("library") || q.includes("asset")) go("library");
    else if (q.includes("master")) go("mastersheet");
    else if (q.includes("avatar")) go("avatar");
    else if (q.includes("market") || q.includes("lora")) go("marketplace");
    else if (q.includes("setup")) go("setup");
    else if (q.includes("setting")) go("settings");
    else go("library");
  };

  const tabLabel = workspaceLabel(tab);
  const selectedSceneObj = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];

  return (
    <CoDirectorProvider
      value={{
        projectId: project.id,
        projectName: project.name,
        sceneId: selectedScene,
        sceneName: selectedSceneObj?.name,
        activeWorkspace: tab,
      }}
    >
      <ProjectCoDirectorBridge
        project={project}
        sceneId={selectedScene}
        sceneName={selectedSceneObj?.name}
        workspaceTab={tab}
        onGoTab={go}
        onApplyPrompt={applyPrompt}
        onAppliedSetup={refresh}
      />
      <div className={`app-shell atmosphere${lockViewportShell ? " app-shell-fixed" : ""}`}>
      <AppStudioChrome
        variant="project"
        projectName={project.name}
        workspaceLabel={tabLabel}
        projectId={project.id}
        onOpenCoDirector={() => openCoDirector()}
        onSetup={() => go("setup")}
        searchValue={search}
        onSearchChange={setSearch}
        onSearchSubmit={runSearch}
        leftExtra={
          <div className="project-dropdown-wrap">
            <button
              type="button"
              className="project-dropdown-btn"
              aria-expanded={projectMenuOpen}
              aria-haspopup="menu"
              onClick={() => {
                setProjectMenuOpen((v) => !v);
                setMenuOpen(false);
              }}
            >
              Project ▼ <span className="scene-meta">{project.name}</span>
            </button>
            <ProjectMenu
              project={project}
              open={projectMenuOpen}
              onClose={() => setProjectMenuOpen(false)}
              onGo={go}
              onRefresh={refresh}
            />
          </div>
        }
        rightExtra={
          <div className="hamburger-wrap">
            <button
              type="button"
              className="hamburger-btn"
              aria-expanded={menuOpen}
              aria-label="Generation Modes and workspaces"
              onClick={() => {
                setMenuOpen((v) => !v);
                setProjectMenuOpen(false);
              }}
            >
              ☰
            </button>
            {menuOpen && (
              <div className="hamburger-menu" role="menu">
                <div className="menu-group-label">Generation Modes</div>
                <button type="button" role="menuitem" className={tab === "imagegen" ? "primary" : ""} onClick={() => go("imagegen")}>
                  ImageGen
                </button>
                <button type="button" role="menuitem" className={tab === "one" ? "primary" : ""} onClick={() => go("one")}>
                  1 Frame
                </button>
                <button type="button" role="menuitem" className={tab === "txt2vid" ? "primary" : ""} onClick={() => go("txt2vid")}>
                  Txt2Vid
                </button>
                <button type="button" role="menuitem" className={tab === "three" ? "primary" : ""} onClick={() => go("three")}>
                  3 Frame
                </button>
                <button type="button" role="menuitem" className={tab === "avatar" ? "primary" : ""} onClick={() => go("avatar")}>
                  Avatar
                </button>
                <div className="menu-sep" />
                <div className="menu-group-label">Production</div>
                <button type="button" role="menuitem" className={tab === "director" ? "primary" : ""} onClick={() => go("director")}>
                  Director
                </button>
                <button type="button" role="menuitem" className={tab === "audiostudio" ? "primary" : ""} onClick={() => go("audiostudio")}>
                  Audio Studio
                </button>
                <button type="button" role="menuitem" className={tab === "editor" ? "primary" : ""} onClick={() => go("editor")}>
                  Editor
                </button>
                <button type="button" role="menuitem" className={tab === "mastersheet" ? "primary" : ""} onClick={() => go("mastersheet")}>
                  Scene Master Sheet
                </button>
                <button type="button" role="menuitem" className={tab === "bible" ? "primary" : ""} onClick={() => go("bible")}>
                  Production Bible
                </button>
                <div className="menu-sep" />
                <div className="menu-group-label">Assets</div>
                <button type="button" role="menuitem" className={tab === "profiles" ? "primary" : ""} onClick={() => go("profiles")}>
                  Profiles
                </button>
                <button type="button" role="menuitem" className={tab === "tools" ? "primary" : ""} onClick={() => go("tools")}>
                  Character / Angles
                </button>
                <button type="button" role="menuitem" className={tab === "library" ? "primary" : ""} onClick={() => go("library")}>
                  Libraries
                </button>
                <button type="button" role="menuitem" className={tab === "marketplace" ? "primary" : ""} onClick={() => go("marketplace")}>
                  Marketplace
                </button>
                <div className="menu-sep" />
                <div className="menu-group-label">Planning</div>
                <button type="button" role="menuitem" className={tab === "script" ? "primary" : ""} onClick={() => go("script")}>
                  Script / Storyboard
                </button>
                <button type="button" role="menuitem" className={tab === "spatial" ? "primary" : ""} onClick={() => go("spatial")}>
                  Spatial Map
                </button>
                <button type="button" role="menuitem" className={tab === "generate" ? "primary" : ""} onClick={() => go("generate")}>
                  Generate Timeline
                </button>
                <button type="button" role="menuitem" className={tab === "shotlist" ? "primary" : ""} onClick={() => go("shotlist")}>
                  Shot List
                </button>
                <button type="button" role="menuitem" className={tab === "home" ? "primary" : ""} onClick={() => go("home")}>
                  Project Home
                </button>
              </div>
            )}
          </div>
        }
      />

      {tab === "home" ? (
        <ProjectHome
          project={project}
          onGo={go}
          onRefresh={refresh}
          onAskCoDirector={(p) => openCoDirector(p)}
        />
      ) : tab === "mastersheet" ? (
        <SceneMasterSheetWorkspace
          project={project}
          sceneId={selectedScene}
          onChange={refresh}
          onGoSpatial={() => go("spatial")}
        />
      ) : tab === "avatar" ? (
        <AvatarStudioWorkspace project={project} onChange={refresh} onGo={go} />
      ) : tab === "editor" ? (
        <EditorWorkspace
          project={project}
          onChange={refresh}
          onGo={go}
          onSelectScene={setSelectedScene}
        />
      ) : tab === "audiostudio" ? (
        <AudioStudioWorkspace project={project} onChange={refresh} onGo={go} />
      ) : tab === "bible" ? (
        <ProductionBibleWorkspace project={project} onChange={refresh} />
      ) : tab === "settings" ? (
        <ProjectSettings project={project} onChange={() => void refresh()} />
      ) : tab === "setup" ? (
        <SetupWizardPanel />
      ) : tab === "profiles" ? (
        <ProfilesWorkspace onOpenAvatar={(profileId) => {
          go("avatar");
          // profile query handled via session bootstrap when user reopens; store hint
          try {
            sessionStorage.setItem("adept_avatar_profile", profileId);
          } catch {
            /* ignore */
          }
        }} />
      ) : tab === "imagegen" ? (
        <ImageGenPanel project={project} onChange={refresh} onGo={go} />
      ) : tab === "txt2vid" ? (
        <Txt2VidPanel project={project} onChange={refresh} onGo={go} />
      ) : tab === "library" ? (
        <LibraryPanel project={project} onChange={refresh} onGo={go} />
      ) : tab === "marketplace" ? (
        <MarketplacePanel project={project} />
      ) : showDirectorShell ? (
        <DirectorSelectionProvider>
          <DirectorWorkspaceShell
            project={project}
            selectedScene={selectedScene}
            setSelectedScene={setSelectedScene}
            tab={tab}
            refresh={refresh}
            onGoEditor={() => go("editor")}
          />
        </DirectorSelectionProvider>
      ) : tab === "tools" ? (
        <>
          <ImageToolsPanel project={project} onChange={refresh} />
          <div className="page" style={{ width: "min(1100px, calc(100% - 2rem))", paddingTop: 0 }}>
            <JobPanel projectId={project.id} onDone={refresh} />
            <div style={{ marginTop: "1rem" }}>
              <GpuVramPanel project={project} onChange={refresh} />
            </div>
          </div>
        </>
      ) : tab === "generate" ? (
        <div className="page generate-page">
          <GenerateTimelinePanel
            project={project}
            onChange={refresh}
            onOpenDirector={() => go("director")}
          />
        </div>
      ) : tab === "spatial" ? (
        <SpatialSceneWorkspace
          project={project}
          scene={project.scenes.find((s) => s.id === selectedScene) || project.scenes[0]}
          onChange={refresh}
          onGoDirector={() => go("director")}
        />
      ) : tab === "script" ? (
        <ScriptStoryboardWorkspace
          project={project}
          onChange={refresh}
          onGoDirector={() => go("director")}
        />
      ) : tab === "shotlist" ? (
        <ScriptStoryboardWorkspace
          project={project}
          onChange={refresh}
          onGoDirector={() => go("director")}
          shotListOnly
        />
      ) : (
        <div className="page">
          <p className="empty">Unknown workspace.</p>
        </div>
      )}

      </div>
    </CoDirectorProvider>
  );
}

function ProjectCoDirectorBridge({
  project,
  sceneId,
  sceneName,
  workspaceTab,
  onGoTab,
  onApplyPrompt,
  onAppliedSetup,
}: {
  project: Project;
  sceneId?: string;
  sceneName?: string;
  workspaceTab: string;
  onGoTab: (tab: string) => void;
  onApplyPrompt: (prompt: string) => void;
  onAppliedSetup: () => void | Promise<void>;
}) {
  useBindCoDirectorWorkspace({
    projectId: project.id,
    projectName: project.name,
    sceneId,
    sceneName,
    workspaceTab,
    onGoTab,
    onApplyPrompt,
    onAppliedSetup,
  });
  return null;
}
