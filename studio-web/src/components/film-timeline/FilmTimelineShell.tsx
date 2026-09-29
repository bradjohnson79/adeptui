import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode, type RefObject } from "react";
import { api } from "../../api";
import { addToTimeline } from "../../filmTimeline/addToTimeline";
import { previewActionsEnabled, resolveFilmTimelinePreviewMedia } from "../../filmTimeline/resolveFilmTimelinePreviewMedia";
import { filmTimelineHasCancellableJob } from "../../filmTimeline/filmTimelineCancelVisibility";
import type { Asset, Project, Scene } from "../../types";
import { isTimelineMediaAsset } from "../../timelineMediaTypes";
import { isEditableTarget, loadHotkeys, matchHotkey } from "../../timelineMaster/timelineHotkeys";
import {
  clampViewerHeight,
  loadProjectPreviewHeightRatio,
  loadTimelineWorkspaceLayout,
  saveProjectPreviewHeightRatio,
  saveTimelineWorkspaceLayout,
} from "../../timelineMaster/workspaceLayout";
import { closedVideoRetakeSession, type VideoRetakeSession } from "../../timelineMaster/videoRetake";
import { usePreviewFullscreen } from "../../workspace/fullscreen/usePreviewFullscreen";
import { PromptToolbar } from "../../filmTimeline/promptGuides/PromptToolbar";
import { FilmReferenceModal, type FilmReference } from "./FilmReferenceModal";
import { filmReferenceChipLabel } from "./filmReferenceChipLabel";
import { AddFromProjectLibraryModal } from "../timeline-master/AddFromProjectLibraryModal";
import { GeneratorQualityControls } from "../timeline-master/GeneratorCapabilityControls";
import {
  allowedProductionAspects,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import { PRODUCTION_ASPECTS, normalizeProductionAspect } from "../../workspacePrefs";
import {
  H3_SUPPORTED_ASPECTS,
  LTX_DEFAULT_QUALITY,
  type LtxTimelineQuality,
} from "../../timelineMaster/legalCanvas";
import { MagiUpscaleChooser } from "../timeline-master/MagiUpscaleChooser";
import { PreviewFullscreenTransport } from "../timeline-master/PreviewFullscreenTransport";
import { PreviewVideoActionMenu } from "../timeline-master/PreviewVideoActionMenu";
import { TimelineGpuPane } from "../timeline-master/TimelineGpuPane";
import { resolveFilmTimelinePlanDims, visibleSegmentError } from "../../filmTimeline/filmTimelinePresentation";
import { TimelineHotKeysPane } from "../timeline-master/TimelineHotKeysPane";
import { TimelineRetakeOverlay } from "../timeline-master/TimelineRetakeOverlay";
import { PreviewPublishBarVisibilityToggle } from "../LivePreviewMonitor";
import { SplitPane } from "../ui/SplitPane";
import "../../styles/film-timeline.css";
import "../../styles/timeline-master/timeline-workspace.css";
import "../../styles/timeline-master/timeline-retake-overlay.css";
import "../../styles/timeline-master/preview-fullscreen.css";

type Reference = FilmReference;
type Segment = {
  id: string;
  order: number;
  durationSec: number;
  status: string;
  timedPrompt: string;
  assetId?: string | null;
  error?: string | null;
  generationMetadata?: { continuity?: { seam?: { warning?: string | null } }; resolvedGeneration?: Record<string, unknown> | null; legalCanvas?: Record<string, unknown> | null };
};
type Shot = {
  id: string;
  name: string;
  order?: number;
  durationSec: number;
  timedPrompt: string;
  status: string;
  segments: Segment[];
  state: { references: Reference[]; firstFrameAssetId?: string | null; stitchAssetId?: string | null; stitchStatus?: string | null; modelId?: string | null; resolvedGeneration?: Record<string, unknown> | null };
};
type Clip = { id: string; label: string; assetId: string; startSec: number; durationSec: number; role?: string };
type Film = {
  name: string;
  generatorId?: string | null;
  references: Reference[];
  shots: Shot[];
  audio: Clip[];
  sfx: Clip[];
  videoClips: Clip[];
  publishedAssetId?: string | null;
};
type ModelRow = { id: string; label: string; local: boolean; available: boolean; unavailableReason: string; supportedDurations?: number[]; maxDurationSec?: number; qualityControl?: string; supportedAspectRatios?: string[] };
type LeftTab = "inspector" | "hotkeys" | "gpu";

type Props = {
  project: Project;
  selectedScene?: string;
  setSelectedScene: (id: string) => void;
  refresh: () => Promise<void> | void;
};

const LEFT_TAB_KEY = "adept_film_timeline_left_tab";
const LEFT_COLLAPSE_KEY = "adept_film_timeline_left_collapsed";
const V2_HOTKEYS = new Set(["playPause", "fullscreen", "generateScene", "retake", "openHotkeys", "escape"]);

function overlaps(a: Clip, b: Clip) {
  return a.startSec < b.startSec + (b.durationSec || 1) && b.startSec < a.startSec + (a.durationSec || 1);
}

function audioRows(clips: Clip[]): Clip[][] {
  const rows: Clip[][] = [];
  for (const clip of [...clips].sort((a, b) => a.startSec - b.startSec)) {
    const row = rows.find((items) => items.every((item) => !overlaps(item, clip)));
    if (row) row.push(clip);
    else rows.push([clip]);
  }
  return rows;
}

function assetLabel(asset: Asset) {
  return asset.tag || asset.filename || asset.id;
}

function formatClock(seconds: number) {
  const whole = Math.floor(Math.max(0, Number.isFinite(seconds) ? seconds : 0));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

function FilmPreviewClock({ videoRef, active }: { videoRef: RefObject<HTMLVideoElement | null>; active: boolean }) {
  const [label, setLabel] = useState("0:00 / 0:00");
  useEffect(() => {
    const video = videoRef.current;
    if (!active || !video) return;
    const tick = () => setLabel(`${formatClock(video.currentTime)} / ${formatClock(video.duration)}`);
    tick();
    video.addEventListener("timeupdate", tick);
    video.addEventListener("loadedmetadata", tick);
    return () => {
      video.removeEventListener("timeupdate", tick);
      video.removeEventListener("loadedmetadata", tick);
    };
  }, [active, videoRef]);
  if (!active) return null;
  return (
    <div className="live-preview-scene-clock" data-testid="live-preview-scene-clock">
      {label}
    </div>
  );
}

function PanelChevron({ direction }: { direction: "left" | "right" }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <polyline
        points={direction === "left" ? "14 6 8 12 14 18" : "10 6 16 12 10 18"}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FilmDesk({
  left,
  right,
  collapsed,
  onExpand,
}: {
  left: ReactNode;
  right: ReactNode;
  collapsed: boolean;
  onExpand: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [bounds, setBounds] = useState<{ initial: number; minPrimary: number; minSecondary: number } | null>(null);
  useEffect(() => {
    const width = ref.current?.clientWidth || 1280;
    const minPrimary = Math.max(220, Math.round(width * 0.25));
    const minSecondary = Math.round(width * 0.45);
    const maxPrimary = Math.max(minPrimary, width - minSecondary - 6);
    const stored = Number(localStorage.getItem("adept_film_timeline_left"));
    const preferred = Number.isFinite(stored) && stored > 0 ? stored : Math.round(width * 0.4);
    setBounds({
      initial: Math.min(maxPrimary, Math.max(minPrimary, preferred)),
      minPrimary,
      minSecondary,
    });
  }, []);
  return (
    <div ref={ref} className={`film-timeline${collapsed ? " is-panel-collapsed" : ""}`} data-testid="film-timeline">
      {collapsed ? (
        <button type="button" className="film-timeline__expand" aria-label="Expand Side Panel" title="Expand Side Panel" onClick={onExpand}>
          <PanelChevron direction="right" />
        </button>
      ) : null}
      {bounds ? (
        <SplitPane
          storageKey="adept_film_timeline_left"
          initialPrimarySize={bounds.initial}
          minPrimary={bounds.minPrimary}
          minSecondary={bounds.minSecondary}
          primarySizeRequest={{ size: bounds.initial, token: 1 }}
          primaryCollapsed={collapsed}
          primary={left}
          secondary={right}
        />
      ) : null}
    </div>
  );
}

export function FilmTimelineShell({ project, selectedScene, setSelectedScene, refresh }: Props) {
  const sceneId = selectedScene || project.scenes[0]?.id || "";
  const scene = project.scenes.find((item) => item.id === sceneId) as Scene | undefined;
  const activeByScene = useRef<Record<string, string>>({});
  const videoRef = useRef<HTMLVideoElement>(null);
  const fullscreen = usePreviewFullscreen();
  const [film, setFilm] = useState<Film | null>(null);
  const [shotId, setShotId] = useState("");
  const [segmentId, setSegmentId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [modelId, setModelId] = useState("");
  const [models, setModels] = useState<ModelRow[]>([]);
  const [h3Resolution, setH3Resolution] = useState<{ mode: "auto" | "manual"; megapixels: number }>({ mode: "auto", megapixels: 0.7 });
  const [ltxQuality, setLtxQuality] = useState<LtxTimelineQuality>(LTX_DEFAULT_QUALITY);
  const [message, setMessage] = useState("");
  const [stickyErrorHidden, setStickyErrorHidden] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<LeftTab>(() => {
    const stored = localStorage.getItem(LEFT_TAB_KEY);
    return stored === "hotkeys" || stored === "gpu" || stored === "inspector" ? stored : "inspector";
  });
  const [panelCollapsed, setPanelCollapsed] = useState(() => localStorage.getItem(LEFT_COLLAPSE_KEY) === "1");
  const centerRef = useRef<HTMLDivElement>(null);
  const previewMeasured = useRef(false);
  const [previewPx, setPreviewPx] = useState(420);
  const assignCenter = useCallback((node: HTMLDivElement | null) => {
    centerRef.current = node;
    if (!node || previewMeasured.current || fullscreen.isFullscreen || node.clientHeight < 400) return;
    previewMeasured.current = true;
    const ratio = loadProjectPreviewHeightRatio(project.id) ?? 0.48;
    setPreviewPx(clampViewerHeight(node.clientHeight * ratio, node.clientHeight, window.innerWidth));
  }, [fullscreen.isFullscreen, project.id]);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [referenceOpen, setReferenceOpen] = useState<{ assetId?: string; editId?: string } | null>(null);
  const [libraryItems, setLibraryItems] = useState<Asset[]>([]);
  const [libraryAssetIds, setLibraryAssetIds] = useState<string[]>([]);
  const libraryAssetIdsRef = useRef<string[]>([]);
  libraryAssetIdsRef.current = libraryAssetIds;
  const [publishBar, setPublishBar] = useState(() => loadTimelineWorkspaceLayout().previewPublishBarVisible);
  const [retake, setRetake] = useState<VideoRetakeSession>(closedVideoRetakeSession());
  const [magiOpen, setMagiOpen] = useState(false);
  const [magiLoading, setMagiLoading] = useState(false);
  const [magiError, setMagiError] = useState<string | null>(null);
  const [magiEngine, setMagiEngine] = useState("ffmpeg-scale");
  const [magiModel, setMagiModel] = useState("lanczos");
  const [magiTarget, setMagiTarget] = useState("");
  const [magiOpts, setMagiOpts] = useState<{
    honesty?: string;
    sourceWidth?: number;
    sourceHeight?: number;
    realesrganReady?: boolean;
    engines?: Array<{ id: string; label?: string; available?: boolean; models?: Array<{ id: string; label?: string }> }>;
    targets?: Array<{ id: string; label: string; width: number; height: number }>;
  } | null>(null);

  useEffect(() => {
    localStorage.setItem(LEFT_TAB_KEY, tab);
  }, [tab]);
  useEffect(() => {
    localStorage.setItem(LEFT_COLLAPSE_KEY, panelCollapsed ? "1" : "0");
  }, [panelCollapsed]);
  useEffect(() => {
    const host = centerRef.current;
    if (!host || fullscreen.isFullscreen) return;
    const ratio = loadProjectPreviewHeightRatio(project.id) ?? 0.48;
    setPreviewPx(clampViewerHeight(host.clientHeight * ratio, host.clientHeight, window.innerWidth));
  }, [project.id, fullscreen.isFullscreen]);

  const shot = useMemo(() => {
    if (!film) return undefined;
    return film.shots.find((item) => item.id === shotId);
  }, [film, shotId]);

  const referenced = useMemo(() => {
    const ids = new Set<string>();
    for (const ref of film?.references || []) if (ref.assetId) ids.add(ref.assetId);
    for (const ref of shot?.state.references || []) if (ref.assetId) ids.add(ref.assetId);
    if (shot?.state.firstFrameAssetId) ids.add(shot.state.firstFrameAssetId);
    return ids;
  }, [film, shot]);

  const selectedSegment = shot?.segments.find((item) => item.id === segmentId) || null;
  const preview = resolveFilmTimelinePreviewMedia({
    selectedSegment,
    stitchAssetId: shot?.state.stitchAssetId,
    stitchStatus: shot?.state.stitchStatus,
    segments: shot?.segments,
  });
  const activeReferences = shot?.state.references?.length ? shot.state.references : film?.references || [];
  const cancellable = filmTimelineHasCancellableJob(shot?.segments);
  const rawSegmentError = (shot?.segments || []).find((item) => item.status === "failed" && item.error)?.error || "";
  const _gidForErr = String(modelId || film?.generatorId || "").toLowerCase();
  const h3DirectorSelected = _gidForErr.includes("minimax-h3") && _gidForErr.includes("local");
  const segmentError = visibleSegmentError(rawSegmentError, stickyErrorHidden, {
    hideLegacyR2v: h3DirectorSelected,
  });
  const planDims = useMemo(
    () =>
      resolveFilmTimelinePlanDims({
        generatorId: modelId || film?.generatorId || null,
        shotResolvedGeneration: shot?.state?.resolvedGeneration,
        segments: shot?.segments,
        h3Resolution,
        aspect: scene?.aspect_ratio,
      }),
    [modelId, film?.generatorId, shot?.state?.resolvedGeneration, shot?.segments, h3Resolution, scene?.aspect_ratio],
  );
  const actionsOn = previewActionsEnabled(preview);
  const completed = (shot?.segments || []).some((item) => item.status === "completed" && item.assetId);
  const generating = cancellable;
  const modelLabel = models.find((item) => item.id === modelId)?.label || modelId || "Model";

  const selectedModel = useMemo(() => models.find((item) => item.id === modelId) || null, [models, modelId]);
  // LTX-only quality: H3 and other generators must not receive ltxQuality.
  const ltxSelected = Boolean(
    selectedModel && (String(selectedModel.id).includes("ltx-2.5") || selectedModel.qualityControl === "ltx_quality"),
  );
  const durationOptions = useMemo(() => {
    const cap = selectedModel;
    if (cap?.supportedDurations && cap.supportedDurations.length) return cap.supportedDurations;
    const max = cap?.maxDurationSec ?? (cap ? 20 : 20);
    const min = 3;
    const options: number[] = [];
    for (let s = min; s <= max; s++) options.push(s);
    return options;
  }, [selectedModel]);

  // Clamp the current duration to a legal option when the model changes.
  useEffect(() => {
    if (durationOptions.length === 0) return;
    if (!durationOptions.includes(duration)) {
      setDuration(durationOptions[0]);
    }
  }, [durationOptions, duration]);
  // When the shot loads, restore its duration if legal; otherwise use first option.
  useEffect(() => {
    if (!shot) return;
    const sec = Math.round(shot.durationSec || 10);
    if (durationOptions.includes(sec)) setDuration(sec);
    else setDuration(durationOptions[0]);
  }, [shot?.id]);

  const modelSwitchNote = useMemo(() => {
    if (!shot) return "";
    const cap = selectedModel;
    const max = cap?.maxDurationSec ?? 20;
    if (shot.durationSec > max) {
      return (
        `This ${String(cap?.label || "model")} generates up to ${max}s per window. ` +
        `This ${Math.round(shot.durationSec)}s scene will render as ${shot.durationSec > max ? `${max}s + ${Math.round(shot.durationSec - max)}s` : `${shot.durationSec}s`}.`
      );
    }
    return "";
  }, [shot, selectedModel]);

  const load = useCallback(async () => {
    if (!sceneId) return;
    const response = await api.filmTimelineGet(project.id, sceneId);
    const next = response.film as Film;
    next.audio = next.audio || [];
    next.sfx = next.sfx || [];
    next.videoClips = next.videoClips || [];
    next.references = next.references || [];
    next.shots = next.shots || [];
    setFilm(next);
    setShotId((current) => {
      const remembered = activeByScene.current[sceneId];
      if (remembered && next.shots.some((item) => item.id === remembered)) return remembered;
      if (current && next.shots.some((item) => item.id === current)) return current;
      const latest = [...next.shots].sort((a, b) => (a.order || 0) - (b.order || 0)).at(-1);
      return latest?.id || "";
    });
  }, [project.id, sceneId]);

  useEffect(() => {
    if (sceneId && shotId) activeByScene.current[sceneId] = shotId;
  }, [sceneId, shotId]);

  useEffect(() => {
    void load().catch((error) => setMessage(error instanceof Error ? error.message : "Timeline could not be opened."));
    void api.filmTimelineCapabilities().then((response) => {
      setModels(
        (response.capabilities || [])
          .filter((item) => !String(item.id || "").includes("stub"))
          .map((item) => ({
            id: String(item.id || ""),
            label: String(item.label || item.id || "Model"),
            local: Boolean(item.local),
            available: item.available !== false,
            unavailableReason: String(item.unavailableReason || (item.local ? "" : "API not connected")),
            supportedDurations: Array.isArray(item.supportedDurations)
              ? item.supportedDurations.map(Number).filter((n) => Number.isFinite(n) && n > 0)
              : undefined,
            maxDurationSec: item.maxDurationSec != null ? Number(item.maxDurationSec) : undefined,
            qualityControl: String((item as any).qualityControl || ""),
            supportedAspectRatios: Array.isArray((item as any).supportedAspectRatios)
              ? (item as any).supportedAspectRatios.map(String)
              : [],
          })),
      );
    });
    void api.library(project.id, { scope: "project", limit: 48, offset: 0 }).then((payload) => {
      const rows = ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item));
      setLibraryItems(rows);
    });
  }, [load, project.id]);

  // Scene-scoped Timeline Library tray membership (SoT: timelineWorkspace.libraryAssetIds).
  useEffect(() => {
    if (!sceneId) {
      setLibraryAssetIds([]);
      return;
    }
    let cancelled = false;
    void api
      .directorTimelineMaster(project.id, sceneId)
      .then((data) => {
        if (cancelled) return;
        setLibraryAssetIds(Array.isArray(data.libraryAssetIds) ? data.libraryAssetIds.map(String) : []);
      })
      .catch(() => {
        if (!cancelled) setLibraryAssetIds([]);
      });
    return () => {
      cancelled = true;
    };
  }, [project.id, sceneId]);

  useEffect(() => {
    if (!shot) return;
    setPrompt(shot.timedPrompt || "");
    const stored = shot.state?.modelId || film?.generatorId || "";
    const nextModelId = stored.includes("minimax-h3") && stored.includes("local") ? "minimax-h3-i2v-local" : stored;
    setModelId(nextModelId);
    // Restore persisted output resolution settings
    const rg = shot.state?.resolvedGeneration;
    if (rg && typeof rg === "object" && !Array.isArray(rg)) {
      if (rg.h3Resolution && typeof rg.h3Resolution === "object" && !Array.isArray(rg.h3Resolution)) {
        const h3 = rg.h3Resolution as Record<string, unknown>;
        setH3Resolution({ mode: (h3.mode as "auto" | "manual") || "auto", megapixels: Number(h3.megapixels) || 0.7 });
      }
      if (typeof rg.ltxQuality === "string") {
        setLtxQuality(rg.ltxQuality as LtxTimelineQuality);
      }
    }
    setSegmentId("");
    setStickyErrorHidden(false);
  }, [shot?.id]);

  useEffect(() => {
    if (!shot || shot.status !== "generating") return;
    const timer = window.setInterval(() => {
      void api.filmTimelineSync(project.id, sceneId, shot.id).then(() => load());
    }, 4000);
    return () => window.clearInterval(timer);
  }, [shot?.id, shot?.status, project.id, sceneId, load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setMessage("");
    try {
      const result = (await action()) as { ok?: boolean; message?: string; error?: string };
      if (result && result.ok === false) setMessage(result.message || result.error || "Timeline could not do that.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Timeline could not do that.");
    } finally {
      setBusy(false);
    }
  }

  async function ensureShot() {
    if (shot) return shot.id;
    const created = (await api.filmTimelineCreateShot(project.id, sceneId, {
      durationSec: duration,
      timedPrompt: prompt,
      generatorId: modelId || undefined,
    })) as { shot?: { id: string } };
    const id = created.shot?.id || "";
    if (id) activeByScene.current[sceneId] = id;
    return id;
  }

  async function generate() {
    // Phase 10: do not keep stale segment failures as current Generate truth.
    setStickyErrorHidden(true);
    setMessage("");
    const id = await ensureShot();
    if (!id) return;
    const body: Record<string, unknown> = { durationSec: duration, timedPrompt: prompt, generatorId: modelId || undefined };
    const providerOpts: Record<string, unknown> = {};
    if (h3Resolution.mode === "manual") providerOpts["h3Resolution"] = h3Resolution;
    if (ltxSelected && ltxQuality) providerOpts["ltxQuality"] = ltxQuality;
    if (Object.keys(providerOpts).length) body["providerOptions"] = providerOpts;
    await run(() => api.filmTimelineGenerate(project.id, sceneId, id, body));
  }

  async function continueShot() {
    if (!shot) return;
    setStickyErrorHidden(false);
    setMessage("");
    const body: Record<string, unknown> = { durationSec: duration, timedPrompt: prompt, generatorId: modelId || undefined };
    const providerOpts: Record<string, unknown> = {};
    if (h3Resolution.mode === "manual") providerOpts["h3Resolution"] = h3Resolution;
    if (ltxSelected && ltxQuality) providerOpts["ltxQuality"] = ltxQuality;
    if (Object.keys(providerOpts).length) body["providerOptions"] = providerOpts;
    await run(() => api.filmTimelineContinue(project.id, sceneId, shot.id, body));
  }

  function place(asset: Asset, mode: "reference" | "timeline") {
    if (mode === "reference") {
      setReferenceOpen({ assetId: asset.id });
      return;
    }
    const kind = String(asset.kind || "image").toLowerCase();
    void run(async () =>
      addToTimeline(project.id, sceneId, {
        mediaType: kind,
        assetId: asset.id,
        shotId: shot?.id || undefined,
        label: assetLabel(asset),
      }),
    );
  }

  async function saveReference(body: { assetId: string; type: string; label: string; tag: string; referenceId?: string }) {
    const id = await ensureShot();
    if (!id) throw new Error("Choose a shot before adding a reference.");
    const result = (await api.filmTimelineAttachReference(project.id, sceneId, id, body)) as { ok?: boolean; message?: string; film?: Film };
    if (result && result.ok === false) throw new Error(result.message || "That reference could not be saved.");
    if (result.film) setFilm(result.film);
    else await load();
    setReferenceOpen(null);
  }

  async function cancelRender() {
    if (!shot) return;
    if (!filmTimelineHasCancellableJob(shot.segments)) return;
    await run(() => api.filmTimelineCancel(project.id, sceneId, shot.id));
  }

  async function createScene() {
    setBusy(true);
    try {
      const created = await api.addScene(project.id, {
        name: `Scene ${project.scenes.length + 1}`,
        engine: "auto",
        duration_sec: duration,
        prompt,
      });
      await refresh();
      if (created?.id) setSelectedScene(created.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "A new scene could not be created.");
    } finally {
      setBusy(false);
    }
  }

  function toggleEye() {
    const next = !publishBar;
    setPublishBar(next);
    saveTimelineWorkspaceLayout({ previewPublishBarVisible: next });
  }

  async function publish(update: boolean) {
    if (!actionsOn) return;
    await run(() => api.filmTimelinePublish(project.id, sceneId, { assetId: preview.assetId, update }));
  }

  async function openMagi() {
    if (!actionsOn) return;
    setMagiOpen(true);
    setMagiLoading(true);
    setMagiError(null);
    try {
      const options = (await api.filmTimelineMagiOptions(project.id, sceneId, preview.assetId)) as {
        ok?: boolean;
        message?: string;
        honesty?: string;
        sourceWidth?: number;
        sourceHeight?: number;
        realesrganReady?: boolean;
        engines?: Array<{ id: string; label?: string; available?: boolean; models?: Array<{ id: string; label?: string }> }>;
        targets?: Array<{ id: string; label: string; width: number; height: number }>;
        defaultEngine?: string;
        defaultModel?: string;
        defaultTarget?: string;
      };
      if (options.ok === false) {
        setMagiError(options.message || "MAGI could not read this video.");
        return;
      }
      setMagiOpts(options);
      setMagiEngine(options.defaultEngine || "ffmpeg-scale");
      setMagiModel(options.defaultModel || "lanczos");
      setMagiTarget(options.defaultTarget || "");
    } catch (error) {
      setMagiError(error instanceof Error ? error.message : "MAGI could not read this video.");
    } finally {
      setMagiLoading(false);
    }
  }

  async function confirmMagi() {
    if (!actionsOn) return;
    setMagiOpen(false);
    await run(() =>
      api.filmTimelineMagi(project.id, sceneId, {
        assetId: preview.assetId,
        engine: magiEngine,
        model: magiModel,
        targetResolution: magiTarget,
      }),
    );
  }

  function mark(which: "in" | "out") {
    const time = videoRef.current?.currentTime ?? 0;
    setRetake((current) => ({ ...current, rangeStart: which === "in" ? time : current.rangeStart, rangeEnd: which === "out" ? time : current.rangeEnd, error: null }));
  }

  async function submitRetake() {
    if (!shot || !actionsOn) return;
    setRetake((current) => ({ ...current, busy: true, error: null }));
    try {
      const result = (await api.filmTimelineRetake(project.id, sceneId, shot.id, {
        markIn: retake.rangeStart,
        markOut: retake.rangeEnd,
        timedPrompt: retake.prompt || prompt,
      })) as { ok?: boolean; message?: string; error?: string };
      if (result.ok === false) {
        setRetake((current) => ({ ...current, busy: false, error: result.message || result.error || "Re-Take could not start." }));
        return;
      }
      setRetake(closedVideoRetakeSession());
      await load();
    } catch (error) {
      setRetake((current) => ({ ...current, busy: false, error: error instanceof Error ? error.message : "Re-Take could not start." }));
    }
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      const binding = matchHotkey(event, loadHotkeys());
      if (!binding || !V2_HOTKEYS.has(binding.actionId)) return;
      event.preventDefault();
      if (binding.actionId === "playPause") {
        const video = videoRef.current;
        if (!video) return;
        if (video.paused) void video.play();
        else video.pause();
      } else if (binding.actionId === "fullscreen" && actionsOn) void fullscreen.toggleFullscreen();
      else if (binding.actionId === "generateScene" && prompt.trim() && !busy) void generate();
      else if (binding.actionId === "retake" && actionsOn) setRetake((current) => ({ ...closedVideoRetakeSession(), open: !current.open }));
      else if (binding.actionId === "openHotkeys") setTab("hotkeys");
      else if (binding.actionId === "escape") setRetake(closedVideoRetakeSession());
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const handleAddFromProjectLibrary = useCallback(
    (assetIds: string[]) => {
      if (!assetIds.length || !sceneId) return;
      void (async () => {
        const already = new Set(libraryAssetIdsRef.current);
        const nextIds = [...libraryAssetIdsRef.current];
        for (const id of assetIds) {
          if (!already.has(id)) nextIds.push(id);
        }
        const result = await api.directorTimelineSetLibraryAssets(project.id, sceneId, nextIds);
        setLibraryAssetIds(Array.isArray(result.libraryAssetIds) ? result.libraryAssetIds.map(String) : nextIds);
        setLibraryOpen(false);
        const payload = await api.library(project.id, { scope: "project", limit: 48, offset: 0 });
        setLibraryItems(((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item)));
      })().catch((error) => setMessage(error instanceof Error ? error.message : "Library update failed."));
    },
    [project.id, sceneId],
  );

  const handleRemoveFromLibrary = useCallback(
    (asset: { id: string }) => {
      if (!sceneId) return;
      const prev = libraryAssetIdsRef.current;
      const nextIds = prev.filter((id) => id !== asset.id);
      if (nextIds.length === prev.length) return;
      setReferenceOpen((current) => (current?.assetId === asset.id ? null : current));
      setLibraryAssetIds(nextIds);
      void api
        .directorTimelineSetLibraryAssets(project.id, sceneId, nextIds)
        .then((result) => {
          setLibraryAssetIds(Array.isArray(result.libraryAssetIds) ? result.libraryAssetIds.map(String) : nextIds);
        })
        .catch((error) => {
          setLibraryAssetIds(prev);
          setMessage(error instanceof Error ? error.message : "Library remove failed.");
        });
    },
    [project.id, sceneId],
  );

  // Staged Library strip: membership from libraryAssetIds SoT (not FE-only pin state).
  const recent = useMemo(() => {
    const byId = new Map<string, Asset>();
    for (const item of libraryItems) byId.set(item.id, item);
    for (const item of project.assets || []) {
      if (isTimelineMediaAsset(item) && !byId.has(item.id)) byId.set(item.id, item);
    }
    return libraryAssetIds.map((id) => byId.get(id)).filter((item): item is Asset => Boolean(item));
  }, [libraryItems, libraryAssetIds, project.assets]);

  const localModels = models.filter((item) => item.local);
  const apiModels = models.filter((item) => !item.local);
  let videoCursor = 0;
  const videoClips = [
    ...(shot?.segments || [])
      .filter((item) => item.assetId)
      .map((item) => {
        const clip = { id: item.id, label: `${item.durationSec}s`, assetId: item.assetId || "", startSec: videoCursor, durationSec: item.durationSec };
        videoCursor += item.durationSec;
        return clip;
      }),
    ...(film?.videoClips || []),
  ];
  const previewUrl = preview.assetId ? api.assetUrl(preview.assetId, null, project.id) : "";

  const inspector = (
    <div className="film-timeline__inspector" data-testid="film-timeline-inspector">
      <button type="button" className="film-timeline__new-scene" data-testid="film-timeline-new-scene" disabled={busy} onClick={() => void createScene()}>
        + New Scene
      </button>
      <label className="film-timeline__field">
        Scene
        <select value={sceneId} onChange={(event) => setSelectedScene(event.target.value)} data-testid="film-timeline-scene">
          {project.scenes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name || "Scene"}
            </option>
          ))}
        </select>
      </label>
      <label className="film-timeline__field">
        Model
        <select value={modelId} onChange={(event) => { const value = event.target.value; setModelId(value); setStickyErrorHidden(true); if (shot) void run(() => api.filmTimelineSetShotModel(project.id, sceneId, shot.id, { generatorId: value })); }} data-testid="film-timeline-model">
          <option value="">Choose a model</option>
          <optgroup label="Local">
            {localModels.map((item) => (
              <option key={item.id} value={item.id} disabled={!item.available}>
                {item.label}
                {item.available ? "" : ` â€” ${item.unavailableReason || "Unavailable"}`}
              </option>
            ))}
          </optgroup>
          <optgroup label="API">
            {apiModels.map((item) => (
              <option key={item.id} value={item.id} disabled={!item.available}>
                {item.label}
                {item.available ? "" : " â€” API not connected"}
              </option>
            ))}
          </optgroup>
        </select>
      </label>

      {(() => {
        // MiniMax H3 advertises no aspect caps; offer its canonical legal set
        // (legalCanvas.H3_SUPPORTED_ASPECTS) instead of the full production list
        // so frontend availability agrees with backend capability refusal.
        const supportedAspects = selectedModel?.supportedAspectRatios;
        const h3Selected = String(selectedModel?.id || "").includes("minimax-h3");
        const aspectOptions = allowedProductionAspects(
          h3Selected && !(supportedAspects && supportedAspects.length) ? H3_SUPPORTED_ASPECTS : PRODUCTION_ASPECTS,
          supportedAspects,
        );
        const current = normalizeProductionAspect(scene?.aspect_ratio);
        const valueInList = aspectOptions.includes(current) ? current : "";
        return (
          <label className="film-timeline__field">
            Picture Shape
            <select
              data-testid="timeline-scene-aspect"
              value={valueInList}
              disabled={!aspectOptions.length || !sceneId}
              onChange={(event) => {
                void api.updateScene(project.id, sceneId, { aspect_ratio: event.target.value }).then(() => refresh());
              }}
            >
              {!aspectOptions.length ? (
                <option value="">No picture shapes for this model</option>
              ) : null}
              {valueInList === "" && aspectOptions.length ? (
                <option value="" disabled>
                  {current} not supported - pick one
                </option>
              ) : null}
              {aspectOptions.map((aspect) => (
                <option key={aspect} value={aspect}>
                  {aspect}
                </option>
              ))}
            </select>
            {!aspectOptions.length ? (
              <span className="scene-meta" role="status" data-testid="timeline-scene-aspect-empty">
                This model lists no production picture shapes.
              </span>
            ) : null}
            {valueInList === "" && aspectOptions.length ? (
              <span className="scene-meta" role="alert" data-testid="timeline-scene-aspect-unsupported">
                {current} is not supported by the selected generator. Choose a listed shape before generate.
              </span>
            ) : null}
          </label>
        );
      })()}

      <GeneratorQualityControls
        // Capability-row projection: ModelRow carries the registry qualityControl /
        // supportedAspectRatios fields this control reads. Boundary cast only.
        option={selectedModel as unknown as TimelineGeneratorOption | null}
        aspectRatio={scene?.aspect_ratio}
        h3Resolution={h3Resolution}
        ltxQuality={ltxQuality}
        seedanceResolution={null}
        draftMode={false}
        megapixelsTestId="film-timeline-megapixels"
        megapixelsSelectTestId="film-timeline-megapixels-select"
        megapixelsAutoTestId="film-timeline-megapixels-auto-dims"
        qualityTestId="film-timeline-quality"
        qualitySelectTestId="film-timeline-quality-select"
        megapixelsLabel="Megapixels"
        megapixelsTip="How many megapixels MiniMax H3 uses for this shot. Auto picks a good size. Higher numbers are sharper but slower."
        qualityLabel="Quality"
        qualityTip="The output size LTX 2.5 renders at. Higher settings are sharper but take longer."
        onH3Change={(next) => { setH3Resolution(next); setStickyErrorHidden(true); }}
        onLtxChange={(tier) => { setLtxQuality(tier); setStickyErrorHidden(true); }}
        onSeedanceChange={() => {}}
      />
      <label className="film-timeline__field">
        Duration
        <select value={duration} onChange={(event) => { setDuration(Number(event.target.value)); setStickyErrorHidden(true); }} data-testid="film-timeline-duration">
          {durationOptions.map((seconds) => (
            <option key={seconds} value={seconds}>
              {seconds} seconds
            </option>
          ))}
        </select>
      </label>
      {modelSwitchNote ? <div className="film-timeline__note" data-testid="film-timeline-duration-note">{modelSwitchNote}</div> : null}
      <button type="button" data-testid="film-timeline-open-library" onClick={() => setLibraryOpen(true)}>
        Open Library
      </button>
      <div className="film-timeline__assets">
        {recent.map((asset) => (
          <div key={asset.id} className="film-timeline__asset" data-testid="film-timeline-asset">
            <img src={api.assetUrl(asset.id, null, project.id)} alt="" />
            <span>{assetLabel(asset)}</span>
            <button
              type="button"
              className={referenced.has(asset.id) ? "is-referenced" : ""}
              onClick={() => place(asset, "reference")}
            >
              {referenced.has(asset.id) ? "âœ“ Referenced" : "Reference"}
            </button>
            <button type="button" onClick={() => place(asset, "timeline")}>
              Add to Timeline
            </button>
            <button
              type="button"
              className="film-timeline__asset-remove"
              data-testid={`film-timeline-asset-remove-${asset.id}`}
              title="Remove reference"
              aria-label="Remove reference"
              onClick={(event) => {
                event.stopPropagation();
                if (shot && referenced.has(asset.id)) {
                  // D4: the X is a real reference detach, then tray membership.
                  void run(() => api.filmTimelineDetachReference(project.id, sceneId, shot.id, asset.id)).then(() =>
                    handleRemoveFromLibrary(asset),
                  );
                  return;
                }
                handleRemoveFromLibrary(asset);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  const seamWarning = [...(shot?.segments || [])]
    .reverse()
    .map((segment) => segment.generationMetadata?.continuity?.seam?.warning || "")
    .find(Boolean);

  const dragPreview = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (fullscreen.isFullscreen) return;
    const host = centerRef.current;
    if (!host) return;
    const startY = event.clientY;
    const startHeight = previewPx;
    let latest = startHeight;
    event.currentTarget.setPointerCapture(event.pointerId);
    const move = (ev: PointerEvent) => {
      latest = clampViewerHeight(startHeight + (ev.clientY - startY), host.clientHeight, window.innerWidth);
      setPreviewPx(latest);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      saveProjectPreviewHeightRatio(project.id, latest / Math.max(1, host.clientHeight));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const left = (
    <div className="film-timeline__left">
      <div className="film-timeline__tabs" role="tablist">
        {(
          [
            ["inspector", "Inspector"],
            ["hotkeys", "Hot Keys"],
            ["gpu", "GPU"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? "is-selected" : ""}
            data-testid={`film-timeline-tab-${id}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          className="film-timeline__panel-toggle"
          aria-label="Collapse Side Panel"
          title="Collapse Side Panel"
          data-testid="film-timeline-collapse-panel"
          onClick={() => setPanelCollapsed(true)}
        >
          <PanelChevron direction="left" />
        </button>
      </div>
      {tab === "inspector" ? inspector : null}
      {tab === "hotkeys" ? <TimelineHotKeysPane /> : null}
      {tab === "gpu" && scene ? <TimelineGpuPane project={project} scene={scene} onChange={() => void refresh()} generatorId={modelId || film?.generatorId || null} planDims={planDims} /> : null}
    </div>
  );

  const center = (
    <div className="film-timeline__center" ref={assignCenter}>
      <div
        className={`film-timeline__monitor live-preview-stage${fullscreen.isFullscreen ? " is-preview-fullscreen" : ""}`}
        ref={fullscreen.containerRef}
        data-testid="film-timeline-monitor"
        style={fullscreen.isFullscreen ? undefined : { height: previewPx, flex: "0 0 auto" }}
      >
        <button
          type="button"
          className={`live-preview-cancel-in-stage${cancellable ? "" : " is-idle"}`}
          data-testid="live-preview-cancel-in-stage"
          data-film-timeline-cancel="1"
          data-cancel-armed={cancellable ? "true" : "false"}
          title={cancellable ? "Cancel render" : "Nothing is rendering"}
          aria-label={cancellable ? "Cancel render" : "Cancel render (nothing to cancel)"}
          aria-disabled={cancellable ? undefined : true}
          disabled={!cancellable}
          onClick={() => {
            if (!cancellable) return;
            void cancelRender();
          }}
        >
          Cancel
        </button>
        {preview.kind === "video" && previewUrl ? <video ref={videoRef} src={previewUrl} controls /> : null}
        {preview.kind === "empty" ? <p>Generate a shot to see it here.</p> : null}
        <FilmPreviewClock videoRef={videoRef} active={preview.kind === "video"} />
        {generating ? (
          <div className="film-timeline__progress" data-testid="film-timeline-progress">
            <span>
              {modelLabel} Â· {duration}s
            </span>
            <i />
          </div>
        ) : null}
        <div
          className={[
            "live-preview-publish-bar",
            magiOpen && publishBar ? "live-preview-publish-bar--chooser" : "",
            !publishBar ? "live-preview-publish-bar--collapsed" : "",
          ].filter(Boolean).join(" ")}
          data-testid="live-preview-publish-bar"
          data-collapsed={publishBar ? "false" : "true"}
          role="group"
          aria-label="Timeline publish and MAGI upscale"
        >
          {publishBar ? (
            <div className="live-preview-publish-bar__row">
              <button
                type="button"
                className="live-preview-publish-bar__btn live-preview-publish-bar__btn--publish"
                data-testid="live-preview-publish"
                title="Register Video Published Master in the Library from the full stitched scene"
                aria-label="Publish"
                disabled={!actionsOn || busy}
                onClick={() => void publish(false)}
              >
                {busy ? "Publishingâ€¦" : "PUBLISH"}
              </button>
              <button
                type="button"
                className="live-preview-publish-bar__btn live-preview-publish-bar__btn--update"
                data-testid="live-preview-update-published"
                title="Update the Video Published Master from the current full stitch"
                aria-label="Update Published"
                disabled={!actionsOn || busy || !film?.publishedAssetId}
                onClick={() => void publish(true)}
              >
                {busy ? "Updatingâ€¦" : "UPDATE PUBLISHED"}
              </button>
              {!magiOpen ? (
                <button
                  type="button"
                  className="live-preview-publish-bar__btn live-preview-publish-bar__btn--upscale"
                  data-testid="live-preview-upscale-magi"
                  title="Upscale the full stitched (or published) master with MAGI â€” does not auto-publish"
                  aria-label="Upscale with MAGI"
                  disabled={!actionsOn || busy}
                  onClick={() => void openMagi()}
                >
                  UPSCALE WITH MAGI
                </button>
              ) : null}
              <PreviewPublishBarVisibilityToggle visible attention={false} onToggle={toggleEye} />
            </div>
          ) : (
            <PreviewPublishBarVisibilityToggle visible={false} attention={false} onToggle={toggleEye} />
          )}
          {publishBar && magiOpen ? (
            <MagiUpscaleChooser
              loading={magiLoading}
              error={magiError}
              honesty={magiOpts?.honesty}
              sourceResolution={magiOpts?.sourceWidth && magiOpts?.sourceHeight ? `${magiOpts.sourceWidth}x${magiOpts.sourceHeight}` : ""}
              realesrganReady={magiOpts?.realesrganReady}
              engines={magiOpts?.engines || []}
              targets={magiOpts?.targets || []}
              engine={magiEngine}
              model={magiModel}
              targetId={magiTarget}
              busy={busy}
              onEngineChange={setMagiEngine}
              onModelChange={setMagiModel}
              onTargetChange={setMagiTarget}
              onCancel={() => setMagiOpen(false)}
              onConfirm={() => void confirmMagi()}
            />
          ) : null}
        </div>
        {retake.open ? (
          <TimelineRetakeOverlay
            session={retake}
            videoAvailable={actionsOn}
            onMarkIn={() => mark("in")}
            onMarkOut={() => mark("out")}
            onPrompt={(value) => setRetake((current) => ({ ...current, prompt: value }))}
            onRemoveBackground={() => setRetake((current) => ({ ...current, removeBackgroundUsed: true }))}
            onCancel={() => setRetake(closedVideoRetakeSession())}
            onSubmit={() => void submitRetake()}
          />
        ) : null}
        <PreviewVideoActionMenu
          enabled={actionsOn}
          showWhenDisabled
          retakeActive={retake.open}
          onOpenRetake={() => setRetake((current) => (current.open ? closedVideoRetakeSession() : { ...closedVideoRetakeSession(), open: true }))}
          isFullscreen={fullscreen.isFullscreen}
          onToggleFullscreen={() => void fullscreen.toggleFullscreen()}
        />
        <PreviewFullscreenTransport
          videoRef={videoRef}
          isFullscreen={fullscreen.isFullscreen}
          isVideoMedia={actionsOn}
          onExitFullscreen={() => void fullscreen.exitFullscreen()}
          onTogglePlay={() => {
            const video = videoRef.current;
            if (!video) return;
            if (video.paused) void video.play();
            else video.pause();
          }}
          onSeekLocalTime={(localSec) => {
            if (videoRef.current) videoRef.current.currentTime = localSec;
          }}
          onRetake={() => setRetake((current) => (current.open ? closedVideoRetakeSession() : { ...closedVideoRetakeSession(), open: true }))}
          retakeActive={retake.open}
          timelineTimeSec={videoRef.current?.currentTime || 0}
          timelineDurationSec={videoRef.current?.duration || 0}
          timelinePlaying={Boolean(videoRef.current && !videoRef.current.paused)}
        />
      </div>
      {fullscreen.isFullscreen ? null : (
        <div
          className="timeline-workspace-divider"
          data-testid="timeline-monitor-divider"
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize preview"
          onPointerDown={dragPreview}
        >
          <span className="timeline-workspace-divider__grip" />
        </div>
      )}
      {videoClips.length ? (
        <div className="film-timeline__track">
          <span>Video</span>
          <div>
            {videoClips.map((clip) => (
              <button key={clip.id} type="button" className={segmentId === clip.id ? "is-selected" : ""} onClick={() => setSegmentId(clip.id)}>
                {clip.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {audioRows(film?.audio || []).map((row, index) => (
        <div key={`audio-${index}`} className="film-timeline__track">
          <span>Audio</span>
          <div>
            {row.map((clip) => (
              <button key={clip.id} type="button">
                {clip.label}
                {clip.role ? ` Â· ${clip.role}` : ""}
              </button>
            ))}
          </div>
        </div>
      ))}
      {(film?.sfx || []).length ? (
        <div className="film-timeline__track">
          <span>SFX</span>
          <div>
            {(film?.sfx || []).map((clip) => (
              <button key={clip.id} type="button">
                {clip.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="film-timeline__tool-slot" data-testid="film-timeline-tool-slot">
        <PromptToolbar
          projectId={project.id}
          sceneId={sceneId}
          shotId={shot?.id || ""}
          prompt={prompt}
          onPrompt={setPrompt}
          onReferences={() => setReferenceOpen({})}
        />
      </div>
      {activeReferences.length ? (
        <div className="film-reference-strip" data-testid="film-reference-strip">
          {activeReferences.map((ref) => {
            const label = filmReferenceChipLabel(ref);
            return (
              <span key={ref.id} className={`film-reference-chip is-${ref.type || "other"}`}>
                <button type="button" onClick={() => setReferenceOpen({ assetId: ref.assetId, editId: ref.id })}>
                  {label}
                </button>
                <button
                  type="button"
                  aria-label={`Remove ${label}`}
                  onClick={() => shot && void run(() => api.filmTimelineDetachReference(project.id, sceneId, shot.id, ref.assetId))}
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      ) : null}
      <label className="film-timeline__prompt">
        Timed Prompt
        <textarea value={prompt} data-testid="film-timeline-prompt" onChange={(event) => setPrompt(event.target.value)} />
      </label>
      <div className="film-timeline__actions">
        <button type="button" data-testid="film-timeline-generate" disabled={busy || !prompt.trim()} onClick={() => void generate()}>
          Generate Shot
        </button>
        <button type="button" data-testid="film-timeline-continue" disabled={busy || !completed || !prompt.trim()} onClick={() => void continueShot()}>
          Continue Shot
        </button>
      </div>
      {message || segmentError || seamWarning ? (
        <p className="film-timeline__error" data-testid="film-timeline-error">
          {message || segmentError || seamWarning}
        </p>
      ) : null}
    </div>
  );

  return (
    <>
      <FilmDesk left={left} right={center} collapsed={panelCollapsed} onExpand={() => setPanelCollapsed(false)} />
      {referenceOpen ? (
        <FilmReferenceModal
          assets={libraryItems}
          references={activeReferences}
          initialAssetId={referenceOpen.assetId}
          editId={referenceOpen.editId}
          onClose={() => setReferenceOpen(null)}
          onSave={saveReference}
        />
      ) : null}
      {libraryOpen ? (
        <AddFromProjectLibraryModal
          project={project}
          alreadyIds={libraryAssetIds}
          onClose={() => setLibraryOpen(false)}
          onAssetsChanged={() => void refresh()}
          onAdd={handleAddFromProjectLibrary}
        />
      ) : null}
    </>
  );
}
