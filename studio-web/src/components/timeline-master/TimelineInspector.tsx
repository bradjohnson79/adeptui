import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
  type DirectorTimelineCameraCatalog,
  type DirectorTimelineCameraCatalogEntry,
} from "../../api";
import type { Project, Scene } from "../../types";
import type { BatchBlock, ReviewCadence, SceneTimelineMaster, TemporalContinuityPacket } from "../../timelineMaster/contracts";
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
import { PromptReferenceField } from "../sceneReferences/PromptReferenceField";
import { ReferenceTokenAutocomplete } from "../sceneReferences/ReferenceTokenAutocomplete";
import {
  countBindingsByKind,
  displayToken,
  isRealBindingId,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";
import {
  SearchableGroupedSelect,
  type SearchableGroupedSelectGroup,
} from "../ui/SearchableGroupedSelect";
import { useDraftField } from "./useDraftField";
import { SceneProductionReadinessPanel } from "./SceneProductionReadinessPanel";
import {
  draftPathwayCopy,
  generatorOptionsFromPayload,
  promoteCopy,
  resolveGeneratorOption,
  supportsVideoMotionReferences,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import { PRODUCTION_ASPECTS, normalizeProductionAspect } from "../../workspacePrefs";
import { timelineActionError } from "../../timelineMaster/timelineErrors";
import { LoRASelector, type LoraSelection } from "../lora/LoRASelector";

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

function InspectorAccordion({
  title,
  testId,
  defaultOpen = false,
  children,
}: {
  title: string;
  testId: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className="timeline-inspector__accordion"
      data-testid={testId}
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>{title}</summary>
      <div className="timeline-inspector__accordion-body">{children}</div>
    </details>
  );
}

function continuityChipLabel(status: string | undefined, stale?: boolean) {
  if (stale) return "Needs update";
  if (status === "Failed") return "Match failed";
  if (status === "Waiting" || status === "Analyzing") return "Matching…";
  if (status === "Ready" || status === "Applied") return "Matched";
  return null;
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
  onActionError,
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
  onActionError?: (message: string) => void;
}) {
  const { selection } = useDirectorSelection();
  const { t } = useTranslation("timeline");
  const [timeline, setTimeline] = useState<DirectorTimeline | null>(null);
  const [cameraCatalog, setCameraCatalog] = useState<DirectorTimelineCameraCatalog | null>(null);
  const [generatorOptions, setGeneratorOptions] = useState<TimelineGeneratorOption[]>([]);
  const [draftMode, setDraftMode] = useState(true);
  const [showProjectStyle, setShowProjectStyle] = useState(false);
  const [scenePromptDraftBase, setScenePromptDraftBase] = useState(scene.prompt || "");
  const [bindings, setBindings] = useState<ReferenceBindingView[]>([]);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [speakerDraft, setSpeakerDraft] = useState("");

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
    let cancelled = false;
    void Promise.all([
      api.sceneReferences.list(project.id, { scopeType: "project", scopeId: project.id }),
      api.listCharacterProfiles(project.id).catch(() => ({ items: [] as { id: string; name?: string }[] })),
    ])
      .then(([res, characters]) => {
        if (cancelled) return;
        const items = (res.items || []) as ReferenceBindingView[];
        const boundIdentities = new Set(items.map((item) => item.identity_id).filter(Boolean));
        const extra: ReferenceBindingView[] = [];
        for (const profile of characters.items || []) {
          if (boundIdentities.has(profile.id)) continue;
          const name = String(profile.name || "").trim();
          if (!name) continue;
          const asset =
            project.assets.find((a) => (a.tag || "").toLowerCase() === name.toLowerCase() && a.kind === "image") ||
            project.assets.find((a) => a.kind === "image");
          extra.push({
            id: `character:${profile.id}`,
            asset_id: asset?.id || "",
            identity_id: profile.id,
            alias: name.replace(/\s+/g, ""),
            media_kind: "entity",
            reference_type: "character",
            display_token: `@${name.replace(/\s+/g, "")}`,
            asset_name: name,
          });
        }
        setBindings([...items, ...extra]);
      })
      .catch(() => {
        if (!cancelled) setBindings([]);
      });
    return () => {
      cancelled = true;
    };
  }, [project.assets, project.id, reloadKey]);

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

  const [movementChoices, setMovementChoices] = useState<Array<{ id: string; label: string; segmentNumber: number }>>([]);
  useEffect(() => {
    let alive = true;
    void api.spatialMap.listMaps(project.id).then((res) => {
      if (!alive) return;
      const docs = (res.documents || []) as Array<{
        movementSegments?: Array<{ id: string; segmentNumber: number; beatName?: string }>;
      }>;
      const rows = docs[0]?.movementSegments || [];
      setMovementChoices(
        [...rows]
          .sort((a, b) => a.segmentNumber - b.segmentNumber)
          .map((row) => ({
            id: row.id,
            segmentNumber: row.segmentNumber,
            label: row.beatName ? `M${row.segmentNumber} — ${row.beatName}` : `Movement ${row.segmentNumber}`,
          })),
      );
    }).catch(() => {
      if (alive) setMovementChoices([]);
    });
    return () => {
      alive = false;
    };
  }, [project.id]);

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
  const selectedGenerator = useMemo(
    () =>
      resolveGeneratorOption(
        generatorOptions,
        selectedBatch?.generatorId,
        master?.batchBlocks[0]?.generatorId,
        master?.sceneGeneratorId,
        scene.engine,
      ),
    [generatorOptions, master?.batchBlocks, master?.sceneGeneratorId, scene.engine, selectedBatch?.generatorId],
  );
  const draftPathway = selectedGenerator?.draftPathway || "none";
  const draftAvailable = draftPathway !== "none";
  const promptBindingCounts = useMemo(() => {
    const ids = [
      ...(timeline?.prompt_segments || []).flatMap((seg) => seg.reference_binding_ids || []),
      ...(timeline?.camera_clips || []).flatMap((clip) => clip.reference_binding_ids || []),
    ];
    return countBindingsByKind(ids, bindings);
  }, [bindings, timeline?.camera_clips, timeline?.prompt_segments]);
  const cameraBindingCounts = useMemo(
    () => countBindingsByKind(selectedCamera?.reference_binding_ids || [], bindings),
    [bindings, selectedCamera?.reference_binding_ids],
  );
  const videoMotionSupported = supportsVideoMotionReferences(selectedGenerator);
  const videoRefBlocked = Boolean(
    selectedGenerator &&
      promptBindingCounts.video > 0 &&
      (!videoMotionSupported || promptBindingCounts.video > selectedGenerator.maximumReferenceVideos),
  );
  const cameraVideoUnsupported = Boolean(
    selectedGenerator && cameraBindingCounts.video > 0 && !videoMotionSupported,
  );
  const imageRefBlocked = Boolean(
    selectedGenerator && promptBindingCounts.image > (selectedGenerator.maximumReferenceImages || 0),
  );
  useEffect(() => {
    setDraftMode(draftAvailable);
  }, [draftAvailable, selectedBatch?.id, selectedBatch?.generatorId]);
  const continuityPolicy = master?.continuityPolicy;
  const isApiContinuity = continuityPolicy?.locality === "api";
  const cdPolicy = master?.coDirectorContinuityPolicy;
  const [cdAdvancedOpen, setCdAdvancedOpen] = useState(false);
  const latestPacket = useMemo<TemporalContinuityPacket | undefined>(() => {
    const packets = master?.temporalPackets || [];
    if (!selectedBatch) return packets[packets.length - 1];
    return (
      [...packets].reverse().find((packet) => packet.source?.batchId === selectedBatch.id) ||
      packets[packets.length - 1]
    );
  }, [master?.temporalPackets, selectedBatch]);
  const staleDownstream = useMemo(
    () => (master?.batchBlocks || []).filter((batch) => batch.downstreamStale),
    [master],
  );
  const [retakeDelta, setRetakeDelta] = useState("");
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
  useEffect(() => {
    setSpeakerDraft("");
  }, [selectedLipSyncClip?.id]);
  const audioAssets = useMemo(
    () => project.assets.filter((asset) => asset.kind === "audio"),
    [project.assets],
  );

  const [loraSelection, setLoraSelection] = useState<LoraSelection | null>(null);

  // Prefill the drawer LoRA from the scene W46 batch config (batch[0] is
  // the authoritative first-generation config) and persist changes to every
  // batch so the selected generation action actually uses the LoRA.
  useEffect(() => {
    let cancelled = false;
    api
      .directorTimelineMaster(project.id, scene.id)
      .then((payload) => {
        if (cancelled) return;
        const master = payload.master as SceneTimelineMaster | undefined;
        const first = master?.batchBlocks?.find((b) => b.lora?.loraId);
        if (first?.lora) {
          setLoraSelection({
            loraId: first.lora.loraId,
            name: first.lora.name || "",
            strength: Number(first.lora.strength ?? 0.8),
          });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [project.id, scene.id]);

  const applySceneLora = async (selection: LoraSelection | null) => {
    setLoraSelection(selection);
    try {
      const payload = await api.directorTimelineMaster(project.id, scene.id);
      const master = payload.master as SceneTimelineMaster | undefined;
      const batches = master?.batchBlocks || [];
      for (const batch of batches) {
        await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, {
          lora: selection ? { ...selection } : null,
        });
      }
    } catch {
      /* registry/batch updates are best-effort in the drawer; the generation
         worker validates selections and refuses incompatible ones */
    }
  };

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

  const ensureBinding = useCallback(
    async (binding: ReferenceBindingView): Promise<ReferenceBindingView | null> => {
      if (isRealBindingId(binding.id)) return binding;
      if (!String(binding.id || "").startsWith("character:")) {
        setTokenError("Pick a named reference from this project's References.");
        return null;
      }
      if (!binding.asset_id) {
        setTokenError("This character needs a picture in the Library before Timeline can use it.");
        return null;
      }
      const created = (await api.sceneReferences.attach(project.id, {
        asset_id: binding.asset_id,
        scope_type: "project",
        scope_id: project.id,
        reference_type: "character",
        media_kind: "entity",
        identity_id: binding.identity_id,
        alias: binding.alias,
        usage_modes: ["identity", "appearance"],
        reference_roles: ["character"],
      })) as ReferenceBindingView;
      const resolved = { ...binding, ...created, id: String(created.id) };
      setBindings((current) => {
        const withoutSynthetic = current.filter((item) => item.id !== binding.id && item.id !== resolved.id);
        return [...withoutSynthetic, resolved];
      });
      await onRefresh();
      return resolved;
    },
    [onRefresh, project.id],
  );

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

  const persistCameraText = useCallback(
    async (text: string) => {
      if (!selectedCamera) return;
      await updateCamera(selectedCamera, { text });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedCamera?.id],
  );

  const cameraTextField = useDraftField(selectedCamera?.text || "", persistCameraText, {
    identity: `camera-text-${selectedCamera?.id || "none"}`,
    idleMs: 400,
  });

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
          <InspectorAccordion title="Scene" testId="timeline-inspector-scene" defaultOpen>
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
              {t("scenePromptVsTimedPrompt")}
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
          </InspectorAccordion>

          <InspectorAccordion title="Generation" testId="timeline-inspector-generation" defaultOpen>
          <label className="field">
            <span>Generator</span>
            <select value={scene.engine} onChange={(e) => void updateScene({ engine: e.target.value as Scene["engine"] })}>
              <option value="auto">Auto Select</option>
              <option value="minimax-h3">MiniMax H3 (Default)</option>
              <option value="ltx">LTX 2.5</option>
              <option value="wan">WAN 2.2</option>
              <option value="fal_seedance">Seedance</option>
              <option value="fal_kling">Kling</option>
              <option value="fal_veo">Veo</option>
              <option value="fal_runway">Runway</option>
            </select>
          </label>
          <label className="field">
            <span>Picture Shape</span>
            <select
              data-testid="timeline-scene-aspect"
              value={normalizeProductionAspect(scene.aspect_ratio)}
              onChange={(e) => void updateScene({ aspect_ratio: e.target.value })}
            >
              {PRODUCTION_ASPECTS.map((ratio) => (
                <option key={ratio} value={ratio}>
                  {ratio}
                </option>
              ))}
            </select>
            <HelpTip text="How wide the picture is. 16:9 is standard. 21:9 is extra wide. Changing this updates the Viewer immediately." />
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
          </InspectorAccordion>

          <InspectorAccordion title="Extend & Continuity" testId="timeline-inspector-continuity">
            <div className="field" data-testid="timeline-cd-continuity">
              <span>
                Co-Director Continuity
                <HelpTip text="When this is on, Adept looks at the finished shot and helps the next generation continue instead of starting over. You do not need to open Co-Director." />
              </span>
              <label className="scene-meta">
                <input
                  type="checkbox"
                  data-testid="timeline-cd-continuity-enabled"
                  checked={cdPolicy?.enabled !== false}
                  onChange={(e) => {
                    void api
                      .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, { enabled: e.target.checked })
                      .then(onRefresh);
                  }}
                />{" "}
                {cdPolicy?.enabled === false ? "Off" : "On"}
              </label>
              <fieldset className="field" data-testid="timeline-cd-review-cadence">
                <legend>
                  Review
                  <HelpTip text="Automatic picks a review pace from the scene. 3 seconds is for fast action. 5 seconds is for slower shots. Every batch reviews once the shot finishes." />
                </legend>
                {(
                  [
                    ["automatic", "Automatic"],
                    ["interval_3", "3 sec"],
                    ["interval_5", "5 sec"],
                    ["every_batch", "Every batch"],
                  ] as Array<[ReviewCadence, string]>
                ).map(([value, label]) => (
                  <label key={value} className="scene-meta">
                    <input
                      type="radio"
                      name="timeline-cd-review"
                      data-testid={`timeline-cd-cadence-${value}`}
                      checked={(cdPolicy?.reviewCadence || "automatic") === value}
                      onChange={() => {
                        void api
                          .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, { reviewCadence: value })
                          .then(onRefresh);
                      }}
                    />{" "}
                    {label}
                  </label>
                ))}
              </fieldset>
              <label className="field">
                <span>
                  Continuity Protection
                  <HelpTip text="Strong keeps successful motion and screen geography and finishes unfinished action. Standard is a lighter touch." />
                </span>
                <select
                  data-testid="timeline-cd-protection"
                  value={cdPolicy?.protection || "strong"}
                  onChange={(e) => {
                    void api
                      .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, { protection: e.target.value })
                      .then(onRefresh);
                  }}
                >
                  <option value="strong">Strong</option>
                  <option value="standard">Standard</option>
                </select>
              </label>
              <button
                type="button"
                className="ghost"
                data-testid="timeline-cd-advanced-toggle"
                onClick={() => setCdAdvancedOpen((open) => !open)}
              >
                {cdAdvancedOpen ? "Hide advanced" : "Advanced"}
              </button>
              {cdAdvancedOpen ? (
                <div data-testid="timeline-cd-advanced">
                  <label className="field">
                    <span>Fast Vision</span>
                    <input value={cdPolicy?.fastVisionModel || "VideoChat3"} readOnly />
                  </label>
                  <label className="field">
                    <span>Deep Review</span>
                    <select
                      data-testid="timeline-cd-deep-review"
                      value={cdPolicy?.deepReview || "auto"}
                      onChange={(e) => {
                        void api
                          .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, { deepReview: e.target.value })
                          .then(onRefresh);
                      }}
                    >
                      <option value="auto">Automatic</option>
                      <option value="off">Off</option>
                      <option value="on">On</option>
                    </select>
                  </label>
                  <label className="scene-meta">
                    <input
                      type="checkbox"
                      data-testid="timeline-cd-show-debug"
                      checked={Boolean(cdPolicy?.showDebugState)}
                      onChange={(e) => {
                        void api
                          .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, {
                            showDebugState: e.target.checked,
                          })
                          .then(onRefresh);
                      }}
                    />{" "}
                    Show review details
                  </label>
                </div>
              ) : null}
              {latestPacket?.availability === "unavailable" ? (
                <p className="scene-meta" data-testid="timeline-cd-unavailable">
                  Co-Director visual continuity unavailable. Timeline generation may continue without visual review.
                </p>
              ) : null}
              {latestPacket?.creatorMarker ? (
                <p className="scene-meta" data-testid="timeline-cd-marker">
                  {latestPacket.creatorMarker}
                </p>
              ) : null}
              {latestPacket && latestPacket.availability !== "unavailable" ? (
                <button
                  type="button"
                  className="ghost"
                  data-testid="timeline-cd-reject"
                  onClick={() => {
                    void api
                      .directorTimelineRejectTemporalContinuation(project.id, scene.id, {
                        packetId: latestPacket.packetId,
                        manualNote: cdPolicy?.creatorNextBatchNote || undefined,
                      })
                      .then(onRefresh);
                  }}
                >
                  Don’t use this continuation
                </button>
              ) : null}
              <label className="field">
                <span>
                  Note for the next shot
                  <HelpTip text="Optional. Tell Adept what the next generation should finish or avoid." />
                </span>
                <textarea
                  data-testid="timeline-cd-next-note"
                  rows={2}
                  defaultValue={cdPolicy?.creatorNextBatchNote || ""}
                  onBlur={(e) => {
                    const value = e.target.value;
                    if (value === (cdPolicy?.creatorNextBatchNote || "")) return;
                    void api
                      .directorTimelineSetCoDirectorContinuityPolicy(project.id, scene.id, {
                        creatorNextBatchNote: value,
                      })
                      .then(onRefresh);
                  }}
                />
              </label>
              {cdPolicy?.showDebugState && latestPacket ? (
                <p className="scene-meta" data-testid="timeline-cd-debug">
                  Review {latestPacket.availability}
                  {latestPacket.reason ? ` · ${latestPacket.reason}` : ""}
                </p>
              ) : null}
            </div>
            <p className="scene-meta">
              Shot matching uses the last moments of the previous shot so the next generation can start from the same picture.
            </p>
            {isApiContinuity ? (
              <label className="field">
                <span>Auto Continuity</span>
                <select
                  data-testid="timeline-continuity-window"
                  value={String(continuityPolicy?.configuredTailDuration ?? 0)}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    void api.directorTimelineSetContinuityPolicy(project.id, scene.id, { configuredTailDuration: n }).then(onRefresh);
                  }}
                >
                  <option value="0">Off</option>
                  <option value="3">Last 3 seconds</option>
                  <option value="5">Last 5 seconds</option>
                </select>
                <HelpTip text="Off means Adept will not spend API credits to match shots in the background. 3 or 5 seconds uses the end of the previous shot when you generate the next one." />
              </label>
            ) : (
              <p className="scene-meta" data-testid="timeline-continuity-local-lock">
                Auto Continuity is on. Adept uses the last 5 seconds of the previous shot — or the whole shot if it is shorter.
              </p>
            )}
          </InspectorAccordion>

          <InspectorAccordion title="Re-Take" testId="timeline-inspector-retake">
            <p className="scene-meta">
              A new take keeps the scene, matching, and original intent. Your note is the change — not a rewrite.
            </p>
            {staleDownstream.length > 0 ? (
              <div className="timeline-inspector__stale" data-testid="timeline-downstream-stale">
                <p className="scene-meta">Later shots still use the old take.</p>
                <button
                  type="button"
                  data-testid="timeline-reconcile-downstream"
                  onClick={() => void api.directorTimelineReconcileDownstream(project.id, scene.id, { spendApiCredits: false }).then(onRefresh)}
                >
                  Update later shots
                </button>
                <button
                  type="button"
                  className="ghost"
                  data-testid="timeline-keep-existing-downstream"
                  onClick={() => void api.directorTimelineKeepExistingDownstream(project.id, scene.id).then(onRefresh)}
                >
                  Keep existing
                </button>
              </div>
            ) : null}
          </InspectorAccordion>

          <InspectorAccordion title="Advanced" testId="timeline-inspector-advanced">
            <LoRASelector
              modelFamily={scene.engine}
              modality="video"
              value={loraSelection}
              onChange={(selection) => void applySceneLora(selection)}
            />
            <SceneProductionReadinessPanel project={project} scene={scene} />
          </InspectorAccordion>
        </div>
      )}

      {selection.kind === "promptSeg" && selectedPrompt ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">{t("timedPromptClip")}</div>
          <label className="field">
            <span>Start</span>
            <input
              type="number"
              data-testid="timeline-timed-prompt-start"
              value={selectedPrompt.start}
              step={0.1}
              onChange={(e) => void updatePrompt(selectedPrompt, { start: Number(e.target.value) || 0 })}
            />
          </label>
          <label className="field">
            <span>Length</span>
            <input type="number" value={selectedPrompt.length} step={0.1} min={0.1} onChange={(e) => void updatePrompt(selectedPrompt, { length: Number(e.target.value) || 1 })} />
          </label>
          <label className="field">
            <span>Weight</span>
            <input type="number" value={selectedPrompt.weight ?? 1} step={0.1} min={0.1} max={2} onChange={(e) => void updatePrompt(selectedPrompt, { weight: Number(e.target.value) || 1 })} />
          </label>
          {movementChoices.length ? (
            <label className="field">
              <span>Movement</span>
              <select
                data-testid="timeline-prompt-movement"
                value={selectedPrompt.movement_segment_ref?.id || ""}
                onChange={(e) => {
                  const chosen = movementChoices.find((row) => row.id === e.target.value);
                  void updatePrompt(selectedPrompt, {
                    movement_segment_ref: chosen
                      ? { id: chosen.id, segmentNumber: chosen.segmentNumber, alias: `M${chosen.segmentNumber}` }
                      : null,
                    movement_segment_revision: chosen ? 1 : null,
                  });
                }}
              >
                <option value="">None</option>
                {movementChoices.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className="field">
            <span>Instruction</span>
            <PromptReferenceField
              text={promptSegField.value}
              bindingIds={selectedPrompt.reference_binding_ids || []}
              bindings={bindings}
              maxImages={selectedGenerator?.maximumReferenceImages}
              maxVideos={selectedGenerator?.maximumReferenceVideos}
              onTextChange={(next) => promptSegField.onChange(next)}
              onTextFocus={promptSegField.onFocus}
              onTextBlur={promptSegField.onBlur}
              onBindingsChange={(ids) => void updatePrompt(selectedPrompt, { reference_binding_ids: ids })}
              onReject={setTokenError}
              ensureBinding={ensureBinding}
            />
            {tokenError ? (
              <p className="scene-meta" data-testid="timeline-reference-type-error">
                {tokenError}
              </p>
            ) : null}
            {imageRefBlocked || videoRefBlocked ? (
              <p className="scene-meta" data-testid="prompt-ref-capability-warning">
                {videoRefBlocked
                  ? "Selected generator does not support Video Reference."
                  : "This generator cannot use all stored image references. Stored references are kept; generation is refused until you switch models or remove extras."}
              </p>
            ) : null}
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
            <span>{t("cameraMotionInstruction")}</span>
            <PromptReferenceField
              text={cameraTextField.value}
              bindingIds={selectedCamera.reference_binding_ids || []}
              bindings={bindings}
              maxVideos={selectedGenerator?.maximumReferenceVideos}
              track="camera"
              placeholder="@ character  * video"
              onTextChange={(next) => cameraTextField.onChange(next)}
              onTextFocus={cameraTextField.onFocus}
              onTextBlur={cameraTextField.onBlur}
              onBindingsChange={(ids) => void updateCamera(selectedCamera, { reference_binding_ids: ids })}
              onReject={setTokenError}
              ensureBinding={ensureBinding}
            />
            <p className="scene-meta">{t("cameraVsTimedPrompt")}</p>
            {tokenError ? (
              <p className="scene-meta" data-testid="timeline-reference-type-error">
                {tokenError}
              </p>
            ) : null}
            {cameraVideoUnsupported ? (
              <p className="scene-meta" data-testid="camera-ref-capability-warning">
                {t("videoMotionUnsupported")}
              </p>
            ) : null}
          </label>
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
              data-testid="timeline-batch-duration"
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
          <label className="field">
            <span>Draft Mode</span>
            <input
              type="checkbox"
              data-testid="timeline-draft-mode"
              checked={draftAvailable && draftMode}
              disabled={!draftAvailable}
              onChange={(e) => setDraftMode(e.target.checked)}
            />
            <HelpTip text={draftPathwayCopy(draftPathway)} />
          </label>
          <p className="scene-meta" data-testid="timeline-draft-pathway-copy">
            {draftPathwayCopy(draftPathway)}
          </p>
          {videoRefBlocked ? (
            <p className="scene-meta" data-testid="timeline-video-ref-blocked">
              Selected model does not support video reference. The * video name stays, but this model will not use it.
            </p>
          ) : null}
          {imageRefBlocked ? (
            <p className="scene-meta" data-testid="timeline-image-ref-blocked">
              This generator cannot use all stored image references. Stored references are kept; generation is refused until you switch models or remove extras.
            </p>
          ) : null}
          {selectedGenerator &&
          selectedGenerator.supportedAspectRatios.length > 0 &&
          !selectedGenerator.supportedAspectRatios.includes(normalizeProductionAspect(scene.aspect_ratio)) &&
          !selectedGenerator.supportedAspectRatios.some((a) => a.includes(normalizeProductionAspect(scene.aspect_ratio))) ? (
            <p className="scene-meta" data-testid="timeline-aspect-warning">
              This generator may not honor {normalizeProductionAspect(scene.aspect_ratio)}. Adept will not crop a different shape and call it {normalizeProductionAspect(scene.aspect_ratio)}.
            </p>
          ) : null}
          <div className="timeline-inspector__row">
            <button
              type="button"
              className="primary"
              data-testid="timeline-generate-draft"
              onClick={() =>
                void api
                  .directorTimelineGenerateBatch(project.id, scene.id, selectedBatch.id, {
                    draftMode: draftAvailable ? draftMode : false,
                  })
                  .then((result) => {
                    const err = timelineActionError(result);
                    if (err) onActionError?.(err);
                    void onRefresh();
                  })
              }
            >
              {draftAvailable ? "Generate Draft" : "Generate Final"}
            </button>
            {draftAvailable ? (
              <button
                type="button"
                data-testid="timeline-generate-final"
                onClick={() =>
                  void api
                    .directorTimelineGenerateBatch(project.id, scene.id, selectedBatch.id, { draftMode: false })
                    .then((result) => {
                      const err = timelineActionError(result);
                      if (err) onActionError?.(err);
                      void onRefresh();
                    })
                }
              >
                Generate Final
              </button>
            ) : null}
          </div>
          {(() => {
            const latest = [...(selectedBatch.candidateVersions || [])].reverse()[0];
            const isDraftTake = String(latest?.takeState?.quality || "").toLowerCase() === "draft";
            const generating = selectedBatch.status === "Generating";
            const canStop =
              generating &&
              (selectedGenerator?.supportsQueuedCancel || selectedGenerator?.supportsRunningCancel);
            return (
              <>
                {generating && canStop ? (
                  <button
                    type="button"
                    data-testid="timeline-stop-jobs"
                    onClick={() =>
                      void api
                        .directorTimelineCancel(project.id, scene.id, { action: "cancel_active_local_job" })
                        .then(onRefresh)
                    }
                  >
                    Stop
                  </button>
                ) : null}
                {generating && !canStop ? (
                  <p className="scene-meta" data-testid="timeline-cancel-unavailable">
                    Provider is rendering — cancellation unavailable
                  </p>
                ) : null}
                {isDraftTake && latest ? (
                  <div className="timeline-inspector__row" data-testid="timeline-draft-actions">
                    <button
                      type="button"
                      className="primary"
                      data-testid="timeline-promote-final"
                      disabled={videoRefBlocked}
                      title={promoteCopy(selectedGenerator?.finalRequiresNewGeneration !== false)}
                      onClick={() =>
                        void api
                          .directorTimelineGenerateBatch(project.id, scene.id, selectedBatch.id, { draftMode: false })
                          .then((result) => {
                            const err = timelineActionError(result);
                            if (err) onActionError?.(err);
                            void onRefresh();
                          })
                      }
                    >
                      Promote to Final
                    </button>
                    <button
                      type="button"
                      data-testid="timeline-reject-take"
                      onClick={() =>
                        void api
                          .directorTimelineRejectTake(project.id, scene.id, selectedBatch.id, latest.id)
                          .then(onRefresh)
                      }
                    >
                      Reject
                    </button>
                    <p className="scene-meta">{promoteCopy(selectedGenerator?.finalRequiresNewGeneration !== false)}</p>
                  </div>
                ) : null}
              </>
            );
          })()}
          <div className="scene-meta">Status: {formatBatchStatus(selectedBatch.status)}</div>
          {selectedBatch.downstreamStale ? (
            <p className="scene-meta" data-testid="timeline-batch-stale">This shot still uses the previous take from earlier in the scene.</p>
          ) : null}
          {(() => {
            const incoming = (master?.continuityBridges || []).find(
              (bridge) => bridge.targetBatchId === selectedBatch.id && bridge.status !== "Superseded",
            );
            if (!incoming) return null;
            if (incoming.status !== "Failed") {
              return (
                <p className="scene-meta" data-testid="timeline-batch-continuity">
                  Continuity: {continuityChipLabel(incoming.status) || incoming.status}
                </p>
              );
            }
            return (
              <div data-testid="timeline-batch-continuity-failed">
                <p className="scene-meta">Matching the previous shot failed.</p>
                <button type="button" onClick={() => void api.directorTimelineRetryBridge(project.id, scene.id, incoming.bridgeId).then(onRefresh)}>
                  Retry
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => void api.directorTimelineContinueWithoutBridge(project.id, scene.id, incoming.bridgeId).then(onRefresh)}
                >
                  Continue without matching
                </button>
              </div>
            );
          })()}
          <label className="field">
            <span>What should change</span>
            <textarea
              data-testid="timeline-retake-delta-field"
              rows={2}
              value={retakeDelta}
              onChange={(e) => setRetakeDelta(e.target.value)}
              placeholder="Example: walk behind the cruiser, not in front"
            />
            <HelpTip text="Adept keeps the scene, the match from the previous shot, and the original idea. This note is only the change." />
          </label>
          <button
            type="button"
            data-testid="timeline-batch-retake"
            onClick={() =>
              void api
                .directorTimelineRetakeBatch(project.id, scene.id, selectedBatch.id, {
                  mode: "directed",
                  userCorrection: { delta: retakeDelta },
                })
                .then(onRefresh)
            }
          >
            New take
          </button>
          {selectedBatch.candidateVersions.length > 1 ? (
            <div className="timeline-inspector__takes" data-testid="timeline-batch-takes">
              {selectedBatch.candidateVersions.map((cand, index) => (
                <button
                  key={cand.id}
                  type="button"
                  className={cand.approved ? "active" : "ghost"}
                  data-testid={`timeline-take-${cand.id}`}
                  onClick={() =>
                    void api.directorTimelineActivateTake(project.id, scene.id, selectedBatch.id, cand.id).then(onRefresh)
                  }
                >
                  {cand.label || `Take ${String.fromCharCode(65 + index)}`}
                  {cand.approved ? " (active)" : ""}
                </button>
              ))}
            </div>
          ) : null}
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
            <span>Character</span>
            <ReferenceTokenAutocomplete
              value={speakerDraft}
              bindings={bindings}
              track="lipsyncSpeaker"
              placeholder={
                selectedLipSyncClip.speaker_binding_id
                  ? displayToken(
                      bindings.find((item) => item.id === selectedLipSyncClip.speaker_binding_id)?.alias ||
                        selectedLipSyncClip.character_name,
                      "entity",
                    ) || "@ character"
                  : "@ character"
              }
              onChange={setSpeakerDraft}
              onCommit={(binding) => {
                void (async () => {
                  const resolved = await ensureBinding(binding);
                  if (!resolved || !isRealBindingId(resolved.id)) {
                    setTokenError("Lip Sync only accepts @ character tokens.");
                    return;
                  }
                  setSpeakerDraft("");
                  void updateLipSyncClip(selectedLipSyncTrack, selectedLipSyncClip, {
                    speaker_binding_id: resolved.id,
                    character_id: resolved.identity_id || null,
                    character_name: resolved.alias || resolved.asset_name || null,
                  });
                })();
              }}
              onReject={setTokenError}
            />
            {selectedLipSyncClip.audio_asset_id && !selectedLipSyncClip.speaker_binding_id ? (
              <p className="scene-meta" data-testid="lipsync-speaker-required">
                Assign a character to this Lip Sync clip.
              </p>
            ) : null}
            {tokenError ? <p className="scene-meta">{tokenError}</p> : null}
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
