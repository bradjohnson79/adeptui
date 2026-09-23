import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, bindAssetUrlProject, isAbortError, isNavigationFetchFailure } from "../api";
import type { Asset, Project } from "../types";
import { UnlockProjectModal } from "../components/ProjectPasswordModals";
import { goHome } from "../navigation/projectLibrary";
import { buildProjectWorkspaceLocation } from "../navigation/projectWorkspaceNavigation";
import { CoDirectorProvider } from "../core/CoDirectorContext";
import { useTranslation } from "react-i18next";
import { ProjectLanguageSync } from "../i18n";
import { isPoseCraftEnabled, isSpatialMapEnabled } from "../core/featureFlags";
import { WORKSPACES, coDirectorProjectPath, isRetiredWorkspace, isStandaloneBibleWorkspace, resolveShelvedCreatorWorkspace } from "../core/workspaces";
// WORKSPACES.labelKey used for i18n nav labels
import { Timeline } from "../components/Timeline";
import { AssetTray, PromptComposer } from "../components/AssetTray";
import { AdvancedPanel, JobPanel } from "../components/JobPanel";
import { GpuVramPanel } from "../components/GpuVramPanel";
import { SpatialMapPanel } from "../components/CoDirector/SpatialMap/SpatialMapPanel";
import { ScriptStoryboardWorkspace } from "../components/ScriptStoryboardWorkspace";
import { StoryboardStudio } from "../components/storyboard-studio/StoryboardStudio";
import { useBindCoDirectorWorkspace, useOpenCoDirector } from "../components/CoDirector";
import { ImageToolsPanel } from "../components/ImageTools";
import { DirectorTracks } from "../components/DirectorTracks";
import { TimelineWorkspaceStack } from "../components/timeline-master/TimelineWorkspaceStack";
import { TimelineEditorShell } from "../components/timeline-master/TimelineEditorShell";
import { OneFramePanel, ThreeFramePanel } from "../components/FrameModes";
import { DirectorSelectionProvider, useDirectorSelection } from "../components/DirectorSelectionContext";
import { ContextInspector } from "../components/ContextInspector";
import { GenerateTimelinePanel } from "../components/GenerateTimelinePanel";
import { SetupWizardPanel } from "../components/SetupWizard";
import { LivePreviewMonitor } from "../components/LivePreviewMonitor";
import { ProjectHome } from "../components/ProjectHome";
import { ProjectSettings } from "../components/ProjectSettings";
import { Txt2VidPanel } from "../components/Txt2VidPanel";
import { CinematicImageStudio } from "../components/image-studio/CinematicImageStudio";
import { LibraryPanel } from "../components/LibraryPanel";
import { MarketplacePanel } from "../components/MarketplacePanel";
import { PropCreatorWorkspace } from "../components/prop-creator/PropCreatorWorkspace";
import { EnvironmentCreatorWorkspace } from "../components/environment-creator/EnvironmentCreatorWorkspace";
import { VoiceStudioShell } from "../components/VoiceStudioShell";
import { CharacterProfileWorkspace } from "../components/CharacterProfileWorkspace";
import { readEditorialContext } from "../components/EditorWorkspace";
import { MagiEditorWorkspace } from "../components/magi/MagiEditorWorkspace";
import { AudioStudioWorkspace } from "../components/AudioStudioWorkspace";
import { GenerationToolsHub } from "../components/GenerationTools/GenerationToolsHub";
import { PoseCraftWorkspace } from "../components/GenerationTools/PoseCraftWorkspace";
import { ScriptwriterStudio } from "../components/scriptwriter/ScriptwriterStudio";
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
import { formatDurationSeconds } from "../lib/formatDuration";
import {
  buildTimelineSearch,
  clearLastSelectedScene,
  isTimelineShellWorkspace,
  loadLastSelectedScene,
  parseSceneIdFromSearch,
  persistWorkspaceKey,
  resolveSelectedScene,
  saveLastSelectedScene,
  shouldPersistSelectedScene,
} from "../sceneSelection";

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
        const duration = scene.duration_sec || 5;
        const id = Math.random().toString(36).slice(2, 10);
        if (asset.kind === "image") {
          // Omni Wave 3A Law 2: Library image → References only (mediaType=image).
          // Do NOT write Visual image_clips guide takes. No silent generation.
          await api.sceneReferences.attach(project.id, {
            asset_id: asset.id,
            scope_type: "scene",
            scope_id: scene.id,
            reference_type: "image",
            media_kind: "image",
            usage_modes: ["appearance"],
            reference_roles: ["image"],
          });
          await refresh();
          return;
        } else if (asset.kind === "video" || asset.kind === "audio") {
          const masterResp = await api.directorTimelineMaster(project.id, scene.id);
          const master = masterResp?.master;
          if (master) {
            const { patchMasterClips } = await import("../timelineMaster/masterTimelineMutate");
            if (asset.kind === "video") {
              await patchMasterClips(
                project.id,
                scene.id,
                master,
                [{ id, kind: "video", start: 0, length: duration, label: "Video", assetId: asset.id }],
                "visualClips",
              );
            } else {
              await patchMasterClips(
                project.id,
                scene.id,
                master,
                [{ id, kind: "audio", start: 0, length: duration, label: asset.tag || "Audio", assetId: asset.id }],
                "audioClips",
              );
            }
          }
        }
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
        onApproved={refresh}
      />
      {isTimelineMode && selected && (
        <div className="timeline-header-badges">
          <span className="pill">{selected.name}</span>
          <span className="pill">{selected.engine === "auto" ? "Auto" : selected.engine}</span>
          <span className="pill">{formatDurationSeconds(selected.duration_sec)}</span>
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
        </>
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
                  onApproved={refresh}
                />
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
  const [activeScriptSceneId, setActiveScriptSceneId] = useState<string | null>(null);
  const openCoDirector = useOpenCoDirector();

  const mountedRef = useRef(true);
  const refreshAcRef = useRef<AbortController | null>(null);
  const locationSearchRef = useRef(locationSearch);
  const tabRef = useRef(tab);
  // Co-Director is an overlay, not a routed workspace. ?workspace=codirector
  // is a deep-link that should open the overlay once on arrival, not re-open
  // on every effect re-run while the param stays in the URL.
  const codirectorDeepLinkOpenedRef = useRef(false);
  locationSearchRef.current = locationSearch;
  tabRef.current = tab;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      refreshAcRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    bindAssetUrlProject(id || null);
    return () => bindAssetUrlProject(null);
  }, [id]);

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
      // Selection precedence: URL → persisted project/workspace → session → first scene.
      const search = locationSearchRef.current || (typeof window !== "undefined" ? window.location.search : "");
      const requestedWorkspace = resolveWorkspace(
        new URLSearchParams(search).get("workspace") ?? new URLSearchParams(search).get("tab"),
      );
      const persistKey = persistWorkspaceKey(requestedWorkspace || "timeline");
      setSelectedScene((prev) => {
        // Re-read at commit time. A refresh started before the creator clicked
        // another scene must not clobber that later persist/URL with a stale snapshot.
        const liveSearch =
          (typeof window !== "undefined" ? window.location.search : "") || search;
        const livePersisted = loadLastSelectedScene(p.id, persistKey);
        const liveValid =
          livePersisted && p.scenes.some((scene) => scene.id === livePersisted) ? livePersisted : null;
        if (livePersisted && !liveValid) {
          clearLastSelectedScene(p.id, persistKey);
        }
        const next = resolveSelectedScene({
          sceneIds: p.scenes.map((scene) => scene.id),
          urlSceneId: parseSceneIdFromSearch(liveSearch),
          persistedSceneId: liveValid,
          sessionSceneId: prev,
        });
        if (next && requestedWorkspace && shouldPersistSelectedScene(requestedWorkspace)) {
          saveLastSelectedScene(p.id, persistWorkspaceKey(requestedWorkspace), next);
        }
        return next;
      });
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
    if (isRetiredWorkspace(raw)) {
      const search = new URLSearchParams(locationSearch);
      search.delete("workspace");
      search.delete("tab");
      const qs = search.toString();
      navigate({ pathname: `/project/${id}`, search: qs ? `?${qs}` : "" }, { replace: true });
      setTab("home");
      setWorkspaceProjectId(id);
      return;
    }
    // v1.1 shelf — stale Spatial Map / PoseCraft bookmarks land on active destinations.
    if (requested === "spatial" || requested === "posecraft") {
      const dest = resolveShelvedCreatorWorkspace(requested);
      if (dest !== requested) {
        const search = new URLSearchParams(locationSearch);
        search.set("workspace", dest);
        search.delete("tab");
        navigate({ pathname: `/project/${id}`, search: `?${search.toString()}` }, { replace: true });
        setTab(dest);
        setWorkspaceProjectId(id);
        return;
      }
    }
    if (isStandaloneBibleWorkspace(requested)) {
      navigate(coDirectorProjectPath(id), { replace: true });
      return;
    }
    // Co-Director is an overlay, not a routed workspace tab. A
    // ?workspace=codirector deep-link should open the Co-Director popup over
    // the project (keeping sceneId context via the existing binding) instead
    // of falling through to project home. Open once per deep-link arrival.
    const rawNormalized = raw ? raw.trim().toLowerCase() : "";
    const isCoDirectorDeepLink = rawNormalized === "codirector" || rawNormalized === "co-director";
    if (isCoDirectorDeepLink) {
      if (!codirectorDeepLinkOpenedRef.current) {
        codirectorDeepLinkOpenedRef.current = true;
        // Underlying tab stays on the project landing so a workspace stays
        // mounted under the overlay (matches the c5 popup-over-workspace model).
        setTab("home");
        setWorkspaceProjectId(id);
        openCoDirector();
      } else {
        // Already opened for this deep-link; just keep the project bound.
        setTab("home");
        setWorkspaceProjectId(id);
      }
      return;
    } else {
      codirectorDeepLinkOpenedRef.current = false;
    }
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
  }, [id, locationSearch, navigate, openCoDirector]);

  useEffect(() => {
    if (!id || workspaceProjectId !== id) return;
    saveLastWorkspace(id, resolveShelvedCreatorWorkspace(tab));
  }, [id, tab, workspaceProjectId]);

  const commitSelectedScene = useCallback(
    (sceneId: string) => {
      setSelectedScene(sceneId);
      if (!id || !shouldPersistSelectedScene(tabRef.current)) return;
      const sid = String(sceneId || "").trim();
      if (!sid) {
        clearLastSelectedScene(id, persistWorkspaceKey(tabRef.current));
        return;
      }
      saveLastSelectedScene(id, persistWorkspaceKey(tabRef.current), sid);
    },
    [id],
  );

  useEffect(() => {
    if (!id || !shouldPersistSelectedScene(tab)) return;
    if (!selectedScene) {
      clearLastSelectedScene(id, persistWorkspaceKey(tab));
      return;
    }
    saveLastSelectedScene(id, persistWorkspaceKey(tab), selectedScene);
  }, [id, selectedScene, tab]);

  useEffect(() => {
    if (!id || !project || !isTimelineShellWorkspace(tab)) return;
    // Stale-tab guard: Production dropdown (and any explicit workspace nav) can
    // update the URL to a non-timeline workspace one render before `tab` catches
    // up. Never rewrite that destination back to workspace=timeline.
    const urlWorkspace = resolveWorkspace(
      new URLSearchParams(locationSearch).get("workspace") ??
        new URLSearchParams(locationSearch).get("tab"),
    );
    if (urlWorkspace && !isTimelineShellWorkspace(urlWorkspace)) return;
    const validScene =
      selectedScene && project.scenes.some((scene) => scene.id === selectedScene) ? selectedScene : "";
    const next = buildTimelineSearch({
      workspace: tab,
      sceneId: validScene,
      currentSearch: validScene ? locationSearch : "",
    });
    if (!next || locationSearch === next) return;
    const current = new URLSearchParams(locationSearch);
    const nextParams = new URLSearchParams(next);
    const workspaceUnchanged =
      (current.get("workspace") || current.get("tab") || "") === (nextParams.get("workspace") || "");
    navigate({ pathname: `/project/${id}`, search: next }, { replace: workspaceUnchanged });
  }, [id, selectedScene, tab, locationSearch, navigate, project]);

  useEffect(() => {
    if (!project) return;
    const urlSceneId = parseSceneIdFromSearch(locationSearch);
    if (!urlSceneId) return;
    // URL → selection only when the URL itself changed. A creator click must
    // be allowed to rewrite the previous first-scene canonicalize; do not let
    // the stale sceneId in the address bar win over that click.
    const next = resolveSelectedScene({
      sceneIds: project.scenes.map((scene) => scene.id),
      urlSceneId,
      persistedSceneId: loadLastSelectedScene(project.id, persistWorkspaceKey(tab)),
      sessionSceneId: selectedScene,
    });
    if (next && next !== selectedScene) commitSelectedScene(next);
    // selectedScene is read for the no-op guard only — do not re-run on click.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commitSelectedScene, locationSearch, project, tab]);

  const go = useCallback(
    (next: string, extra?: Record<string, string>) => {
      if (!id) return;
      const resolvedRaw = resolveWorkspace(next);
      if (!resolvedRaw) return;
      const resolved = resolveShelvedCreatorWorkspace(resolvedRaw);
      // QUERY-PARAM LAW: leaving Timeline must not carry workspace=timeline.
      // sceneId is Timeline restore state — attach it only for timeline-shell
      // destinations (or when the caller explicitly passes sceneId/scene).
      // Other workspaces keep projectId only; return-to-Timeline reloads scene
      // from persisted last-selected storage.
      const explicitScene = String(extra?.sceneId || extra?.scene || "").trim() || undefined;
      const rememberedScene =
        explicitScene ||
        loadLastSelectedScene(id, persistWorkspaceKey(resolved)) ||
        selectedScene ||
        undefined;
      const sceneIdForUrl = isTimelineShellWorkspace(resolved) ? rememberedScene : explicitScene;
      const location = buildProjectWorkspaceLocation({
        projectId: id,
        tab: resolved,
        sceneId: sceneIdForUrl,
        extra,
      });
      if (!location) return;
      if (isStandaloneBibleWorkspace(resolved)) {
        navigate(`${location.pathname}${location.search}`, { replace: true });
        return;
      }
      setTab(resolved);
      // ROUTING CONTRACT: the project landing page is the bare URL — no
      // workspace query param. Named workspaces carry an explicit param.
      // User-initiated switches PUSH history so Back/Forward stays coherent
      // (View Timeline → Back returns to the landing). Only the legacy-alias
      // canonicalization above uses replace.
      if (locationSearch === location.search) return;
      navigate({ pathname: location.pathname, search: location.search });
    },
    [id, locationSearch, navigate, selectedScene],
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

  const routeSceneId = selectedScene || parseSceneIdFromSearch(locationSearch) || undefined;
  const bindNode = id ? (
    <ProjectCoDirectorBridge
      projectId={id}
      projectName={project?.name || "Project"}
      primaryProjectType={project?.primary_project_type || "custom"}
      sceneId={routeSceneId}
      sceneName={project?.scenes.find((scene) => scene.id === routeSceneId)?.name}
      workspaceTab={persistWorkspaceKey(resolveShelvedCreatorWorkspace(tab)) === "timeline" ? "timeline" : resolveShelvedCreatorWorkspace(tab)}
      activeDocumentId={project && tab === "scriptwriter" ? activeDocumentId : undefined}
      scriptwriterSceneId={project && tab === "scriptwriter" ? activeScriptSceneId : undefined}
      onGoTab={go}
      onApplyPrompt={applyPrompt}
      onAppliedSetup={refresh}
    />
  ) : null;

  if (!project) {
    if (lockedGate && id) {
      return (
        <div className="app-shell" data-testid="project-locked-gate">
          {bindNode}
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
        {bindNode}
        <header className="topbar">
          <div className="brand">
            Adept <span>UI Studio</span>
          </div>
        </header>
        <p className="empty">Loading project…</p>
      </div>
    );
  }

  // 1 Frame / 3 Frame are standalone CREATE surfaces — no Timeline shell.
  const viewTab = resolveShelvedCreatorWorkspace(tab);
  const showTimelineShell = viewTab === "timeline" || viewTab === "director";
  // Viewport-locked shell only for multi-pane app layouts; document pages use native window scroll.
  const lockViewportShell = showTimelineShell || viewTab === "spatial" || viewTab === "magi" || viewTab === "editor";

  const tabLabel = t(WORKSPACES[viewTab].labelKey);
  const selectedSceneObj = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];

  return (
    <CoDirectorProvider
      value={{
        projectId: project.id,
        projectName: project.name,
        sceneId: selectedSceneObj?.id,
        sceneName: selectedSceneObj?.name,
        activeWorkspace: persistWorkspaceKey(tab) === "timeline" ? "timeline" : tab,
      }}
    >
      <ProjectLanguageSync project={project} />
      {bindNode}
      <div className={`app-shell atmosphere${lockViewportShell ? " app-shell-fixed" : ""}`}>
      <AppStudioChrome
        variant="project"
        projectName={project.name}
        workspaceLabel={tabLabel}
        projectId={project.id}
        activeWorkspace={viewTab}
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

      {viewTab === "home" ? (
        <ProjectHome
          project={project}
          onGo={go}
          onRefresh={refresh}
          onAskCoDirector={(p) => openCoDirector(p)}
        />
      ) : viewTab === "environmentcreator" ? (
        <EnvironmentCreatorWorkspace project={project} onGo={go} />
      ) : viewTab === "propcreator" ? (
        <PropCreatorWorkspace project={project} onGo={go} />
      
      ) : viewTab === "avatar" ? (
        <div className="workspace-retired-notice" style={{ padding: "2rem", maxWidth: 560 }}>
          <h2 style={{ marginTop: 0 }}>Avatar Studio is not available in this version</h2>
          <p>
            Avatar Studio has been temporarily retired from the current Adept UI.
            InfiniteTalk / Wan are not part of the current production direction.
            Existing Avatar outputs remain in Library. Voice Creator remains available.
          </p>
          <p style={{ opacity: 0.8 }}>Future direction: cloud Avatar for Adept UI v1.2 (no delivery date).</p>
          <button type="button" onClick={() => go("home")}>Back to Project Home</button>
        </div>
      ) : viewTab === "voicestudio" ? (
        <VoiceStudioShell
          project={project}
          initialCharacterId={new URLSearchParams(locationSearch).get("characterId") || undefined}
          onChange={refresh}
          returnWorkspace={
            new URLSearchParams(locationSearch).get("returnWorkspace") ||
            new URLSearchParams(locationSearch).get("return") ||
            undefined
          }
        />
      ) : viewTab === "characters" || viewTab === "identityregistry" ? (
        <CharacterProfileWorkspace
          project={project}
          onGo={go}
          onChange={refresh}
          initialTab={viewTab === "identityregistry" ? "identityRegistry" : undefined}
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
      ) : viewTab === "magi" || viewTab === "editor" ? (
        <MagiEditorWorkspace project={project} onChange={refresh} />
      ) : viewTab === "audiostudio" ? (
        <AudioStudioWorkspace project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "generationtools" ? (
        <GenerationToolsHub project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "scriptwriter" ? (
        <ScriptwriterStudio
          project={project}
          onChange={refresh}
          onGo={go}
          onActiveDocumentId={setActiveDocumentId}
          onActiveSceneChange={setActiveScriptSceneId}
        />
      ) : viewTab === "posecraft" && isPoseCraftEnabled() ? (
        <PoseCraftWorkspace
          project={project}
          onChange={refresh}
          onGo={go}
          onAskCoDirector={(p) => openCoDirector(p, { autoSend: Boolean(p) })}
        />
      ) : viewTab === "continuity" ? (
        <ContinuityWorkspace project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "settings" ? (
        <ProjectSettings project={project} onChange={() => void refresh()} />
      ) : viewTab === "setup" ? (
        <SetupWizardPanel projectId={project.id} />
      ) : viewTab === "imagegen" ? (
        <CinematicImageStudio project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "txt2vid" ? (
        <Txt2VidPanel project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "one" ? (
        <OneFramePanel project={project} scene={selectedSceneObj} onChange={refresh} />
      ) : viewTab === "three" ? (
        <ThreeFramePanel project={project} scene={selectedSceneObj} onChange={refresh} />
      ) : viewTab === "library" ? (
        <LibraryPanel project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "marketplace" ? (
        <MarketplacePanel project={project} />
      ) : showTimelineShell ? (
        <DirectorSelectionProvider>
          <DirectorWorkspaceShell
            project={project}
            selectedScene={selectedScene}
            setSelectedScene={commitSelectedScene}
            tab={viewTab}
            refresh={refresh}
            onGoEditor={() => go("magi")}
            onOpenCharacterCreator={() => go("characters")}
          />
        </DirectorSelectionProvider>
      ) : viewTab === "tools" ? (
        <>
          <ImageToolsPanel project={project} onChange={refresh} />
          <div className="page" style={{ width: "min(1100px, 100%)", paddingTop: 0 }}>
            <JobPanel projectId={project.id} onDone={refresh} />
            <div style={{ marginTop: "1rem" }}>
              <GpuVramPanel project={project} onChange={refresh} />
            </div>
          </div>
        </>
      ) : viewTab === "generate" ? (
        <div className="page generate-page">
          <GenerateTimelinePanel
            project={project}
            onChange={refresh}
            onOpenTimeline={() => go("timeline")}
          />
        </div>
      ) : viewTab === "spatial" && isSpatialMapEnabled() ? (
        <SpatialMapPanel projectId={project.id} onGoTab={go} variant="standard" />
      ) : viewTab === "script" ? (
        <StoryboardStudio project={project} onChange={refresh} onGo={go} />
      ) : viewTab === "shotlist" ? (
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
  projectId,
  projectName,
  primaryProjectType,
  sceneId,
  sceneName,
  workspaceTab,
  activeDocumentId,
  scriptwriterSceneId,
  onGoTab,
  onApplyPrompt,
  onAppliedSetup,
}: {
  projectId: string;
  projectName: string;
  primaryProjectType?: string;
  sceneId?: string;
  sceneName?: string;
  workspaceTab: string;
  activeDocumentId?: string;
  scriptwriterSceneId?: string | null;
  onGoTab: (tab: string, extra?: Record<string, string>) => void;
  onApplyPrompt: (prompt: string) => void;
  onAppliedSetup: () => void | Promise<void>;
}) {
  useBindCoDirectorWorkspace({
    projectId,
    projectName,
    primaryProjectType: primaryProjectType || "custom",
    sceneId,
    sceneName,
    workspaceTab,
    activeDocumentId,
    scriptwriterSceneId: scriptwriterSceneId ?? undefined,
    onGoTab,
    onApplyPrompt,
    onAppliedSetup,
  });
  return null;
}
