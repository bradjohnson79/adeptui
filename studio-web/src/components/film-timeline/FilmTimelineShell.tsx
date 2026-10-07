import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode, type RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { previewActionsEnabled, resolveFilmTimelinePreviewMedia } from "../../filmTimeline/resolveFilmTimelinePreviewMedia";
import { filmTimelineCancelPresentation, filmTimelineHasCancellableJob } from "../../filmTimeline/filmTimelineCancelVisibility";
import type { Asset, Project, Scene } from "../../types";
import { isTimelineMediaAsset } from "../../timelineMediaTypes";
import { isEditableTarget, loadHotkeys, matchHotkey, registerWorkspaceKeyHandler } from "../../timelineMaster/timelineHotkeys";
import {
  clampViewerHeight,
  loadProjectPreviewHeightRatio,
  loadTimelineWorkspaceLayout,
  saveProjectPreviewHeightRatio,
  saveTimelineWorkspaceLayout,
} from "../../timelineMaster/workspaceLayout";
import { closedVideoRetakeSession, canSubmitVideoRetake, type VideoRetakeSession } from "../../timelineMaster/videoRetake";
import { usePreviewFullscreen } from "../../workspace/fullscreen/usePreviewFullscreen";
import { PromptToolbar } from "../../filmTimeline/promptGuides/PromptToolbar";
import { canonicalSceneBatches, nextShotNumber, pendingSceneBatch, previewShotIdentity, shotTag, trackHasBatches } from "../../filmTimeline/sceneBatches";
import { fileTimeForWindow, sceneLocalFromFile, stitchCoversClips, windowReachedEnd } from "../../filmTimeline/scenePlayback";
import { clipAtTime, sceneDuration, sceneTimeFromPreview, skipSceneTime, visualWindows, type VisualClip } from "../../filmTimeline/visualTrack";
import { buildProjectWorkspaceLocation } from "../../navigation/projectWorkspaceNavigation";
import { VisualTrack } from "./VisualTrack";
import { SPOKEN_LANGUAGES } from "../../filmTimeline/spokenLanguage";
import { FilmReferenceModal, type FilmReference, type FilmReferenceSave } from "./FilmReferenceModal";
import { publishableSceneAsset } from "../../filmTimeline/publishableSceneAsset";
import { LibraryReferenceControl } from "./LibraryReferenceControl";
import type { ImageRole } from "./referenceRole";
import { libraryAfterClassification, mergeLibraryPage } from "./referenceLibrary";
import { filmReferenceChipLabel } from "./filmReferenceChipLabel";
import { AddFromProjectLibraryModal } from "../timeline-master/AddFromProjectLibraryModal";
import { GeneratorQualityControls } from "../timeline-master/GeneratorCapabilityControls";
import {
  allowedProductionAspects,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import { normalizeProductionAspect } from "../../workspacePrefs";
import { LTX_DEFAULT_QUALITY, type LtxTimelineQuality } from "../../timelineMaster/legalCanvas";
import { ltxTimelineFrameCount } from "../../video/legalCanvas";
import { PreviewFullscreenTransport } from "../timeline-master/PreviewFullscreenTransport";
import {
  TransportBatchEndIcon,
  TransportBatchStartIcon,
  TransportForward5Icon,
  TransportPauseIcon,
  TransportPlayIcon,
  TransportRewind5Icon,
  TransportSceneEndIcon,
  TransportSceneStartIcon,
} from "../timeline-master/previewTransportIcons";
import { PreviewVideoActionMenu } from "../timeline-master/PreviewVideoActionMenu";
import { TimelineGpuPane } from "../timeline-master/TimelineGpuPane";
import { displayLtxMode, filmTimelineRenderHud, filmTimelineRenderLine, foldLegacyProductionSelection, renderNoticeForSegments, resolveFilmTimelinePlanDims, visibleRenderNotice, visibleSegmentError, type FilmRenderHudModel } from "../../filmTimeline/filmTimelinePresentation";
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
  compositionRole?: string | null;
  sourceSegmentId?: string | null;
  origin?: string | null;
  trimInSec?: number | null;
  trimOutSec?: number | null;
  shotNumber?: number | null;
  lastFrameAssetId?: string | null;
    generationMetadata?: {
    compositionHold?: boolean;
    segmentedRetake?: { sourceSegmentId?: string } | null;
    prepend?: { targetSegmentId?: string } | null;
    continuity?: { seam?: { warning?: string | null } };
    resolvedGeneration?: Record<string, unknown> | null;
    legalCanvas?: Record<string, unknown> | null;
    renderStatus?: {
      progress?: number;
      progressGrounded?: boolean;
      phaseLabel?: string;
      elapsedSec?: number;
      status?: string;
      apiPhase?: string | null;
    };
  };
};
type Shot = {
  id: string;
  name: string;
  order?: number;
  durationSec: number;
  timedPrompt: string;
  status: string;
  segments: Segment[];
  state: { references: Reference[]; firstFrameAssetId?: string | null; stitchAssetId?: string | null; stitchStatus?: string | null; stitchSegmentIds?: string[] | null; modelId?: string | null; resolvedGeneration?: Record<string, unknown> | null; spokenLanguage?: string | null; spokenLanguageCustom?: string | null; dialogueAuthority?: string | null };
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
  publishedSourceAssetId?: string | null;
  highestShotNumber?: number | null;
};
type ModelRow = { id: string; label: string; local: boolean; available: boolean; unavailableReason: string; supportedDurations?: number[]; maxDurationSec?: number; qualityControl?: string; supportedAspectRatios?: string[]; continuationMode?: "hard" | "soft" | "none"; supportsTextToVideo?: boolean; supportsStartFrame?: boolean; supportsEndFrame?: boolean; supportsThreeFrame?: boolean; supportsReferenceToVideo?: boolean; notes?: string };
type LeftTab = "inspector" | "hotkeys" | "gpu";
type WorkspaceTab = "prompt" | "track";

type Props = {
  project: Project;
  selectedScene?: string;
  setSelectedScene: (id: string) => void;
  refresh: () => Promise<void> | void;
};

const LEFT_TAB_KEY = "adept_film_timeline_left_tab";
const LEFT_COLLAPSE_KEY = "adept_film_timeline_left_collapsed";
const V2_HOTKEYS = new Set(["playPause", "fullscreen", "generateScene", "retake", "openHotkeys", "escape"]);

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

function RenderMeter({ model }: { model: FilmRenderHudModel }) {
  const set = model.bar === "live" || model.bar === "held";
  return (
    <i
      className={set ? "is-set" : undefined}
      style={set && model.percent !== null ? { width: `${model.percent}%` } : undefined}
      data-testid="film-timeline-render-meter"
    />
  );
}

function PreviewTransport({
  clips,
  playheadSec,
  playing,
  onTogglePlay,
  onSeek,
}: {
  clips: VisualClip[];
  playheadSec: number;
  playing: boolean;
  onTogglePlay: () => void;
  onSeek: (sceneTime: number) => void;
}) {
  const piece = clipAtTime(clips, playheadSec);
  const sceneEnd = sceneDuration(clips);
  const hasPicture = clips.length > 0;
  const playLabel = playing ? "Pause" : "Play";
  const skip = (delta: number) => onSeek(skipSceneTime(playheadSec, delta, sceneEnd));
  return (
    <div className="film-preview-transport" data-testid="film-timeline-transport" role="toolbar" aria-label="Preview transport">
      <button type="button" className="preview-transport-btn" title="Beginning of Scene" aria-label="Beginning of Scene" disabled={!hasPicture} onClick={() => onSeek(0)}>
        <TransportSceneStartIcon />
      </button>
      <button type="button" className="preview-transport-btn" title="Start of Batch" aria-label="Start of Batch" disabled={!piece} onClick={() => piece && onSeek(piece.start)}>
        <TransportBatchStartIcon />
      </button>
      <button type="button" className="preview-transport-btn" data-testid="film-timeline-skip-back" title="Back 5 seconds" aria-label="Back 5 seconds" disabled={!hasPicture} onClick={() => skip(-5)}>
        <TransportRewind5Icon />
      </button>
      <button type="button" className="preview-transport-btn preview-transport-play" title={playLabel} aria-label={playLabel} aria-pressed={playing} disabled={!hasPicture} onClick={onTogglePlay}>
        {playing ? <TransportPauseIcon /> : <TransportPlayIcon />}
      </button>
      <button type="button" className="preview-transport-btn" data-testid="film-timeline-skip-forward" title="Forward 5 seconds" aria-label="Forward 5 seconds" disabled={!hasPicture} onClick={() => skip(5)}>
        <TransportForward5Icon />
      </button>
      <button type="button" className="preview-transport-btn" title="End of Batch" aria-label="End of Batch" disabled={!piece} onClick={() => piece && onSeek(piece.end)}>
        <TransportBatchEndIcon />
      </button>
      <button type="button" className="preview-transport-btn" title="End of Scene" aria-label="End of Scene" disabled={!hasPicture} onClick={() => onSeek(sceneEnd)}>
        <TransportSceneEndIcon />
      </button>
    </div>
  );
}

function FilmTimelineRenderHud({ model, onDismiss }: { model: FilmRenderHudModel; onDismiss: () => void }) {
  const [compact, setCompact] = useState(false);
  const terminal = model.kind === "cancelled" || model.kind === "failed";
  return (
    <div className={`film-timeline__hud${compact ? " is-compact" : ""}`} data-testid="film-timeline-render-hud" aria-live="polite">
      <div className="film-timeline__hud-head">
        <strong data-testid="film-timeline-render-headline">{filmTimelineRenderLine(model)}</strong>
        <span className="film-timeline__hud-tools">
          <button type="button" className="film-timeline__hud-fold" aria-label={compact ? "Expand render status" : "Collapse render status"} onClick={() => setCompact((value) => !value)}>
            {compact ? "+" : "−"}
          </button>
          {terminal ? (
            <button type="button" className="film-timeline__remove" aria-label="Dismiss notice" data-testid="film-timeline-hud-dismiss" onClick={onDismiss}>
              ×
            </button>
          ) : null}
        </span>
      </div>
      {compact ? null : (
        <>
          {model.model ? <p>{model.model}</p> : null}
          {model.place ? <p>{model.place}</p> : null}
          {model.elapsed ? <p>{`Elapsed ${model.elapsed}`}</p> : null}
          {model.detail ? <p>{model.detail}</p> : null}
          {model.bar !== "none" ? (
            <div className="film-timeline__hud-bar">
              <RenderMeter model={model} />
            </div>
          ) : null}
        </>
      )}
    </div>
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

const UNPUBLISHED_MAGI = "Your scene must be published before it can be sent to MAGI.";
const STALE_MAGI = "Update Published before this scene can be sent to MAGI.";
/** Visual lifetime of the top-action notification beneath the publish bar. */
const TIMELINE_TOP_ACTION_NOTE_MS = 10_000;

export function FilmTimelineShell({ project, selectedScene, setSelectedScene, refresh }: Props) {
  const navigate = useNavigate();
  const sceneId = selectedScene || project.scenes[0]?.id || "";
  const scene = project.scenes.find((item) => item.id === sceneId) as Scene | undefined;
  const activeByScene = useRef<Record<string, string>>({});
  // Scene id of the film currently held in state. During a scene switch there
  // is one render where the NEW sceneId meets the OLD film; scene-scoped shot
  // reads (dialogue, etc.) must not fire for that stale pairing.
  const filmSceneRef = useRef<string>("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const pendingSeek = useRef<number | null>(null);
  const [playheadSec, setPlayheadSec] = useState(0);
  const fullscreen = usePreviewFullscreen();
  const [film, setFilm] = useState<Film | null>(null);
  const [shotId, setShotId] = useState("");
  const [segmentId, setSegmentId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [spokenLanguage, setSpokenLanguage] = useState("en");
  const [spokenCustom, setSpokenCustom] = useState("");
  const [dialogueAuthority, setDialogueAuthority] = useState("native_model");
  const [dialogueNote, setDialogueNote] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceTab>("prompt");
  const [addIntent, setAddIntent] = useState<"append" | "prepend" | null>(null);
  const [modelId, setModelId] = useState("");
  const [models, setModels] = useState<ModelRow[]>([]);
  const [productionAspects, setProductionAspects] = useState<string[]>([]);
  const [h3Aspects, setH3Aspects] = useState<string[]>([]);
  const [h3Resolution, setH3Resolution] = useState<{ mode: "auto" | "manual"; megapixels: number }>({ mode: "auto", megapixels: 0.7 });
  const [ltxQuality, setLtxQuality] = useState<LtxTimelineQuality>(LTX_DEFAULT_QUALITY);
  const [ltxMode, setLtxMode] = useState<"text" | "one_frame" | "start_end">("text");
  const [ltxStartAssetId, setLtxStartAssetId] = useState("");
  const [ltxEndAssetId, setLtxEndAssetId] = useState("");
  const [seedanceResolution, setSeedanceResolution] = useState<string>("720p");
  const [message, setMessage] = useState("");
  const [stickyErrorHidden, setStickyErrorHidden] = useState(false);
  const [dismissedNoticeKey, setDismissedNoticeKey] = useState("");
  const [completeKey, setCompleteKey] = useState("");
  const sawGenerating = useRef(false);
  const batchesAtStart = useRef(0);
  const [busy, setBusy] = useState(false);
  const publishLock = useRef(false);
  const [publishPhase, setPublishPhase] = useState<null | "publish" | "update">(null);
  const [creatingScene, setCreatingScene] = useState(false);
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
  const [libraryOpen, setLibraryOpen] = useState<null | "references" | "visual" | "ltx-frame" | "ltx-end">(null);
  const [referenceOpen, setReferenceOpen] = useState<{ assetId?: string; editId?: string } | null>(null);
  const [libraryItems, setLibraryItems] = useState<Asset[]>([]);
  const [classifyingId, setClassifyingId] = useState("");
  const [classifyError, setClassifyError] = useState<{ assetId: string; message: string } | null>(null);
  const classifyStamp = useRef(0);
  const [libraryAssetIds, setLibraryAssetIds] = useState<string[]>([]);
  const libraryAssetIdsRef = useRef<string[]>([]);
  libraryAssetIdsRef.current = libraryAssetIds;
  const [publishBar, setPublishBar] = useState(() => loadTimelineWorkspaceLayout().previewPublishBarVisible);
  const [retake, setRetake] = useState<VideoRetakeSession>(closedVideoRetakeSession());
  const [playing, setPlaying] = useState(false);
  const [stitching, setStitching] = useState(false);
  const [stitchNote, setStitchNote] = useState("");
  const continueScene = useRef(false);
  // Top-action notification (Publish / Update Published / Send to MAGI): purely
  // event-driven with one shared 10-second auto-dismiss lifetime. The publish
  // gate state still drives button disabled/title — it no longer pins text
  // beneath the bar. `key` re-arms the CSS fade and the timer on re-trigger.
  const [magiNote, setMagiNote] = useState<{ text: string; key: number }>({ text: "", key: 0 });
  const magiNoteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retakeAwaiting = useRef("");
  const trackScrollByScene = useRef<Record<string, number>>({});

  const clearMagiNoteTimer = useCallback(() => {
    if (magiNoteTimer.current != null) {
      clearTimeout(magiNoteTimer.current);
      magiNoteTimer.current = null;
    }
  }, []);

  const showMagiNote = useCallback(
    (text: string) => {
      const note = String(text || "").trim();
      if (!note) return;
      clearMagiNoteTimer();
      setMagiNote((current) => ({ text: note, key: current.key + 1 }));
      magiNoteTimer.current = setTimeout(() => {
        magiNoteTimer.current = null;
        setMagiNote((current) => ({ ...current, text: "" }));
      }, TIMELINE_TOP_ACTION_NOTE_MS);
    },
    [clearMagiNoteTimer],
  );

  // Scene/shot switch clears any stale top-action note so a message from one
  // scene can never linger over another. Unmount (leaving Timeline) clears the
  // timer so no ghost message can fire later.
  useEffect(() => {
    clearMagiNoteTimer();
    setMagiNote({ text: "", key: 0 });
  }, [sceneId, shotId, clearMagiNoteTimer]);
  useEffect(() => () => clearMagiNoteTimer(), [clearMagiNoteTimer]);

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

  const magiGate = useMemo(() => {
    const stitchId = publishableSceneAsset(shot);
    const stitchReady = Boolean(stitchId);
    const published = String(film?.publishedAssetId || "");
    const source = String(film?.publishedSourceAssetId || "");
    if (!published) {
      return { state: "unpublished" as const, stitchId, stitchReady, note: UNPUBLISHED_MAGI };
    }
    if (!stitchReady || source !== stitchId) {
      return { state: "stale" as const, stitchId, stitchReady, note: STALE_MAGI };
    }
    return { state: "current" as const, stitchId, stitchReady, note: "" };
  }, [film?.publishedAssetId, film?.publishedSourceAssetId, shot?.state.stitchAssetId, shot?.state.stitchStatus, shot?.segments]);

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
  const cancelUi = filmTimelineCancelPresentation(shot?.segments);
  const cancellable = cancelUi.armed;
  const rawSegmentError = (shot?.segments || []).find((item) => item.status === "failed" && item.error)?.error || "";
  const _gidForErr = String(modelId || film?.generatorId || "").toLowerCase();
  const h3DirectorSelected = _gidForErr.includes("minimax-h3") && _gidForErr.includes("local");
  const renderNotice = visibleRenderNotice(renderNoticeForSegments(shot?.segments), dismissedNoticeKey);
  const segmentError = visibleSegmentError(rawSegmentError, stickyErrorHidden || Boolean(renderNotice) || dismissedNoticeKey.endsWith(":failed"), {
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
  const previewShotLabel = useMemo(
    () => previewShotIdentity(shot?.segments, playheadSec, segmentId),
    [shot?.segments, playheadSec, segmentId],
  );
  const renderHud = useMemo(
    () =>
      filmTimelineRenderHud({
        segments: shot?.segments,
        stitchStatus: stitching ? "stitching" : shot?.state.stitchStatus,
        modelLabel: models.find((item) => item.id === modelId)?.label || "",
        sceneName: scene?.name,
        shotName: previewShotLabel,
        showComplete: Boolean(completeKey) && renderNotice?.key === completeKey,
        showTerminal: renderNotice?.status === "failed" || renderNotice?.status === "cancelled",
      }),
    [shot?.segments, shot?.state.stitchStatus, stitching, models, modelId, scene?.name, previewShotLabel, completeKey, renderNotice],
  );

  const selectedModel = useMemo(() => models.find((item) => item.id === modelId) || null, [models, modelId]);
  // LTX-only quality: H3 and other generators must not receive ltxQuality.
  const ltxSelected = Boolean(
    selectedModel && (String(selectedModel.id).includes("ltx-2.5") || selectedModel.qualityControl === "ltx_quality"),
  );
  const frameModeModel = Boolean(
    selectedModel?.supportsTextToVideo && (selectedModel.supportsStartFrame || selectedModel.supportsEndFrame),
  );
  const showSemanticReferences = selectedModel?.supportsReferenceToVideo !== false;
  const seedanceSelected = Boolean(selectedModel && selectedModel.qualityControl === "seedance_resolution");
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
    filmSceneRef.current = sceneId;
    setFilm(next);
    setShotId((current) => {
      const remembered = activeByScene.current[sceneId];
      if (remembered && next.shots.some((item) => item.id === remembered)) return remembered;
      if (current && next.shots.some((item) => item.id === current)) return current;
      const latest = [...next.shots].sort((a, b) => (a.order || 0) - (b.order || 0)).at(-1);
      return latest?.id || "";
    });
  }, [project.id, sceneId]);

  // A scene switch must never paint the previous scene's film under the new id.
  // Clear the scene-local film while the new scene's canonical state loads; the
  // monitor shows its empty state instead of stale Shot labels or a stale stitch.
  useEffect(() => {
    filmSceneRef.current = "";
    setFilm(null);
    setShotId("");
    setSegmentId("");
    setPlayheadSec(0);
    continueScene.current = false;
    pendingSeek.current = null;
    videoRef.current?.pause();
    setPlaying(false);
    setRetake(closedVideoRetakeSession());
    setReferenceOpen(null);
    setLibraryOpen(null);
    setDismissedNoticeKey("");
    setStitchNote("");
  }, [sceneId]);

  useEffect(() => {
    if (sceneId && shotId) activeByScene.current[sceneId] = shotId;
  }, [sceneId, shotId]);

  useEffect(() => {
    void load().catch((error) => setMessage(error instanceof Error ? error.message : "Timeline could not be opened."));
    void api.filmTimelineCapabilities().then((response) => {
      setProductionAspects(Array.isArray(response.productionAspects) ? response.productionAspects.map(String) : []);
      setH3Aspects(Array.isArray(response.h3Aspects) ? response.h3Aspects.map(String) : []);
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
            continuationMode: String(item.continuationMode || "") === "hard" ? "hard" : String(item.continuationMode || "") === "soft" ? "soft" : "none",
            supportsTextToVideo: Boolean(item.supportsTextToVideo),
            supportsStartFrame: Boolean(item.supportsStartFrame),
            supportsEndFrame: Boolean(item.supportsEndFrame),
            supportsThreeFrame: Boolean(item.supportsThreeFrame),
            supportsReferenceToVideo: Boolean(item.supportsReferenceToVideo),
            notes: String(item.notes || ""),
          })),
      );
    });
    const stampAtLoad = classifyStamp.current;
    void api.library(project.id, { scope: "project", limit: 48, offset: 0 }).then((payload) => {
      if (stampAtLoad !== classifyStamp.current) return;
      const rows = ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item));
      setLibraryItems((current) => mergeLibraryPage(current, rows));
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

  const missingTrayIds = libraryAssetIds.filter((id) => !libraryItems.some((item) => item.id === id)).join(",");
  useEffect(() => {
    if (!missingTrayIds) return;
    const stampAtFetch = classifyStamp.current;
    let cancelled = false;
    void api.library(project.id, { scope: "project", ids: missingTrayIds, limit: 64 }).then((payload) => {
      if (cancelled || stampAtFetch !== classifyStamp.current) return;
      const rows = ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item));
      setLibraryItems((current) => mergeLibraryPage(current, rows));
    });
    return () => {
      cancelled = true;
    };
  }, [missingTrayIds, project.id]);

  useEffect(() => {
    if (!shot) return;
    setPrompt(shot.timedPrompt || "");
    const storedLanguage = String(shot.state?.spokenLanguage || "en");
    setSpokenLanguage(SPOKEN_LANGUAGES.some((item) => item.code === storedLanguage) ? storedLanguage : "en");
    setSpokenCustom(String(shot.state?.spokenLanguageCustom || ""));
    const storedDialogue = String(shot.state?.dialogueAuthority || "native_model");
    setDialogueAuthority(storedDialogue === "character_voice" ? "character_voice" : "native_model");
    setDialogueNote("");
    setWorkspace(trackHasBatches(shot.segments) ? "track" : "prompt");
    const stored = shot.state?.modelId || film?.generatorId || "";
    const rg = shot.state?.resolvedGeneration;
    const storedMode = rg && typeof rg === "object" && !Array.isArray(rg) ? String(rg.ltxMode || "") : "";
    const folded = foldLegacyProductionSelection(stored, storedMode);
    const nextModelId = folded.modelId.includes("minimax-h3") && folded.modelId.includes("local") ? "minimax-h3-i2v-local" : folded.modelId;
    setModelId(nextModelId);
    // Restore persisted output resolution settings
    if (rg && typeof rg === "object" && !Array.isArray(rg)) {
      if (rg.h3Resolution && typeof rg.h3Resolution === "object" && !Array.isArray(rg.h3Resolution)) {
        const h3 = rg.h3Resolution as Record<string, unknown>;
        setH3Resolution({ mode: (h3.mode as "auto" | "manual") || "auto", megapixels: Number(h3.megapixels) || 0.7 });
      }
      if (typeof rg.ltxQuality === "string") {
        setLtxQuality(rg.ltxQuality as LtxTimelineQuality);
      }
      if (typeof rg.seedanceResolution === "string" && rg.seedanceResolution) {
        setSeedanceResolution(rg.seedanceResolution);
      }
    }
    const storedFrame = rg && typeof rg === "object" && !Array.isArray(rg) ? rg.ltxStartAssetId : "";
    const storedEnd = rg && typeof rg === "object" && !Array.isArray(rg) ? rg.ltxEndAssetId : "";
    const startId = typeof storedFrame === "string" ? storedFrame : "";
    const endId = typeof storedEnd === "string" ? storedEnd : "";
    setLtxMode(displayLtxMode(folded.ltxMode, startId));
    setLtxStartAssetId(startId);
    setLtxEndAssetId(endId);
    setSegmentId("");
    setAddIntent(null);
    setStickyErrorHidden(false);
    setCompleteKey("");
    sawGenerating.current = false;
  }, [shot?.id]);

  useEffect(() => {
    if (!sceneId || !shot?.id || dialogueAuthority !== "character_voice") return;
    // Stale-pair guard: during a scene switch the outgoing scene's film is
    // still in state for one render; never ask the NEW scene about the OLD shot.
    if (filmSceneRef.current !== sceneId) return;
    let cancelled = false;
    void api.filmTimelineDialogue(project.id, sceneId, shot.id).then((saved) => {
      if (!cancelled) setDialogueNote(String(saved.message || ""));
    }).catch(() => {
      if (!cancelled) setDialogueNote("");
    });
    return () => {
      cancelled = true;
    };
  }, [project.id, sceneId, shot?.id, dialogueAuthority]);

  useEffect(() => {
    const sourceId = retakeAwaiting.current;
    if (!sourceId || !shot) return;
    const hold = shot.segments.some(
      (item) => item.generationMetadata?.segmentedRetake && item.status !== "failed" && item.status !== "cancelled",
    );
    const source = shot.segments.some((item) => item.id === sourceId);
    if (!source && !hold) {
      retakeAwaiting.current = "";
      setRetake(closedVideoRetakeSession());
      return;
    }
    const failed = shot.segments.find((item) => item.generationMetadata?.segmentedRetake && item.status === "failed" && item.error);
    if (failed && !hold) {
      retakeAwaiting.current = "";
      setRetake((current) => ({ ...current, busy: false, error: failed.error || "The original picture was kept." }));
    }
  }, [shot]);

  useEffect(() => {
    if (!shot || shot.status !== "generating") return;
    const timer = window.setInterval(() => {
      void api.filmTimelineSync(project.id, sceneId, shot.id).then(() => load());
    }, 4000);
    return () => window.clearInterval(timer);
  }, [shot?.id, shot?.status, project.id, sceneId, load]);

  useEffect(() => {
    if (shot?.status === "generating") sawGenerating.current = true;
  }, [shot?.status, shot?.id]);

  useEffect(() => {
    if (shot?.status === "generating") return;
    if (!sawGenerating.current || renderNotice?.status !== "completed") return;
    sawGenerating.current = false;
    setCompleteKey(renderNotice.key);
    const finishedId = String(renderNotice.key || "").split(":")[0];
    const finished = visualWindows(canonicalSceneBatches(shot?.segments)).find((item) => item.id === finishedId);
    if (finished) {
      setSegmentId(finished.id);
      setPlayheadSec((current) => (current >= finished.start && current < finished.end ? current : finished.start));
    }
    if (batchesAtStart.current >= 1) setWorkspace("track");
    const timer = window.setTimeout(() => setCompleteKey(""), 5000);
    return () => window.clearTimeout(timer);
  }, [renderNotice?.key, renderNotice?.status, shot?.status, shot?.segments]);

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

  async function removeVideoItem(item: { id: string; kind?: "segment" | "clip" }) {
    if (!sceneId) return;
    if (item.kind === "segment") {
      if (!shot) return;
      await run(() => api.filmTimelineDeleteSegment(project.id, sceneId, shot.id, item.id));
      if (segmentId === item.id) setSegmentId("");
    }
  }

  function generationBody() {
    const body: Record<string, unknown> = {
      durationSec: duration,
      timedPrompt: prompt,
      generatorId: modelId || undefined,
      spokenLanguage,
      spokenLanguageCustom: spokenLanguage === "custom" ? spokenCustom : "",
      dialogueAuthority,
    };
    const providerOpts: Record<string, unknown> = {};
    if (h3Resolution.mode === "manual") providerOpts["h3Resolution"] = h3Resolution;
    if (ltxSelected && ltxQuality) providerOpts["ltxQuality"] = ltxQuality;
    if (frameModeModel) {
      providerOpts["ltxMode"] = ltxMode;
      providerOpts["ltxStartAssetId"] = ltxStartAssetId;
      providerOpts["ltxEndAssetId"] = ltxEndAssetId;
    }
    if (seedanceSelected && seedanceResolution) providerOpts["seedanceResolution"] = seedanceResolution;
    if (Object.keys(providerOpts).length) body["providerOptions"] = providerOpts;
    return body;
  }

  async function persistDialogue(mode: string) {
    if (!sceneId) return;
    setDialogueAuthority(mode);
    setDialogueNote("");
    try {
      const id = shot?.id || (await ensureShot());
      if (!id) return;
      const saved = await api.filmTimelineSetDialogue(project.id, sceneId, id, { dialogueAuthority: mode });
      setDialogueNote(String(saved.message || ""));
      await load();
    } catch (error) {
      setDialogueNote(error instanceof Error ? error.message : "Timeline could not save Dialogue.");
    }
  }

  async function persistLanguage(code: string, custom: string) {
    if (!sceneId) return;
    setSpokenLanguage(code);
    setSpokenCustom(custom);
    try {
      const id = shot?.id || (await ensureShot());
      if (!id) return;
      await api.filmTimelineSetSpokenLanguage(project.id, sceneId, id, {
        spokenLanguage: code,
        spokenLanguageCustom: code === "custom" ? custom : "",
      });
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That language could not be saved.");
    }
  }

  async function removeTimedPrompt() {
    if (!shot || !sceneId) return;
    const selected = shot.segments.find((item) => item.id === segmentId);
    await run(async () => {
      const result = await api.filmTimelineDeletePrompt(project.id, sceneId, shot.id, selected?.id);
      setPrompt("");
      return result;
    });
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
    setStickyErrorHidden(true);
    setMessage("");
    setAddIntent(null);
    batchesAtStart.current = canonicalSceneBatches(shot?.segments).length;
    const id = await ensureShot();
    if (!id) return;
    await run(() => api.filmTimelineGenerate(project.id, sceneId, id, generationBody()));
  }

  async function continueShot() {
    if (!shot) return;
    setStickyErrorHidden(false);
    setMessage("");
    setAddIntent(null);
    batchesAtStart.current = canonicalSceneBatches(shot.segments).length;
    await run(() => api.filmTimelineContinue(project.id, sceneId, shot.id, generationBody()));
  }

  async function prependShot() {
    if (!shot) return;
    setStickyErrorHidden(false);
    setMessage("");
    setAddIntent(null);
    batchesAtStart.current = canonicalSceneBatches(shot.segments).length;
    await run(() => api.filmTimelinePrepend(project.id, sceneId, shot.id, generationBody()));
  }

  function addNextBatch() {
    setAddIntent(trackHasBatches(shot?.segments) ? "append" : null);
    setWorkspace("prompt");
    setPrompt("");
    setSegmentId("");
  }

  function addPreviousBatch() {
    setAddIntent("prepend");
    setWorkspace("prompt");
    setPrompt("");
    setSegmentId("");
  }

  function importVideo(assetIds: string[]) {
    const assetId = assetIds[0];
    if (!assetId || !sceneId) return;
    setLibraryOpen(null);
    void (async () => {
      const id = await ensureShot();
      if (!id) return;
      await run(() => api.filmTimelineImportVideo(project.id, sceneId, id, assetId));
      setWorkspace("track");
    })().catch((error) => setMessage(error instanceof Error ? error.message : "That video could not be added."));
  }

  function sceneStitchCurrent(windows = currentClips()) {
    return stitchCoversClips(shot?.state.stitchStatus, shot?.state.stitchAssetId, shot?.state.stitchSegmentIds, windows.map((clip) => clip.id));
  }

  function stopAtSceneEnd(windows = currentClips()) {
    continueScene.current = false;
    setPlayheadSec(sceneDuration(windows));
    videoRef.current?.pause();
  }

  function showClipAt(clip: VisualClip, fileTime: number, windows = currentClips()) {
    setPlayheadSec(Math.min(clip.end, Math.max(clip.start, clip.start + sceneLocalFromFile(clip.trimInSec, fileTime))));
    const video = videoRef.current;
    if (video && preview.assetId === clip.assetId && (segmentId === clip.id || preview.source !== "stitch")) {
      video.currentTime = fileTime;
      if (segmentId !== clip.id) setSegmentId(clip.id);
      if (continueScene.current) void video.play();
      return;
    }
    pendingSeek.current = fileTime;
    setSegmentId(clip.id);
    void windows;
  }

  function advancePast(clip: VisualClip) {
    const windows = currentClips();
    const index = windows.findIndex((item) => item.id === clip.id);
    if (!continueScene.current || index < 0 || index >= windows.length - 1) {
      stopAtSceneEnd(windows);
      return;
    }
    const next = windows[index + 1];
    showClipAt(next, fileTimeForWindow(next.trimInSec, 0), windows);
  }

  function togglePlay() {
    const video = videoRef.current;
    if (!video) return;
    if (!video.paused && !video.ended) {
      continueScene.current = false;
      video.pause();
      return;
    }
    const windows = currentClips();
    const atEnd = playheadSec >= sceneDuration(windows) - 0.05;
    const time = atEnd ? 0 : playheadSec;
    if (atEnd) setPlayheadSec(0);
    continueScene.current = true;
    if (sceneStitchCurrent(windows)) {
      if (preview.source !== "stitch") {
        pendingSeek.current = time;
        setSegmentId("");
        return;
      }
      if (Math.abs(video.currentTime - time) > 0.2) video.currentTime = time;
      void video.play();
      return;
    }
    const clip = clipAtTime(windows, Math.min(time, Math.max(0, sceneDuration(windows) - 0.001)));
    if (!clip) return;
    showClipAt(clip, fileTimeForWindow(clip.trimInSec, Math.max(0, time - clip.start)), windows);
  }

  function place(asset: Asset) {
    setReferenceOpen({ assetId: asset.id });
  }

  async function classifyReference(asset: Asset, approvedAs: ImageRole | null) {
    const stamp = ++classifyStamp.current;
    setClassifyingId(asset.id);
    setClassifyError(null);
    setMessage("");
    try {
      const updated = await api.setReferenceClassification(project.id, asset.id, approvedAs);
      if (stamp !== classifyStamp.current) return;
      const confirmed = { ...asset, ...updated, id: asset.id };
      setLibraryItems((current) => libraryAfterClassification(current, confirmed, true));
      try {
        const payload = await api.library(project.id, { scope: "project", limit: 48, offset: 0 });
        if (stamp !== classifyStamp.current) return;
        const rows = ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item));
        setLibraryItems((current) => libraryAfterClassification(mergeLibraryPage(current, rows), confirmed, true));
      } catch {
        // The confirmed response is already in the shared library list.
      }
    } catch (error) {
      if (stamp !== classifyStamp.current) return;
      const text = error instanceof Error ? error.message : "That reference role could not be saved.";
      setClassifyError({ assetId: asset.id, message: text });
      setMessage(text);
    } finally {
      if (stamp === classifyStamp.current) setClassifyingId("");
    }
  }

  async function saveReference(body: FilmReferenceSave) {
    const id = await ensureShot();
    if (!id) throw new Error("Choose a shot before adding a reference.");
    const frames = body.frames?.length ? body.frames : [body];
    let film: Film | undefined;
    for (const frame of frames) {
      const result = (await api.filmTimelineAttachReference(project.id, sceneId, id, frame)) as { ok?: boolean; message?: string; film?: Film };
      if (result && result.ok === false) throw new Error(result.message || "That reference could not be saved.");
      if (result.film) film = result.film;
    }
    if (film) setFilm(film);
    else await load();
    setReferenceOpen(null);
  }

  async function cancelRender() {
    if (!shot) return;
    if (!filmTimelineHasCancellableJob(shot.segments)) return;
    await run(() => api.filmTimelineCancel(project.id, sceneId, shot.id));
  }

  async function createScene() {
    // Single-flight and atomic: the UI stays on the current scene until the new
    // scene exists in the project payload AND its canonical film has loaded.
    if (creatingScene || busy) return;
    setCreatingScene(true);
    setMessage("");
    try {
      const created = await api.addScene(project.id, {
        name: `Scene ${project.scenes.length + 1}`,
        engine: "auto",
        duration_sec: duration,
        prompt: "",
      });
      const newId = String(created?.id || "");
      if (!newId) throw new Error("Could not create scene");
      // Hydrate the new scene's canonical state BEFORE switching selection so a
      // transient film-timeline read cannot race the transition.
      await api.filmTimelineGet(project.id, newId);
      await refresh();
      // Final transition step: commit selection and the sceneId query param in
      // the same tick. Selection must never lead the URL — ProjectEditor keeps
      // URL↔selection effects that treat a disagreement as a canonicalize
      // conflict and ping-pong sceneId old↔new (a request storm whose transport
      // errors trip the global Studio API Offline banner).
      setSelectedScene(newId);
      const params = new URLSearchParams(window.location.search);
      params.set("sceneId", newId);
      navigate({ search: `?${params.toString()}` }, { replace: true });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create scene");
    } finally {
      setCreatingScene(false);
    }
  }

  function toggleEye() {
    const next = !publishBar;
    setPublishBar(next);
    saveTimelineWorkspaceLayout({ previewPublishBarVisible: next });
  }

  async function publish(update: boolean) {
    if (publishLock.current || busy || publishPhase) return;
    if (!actionsOn || !shot || !magiGate.stitchReady) return;
    if (update ? magiGate.state !== "stale" : magiGate.state !== "unpublished") return;
    publishLock.current = true;
    setPublishPhase(update ? "update" : "publish");
    try {
      await run(async () => {
        const result = await api.filmTimelinePublish(project.id, sceneId, {
          assetId: magiGate.stitchId,
          update,
          shotId: shot.id,
        });
        if (result && result.ok !== false) {
          setMessage(update ? "Published version updated." : "Scene published.");
        }
        return result;
      });
    } finally {
      publishLock.current = false;
      setPublishPhase(null);
    }
  }

  function sendToMagi() {
    if (magiGate.state !== "current") {
      showMagiNote(magiGate.note);
      return;
    }
    const location = buildProjectWorkspaceLocation({ projectId: project.id, tab: "magi", sceneId });
    if (!location) return;
    navigate({ pathname: location.pathname, search: location.search });
  }

  function currentClips() {
    return visualWindows(canonicalSceneBatches(shot?.segments));
  }

  function mark(which: "in" | "out") {
    const local = videoRef.current?.currentTime ?? 0;
    const time = sceneTimeFromPreview(preview.source, local, currentClips(), preview.assetId);
    setRetake((current) => ({ ...current, rangeStart: which === "in" ? time : current.rangeStart, rangeEnd: which === "out" ? time : current.rangeEnd, error: null }));
  }

  function seekScene(sceneTime: number) {
    const windows = currentClips();
    const limit = sceneDuration(windows);
    const time = Math.max(0, Math.min(sceneTime, limit));
    setPlayheadSec(time);
    const video = videoRef.current;
    if (sceneStitchCurrent(windows)) {
      if (preview.source === "stitch" && video) {
        video.currentTime = time;
        return;
      }
      pendingSeek.current = time;
      if (segmentId) setSegmentId("");
      return;
    }
    const clip = clipAtTime(windows, time);
    if (!clip) return;
    const fileTime = fileTimeForWindow(clip.trimInSec, Math.max(0, time - clip.start));
    if (preview.assetId === clip.assetId && video && segmentId === clip.id) {
      video.currentTime = fileTime;
      return;
    }
    pendingSeek.current = fileTime;
    setSegmentId(clip.id);
  }

  async function moveClip(clip: VisualClip, direction: "earlier" | "later") {
    if (!shot) return;
    setStitchNote("");
    try {
      const result = (await api.filmTimelineReorder(project.id, sceneId, shot.id, { segmentId: clip.id, direction })) as { ok?: boolean; film?: Film; message?: string };
      if (result.film) setFilm(result.film);
      else await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That clip could not be moved.");
    }
  }

  async function stitchScene() {
    if (!shot || stitching) return;
    setStitching(true);
    setStitchNote("");
    try {
      const result = (await api.filmTimelineStitch(project.id, sceneId, shot.id)) as { ok?: boolean; film?: Film; message?: string; error?: string };
      if (result.film) setFilm(result.film);
      else await load();
      if (result.ok === false) {
        setStitchNote("Stitch failed");
        return;
      }
      setSegmentId("");
      setStitchNote("Scene stitched");
    } catch (error) {
      setStitchNote("Stitch failed");
      setMessage(error instanceof Error ? error.message : "Stitch failed");
    } finally {
      setStitching(false);
    }
  }

  function selectClip(clip: VisualClip) {
    const inside = playheadSec >= clip.start && playheadSec <= clip.end;
    pendingSeek.current = inside ? Math.max(0, playheadSec - clip.start) : 0;
    if (!inside) setPlayheadSec(clip.start);
    setSegmentId(clip.id);
  }

  async function submitRetake() {
    if (!shot || !actionsOn) return;
    const ready = canSubmitVideoRetake(retake);
    if (!ready.ok) {
      setRetake((current) => ({ ...current, error: ready.error }));
      return;
    }
    const markIn = Math.min(retake.rangeStart ?? 0, retake.rangeEnd ?? 0);
    const markOut = Math.max(retake.rangeStart ?? 0, retake.rangeEnd ?? 0);
    setRetake((current) => ({ ...current, busy: true, error: null }));
    try {
      const result = (await api.filmTimelineRetake(project.id, sceneId, shot.id, {
        markIn,
        markOut,
        timedPrompt: retake.prompt.trim(),
      })) as { ok?: boolean; message?: string; error?: string; mode?: string; sourceSegmentId?: string };
      if (result.ok === false) {
        setRetake((current) => ({ ...current, busy: false, error: result.message || result.error || "Re-Take could not start." }));
        return;
      }
      if (result.mode === "partial") {
        retakeAwaiting.current = String(result.sourceSegmentId || "");
        setRetake((current) => ({ ...current, busy: false, error: null }));
        await load();
        return;
      }
      setRetake(closedVideoRetakeSession());
      await load();
    } catch (error) {
      setRetake((current) => ({ ...current, busy: false, error: error instanceof Error ? error.message : "Re-Take could not start." }));
    }
  }

  const timelineKeyRef = useRef<(event: KeyboardEvent) => void>(() => {});
  timelineKeyRef.current = (event: KeyboardEvent) => {
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
  useEffect(() => registerWorkspaceKeyHandler("timeline", (event) => timelineKeyRef.current(event)), []);

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
        setLibraryOpen(null);
        const payload = await api.library(project.id, { scope: "project", limit: 48, offset: 0 });
        setLibraryItems((current) =>
          mergeLibraryPage(current, ((payload.items || []) as Asset[]).filter((item) => isTimelineMediaAsset(item))),
        );
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
  const batches = canonicalSceneBatches(shot?.segments);
  const clips = visualWindows(batches);
  const continuationMode = models.find((item) => item.id === modelId)?.continuationMode || "none";
  const continuationLabel =
    continuationMode === "hard" ? "Continuation: Hard start-frame" : continuationMode === "soft" ? "Continuation: Soft reference" : "";
  const continuationHelper =
    continuationMode === "soft" ? "Exact opening pose continuity is not guaranteed by this model." : "";
  const retakeStart = retake.rangeStart == null || retake.rangeEnd == null ? null : Math.min(retake.rangeStart, retake.rangeEnd);
  const retakeEnd = retake.rangeStart == null || retake.rangeEnd == null ? null : Math.max(retake.rangeStart, retake.rangeEnd);
  const wholeShotRetake =
    retake.open &&
    retakeStart != null &&
    retakeEnd != null &&
    clips.some((clip) => Math.abs(clip.start - retakeStart) <= 0.05 && Math.abs(clip.end - retakeEnd) <= 0.05);
  const upcomingShot = nextShotNumber(
    film?.highestShotNumber || 0,
    (film?.shots || []).flatMap((item) => (item.segments || []).map((segment) => segment.shotNumber)),
  );
  const pendingBatch = pendingSceneBatch(shot?.segments);
  const trackEnabled = trackHasBatches(shot?.segments);
  const showContinuation = Boolean(continuationLabel) && ((trackEnabled && addIntent !== "prepend") || wholeShotRetake);
  const continuationStillId = (() => {
    const done = (shot?.segments || []).filter((item) => item.status === "completed" && item.lastFrameAssetId);
    return done.length ? String(done[done.length - 1].lastFrameAssetId) : "";
  })();
  const previewUrl = preview.assetId ? api.assetUrl(preview.assetId, null, project.id) : "";

  const inspector = (
    <div className="film-timeline__inspector" data-testid="film-timeline-inspector">
      <button type="button" className="film-timeline__new-scene" data-testid="film-timeline-new-scene" disabled={busy || creatingScene} onClick={() => void createScene()}>
        {creatingScene ? "Creating scene…" : "+ New Scene"}
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
        Production
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
      {frameModeModel ? (
        <label className="film-timeline__field">
          Mode
          <select
            data-testid="film-timeline-ltx-mode"
            value={ltxMode}
            onChange={(event) => {
              const raw = event.target.value;
              const next = raw === "start_end" ? "start_end" : raw === "one_frame" ? "one_frame" : "text";
              setLtxMode(next);
              setStickyErrorHidden(true);
              if (shot && sceneId) {
                void api.filmTimelineSetShotModel(project.id, sceneId, shot.id, {
                  generatorId: modelId,
                  providerOptions: { ltxMode: next, ltxStartAssetId, ltxEndAssetId },
                });
              }
            }}
          >
            <option value="text">Text to Video</option>
            {selectedModel?.supportsStartFrame ? <option value="one_frame">Start Frame</option> : null}
            {selectedModel?.supportsEndFrame ? <option value="start_end">Start + End Frame</option> : null}
          </select>
        </label>
      ) : null}
      {frameModeModel && (ltxMode === "one_frame" || ltxMode === "start_end") && !(trackEnabled && addIntent !== "prepend") ? (
        <div className="film-timeline__field" data-testid="film-timeline-ltx-frame">
          Start frame
          <div className="film-timeline__ltx-frame">
            {ltxStartAssetId ? (
              <img src={api.assetUrl(ltxStartAssetId, null, project.id)} alt="Start frame" />
            ) : (
              <span className="film-timeline__ltx-empty">Start frame</span>
            )}
            <button type="button" onClick={() => setLibraryOpen("ltx-frame")}>
              {ltxStartAssetId ? "Change" : "Choose"}
            </button>
            {ltxStartAssetId ? (
              <button
                type="button"
                aria-label="Clear start frame"
                onClick={() => {
                  setLtxStartAssetId("");
                  if (shot && sceneId) {
                    void api.filmTimelineSetShotModel(project.id, sceneId, shot.id, {
                      generatorId: modelId,
                      providerOptions: { ltxMode, ltxStartAssetId: "", ltxEndAssetId },
                    });
                  }
                }}
              >
                ×
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      {frameModeModel && ltxMode === "start_end" ? (
        <div className="film-timeline__field" data-testid="film-timeline-ltx-end">
          End frame
          <div className="film-timeline__ltx-frame">
            {ltxEndAssetId ? (
              <img src={api.assetUrl(ltxEndAssetId, null, project.id)} alt="End frame" />
            ) : (
              <span className="film-timeline__ltx-empty">End frame</span>
            )}
            <button type="button" onClick={() => setLibraryOpen("ltx-end")}>
              {ltxEndAssetId ? "Change" : "Choose"}
            </button>
            {ltxEndAssetId ? (
              <button
                type="button"
                aria-label="Clear end frame"
                onClick={() => {
                  setLtxEndAssetId("");
                  if (shot && sceneId) {
                    void api.filmTimelineSetShotModel(project.id, sceneId, shot.id, {
                      generatorId: modelId,
                      providerOptions: { ltxMode, ltxStartAssetId, ltxEndAssetId: "" },
                    });
                  }
                }}
              >
                ×
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      {frameModeModel && showContinuation ? (
        <div className="film-timeline__field" data-testid="film-timeline-ltx-continuation">
          Continuation start
          <div className="film-timeline__ltx-frame">
            {continuationStillId ? (
              <img src={api.assetUrl(continuationStillId, null, project.id)} alt="Previous shot final frame" />
            ) : (
              <span className="film-timeline__ltx-empty">Previous frame</span>
            )}
            <span>From previous shot</span>
          </div>
        </div>
      ) : null}

      {(() => {
        // Picture shapes come from the backend production contract. H3 with no
        // advertised caps uses that contract's H3 subset.
        const supportedAspects = selectedModel?.supportedAspectRatios;
        const h3Selected = String(selectedModel?.id || "").includes("minimax-h3");
        const aspectCatalog = h3Selected && !(supportedAspects && supportedAspects.length) ? h3Aspects : productionAspects;
        const aspectOptions = allowedProductionAspects(aspectCatalog, supportedAspects);
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
        seedanceResolution={seedanceResolution}
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
        onSeedanceChange={(next) => { setSeedanceResolution(next); setStickyErrorHidden(true); }}
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
        {ltxSelected ? (
          <span className="scene-meta" data-testid="film-timeline-ltx-frames">
            LTX renders {ltxTimelineFrameCount(duration)} frames so the count stays legal.
          </span>
        ) : null}
        {selectedModel?.notes?.includes("480p") ? (
          <span className="scene-meta" data-testid="film-timeline-output-class">
            {selectedModel.notes}
          </span>
        ) : null}
      </label>
      <label className="film-timeline__field">
        Language
        <select
          value={spokenLanguage}
          data-testid="film-timeline-language"
          title="If anyone speaks in this shot, they use this language. A quiet shot stays quiet."
          onChange={(event) => {
            const code = event.target.value;
            if (code === "custom") {
              setSpokenLanguage("custom");
              return;
            }
            void persistLanguage(code, "");
          }}
        >
          {SPOKEN_LANGUAGES.map((item) => (
            <option key={item.code} value={item.code}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      {spokenLanguage === "custom" ? (
        <label className="film-timeline__field">
          Spoken language
          <input
            data-testid="film-timeline-language-custom"
            value={spokenCustom}
            placeholder="Name the language"
            onChange={(event) => setSpokenCustom(event.target.value)}
            onBlur={() => {
              if (spokenCustom.trim()) void persistLanguage("custom", spokenCustom.trim());
            }}
          />
        </label>
      ) : null}
      <label className="film-timeline__field">
        Dialogue
        <select
          value={dialogueAuthority}
          data-testid="film-timeline-dialogue"
          title="Native Model lets the video generator speak. Character Voice uses this character's saved voice."
          onChange={(event) => {
            void persistDialogue(event.target.value);
          }}
        >
          <option value="native_model">Native Model</option>
          <option value="character_voice">Character Voice</option>
        </select>
      </label>
      {dialogueNote ? (
        <div className="film-timeline__note" data-testid="film-timeline-dialogue-warning">{dialogueNote}</div>
      ) : null}
      {modelSwitchNote ? <div className="film-timeline__note" data-testid="film-timeline-duration-note">{modelSwitchNote}</div> : null}
      <button type="button" data-testid="film-timeline-open-library" onClick={() => setLibraryOpen("references")}>
        Open Library
      </button>
      <div className="film-timeline__assets">
        {recent.map((asset) => (
          <div key={asset.id} className="film-timeline__asset" data-testid="film-timeline-asset">
            <img src={api.assetUrl(asset.id, null, project.id)} alt="" />
            <span>{assetLabel(asset)}</span>
            <LibraryReferenceControl
              asset={asset}
              busy={classifyingId === asset.id}
              error={classifyError?.assetId === asset.id ? classifyError.message : ""}
              onClassify={(approvedAs) => void classifyReference(asset, approvedAs)}
              onUse={() => place(asset)}
            />
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
          className={`live-preview-cancel-in-stage${cancellable ? "" : " is-idle"}${cancelUi.visible ? "" : " is-hidden"}`}
          hidden={!cancelUi.visible}
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
        {preview.kind === "video" && previewUrl ? (
          <video
            ref={videoRef}
            src={previewUrl}
            data-preview-source={preview.source}
            controls
            onLoadedMetadata={(event) => {
              const local = pendingSeek.current;
              if (local != null) {
                event.currentTarget.currentTime = local;
                pendingSeek.current = null;
              } else if (preview.source === "stitch") {
                setPlayheadSec(sceneTimeFromPreview(preview.source, event.currentTarget.currentTime, clips, preview.assetId));
              }
              if (continueScene.current) void event.currentTarget.play();
            }}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => {
              if (preview.source === "stitch" || !continueScene.current) {
                continueScene.current = false;
                if (preview.source === "stitch") setPlayheadSec(sceneDuration(clips));
                return;
              }
              const clip = clips.find((item) => item.id === segmentId) || clipAtTime(clips, playheadSec);
              if (clip) advancePast(clip);
            }}
            onTimeUpdate={(event) => {
              if (pendingSeek.current != null) return;
              if (preview.source === "stitch") {
                setPlayheadSec(sceneTimeFromPreview(preview.source, event.currentTarget.currentTime, clips, preview.assetId));
                return;
              }
              const clip = clips.find((item) => item.id === segmentId);
              if (!clip) return;
              if (continueScene.current && windowReachedEnd(clip.trimInSec, clip.trimOutSec, clip.durationSec, event.currentTarget.currentTime)) {
                advancePast(clip);
                return;
              }
              const sceneTime = clip.start + sceneLocalFromFile(clip.trimInSec, event.currentTarget.currentTime);
              setPlayheadSec(Math.max(clip.start, Math.min(clip.end, sceneTime)));
            }}
            onSeeked={(event) => {
              if (pendingSeek.current != null) return;
              if (preview.source === "stitch") {
                setPlayheadSec(sceneTimeFromPreview(preview.source, event.currentTarget.currentTime, clips, preview.assetId));
                return;
              }
              const clip = clips.find((item) => item.id === segmentId);
              if (!clip) return;
              const sceneTime = clip.start + sceneLocalFromFile(clip.trimInSec, event.currentTarget.currentTime);
              setPlayheadSec(Math.max(clip.start, Math.min(clip.end, sceneTime)));
            }}
          />
        ) : null}
        {preview.kind === "empty" ? <p>Generate a shot to see it here.</p> : null}
        <FilmPreviewClock videoRef={videoRef} active={preview.kind === "video"} />
        {renderNotice ? (
          <p className="film-timeline__notice" data-testid="film-timeline-render-notice">
            <span>{renderNotice.text}</span>
            <button type="button" className="film-timeline__remove" aria-label="Dismiss notice" data-testid="film-timeline-dismiss-notice" onClick={() => setDismissedNoticeKey(renderNotice.key)}>
              ×
            </button>
          </p>
        ) : null}
        {renderHud && (renderHud.kind === "active" || renderHud.kind === "complete") ? (
          <div className="film-timeline__progress" data-testid="film-timeline-progress">
            <span>{filmTimelineRenderLine(renderHud)}</span>
            {renderHud.bar !== "none" ? <RenderMeter model={renderHud} /> : null}
          </div>
        ) : null}
        {renderHud ? <FilmTimelineRenderHud model={renderHud} onDismiss={() => renderNotice && setDismissedNoticeKey(renderNotice.key)} /> : null}
        <div
          className={[
            "live-preview-publish-bar",
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
                disabled={!actionsOn || busy || publishPhase !== null || magiGate.state !== "unpublished" || !magiGate.stitchReady}
                aria-busy={publishPhase === "publish"}
                onClick={() => void publish(false)}
              >
                {publishPhase === "publish" ? "Publishing..." : "PUBLISH"}
              </button>
              <button
                type="button"
                className="live-preview-publish-bar__btn live-preview-publish-bar__btn--update"
                data-testid="live-preview-update-published"
                title="Update the Video Published Master from the current full stitch"
                aria-label="Update Published"
                disabled={!actionsOn || busy || publishPhase !== null || magiGate.state !== "stale" || !magiGate.stitchReady}
                aria-busy={publishPhase === "update"}
                onClick={() => void publish(true)}
              >
                {publishPhase === "update" ? "Updating..." : "UPDATE PUBLISHED"}
              </button>
              <button
                type="button"
                className="live-preview-publish-bar__btn live-preview-publish-bar__btn--upscale"
                data-testid="film-timeline-send-magi"
                title="Send the assembled scene to MAGI for finishing"
                aria-label="Send to MAGI"
                disabled={!actionsOn || busy}
                onClick={sendToMagi}
              >
                SEND TO MAGI
              </button>
              <PreviewPublishBarVisibilityToggle visible attention={false} onToggle={toggleEye} />
            </div>
          ) : (
            <PreviewPublishBarVisibilityToggle visible={false} attention={false} onToggle={toggleEye} />
          )}
          {magiNote.text ? (
            <p
              key={magiNote.key}
              className="film-timeline__note film-timeline__note--top-action"
              data-testid="film-timeline-magi-note"
              role="status"
            >
              {magiNote.text}
            </p>
          ) : null}
        </div>
        {retake.open ? (
          <TimelineRetakeOverlay
            session={retake}
            videoAvailable={actionsOn}
            showRemoveBackground={false}
            promptPlaceholder="Describe what should be different within the selected range."
            submitEnabled={canSubmitVideoRetake(retake).ok && !shot?.segments.some((item) => item.generationMetadata?.segmentedRetake && item.status !== "failed" && item.status !== "cancelled")}
            continuationLabel={wholeShotRetake ? continuationLabel : ""}
            continuationHelper={wholeShotRetake ? continuationHelper : ""}
            onMarkIn={() => mark("in")}
            onMarkOut={() => mark("out")}
            onPrompt={(value) => setRetake((current) => ({ ...current, prompt: value }))}
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
          sceneTimeSec={playheadSec}
          sceneDurationSec={sceneDuration(clips)}
          onSceneSeek={seekScene}
          onBatchStart={() => {
            const piece = clipAtTime(clips, playheadSec);
            if (piece) seekScene(piece.start);
          }}
          onBatchEnd={() => {
            const piece = clipAtTime(clips, playheadSec);
            if (piece) seekScene(piece.end);
          }}
          onTogglePlay={togglePlay}
          onSeekLocalTime={(localSec) => {
            if (preview.source === "stitch") {
              seekScene(localSec);
              return;
            }
            const clip = clips.find((item) => item.id === segmentId) || clips.find((item) => item.assetId === preview.assetId);
            seekScene((clip?.start || 0) + localSec);
          }}
          onRetake={() => setRetake((current) => (current.open ? closedVideoRetakeSession() : { ...closedVideoRetakeSession(), open: true }))}
          retakeActive={retake.open}
          timelineTimeSec={videoRef.current?.currentTime || 0}
          timelineDurationSec={videoRef.current?.duration || 0}
          timelinePlaying={Boolean(videoRef.current && !videoRef.current.paused)}
        />
      </div>
      {fullscreen.isFullscreen || !previewShotLabel ? null : (
        <p className="film-timeline__preview-shot" data-testid="film-timeline-preview-shot">
          {previewShotLabel}
        </p>
      )}
      {fullscreen.isFullscreen ? null : (
        <PreviewTransport
          clips={clips}
          playheadSec={playheadSec}
          playing={playing}
          onTogglePlay={togglePlay}
          onSeek={seekScene}
        />
      )}
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
      <div className="film-timeline__workspace" data-testid="film-timeline-workspace">
        <div className="film-timeline__workspace-tabs" role="tablist" aria-label="Scene workspace">
          <button
            type="button"
            role="tab"
            aria-selected={workspace === "prompt"}
            className={workspace === "prompt" ? "is-selected" : ""}
            data-testid="film-timeline-workspace-prompt"
            onClick={() => setWorkspace("prompt")}
          >
            Prompt
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={workspace === "track"}
            className={workspace === "track" ? "is-selected" : ""}
            data-testid="film-timeline-workspace-track"
            title="Visual track"
            onClick={() => {
              setAddIntent(null);
              setWorkspace("track");
            }}
          >
            Track
          </button>
        </div>
        {workspace === "track" ? (
          <VisualTrack
            key={sceneId}
            sceneId={sceneId}
            initialScrollLeft={trackScrollByScene.current[sceneId] || 0}
            onViewportScroll={(left) => {
              trackScrollByScene.current[sceneId] = left;
            }}
            clips={clips}
            pending={
              pendingBatch
                ? { id: pendingBatch.id, label: pendingBatch.label, durationSec: pendingBatch.durationSec, placement: pendingBatch.placement }
                : null
            }
            selectedId={segmentId}
            playheadSec={playheadSec}
            rangeStart={retake.open ? retake.rangeStart : null}
            rangeEnd={retake.open ? retake.rangeEnd : null}
            projectId={project.id}
            onSelect={selectClip}
            onDelete={(clip) => void removeVideoItem({ id: clip.id, kind: "segment" })}
            onSeek={seekScene}
            onAdd={addNextBatch}
            onAddPrevious={addPreviousBatch}
            onAddFromLibrary={() => setLibraryOpen("visual")}
            onMove={(clip, direction) => void moveClip(clip, direction)}
            onStitch={() => void stitchScene()}
            canStitch={clips.length >= 2 && !pendingBatch && !stitching}
            stitching={stitching}
            stitchNote={stitchNote}
          />
        ) : (
          <>
            <div className="film-timeline__tool-slot" data-testid="film-timeline-tool-slot">
              <PromptToolbar
                projectId={project.id}
                sceneId={sceneId}
                shotId={shot?.id || ""}
                prompt={prompt}
                onPrompt={setPrompt}
                onReferences={showSemanticReferences ? () => setReferenceOpen({}) : undefined}
                showReferences={showSemanticReferences}
              />
            </div>
            <div className="film-reference-strip" data-testid="film-reference-strip">
              <span className="film-timeline__shot-tag" data-testid="film-timeline-shot-tag">{shotTag(upcomingShot)}</span>
              {showSemanticReferences ? activeReferences.map((ref) => {
                  const label = filmReferenceChipLabel(ref);
                  return (
                    <span key={ref.id} className={`film-reference-chip is-${ref.type || "other"}`} data-asset-id={ref.assetId} data-source={ref.source || ""}>
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
              }) : null}
            </div>
            <div className="film-timeline__prompt">
              <span className="film-timeline__prompt-head">
                Timed Prompt
                <button type="button" className="film-timeline__remove" aria-label="Remove timed prompt" data-testid="film-timeline-delete-prompt" disabled={!prompt.trim()} onClick={() => void removeTimedPrompt()}>
                  ×
                </button>
              </span>
              <textarea
                value={prompt}
                data-testid="film-timeline-prompt"
                placeholder={addIntent === "prepend" ? "What happens immediately before this?" : trackEnabled ? "What happens next?" : ""}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </div>
            <div className="film-timeline__actions">
              <button
                type="button"
                data-testid={addIntent === "prepend" ? "film-timeline-prepend" : trackEnabled ? "film-timeline-continue" : "film-timeline-generate"}
                disabled={busy || !prompt.trim() || (frameModeModel && (ltxMode === "one_frame" || ltxMode === "start_end") && !ltxStartAssetId && !(trackEnabled && addIntent !== "prepend")) || (frameModeModel && ltxMode === "start_end" && !ltxEndAssetId)}
                onClick={() => void (addIntent === "prepend" ? prependShot() : trackEnabled ? continueShot() : generate())}
              >
                {addIntent === "prepend" ? "Create Previous Shot" : trackEnabled ? "Continue Shot" : "Generate Shot"}
              </button>
              {showContinuation && trackEnabled && addIntent !== "prepend" ? (
                <p className="film-timeline__continuation" data-testid="film-timeline-continuation">
                  {continuationLabel}
                  {continuationHelper ? <span>{continuationHelper}</span> : null}
                </p>
              ) : null}
            </div>
          </>
        )}
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
          projectId={project.id}
          initialAssetId={referenceOpen.assetId}
          editId={referenceOpen.editId}
          onClose={() => setReferenceOpen(null)}
          onSave={saveReference}
        />
      ) : null}
      {libraryOpen ? (
        <AddFromProjectLibraryModal
          project={project}
          alreadyIds={libraryOpen === "visual" || libraryOpen === "ltx-frame" || libraryOpen === "ltx-end" ? [] : libraryAssetIds}
          mediaKind={libraryOpen === "visual" ? "video" : "all"}
          single={libraryOpen === "visual" || libraryOpen === "ltx-frame" || libraryOpen === "ltx-end"}
          onClose={() => setLibraryOpen(null)}
          onAssetsChanged={() => void refresh()}
          onAdd={
            libraryOpen === "visual"
              ? importVideo
              : libraryOpen === "ltx-frame" || libraryOpen === "ltx-end"
                ? (ids) => {
                    const choosingEnd = libraryOpen === "ltx-end";
                    const id = String(ids[0] || "");
                    const asset = [...libraryItems, ...(project.assets || [])].find((item) => item.id === id);
                    setLibraryOpen(null);
                    if (!asset || asset.kind !== "image") {
                      setMessage(`LTX_FRAME_INPUT_INVALID: Choose a still image for the ${choosingEnd ? "end" : "start"} frame.`);
                      return;
                    }
                    const nextMode = choosingEnd ? "start_end" : ltxMode === "start_end" ? "start_end" : "one_frame";
                    const nextStart = choosingEnd ? ltxStartAssetId : id;
                    const nextEnd = choosingEnd ? id : ltxEndAssetId;
                    if (choosingEnd) setLtxEndAssetId(id);
                    else setLtxStartAssetId(id);
                    setLtxMode(nextMode);
                    if (shot && sceneId) {
                      void api.filmTimelineSetShotModel(project.id, sceneId, shot.id, {
                        generatorId: modelId,
                        providerOptions: { ltxMode: nextMode, ltxStartAssetId: nextStart, ltxEndAssetId: nextEnd },
                      });
                    }
                  }
                : handleAddFromProjectLibrary
          }
        />
      ) : null}
    </>
  );
}
