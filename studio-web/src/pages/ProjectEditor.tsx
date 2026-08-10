import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, isAbortError, isNavigationFetchFailure } from "../api";
import type { Asset, Project } from "../types";
import { UnlockProjectModal } from "../components/ProjectPasswordModals";
import { goHome } from "../navigation/projectLibrary";
import { CoDirectorProvider } from "../core/CoDirectorContext";
import { useTranslation } from "react-i18next";
import { WORKSPACES, workspaceLabel } from "../core/workspaces";
// WORKSPACES.labelKey used for i18n nav labels
import { Timeline } from "../components/Timeline";
import { AssetTray, PromptComposer } from "../components/AssetTray";
import { AdvancedPanel, JobPanel } from "../components/JobPanel";
import { GpuVramPanel } from "../components/GpuVramPanel";
import { SpatialMapStudio } from "../components/spatial-map/SpatialMapStudio";
import { ScriptStoryboardWorkspace } from "../components/ScriptStoryboardWorkspace";
import { StoryboardStudio } from "../components/storyboard-studio/StoryboardStudio";
import { useBindCoDirectorWorkspace, useOpenCoDirector } from "../components/CoDirector";
import { ImageToolsPanel } from "../components/ImageTools";
import { DirectorTracks } from "../components/DirectorTracks";
import { TimelineMasterPanel } from "../components/timeline-master/TimelineMasterPanel";
import { TimelineWorkspaceStack } from "../components/timeline-master/TimelineWorkspaceStack";
import { TimelineEditorShell } from "../components/timeline-master/TimelineEditorShell";
import { OneFramePanel, ThreeFramePanel } from "../components/FrameModes";
import { DirectorSelectionProvider, useDirectorSelection } from "../components/DirectorSelectionContext";
import { ContextInspector } from "../components/ContextInspector";
import { GenerateTimelinePanel } from "../components/GenerateTimelinePanel";
import { LipSyncTracksPanel } from "../components/LipSyncTracks";
import { SetupWizardPanel } from "../components/SetupWizard";
import { ProfilesWorkspace } from "../components/ProfilesWorkspace";
import { LivePreviewMonitor } from "../components/LivePreviewMonitor";
import { ProjectHome } from "../components/ProjectHome";
import { ProjectSettings } from "../components/ProjectSettings";
import { Txt2VidPanel } from "../components/Txt2VidPanel";
import { CinematicImageStudio } from "../components/image-studio/CinematicImageStudio";
import { LibraryPanel } from "../components/LibraryPanel";
import { MarketplacePanel } from "../components/MarketplacePanel";
import { SceneMasterSheetWorkspace } from "../components/SceneMasterSheetWorkspace";
import { AvatarStudioWorkspace } from "../components/AvatarStudioWorkspace";
import { VoiceStudioShell } from "../components/VoiceStudioShell";
import { CharacterProfileWorkspace } from "../components/CharacterProfileWorkspace";
import { readEditorialContext } from "../components/EditorWorkspace";
import { MagiEditorWorkspace } from "../components/magi/MagiEditorWorkspace";
import { AudioStudioWorkspace } from "../components/AudioStudioWorkspace";
import { GenerationToolsHub } from "../components/GenerationTools/GenerationToolsHub";
import { BrandStudioWorkspace } from "../components/GenerationTools/BrandStudioWorkspace";
import { PoseCraftWorkspace } from "../components/GenerationTools/PoseCraftWorkspace";
import { ScriptwriterStudio } from "../components/scriptwriter/ScriptwriterStudio";
import { ProductionBibleWorkspace } from "../components/ProductionBibleWorkspace";
import { ContinuityWorkspace } from "../components/continuity/ContinuityWorkspace";
import { ReferencesPane } from "../components/sceneReferences/ReferencesPane";
import { TimelineCharacterCreatorPanel } from "../components/TimelineCharacterCreatorPanel";
import { StudioChrome as AppStudioChrome } from "../components/dashboard/StudioChrome";
import { SplitPane } from "../components/ui/SplitPane";
import { continuityLockedCount } from "../directorSelection";
import {
  type EditorTab,
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
  onOpenCharacterCreator,
}: {
  project: Project;
  selectedScene?: string;
  setSelectedScene: (id: string) => void;
  tab: "one" | "three" | "timeline" | "director";
  refresh: () => Promise<void>;
  onGoEditor?: () => void;
  onOpenCharacterCreator?: () => void;
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
  const [libraryPreviewId, setLibraryPreviewId] = useState<string | null>(null);
  const [playheadSec, setPlayheadSec] = useState(0);
  const selected = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
  const libraryPreviewAsset =
    (libraryPreviewId && project.assets.find((a) => a.id === libraryPreviewId)) || null;
  const cont = continuityLockedCount(selected?.continuity_json);
  const sceneW = selected?.width || project.width;
  const sceneH = selected?.height || project.height;
  const sceneFps =
    selected?.fps_mode && selected.fps_mode !== "auto" && selected.fps
      ? selected.fps
      : project.fps;
  const isTimelineMode = false;

  useEffect(() => {
    setPlayheadSec(0);
  }, [selectedScene]);

  const handleAddAssetToTimeline = useCallback(
    async (asset: Asset) => {
      const scene = selected;
      if (!scene) return;
      try {
        const tl = await api.getDirector(project.id, scene.id);
        const duration = tl.duration_sec || scene.duration_sec || 5;
        const id = Math.random().toString(36).slice(2, 10);
        let next = { ...tl };
        if (asset.kind === "image") {
          const imageClips = tl.image_clips || [];
          const start = (imageClips as Array<{ start: number; length: number }>).reduce(
            (m: number, c: { start: number; length: number }) => Math.max(m, c.start + c.length),
            0,
          );
          next = {
            ...next,
            media_mode: "image" as const,
            image_clips: [
              ...imageClips,
              {
                id,
                start: Math.min(start, Math.max(0, duration - 1)),
                length: Math.min(2, duration),
                label: `Image ${imageClips.length + 1}`,
                role: "guide" as const,
                asset_id: asset.id,
              },
            ],
          };
        } else if (asset.kind === "video") {
          next = {
            ...next,
            media_mode: "video" as const,
            video_clips: [
              {
                id,
                start: 0,
                length: duration,
                label: "Video",
                asset_id: asset.id,
                trim_start: 0,
              },
            ],
          };
        } else if (asset.kind === "audio") {
          next = {
            ...next,
            audio_clips: [
              ...(tl.audio_clips || []),
              {
                id,
                start: 0,
                length: duration,
                label: asset.tag || "Audio",
                asset_id: asset.id,
                volume: 1,
              },
            ],
          };
        }
        await api.putDirector(project.id, scene.id, next);
        await refresh();
      } catch (e) {
        console.error(e);
      }
    },
    [project.id, refresh, selected],
  );

  const handleAddAssetAsReference = useCallback(
    async (asset: Asset) => {
      const scene = selected;
      if (!scene) return;
      try {
        const refType =
          asset.kind === "image" ? "character" : asset.kind === "video" ? "environment" : "prop";
        await api.sceneReferences.attach(project.id, {
          asset_id: asset.id,
          scope_type: "scene",
          scope_id: scene.id,
          reference_type: refType,
          usage_modes: ["appearance"],
          reference_roles: [refType],
        });
        await refresh();
      } catch (e) {
        console.error(e);
      }
    },
    [project.id, refresh, selected],
  );

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
      if (e.key === "Escape") {
        clearSelection();
        setLibraryPreviewId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearSelection]);

  // Drop stale library preview if the asset was deleted from the project.
  useEffect(() => {
    if (libraryPreviewId && !project.assets.some((a) => a.id === libraryPreviewId)) {
      setLibraryPreviewId(null);
    }
  }, [project.assets, libraryPreviewId]);

  const stackedTimeline = false;
  const showMonitor = !stackedTimeline;
  const showTracks = false;

  const monitorBlock = (
    <div className="director-center-pane director-monitor-pane">
      {isTimelineMode && (
        <p
          className="scene-meta"
          style={{
            margin: "0 0 0.35rem",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            fontSize: "0.7rem",
          }}
        >
          Prompt Timeline · Monitor
        </p>
      )}
      <LivePreviewMonitor
        project={project}
        scene={selected}
        libraryAsset={libraryPreviewAsset}
        onClearLibraryAsset={() => setLibraryPreviewId(null)}
        playheadSec={stackedTimeline ? playheadSec : undefined}
        onPlayheadChange={stackedTimeline ? setPlayheadSec : undefined}
      />
      {isTimelineMode && selected && (
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
    </div>
  );

  const tracksBlock = (
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
        <>
          <DirectorTracks
            project={project}
            scene={selected}
            onChange={refresh}
            viewMode={workspaceTab === "prompt" ? "prompt" : "tracks"}
            onGoEditor={onGoEditor}
            hideEmbeddedStage={stackedTimeline}
            externalPlayhead={stackedTimeline ? playheadSec : undefined}
            onPlayheadChange={stackedTimeline ? setPlayheadSec : undefined}
          />
          {workspaceTab === "timeline" && selected && (
            <TimelineMasterPanel projectId={project.id} sceneId={selected.id} />
          )}
        </>
      )}
      {workspaceTab === "lipsync" && selected && (
        <LipSyncTracksPanel project={project} scene={selected} onChange={onChangeSafe(refresh)} />
      )}
      {workspaceTab === "settings" && (
        <PromptComposer project={project} sceneId={selectedScene} onChange={refresh} showContinuity />
      )}
    </div>
  );

  if (tab === "timeline") {
    return (
      <TimelineEditorShell
        project={project}
        selectedScene={selectedScene}
        setSelectedScene={setSelectedScene}
        refresh={refresh}
      />
    );
  }

  return (
    <div className="director-shell director-shell--split">
      <SplitPane
        storageKey="adept_ui_split_director_left"
        initialPrimarySize={280}
        minPrimary={200}
        minSecondary={360}
        primary={
      <aside className="shell-pane shell-left">
        <AssetTray
          project={project}
          onChange={refresh}
          selectedAssetId={libraryPreviewId}
          onSelectAsset={(asset) => {
            setLibraryPreviewId(asset.id);
            if (!stackedTimeline) setCenterView("monitor");
          }}
          onAddToTimeline={handleAddAssetToTimeline}
          onAddAsReference={handleAddAssetAsReference}
        />
        <TimelineCharacterCreatorPanel
          project={project}
          onChange={() => void refresh()}
          onOpenCharacterCreator={() => onOpenCharacterCreator?.()}
        />
        <ReferencesPane
          project={project}
          sceneId={selectedScene || selected?.id || null}
          workflowTab={tab}
          onChange={refresh}
        />
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
        }
        secondary={
          <SplitPane
            storageKey="adept_ui_split_director_right_primary"
            initialPrimarySize={720}
            minPrimary={360}
            minSecondary={240}
            primary={
      <main className="shell-pane shell-main">
        {editorialNote && isTimelineMode && (
          <div className="pill" style={{ margin: "0.5rem 1rem" }}>
            {editorialNote}
          </div>
        )}

        {stackedTimeline ? (
          <TimelineWorkspaceStack projectId={project.id} monitor={monitorBlock} timeline={tracksBlock} />
        ) : (
          <>
            {showMonitor && (
              <div className="director-center-pane director-monitor-pane">
                <LivePreviewMonitor
                  project={project}
                  scene={selected}
                  libraryAsset={libraryPreviewAsset}
                  onClearLibraryAsset={() => setLibraryPreviewId(null)}
                />
                {tab === "one" && <OneFramePanel project={project} scene={selected} onChange={refresh} />}
                {tab === "three" && <ThreeFramePanel project={project} scene={selected} onChange={refresh} />}
                <PromptComposer project={project} sceneId={selectedScene} onChange={refresh} />
              </div>
            )}
            {showTracks && tracksBlock}
          </>
        )}
      </main>
            }
            secondary={
      <aside className="shell-pane shell-right">
        <ContextInspector project={project} scene={selected} onChange={refresh} />
        <JobPanel projectId={project.id} onDone={refresh} />
        <GpuVramPanel project={project} onChange={refresh} />
      </aside>
            }
          />
        }
      />
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
  const navigate = useNavigate();
  const { t } = useTranslation("navigation");
  const [project, setProject] = useState<Project | null>(null);
  const [selectedScene, setSelectedScene] = useState<string>();
  const [tab, setTab] = useState<EditorTab>("home");
  const [workspaceProjectId, setWorkspaceProjectId] = useState<string>();
  const [lockedGate, setLockedGate] = useState(false);
  const [activeDocumentId, setActiveDocumentId] = useState<string | undefined>();
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
    // ROUTING CONTRACT (stale-render guard): a project switch must never
    // render the previous project's data under the new project's URL. Clear
    // the loaded project up front so the loading gate shows until the fetch
    // for the new id resolves. In-place refreshes (same id) keep the data.
    setProject((prev) => (prev && prev.id !== id ? null : prev));
    try {
      const p = await api.getProject(id, { signal: ac.signal });
      if (!mountedRef.current || ac.signal.aborted) return;
      setLockedGate(false);
      setProject(p);
      // Scene selection is only valid within its own project — a foreign
      // scene id from a previous project must not leak into this one.
      setSelectedScene((prev) =>
        prev && p.scenes.some((s) => s.id === prev) ? prev : p.scenes[0]?.id,
      );
      pushRecentProject(p.id, p.name);
    } catch (error) {
      if (isAbortError(error) || ac.signal.aborted || !mountedRef.current) return;
      if (error instanceof ApiError && (error.code === "PROJECT_LOCKED" || error.status === 403)) {
        setProject(null);
        setLockedGate(true);
        return;
      }
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
    const onRenamed = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId?: string }>).detail;
      if (!detail?.projectId || detail.projectId !== id) return;
      void refresh();
    };
    window.addEventListener("adept:project-renamed", onRenamed as EventListener);
    return () => window.removeEventListener("adept:project-renamed", onRenamed as EventListener);
  }, [id, refresh]);

  useEffect(() => {
    if (!id) return;
    const query = new URLSearchParams(locationSearch);
    const raw = query.get("workspace") ?? query.get("tab");
    const requested = resolveWorkspace(raw);
    // ROUTING CONTRACT: Open Project (no ?workspace= param) ALWAYS lands on
    // the project landing page. Workspace memory never silently reroutes a
    // plain project open — resume only happens via the intentional Continue
    // affordance on the landing page, which navigates with an explicit
    // ?workspace= param. Explicit deep links are honored exactly.
    const next = requested || "home";
    setTab(next);
    setWorkspaceProjectId(id);
    // Wave 4C: canonicalize legacy director → timeline in the URL without dropping context.
    if (requested && raw && raw.trim().toLowerCase() !== requested) {
      const search = new URLSearchParams(locationSearch);
      search.set("workspace", requested);
      search.delete("tab");
      navigate({ pathname: `/project/${id}`, search: `?${search.toString()}` }, { replace: true });
    }
  }, [id, locationSearch, navigate]);

  useEffect(() => {
    if (!id || workspaceProjectId !== id) return;
    saveLastWorkspace(id, tab);
  }, [id, tab, workspaceProjectId]);

  const go = useCallback(
    (next: string) => {
      if (!id) return;
      const resolved = resolveWorkspace(next);
      if (!resolved) return;
      setTab(resolved);
      // ROUTING CONTRACT: the project landing page is the bare URL — no
      // workspace query param. Named workspaces carry an explicit param.
      // User-initiated switches PUSH history so Back/Forward stays coherent
      // (View Timeline → Back returns to the landing). Only the legacy-alias
      // canonicalization above uses replace.
      const search = resolved === "home" ? "" : `?workspace=${encodeURIComponent(resolved)}`;
      if (locationSearch === search) return;
      navigate({ pathname: `/project/${id}`, search });
    },
    [id, locationSearch, navigate],
  );

  const applyPrompt = useCallback(
    async (prompt: string) => {
      if (!project) return;
      const scene = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
      if (!scene) return;
      await api.updateScene(project.id, scene.id, { ...scene, prompt });
      await refresh();
    },
    [project, refresh, selectedScene],
  );

  if (!project) {
    if (lockedGate && id) {
      return (
        <div className="app-shell" data-testid="project-locked-gate">
          <header className="topbar">
            <div className="brand">
              Adept <span>UI Studio</span>
            </div>
          </header>
          <p className="empty">This project is password protected.</p>
          <UnlockProjectModal
            projectId={id}
            projectName="Protected project"
            onClose={() => goHome(navigate)}
            onUnlocked={() => {
              setLockedGate(false);
              void refresh();
            }}
          />
        </div>
      );
    }
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            Adept <span>UI Studio</span>
          </div>
        </header>
        <p className="empty">Loading project…</p>
      </div>
    );
  }

  const showTimelineShell = tab === "one" || tab === "three" || tab === "timeline" || tab === "director";
  // Viewport-locked shell only for multi-pane app layouts; document pages use native window scroll.
  const lockViewportShell = showTimelineShell || tab === "spatial" || tab === "magi" || tab === "editor";

  const tabLabel = t(WORKSPACES[tab].labelKey, { defaultValue: workspaceLabel(tab) });
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
        activeDocumentId={tab === "scriptwriter" ? activeDocumentId : undefined}
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
        activeWorkspace={tab}
        onNavigateWorkspace={(next) => go(next)}
        // c5: open Co-Director as a popup over the project workspace so the underlying
        // Timeline/Scene workspace stays mounted and receives mutation events.
        onOpenCoDirector={openCoDirector}
        onSetup={() => go("setup")}
        onExport={() => {
          void api.exportPack(project.id).then(() => refresh());
        }}
        breadcrumbs={[
          { label: "Home", onClick: () => goHome(navigate) },
          { label: "Project", onClick: () => go("home") },
          { label: tabLabel },
        ]}
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
      ) : tab === "voicestudio" ? (
        <VoiceStudioShell
          project={project}
          initialCharacterId={
            new URLSearchParams(locationSearch).get("characterId") ||
            (() => {
              try {
                return sessionStorage.getItem("adept_selected_character") || "";
              } catch {
                return "";
              }
            })() ||
            undefined
          }
          onChange={refresh}
        />
      ) : tab === "characters" || tab === "identityregistry" ? (
        <CharacterProfileWorkspace
          project={project}
          onChange={refresh}
          initialTab={tab === "identityregistry" ? "identityRegistry" : undefined}
          initialCharacterId={
            new URLSearchParams(locationSearch).get("characterId") ||
            (() => {
              try {
                return sessionStorage.getItem("adept_selected_character") || "";
              } catch {
                return "";
              }
            })() ||
            undefined
          }
          initialIdentityId={new URLSearchParams(locationSearch).get("identityId") || undefined}
          returnWorkspace={
            new URLSearchParams(locationSearch).get("returnWorkspace") ||
            new URLSearchParams(locationSearch).get("return") ||
            undefined
          }
        />
      ) : tab === "magi" || tab === "editor" ? (
        <MagiEditorWorkspace project={project} onChange={refresh} />
      ) : tab === "audiostudio" ? (
        <AudioStudioWorkspace project={project} onChange={refresh} onGo={go} />
      ) : tab === "generationtools" ? (
        <GenerationToolsHub project={project} onChange={refresh} onGo={go} />
      ) : tab === "scriptwriter" ? (
        <ScriptwriterStudio
          project={project}
          onChange={refresh}
          onGo={go}
          onActiveDocumentId={setActiveDocumentId}
        />
      ) : tab === "brandstudio" ? (
        <BrandStudioWorkspace project={project} onChange={refresh} />
      ) : tab === "posecraft" ? (
        <PoseCraftWorkspace
          project={project}
          onChange={refresh}
          onGo={go}
          onAskCoDirector={(p) => openCoDirector(p, { autoSend: Boolean(p) })}
        />
      ) : tab === "bible" ? (
        <ProductionBibleWorkspace project={project} onChange={refresh} />
      ) : tab === "continuity" ? (
        <ContinuityWorkspace project={project} onChange={refresh} onGo={go} />
      ) : tab === "settings" ? (
        <ProjectSettings project={project} onChange={() => void refresh()} />
      ) : tab === "setup" ? (
        <SetupWizardPanel projectId={project.id} />
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
        <CinematicImageStudio project={project} onChange={refresh} onGo={go} />
      ) : tab === "txt2vid" ? (
        <Txt2VidPanel project={project} onChange={refresh} onGo={go} />
      ) : tab === "library" ? (
        <LibraryPanel project={project} onChange={refresh} onGo={go} />
      ) : tab === "marketplace" ? (
        <MarketplacePanel project={project} />
      ) : showTimelineShell ? (
        <DirectorSelectionProvider>
          <DirectorWorkspaceShell
            project={project}
            selectedScene={selectedScene}
            setSelectedScene={setSelectedScene}
            tab={tab}
            refresh={refresh}
            onGoEditor={() => go("magi")}
            onOpenCharacterCreator={() => go("characters")}
          />
        </DirectorSelectionProvider>
      ) : tab === "tools" ? (
        <>
          <ImageToolsPanel project={project} onChange={refresh} />
          <div className="page" style={{ width: "min(1100px, 100%)", paddingTop: 0 }}>
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
            onOpenTimeline={() => go("timeline")}
          />
        </div>
      ) : tab === "spatial" ? (
        <SpatialMapStudio
          project={project}
          scene={project.scenes.find((s) => s.id === selectedScene) || project.scenes[0]}
          onChange={refresh}
          onGoTimeline={() => go("timeline")}
        />
      ) : tab === "script" ? (
        <StoryboardStudio project={project} onChange={refresh} onGo={go} />
      ) : tab === "shotlist" ? (
        <ScriptStoryboardWorkspace
          project={project}
          onChange={refresh}
          onGoTimeline={() => go("timeline")}
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
  activeDocumentId,
  onGoTab,
  onApplyPrompt,
  onAppliedSetup,
}: {
  project: Project;
  sceneId?: string;
  sceneName?: string;
  workspaceTab: string;
  activeDocumentId?: string;
  onGoTab: (tab: string) => void;
  onApplyPrompt: (prompt: string) => void;
  onAppliedSetup: () => void | Promise<void>;
}) {
  useBindCoDirectorWorkspace({
    projectId: project.id,
    projectName: project.name,
    primaryProjectType: project.primary_project_type || "custom",
    sceneId,
    sceneName,
    workspaceTab,
    activeDocumentId,
    onGoTab,
    onApplyPrompt,
    onAppliedSetup,
  });
  return null;
}
