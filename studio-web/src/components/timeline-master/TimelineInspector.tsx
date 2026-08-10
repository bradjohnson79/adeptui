import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type DirectorTimelineCameraCatalog,
  type DirectorTimelineCameraCatalogEntry,
} from "../../api";
import type { Project, Scene } from "../../types";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { formatBatchStatus } from "../../timelineMaster/contracts";
import { formatDurationSeconds } from "../../lib/formatDuration";
import { useDirectorSelection } from "../DirectorSelectionContext";
import {
  normalizeLipSyncTracks,
  type CameraClip,
  type DirectorTimeline,
  type LipSyncClip,
  type LipSyncTrack,
  type PromptSegment,
  type TimelineClip,
} from "../DirectorTracks";
import { HelpTip } from "../HelpTip";
import { PromptIntelligencePanel } from "../CoDirector/PromptIntelligencePanel";
import {
  SearchableGroupedSelect,
  type SearchableGroupedSelectGroup,
} from "../ui/SearchableGroupedSelect";
import { useDraftField } from "./useDraftField";
import { SceneProductionReadinessPanel } from "./SceneProductionReadinessPanel";

function executionLabel(engine: string) {
  return engine.startsWith("fal_") ? "Hosted" : engine === "auto" ? "Automatic" : "Local";
}

const CAMERA_CAPABILITY_ORDER = {
  Native: 0,
  "Workflow-Mapped": 1,
  "Compiled Prompt Guidance": 2,
  Approximate: 3,
  Unsupported: 4,
} as const;

const EXECUTION_STRATEGY_LABELS: Record<string, string> = {
  native: "Native",
  workflow_mapped: "Workflow-Mapped",
  compiled_prompt_guidance: "Compiled Prompt Guidance",
  approximate: "Approximate",
  unsupported: "Unsupported",
};

function cameraLabel(value: string | null | undefined) {
  return (value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
    .trim();
}

type TimelineGeneratorOption = {
  id: string;
  label: string;
  executable: boolean;
  capabilityLabel?: string;
  notes?: string;
};

/** CAPABILITY_DRIVEN_GENERATOR_MENU: build the batch generator dropdown from
 * the registered Timeline adapter capabilities (never a hardcoded list).
 * The certification stub is filtered out — it is wiring-cert tooling, never
 * creator chrome. Non-executable adapters stay visible but disabled with the
 * honest capability label (Honest Capability Labels, Law 20). */
function generatorOptionsFromPayload(payload: Record<string, unknown>): TimelineGeneratorOption[] {
  const adapters = Array.isArray(payload?.timelineAdapters)
    ? (payload.timelineAdapters as Array<Record<string, unknown>>)
    : [];
  const out: TimelineGeneratorOption[] = [];
  for (const a of adapters) {
    const id = String(a.id || "");
    if (!id || id === "cert-stub-local") continue;
    out.push({
      id,
      label: String(a.label || id),
      executable: a.executable !== false,
      capabilityLabel: a.capabilityLabel ? String(a.capabilityLabel) : undefined,
      notes: a.notes ? String(a.notes) : undefined,
    });
  }
  return out;
}

function resolveCatalogEntry(entries: DirectorTimelineCameraCatalogEntry[], value: string | null | undefined) {
  const key = (value || "").trim().toLowerCase().replace(/-/g, "_");
  if (!key) return null;
  return (
    entries.find((entry) => entry.id === key) ||
    entries.find((entry) => entry.aliases.some((alias) => alias.trim().toLowerCase().replace(/-/g, "_") === key)) ||
    null
  );
}

function classifyExecutionStrategy(clip: CameraClip, catalog: DirectorTimelineCameraCatalog | null) {
  const explicit = (clip.execution_strategy || "").trim().toLowerCase();
  if (explicit) return explicit;
  if (!catalog) return null;
  const hasCustomMotion = Boolean((clip.custom_motion_label || "").trim());
  const hasCustomRig = Boolean((clip.custom_rig_label || "").trim());
  const motionCapability = hasCustomMotion
    ? "Compiled Prompt Guidance"
    : resolveCatalogEntry(catalog.motions, clip.motion_id || clip.motion_type)?.capability || "Unsupported";
  const rigCapability = hasCustomRig
    ? "Compiled Prompt Guidance"
    : resolveCatalogEntry(catalog.rigs, clip.rig_id || clip.rig)?.capability || "Unsupported";
  const capability =
    CAMERA_CAPABILITY_ORDER[motionCapability] >= CAMERA_CAPABILITY_ORDER[rigCapability] ? motionCapability : rigCapability;
  return {
    Native: "native",
    "Workflow-Mapped": "workflow_mapped",
    "Compiled Prompt Guidance": "compiled_prompt_guidance",
    Approximate: "approximate",
    Unsupported: "unsupported",
  }[capability];
}

function cameraGroupOptions(groups: DirectorTimelineCameraCatalog["motionGroups"] | DirectorTimelineCameraCatalog["rigGroups"]): SearchableGroupedSelectGroup[] {
  return groups.map((group) => ({
    label: group.category,
    options: group.items.map((item) => ({
      value: item.id,
      label: item.label,
      description: item.description,
      title: item.description,
      keywords: item.aliases,
    })),
  }));
}

export function TimelineInspector({
  project,
  scene,
  master,
  reloadKey,
  preflightSummary,
  focusFinding = null,
  onRefresh,
  mutateTimeline,
}: {
  project: Project;
  scene: Scene;
  master: SceneTimelineMaster | null;
  reloadKey: number;
  preflightSummary: string;
  focusFinding?: string | null;
  onRefresh: () => void | Promise<void>;
  mutateTimeline: (
    mutator: (timeline: DirectorTimeline) => DirectorTimeline,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
}) {
  const { selection } = useDirectorSelection();
  const [timeline, setTimeline] = useState<DirectorTimeline | null>(null);
  const [cameraCatalog, setCameraCatalog] = useState<DirectorTimelineCameraCatalog | null>(null);
  const [generatorOptions, setGeneratorOptions] = useState<TimelineGeneratorOption[]>([]);
  const [showProjectStyle, setShowProjectStyle] = useState(false);
  const [scenePromptDraftBase, setScenePromptDraftBase] = useState(scene.prompt || "");

  useEffect(() => {
    let alive = true;
    void api
      .directorTimelineGenerators()
      .then((payload) => {
        if (!alive) return;
        setGeneratorOptions(generatorOptionsFromPayload(payload));
      })
      .catch(() => {
        if (!alive) return;
        setGeneratorOptions([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    setScenePromptDraftBase(scene.prompt || "");
  }, [scene.id, scene.prompt]);

  useEffect(() => {
    let alive = true;
    void api.getDirector(project.id, scene.id).then((result) => {
      if (!alive) return;
      // Do not clobber local timeline while an inspector field is focused.
      const active = document.activeElement as HTMLElement | null;
      if (active && active.closest?.("[data-testid='timeline-inspector']")) {
        const tag = active.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || active.isContentEditable) return;
      }
      setTimeline(result as DirectorTimeline);
    });
    return () => {
      alive = false;
    };
  }, [project.id, scene.id, reloadKey]);

  useEffect(() => {
    let alive = true;
    void api
      .directorTimelineCameraCatalog()
      .then((result) => {
        if (!alive) return;
        setCameraCatalog(result);
      })
      .catch(() => {
        if (!alive) return;
        setCameraCatalog(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const selectedPrompt = useMemo(
    () => timeline?.prompt_segments.find((segment) => segment.id === selection.id),
    [timeline, selection.id],
  );
  const selectedImage = useMemo(() => {
    if (!timeline) return undefined;
    if (selection.kind === "imageClip") {
      return timeline.image_clips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "videoClip") {
      return timeline.video_clips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "audio") {
      return timeline.audio_clips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "sfx") {
      return timeline.sfx_clips.find((clip) => clip.id === selection.id);
    }
    return undefined;
  }, [selection.id, selection.kind, timeline]);
  const selectedCamera = useMemo(
    () => timeline?.camera_clips?.find((clip) => clip.id === selection.id),
    [timeline, selection.id],
  );
  const selectedBatch = useMemo(
    () => master?.batchBlocks.find((batch) => batch.id === selection.id),
    [master, selection.id],
  );
  const selectedRepair = useMemo(
    () => master?.batchBlocks.flatMap((batch) => batch.repairRanges.map((repair) => ({ batch, repair }))).find((entry) => entry.repair.id === selection.id),
    [master, selection.id],
  );
  const motionGroups = useMemo(
    () => (cameraCatalog ? cameraGroupOptions(cameraCatalog.motionGroups) : []),
    [cameraCatalog],
  );
  const rigGroups = useMemo(
    () => (cameraCatalog ? cameraGroupOptions(cameraCatalog.rigGroups) : []),
    [cameraCatalog],
  );
  const cameraExecutionStrategy = useMemo(
    () => (selectedCamera ? classifyExecutionStrategy(selectedCamera, cameraCatalog) : null),
    [cameraCatalog, selectedCamera],
  );
  const lipSyncTracks = useMemo(
    () => normalizeLipSyncTracks(timeline?.lipsync?.tracks),
    [timeline],
  );
  const selectedLipSyncTrack = useMemo(() => {
    if (selection.kind === "lipsyncTrack") {
      return lipSyncTracks.find((track) => track.id === selection.id);
    }
    if (selection.kind === "lipsyncClip") {
      return lipSyncTracks.find(
        (track) => track.id === selection.trackId || (track.clips || []).some((clip) => clip.id === selection.id),
      );
    }
    if (selection.kind === "lipsync") {
      return lipSyncTracks[selection.trackIndex ?? Number(selection.id || 0)] || lipSyncTracks[0];
    }
    return undefined;
  }, [lipSyncTracks, selection.id, selection.kind, selection.trackId, selection.trackIndex]);
  const selectedLipSyncClip = useMemo(
    () =>
      selection.kind === "lipsyncClip"
        ? selectedLipSyncTrack?.clips?.find((clip) => clip.id === selection.id)
        : undefined,
    [selectedLipSyncTrack, selection.id, selection.kind],
  );
  const audioAssets = useMemo(
    () => project.assets.filter((asset) => asset.kind === "audio"),
    [project.assets],
  );

  const updateScene = async (patch: Partial<Scene>, opts?: { refresh?: boolean }) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    if (opts?.refresh === false) return;
    await onRefresh();
  };

  const updatePrompt = async (
    segment: PromptSegment,
    patch: Partial<PromptSegment>,
    opts?: { refresh?: boolean },
  ) => {
    setTimeline((current) =>
      current
        ? {
            ...current,
            prompt_segments: current.prompt_segments.map((item) =>
              item.id === segment.id ? { ...item, ...patch } : item,
            ),
          }
        : current,
    );
    await mutateTimeline(
      (current) => ({
        ...current,
        prompt_segments: current.prompt_segments.map((item) => (item.id === segment.id ? { ...item, ...patch } : item)),
      }),
      { refresh: opts?.refresh !== false ? true : false },
    );
  };

  const persistScenePrompt = useCallback(
    async (text: string) => {
      setScenePromptDraftBase(text);
      await updateScene({ prompt: text }, { refresh: false });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [project.id, scene.id, scene.name, scene.engine, scene.duration_sec, scene.director_json],
  );

  const scenePromptField = useDraftField(scenePromptDraftBase, persistScenePrompt, {
    identity: `scene-prompt-${scene.id}`,
    idleMs: 400,
  });

  const persistPromptSegText = useCallback(
    async (text: string) => {
      if (!selectedPrompt) return;
      await updatePrompt(selectedPrompt, { text }, { refresh: false });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedPrompt?.id],
  );

  const promptSegField = useDraftField(selectedPrompt?.text || "", persistPromptSegText, {
    identity: `prompt-seg-${selectedPrompt?.id || "none"}`,
    idleMs: 400,
  });

  const updateClip = async (clip: TimelineClip, key: "image_clips" | "video_clips" | "audio_clips" | "sfx_clips", patch: Partial<TimelineClip>) => {
    await mutateTimeline((current) => ({
      ...current,
      [key]: (current[key] || []).map((item) => (item.id === clip.id ? { ...item, ...patch } : item)),
    }));
  };

  const updateCamera = async (clip: CameraClip, patch: Partial<CameraClip>) => {
    await mutateTimeline((current) => ({
      ...current,
      camera_clips: (current.camera_clips || []).map((item) => (item.id === clip.id ? { ...item, ...patch } : item)),
    }));
  };

  const updateLipSyncTrack = async (track: LipSyncTrack, patch: Partial<LipSyncTrack>) => {
    await mutateTimeline((current) => {
      const tracks = normalizeLipSyncTracks(current.lipsync?.tracks).map((item) =>
        item.id === track.id ? { ...item, ...patch } : item,
      );
      return {
        ...current,
        lipsync: {
          ...current.lipsync,
          tracks,
        },
      };
    });
  };

  const updateLipSyncClip = async (track: LipSyncTrack, clip: LipSyncClip, patch: Partial<LipSyncClip>) => {
    await mutateTimeline((current) => {
      const tracks = normalizeLipSyncTracks(current.lipsync?.tracks).map((item) => {
        if (item.id !== track.id) return item;
        const clips = (item.clips || []).map((entry) => (entry.id === clip.id ? { ...entry, ...patch } : entry));
        const firstAudio = clips.find((entry) => entry.audio_asset_id);
        const firstCharacterId = clips.find((entry) => entry.character_id);
        const firstCharacterName = clips.find((entry) => entry.character_name);
        return {
          ...item,
          enabled: true,
          clips,
          audio_asset_id: firstAudio?.audio_asset_id || item.audio_asset_id || null,
          character_id: firstCharacterId?.character_id || item.character_id || null,
          character_name: firstCharacterName?.character_name || item.character_name || null,
        };
      });
      return {
        ...current,
        lipsync: {
          ...current.lipsync,
          tracks,
        },
      };
    });
  };

  const updateCameraMotion = async (clip: CameraClip, motionId: string) => {
    const entry = resolveCatalogEntry(cameraCatalog?.motions || [], motionId);
    await updateCamera(clip, {
      motion_id: motionId,
      motion_type: motionId === "custom" ? clip.motion_type || "static" : entry?.native_motion_type || entry?.workflow_motion_type || clip.motion_type || "static",
      custom_motion_label: motionId === "custom" ? clip.custom_motion_label || "" : null,
      speed: clip.speed ?? entry?.defaults.speed ?? 1,
      intensity: clip.intensity ?? entry?.defaults.intensity ?? null,
      subject_lock: clip.subject_lock ?? entry?.defaults.subjectLock ?? null,
      execution_strategy: null,
    });
  };

  const updateCameraRig = async (clip: CameraClip, rigId: string) => {
    const entry = resolveCatalogEntry(cameraCatalog?.rigs || [], rigId);
    await updateCamera(clip, {
      rig_id: rigId,
      rig: rigId === "custom" ? clip.rig || "tripod" : entry?.native_rig || entry?.workflow_rig || clip.rig || "tripod",
      custom_rig_label: rigId === "custom" ? clip.custom_rig_label || "" : null,
      execution_strategy: null,
    });
  };

  const updateBatch = async (batch: BatchBlock, patch: Record<string, unknown>, opts?: { refresh?: boolean }) => {
    await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, patch);
    if (opts?.refresh === false) return;
    await onRefresh();
  };

  const persistBatchPrompt = useCallback(
    async (text: string) => {
      if (!selectedBatch) return;
      const segments = selectedBatch.promptSegments.length
        ? selectedBatch.promptSegments.map((seg, idx) => (idx === 0 ? { ...seg, text } : seg))
        : [
            {
              id: `ps_${selectedBatch.id}`,
              start: 0,
              length: selectedBatch.duration.plannedDuration,
              text,
              role: "primary" as const,
              strength: 1,
              anchorIds: [],
              executionStrategy: "compiled" as const,
              versionId: `psv_${selectedBatch.id}`,
            },
          ];
      await updateBatch(selectedBatch, { promptSegments: segments }, { refresh: false });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedBatch?.id, project.id, scene.id],
  );

  const batchPromptField = useDraftField(selectedBatch?.promptSegments[0]?.text || "", persistBatchPrompt, {
    identity: `batch-prompt-${selectedBatch?.id || "none"}`,
    idleMs: 400,
  });

  // Stable draft fields for Scene Name and Duration so typing never triggers
  // a hard save/refresh/remount mid-keystroke (DRAFT_FIELD_STABILITY). They
  // persist on blur/idle and resync from props when not focused.
  const sceneNameField = useDraftField(scene.name, (v) => void updateScene({ name: v }, { refresh: false }), {
    identity: `scene-name-${scene.id}`,
    idleMs: 500,
  });
  const sceneDurationField = useDraftField(
    String(Number(scene.duration_sec.toFixed(2))),
    (v) => {
      const n = Number(v);
      if (Number.isFinite(n) && n > 0) void updateScene({ duration_sec: n }, { refresh: false });
    },
    { identity: `scene-duration-${scene.id}`, idleMs: 500 },
  );

  return (
    <section className="timeline-inspector panel" data-testid="timeline-inspector">
      <div className="timeline-inspector__eyebrow">
        {selection.kind === "scene" || selection.kind === null
          ? "Scene Inspector"
          : selection.kind === "promptSeg"
            ? "Prompt Clip"
            : selection.kind === "imageClip"
              ? "Image Clip"
              : selection.kind === "videoClip"
                ? "Video Clip"
                : selection.kind === "camera"
                  ? "Camera Segment"
                  : selection.kind === "audio"
                    ? "Audio Clip"
                    : selection.kind === "sfx"
                      ? "SFX Clip"
                      : selection.kind === "lipsyncTrack"
                        ? "Lip Sync Track"
                        : selection.kind === "lipsyncClip"
                          ? "Lip Sync Clip"
                          : selection.kind === "batch"
                            ? "Batch"
                            : selection.kind === "repair"
                              ? "Repair Range"
                              : "Scene Inspector"}
      </div>

      {(selection.kind === null || selection.kind === "scene") && (
        <div className="timeline-inspector__stack">
          <label className="field">
            <span>Name</span>
            <input
              value={sceneNameField.value}
              onChange={(e) => sceneNameField.onChange(e.target.value)}
              onFocus={sceneNameField.onFocus}
              onBlur={sceneNameField.onBlur}
            />
          </label>
          <label className="field">
            <span>Scene Prompt</span>
            <textarea
              id="timeline-focus-scene-prompt"
              data-testid="timeline-scene-prompt"
              aria-label="Scene Prompt"
              value={scenePromptField.value}
              onChange={(e) => scenePromptField.onChange(e.target.value)}
              onFocus={scenePromptField.onFocus}
              onBlur={scenePromptField.onBlur}
            />
            <p className="scene-meta">
              Scene Prompt defines the overall Scene. Timed Instructions control particular moments on the Prompt track.
            </p>
          </label>
          <PromptIntelligencePanel
            creatorPrompt={scene.prompt || ""}
            domain="video"
            engineId={scene.engine}
            projectId={project.id}
            sceneId={scene.id}
            negativePrompt={project.negative_prompt}
            compact
            onApply={({ finalProviderPrompt, record }) => {
              let director: Record<string, unknown> = {};
              try {
                director = scene.director_json ? JSON.parse(scene.director_json) : {};
              } catch {
                director = {};
              }
              void updateScene({
                prompt: finalProviderPrompt,
                director_json: JSON.stringify({ ...director, promptIntelligence: record }),
              });
            }}
          />
          <label className="field">
            <span>Generator</span>
            <select value={scene.engine} onChange={(e) => void updateScene({ engine: e.target.value as Scene["engine"] })}>
              <option value="auto">Auto Select</option>
              <option value="minimax-h3">MiniMax H3 (Default)</option>
              <option value="ltx">LTX 2.3</option>
              <option value="wan">WAN 2.2</option>
              <option value="fal_seedance">Seedance</option>
              <option value="fal_kling">Kling</option>
              <option value="fal_veo">Veo</option>
              <option value="fal_runway">Runway</option>
            </select>
          </label>
          <label className="field">
            <span>Duration</span>
            <input
              type="number"
              min={0.1}
              max={120}
              step={0.1}
              value={sceneDurationField.value}
              onChange={(e) => sceneDurationField.onChange(e.target.value)}
              onFocus={sceneDurationField.onFocus}
              onBlur={sceneDurationField.onBlur}
            />
          </label>
          <div className="timeline-inspector__meta-grid">
            <div>
              <strong>Execution</strong>
              <div className="scene-meta">{executionLabel(scene.engine)}</div>
            </div>
            <div>
              <strong>Project Style</strong>
              <div className="scene-meta">
                Inherited{" "}
                <button type="button" className="ghost" onClick={() => setShowProjectStyle((value) => !value)}>
                  View
                </button>{" "}
                <button type="button" className="ghost" onClick={() => void updateScene({ prompt: `${scene.prompt}\n${project.global_prompt}`.trim() })}>
                  Override
                </button>
              </div>
              {showProjectStyle ? <p className="scene-meta">{project.global_prompt || "No project style prompt set."}</p> : null}
            </div>
            <div id="timeline-focus-preflight" data-testid="timeline-preflight-status">
              <strong>Preflight</strong>
              <div className="scene-meta">{preflightSummary}</div>
              {focusFinding ? (
                <p className="scene-meta" data-testid="timeline-preflight-finding-focus">
                  Focused finding: {focusFinding}
                </p>
              ) : null}
            </div>
          </div>
          <SceneProductionReadinessPanel project={project} scene={scene} />
        </div>
      )}

      {selection.kind === "promptSeg" && selectedPrompt ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">Timed Instruction</div>
          <label className="field">
            <span>Start</span>
            <input type="number" value={selectedPrompt.start} step={0.1} onChange={(e) => void updatePrompt(selectedPrompt, { start: Number(e.target.value) || 0 })} />
          </label>
          <label className="field">
            <span>Length</span>
            <input type="number" value={selectedPrompt.length} step={0.1} min={0.1} onChange={(e) => void updatePrompt(selectedPrompt, { length: Number(e.target.value) || 1 })} />
          </label>
          <label className="field">
            <span>Weight</span>
            <input type="number" value={selectedPrompt.weight ?? 1} step={0.1} min={0.1} max={2} onChange={(e) => void updatePrompt(selectedPrompt, { weight: Number(e.target.value) || 1 })} />
          </label>
          <label className="field">
            <span>Instruction</span>
            <textarea
              data-testid="timeline-prompt-instruction"
              value={promptSegField.value}
              onChange={(e) => promptSegField.onChange(e.target.value)}
              onFocus={promptSegField.onFocus}
              onBlur={promptSegField.onBlur}
            />
          </label>
        </div>
      ) : null}

      {selection.kind === "imageClip" && selectedImage ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">Visual Clip</div>
          <label className="field"><span>Start</span><input type="number" value={selectedImage.start} step={0.1} onChange={(e) => void updateClip(selectedImage, "image_clips", { start: Number(e.target.value) || 0 })} /></label>
          <label className="field"><span>Length</span><input type="number" value={selectedImage.length} step={0.1} onChange={(e) => void updateClip(selectedImage, "image_clips", { length: Number(e.target.value) || 1 })} /></label>
          <label className="field">
            <span>Asset</span>
            <select value={selectedImage.asset_id || ""} onChange={(e) => void updateClip(selectedImage, "image_clips", { asset_id: e.target.value || null })}>
              <option value="">Select image</option>
              {project.assets.filter((asset) => asset.kind === "image").map((asset) => (
                <option key={asset.id} value={asset.id}>@{asset.tag || asset.filename}</option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {selection.kind === "videoClip" && selectedImage ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">Video Clip</div>
          <label className="field"><span>Start</span><input type="number" value={selectedImage.start} step={0.1} onChange={(e) => void updateClip(selectedImage, "video_clips", { start: Number(e.target.value) || 0 })} /></label>
          <label className="field"><span>Length</span><input type="number" value={selectedImage.length} step={0.1} onChange={(e) => void updateClip(selectedImage, "video_clips", { length: Number(e.target.value) || 1 })} /></label>
          <label className="field"><span>Trim Start</span><input type="number" value={selectedImage.trim_start || 0} step={0.1} onChange={(e) => void updateClip(selectedImage, "video_clips", { trim_start: Number(e.target.value) || 0 })} /></label>
        </div>
      ) : null}

      {(selection.kind === "audio" || selection.kind === "sfx") && selectedImage ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">{selection.kind === "audio" ? "Audio Clip" : "SFX Clip"}</div>
          <label className="field"><span>Start</span><input type="number" value={selectedImage.start} step={0.1} onChange={(e) => void updateClip(selectedImage, selection.kind === "audio" ? "audio_clips" : "sfx_clips", { start: Number(e.target.value) || 0 })} /></label>
          <label className="field"><span>Length</span><input type="number" value={selectedImage.length} step={0.1} onChange={(e) => void updateClip(selectedImage, selection.kind === "audio" ? "audio_clips" : "sfx_clips", { length: Number(e.target.value) || 1 })} /></label>
          <label className="field"><span>Volume</span><input type="number" value={selectedImage.volume ?? 1} step={0.1} min={0} max={2} onChange={(e) => void updateClip(selectedImage, selection.kind === "audio" ? "audio_clips" : "sfx_clips", { volume: Number(e.target.value) || 1 })} /></label>
        </div>
      ) : null}

      {selection.kind === "camera" && selectedCamera ? (
        <div className="timeline-inspector__stack">
          <label className="field"><span>Start</span><input type="number" value={selectedCamera.start} step={0.1} onChange={(e) => void updateCamera(selectedCamera, { start: Number(e.target.value) || 0 })} /></label>
          <label className="field"><span>Length</span><input type="number" value={selectedCamera.length} step={0.1} onChange={(e) => void updateCamera(selectedCamera, { length: Number(e.target.value) || 1 })} /></label>
          <label className="field">
            <span className="timeline-inspector__label">
              Motion
              <HelpTip
                label="Camera Motion"
                content="Pick the move you want the shot to feel. Search by cinematic language, or choose Custom to name your own move."
              />
            </span>
            <SearchableGroupedSelect
              ariaLabel="Camera motion"
              groups={motionGroups}
              value={selectedCamera.motion_id || selectedCamera.motion_type}
              customValue={selectedCamera.custom_motion_label || ""}
              placeholder={cameraCatalog ? "Choose camera motion" : cameraLabel(selectedCamera.motion_type) || "Loading camera motion"}
              searchPlaceholder="Search camera motion"
              customInputLabel="Custom motion"
              customInputPlaceholder="Describe the move in plain language"
              disabled={!cameraCatalog}
              onValueChange={(value) => void updateCameraMotion(selectedCamera, value)}
              onCustomValueChange={(value) =>
                void updateCamera(selectedCamera, {
                  motion_id: "custom",
                  custom_motion_label: value,
                  execution_strategy: null,
                })
              }
            />
          </label>
          <label className="field">
            <span className="timeline-inspector__label">
              Rig
              <HelpTip
                label="Camera Rig"
                content="Choose the support or capture style for the shot. Use Custom when the setup needs your own wording."
              />
            </span>
            <SearchableGroupedSelect
              ariaLabel="Camera rig"
              groups={rigGroups}
              value={selectedCamera.rig_id || selectedCamera.rig}
              customValue={selectedCamera.custom_rig_label || ""}
              placeholder={cameraCatalog ? "Choose camera rig" : cameraLabel(selectedCamera.rig) || "Loading camera rig"}
              searchPlaceholder="Search camera rig"
              customInputLabel="Custom rig"
              customInputPlaceholder="Describe the support or setup"
              disabled={!cameraCatalog}
              onValueChange={(value) => void updateCameraRig(selectedCamera, value)}
              onCustomValueChange={(value) =>
                void updateCamera(selectedCamera, {
                  rig_id: "custom",
                  custom_rig_label: value,
                  execution_strategy: null,
                })
              }
            />
          </label>
          <div className="timeline-inspector__meta-block">
            <strong>
              Execution strategy{" "}
              <HelpTip
                label="Execution Strategy"
                content="This tells you how honestly the selected camera note can be executed: native, workflow-mapped, prompt-guided, approximate, or unsupported."
              />
            </strong>
            <div className="scene-meta">{cameraExecutionStrategy ? EXECUTION_STRATEGY_LABELS[cameraExecutionStrategy] || cameraLabel(cameraExecutionStrategy) : "Unknown"}</div>
          </div>
          <details className="advanced">
            <summary>
              Advanced{" "}
              <HelpTip
                label="Advanced Camera Controls"
                content="Fine tune speed, intensity, subject lock, and stabilization when the shot needs more control."
              />
            </summary>
            <label className="field">
              <span>Speed</span>
              <input
                type="number"
                step={0.05}
                min={0}
                value={selectedCamera.speed ?? ""}
                onChange={(e) => void updateCamera(selectedCamera, { speed: Number(e.target.value) || 0 })}
              />
            </label>
            <label className="field">
              <span>Intensity</span>
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                value={selectedCamera.intensity ?? ""}
                onChange={(e) => void updateCamera(selectedCamera, { intensity: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Subject lock</span>
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                value={selectedCamera.subject_lock ?? ""}
                onChange={(e) => void updateCamera(selectedCamera, { subject_lock: e.target.value === "" ? null : Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Stabilization</span>
              <input
                value={selectedCamera.stabilization ?? ""}
                placeholder="Off, low, medium, or high"
                onChange={(e) => void updateCamera(selectedCamera, { stabilization: e.target.value || null })}
              />
            </label>
          </details>
        </div>
      ) : null}

      {selection.kind === "batch" && selectedBatch ? (
        <div className="timeline-inspector__stack" data-testid="timeline-batch-inspector">
          <div className="timeline-inspector__eyebrow">Batch</div>
          <label className="field">
            <span>Name</span>
            <input value={selectedBatch.label} onChange={(e) => void updateBatch(selectedBatch, { label: e.target.value })} />
          </label>
          <label className="field">
            <span>Planned Duration</span>
            <input
              type="number"
              value={Number(selectedBatch.duration.plannedDuration.toFixed(2))}
              step={0.1}
              onChange={(e) =>
                void updateBatch(selectedBatch, {
                  plannedDuration: Number(e.target.value) || selectedBatch.duration.plannedDuration,
                })
              }
            />
          </label>
          <label className="field">
            <span>Prompt</span>
            <textarea
              data-testid="timeline-batch-prompt"
              rows={3}
              value={batchPromptField.value}
              onChange={(e) => batchPromptField.onChange(e.target.value)}
              onFocus={batchPromptField.onFocus}
              onBlur={batchPromptField.onBlur}
              placeholder="Describe the motion for this batch"
            />
          </label>
          <label className="field">
            <span>Start Image</span>
            <select
              data-testid="timeline-batch-start-image"
              value={selectedBatch.sourceAnchors.find((a) => a.kind === "image")?.assetId || ""}
              onChange={(e) => {
                const assetId = e.target.value || null;
                const existing = selectedBatch.sourceAnchors.filter((a) => a.kind !== "image");
                const nextAnchors = assetId
                  ? [
                      {
                        id: selectedBatch.sourceAnchors.find((a) => a.kind === "image")?.id || `anc_${selectedBatch.id}`,
                        kind: "image" as const,
                        assetId,
                        label: "Start",
                        atTime: 0,
                        strength: 1,
                      },
                      ...existing,
                    ]
                  : existing;
                void updateBatch(selectedBatch, { sourceAnchors: nextAnchors });
              }}
            >
              <option value="">No start image</option>
              {project.assets
                .filter((asset) => asset.kind === "image")
                .map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.tag || asset.filename || asset.id.slice(0, 8)}
                  </option>
                ))}
            </select>
            <HelpTip text="Guide frame for this batch. With MiniMax H3 Image-to-Video, this picture shapes the motion. Text-to-video keeps it as a planning note only." />
          </label>
          <label className="field">
            <span>Generator</span>
            <select
              data-testid="timeline-batch-generator"
              value={selectedBatch.generatorId || ""}
              onChange={(e) => void updateBatch(selectedBatch, { generatorId: e.target.value || null })}
            >
              <option value="">Select generator</option>
              {generatorOptions.map((g) => (
                <option
                  key={g.id}
                  value={g.id}
                  disabled={!g.executable}
                  title={g.executable ? g.notes : `${g.capabilityLabel || "Unavailable"} — ${g.notes || "not ready"}`}
                >
                  {g.label}
                  {g.capabilityLabel && g.capabilityLabel !== "Certified" ? ` (${g.capabilityLabel})` : ""}
                </option>
              ))}
              {/* Legacy/current value not in the registry stays selectable so
                  existing batches never render blank (preserve capability). */}
              {selectedBatch.generatorId &&
              !generatorOptions.some((g) => g.id === selectedBatch.generatorId) ? (
                <option value={selectedBatch.generatorId}>
                  {selectedBatch.generatorId} (legacy)
                </option>
              ) : null}
            </select>
          </label>
          <div className="scene-meta">Status: {formatBatchStatus(selectedBatch.status)}</div>
        </div>
      ) : null}

      {selection.kind === "repair" && selectedRepair ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">Repair Range</div>
          <div className="scene-meta">{selectedRepair.batch.label}</div>
          <label className="field"><span>Label</span><input value={selectedRepair.repair.label} readOnly /></label>
          <label className="field"><span>Start</span><input value={formatDurationSeconds(selectedRepair.repair.start)} readOnly /></label>
          <label className="field"><span>Length</span><input value={formatDurationSeconds(selectedRepair.repair.length)} readOnly /></label>
          <div className="scene-meta">Status: {selectedRepair.repair.status}</div>
        </div>
      ) : null}

      {(selection.kind === "lipsyncTrack" || selection.kind === "lipsync") && selectedLipSyncTrack ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">LIP SYNC TRACK</div>
          <label className="field">
            <span>Track Name</span>
            <input
              value={selectedLipSyncTrack.label || ""}
              onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { label: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Default Character Name</span>
            <input
              value={selectedLipSyncTrack.character_name || ""}
              placeholder="Who is speaking on this track?"
              onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { character_name: e.target.value || null })}
            />
          </label>
          <label className="field">
            <span>Default Character ID</span>
            <input
              value={selectedLipSyncTrack.character_id || ""}
              placeholder="Optional character profile ID"
              onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { character_id: e.target.value || null })}
            />
          </label>
          <label className="field">
            <span>Default Dialogue Audio</span>
            <select
              value={selectedLipSyncTrack.audio_asset_id || ""}
              onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { audio_asset_id: e.target.value || null })}
            >
              <option value="">Select audio</option>
              {audioAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  @{asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>
              <input
                type="checkbox"
                checked={selectedLipSyncTrack.enabled}
                style={{ width: "auto", marginRight: 8 }}
                onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { enabled: e.target.checked })}
              />
              Track enabled
            </span>
          </label>
          <label className="field">
            <span>Notes</span>
            <textarea
              value={selectedLipSyncTrack.notes || ""}
              onChange={(e) => void updateLipSyncTrack(selectedLipSyncTrack, { notes: e.target.value })}
            />
          </label>
          <p className="scene-meta">
            {selectedLipSyncTrack.clips?.length || 0} clip(s) on this track. Lip Sync 1 stays in the scene; additional tracks can be removed from the toolbar.
          </p>
        </div>
      ) : null}

      {selection.kind === "lipsyncClip" && selectedLipSyncTrack && selectedLipSyncClip ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">LIP SYNC CLIP</div>
          <label className="field">
            <span>Start</span>
            <input
              type="number"
              min={0}
              step={0.1}
              value={selectedLipSyncClip.start}
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  start: Number(e.target.value) || 0,
                })
              }
            />
          </label>
          <label className="field">
            <span>Length</span>
            <input
              type="number"
              min={0.1}
              step={0.1}
              value={selectedLipSyncClip.length}
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  length: Number(e.target.value) || 0.1,
                })
              }
            />
          </label>
          <label className="field">
            <span>Status</span>
            <input
              value={selectedLipSyncClip.status || ""}
              onChange={(e) => void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, { status: e.target.value })}
            />
          </label>
          <label className="field">
            <span>Character Name</span>
            <input
              value={selectedLipSyncClip.character_name || ""}
              placeholder="Who speaks in this clip?"
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  character_name: e.target.value || null,
                })
              }
            />
          </label>
          <label className="field">
            <span>Character ID</span>
            <input
              value={selectedLipSyncClip.character_id || ""}
              placeholder="Optional character profile ID"
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  character_id: e.target.value || null,
                })
              }
            />
          </label>
          <label className="field">
            <span>Dialogue Audio</span>
            <select
              value={selectedLipSyncClip.audio_asset_id || ""}
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  audio_asset_id: e.target.value || null,
                })
              }
            >
              <option value="">Select audio</option>
              {audioAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  @{asset.tag || asset.filename}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Follow Policy</span>
            <select
              value={selectedLipSyncClip.follow_policy || "follow_audio"}
              onChange={(e) =>
                void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                  follow_policy: e.target.value,
                })
              }
            >
              <option value="follow_audio">Follow audio</option>
              <option value="manual">Manual timing</option>
            </select>
          </label>
        </div>
      ) : null}

      {selection.kind &&
        selection.kind !== "scene" &&
        selection.kind !== "batch" &&
        selection.kind !== "job" &&
        !timeline ? (
        <div className="timeline-inspector__stack">
          <p className="scene-meta" data-testid="timeline-inspector-loading">
            Loading clip…
          </p>
        </div>
      ) : null}
    </section>
  );
}
