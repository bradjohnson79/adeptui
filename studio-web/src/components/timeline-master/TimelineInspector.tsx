import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
} from "../../api";
import type { Project, Scene } from "../../types";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { formatBatchStatus } from "../../timelineMaster/contracts";
import { formatDurationSeconds } from "../../lib/formatDuration";
import { useDirectorSelection } from "../DirectorSelectionContext";
import {
  dropTombstonedPrompts,
  isPromptTombstoned,
  type TimelineBoardView,
  type PromptSegment,
  type TimelineClip,
} from "../DirectorTracks";
import { authoredScenePromptFromTimedPrompts } from "../authoredScenePrompt";
import { ActionWithHelp, HelpTip } from "../HelpTip";
import { PromptIntelligencePanel } from "../CoDirector/PromptIntelligencePanel";
/* Phase 0: PromptReferenceField camera-track chrome removed */
import {
  countBindingsByKind,
  type ReferenceBindingView,
} from "../../sceneReferences/referenceTokens";
/* Phase 0: SearchableGroupedSelect was camera-clip-only */
import { useDraftField } from "./useDraftField";
import { TimeStepperField } from "./TimeStepperField";
import { ScenePromptTemplateBar } from "./ScenePromptTemplateBar";
import { SceneProductionReadinessPanel } from "./SceneProductionReadinessPanel";
import type { TimelinePreflightFinding, TimelinePreflightStatus } from "../../timelineMaster/useTimelinePreflight";
import { TimedPromptReferenceBindingsEditor } from "./TimedPromptReferenceBindingsEditor";
import {
  getBoundShellTimeline,
  subscribeShellTimelineSnapshot,
} from "./timelineMutateBridge";
import {
  bindingIdsFromNameBindings,
  hydrateTimedPromptNameBindings,
  labelCharacterBindingFromIdentity,
} from "../../timelineMaster/timedPromptNameBindings";
import {
  collectPromptBindingIds,
  loadTimelineReferenceCatalog,
} from "../../timelineMaster/loadTimelineReferenceCatalog";
import {
  canonicalGeneratorId,
  resolveGeneratorOption,
  supportsTurboLora,
  supportsVideoMotionReferences,
  type TimelineGeneratorOption,
} from "../../timelineMaster/draftCapabilities";
import { loadTimelineVideoGenerators } from "../../timelineMaster/useTimelineVideoGenerators";
import { applyTimelineSceneGenerator, applyTimelineTurboLora } from "../../timelineMaster/applySceneGenerator";
import { h3PrewarmOnGeneratorSelect } from "../minimax-h3/prewarmTrigger";
import { creatorGeneratorLine } from "../../timelineMaster/generatorDuration";
import {
  decideTimedPromptRange,
  formatSceneClockSec,
  h3ExtensionWindows,
  H3_NATIVE_GENERATION_SEC,
  liveSceneClockSec,
  sanitizeSceneDurationSec,
  sceneDurationHelp,
} from "../../timelineMaster/sceneDurationAuthority";
import { persistCanonicalSceneDuration } from "../../timelineMaster/persistSceneDuration";
import { isMinimaxH3Engine } from "../timelineSceneDuration";
import { resolveMediaClipLabels } from "../../timelineMaster/mediaClipLabels";
import { PRODUCTION_ASPECTS, normalizeProductionAspect } from "../../workspacePrefs";
import type { SceneFinalCheckState } from "../../timelineMaster/sceneFinalCheck";
import { LoRASelector, type LoraSelection } from "../lora/LoRASelector";
import { TimelineSceneTakesPanel } from "./TimelineSceneTakesPanel";
import { GeneratorQualityControls, NativeAudioCapability } from "./GeneratorCapabilityControls";
import { SceneContinuityPolicy } from "./ExtendContinuityPanel";
import { TimedPromptWindowInspector } from "./TimedPromptWindowInspector";
import { FinalCheckPanel } from "./FinalCheckPanel";
import { GenerationDetailsReadOnly } from "./GenerationDetailsReadOnly";
import {
  executionWindowSpans,
  resolveExecutionWindowForPrompt,
} from "../../timelineMaster/resolveExecutionWindowForPrompt";

function executionLabel(engine: string) {
  return engine.startsWith("fal_") ? "Hosted" : engine === "auto" ? "Automatic" : "Local";
}

const SPOKEN_LANGUAGE_OPTIONS: Array<{ code: string; label: string }> = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "zh", label: "Chinese" },
  { code: "pt", label: "Portuguese" },
  { code: "it", label: "Italian" },
  { code: "hi", label: "Hindi" },
];

function sceneSpokenLanguageFromMaster(master: SceneTimelineMaster | null): string {
  return String(master?.sceneLanguage || master?.spokenLanguage?.sceneLanguage || "").trim();
}

/* Phase 0: camera-clip catalog helpers removed — Timed Prompt is sole camera authority */

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


export function TimelineInspector({
  project,
  scene,
  master,
  reloadKey,
  preflightSummary,
  preflightStatus = "idle",
  preflightFindings = [],
  onPreflightRecheck,
  focusFinding = null,
  onRefresh,
  mutateTimeline,
  onActionError,
  onGenerationStandby,
  previewTakeId = null,
  onPreviewTake,
}: {
  project: Project;
  scene: Scene;
  master: SceneTimelineMaster | null;
  reloadKey: number;
  preflightSummary: string;
  preflightStatus?: TimelinePreflightStatus;
  preflightFindings?: TimelinePreflightFinding[];
  onPreflightRecheck?: () => void | Promise<void>;
  focusFinding?: string | null;
  onRefresh: () => void | Promise<void>;
  mutateTimeline: (
    mutator: (timeline: TimelineBoardView) => TimelineBoardView,
    opts?: { refresh?: boolean },
  ) => Promise<void>;
  onActionError?: (message: string) => void;
  onGenerationStandby?: (standby: boolean) => void;
  previewTakeId?: string | null;
  onPreviewTake?: (takeId: string | null) => void;
}) {
  const { selection } = useDirectorSelection();
  const { t } = useTranslation("timeline");
  const [timeline, setTimeline] = useState<TimelineBoardView | null>(null);
  /* Phase 0: cameraCatalog fetch removed with camera-clip Inspector */
  const [generatorOptions, setGeneratorOptions] = useState<TimelineGeneratorOption[]>([]);
  const [generatorLoad, setGeneratorLoad] = useState<"loading" | "ready" | "error">("loading");
  const [draftMode, setDraftMode] = useState(true);
  const [showProjectStyle, setShowProjectStyle] = useState(false);
  const authoredTimedPrompt = useMemo(
    () => authoredScenePromptFromTimedPrompts(master),
    [master],
  );
  const syncedScenePromptKey = useRef("");
  const [scenePromptDraftBase, setScenePromptDraftBase] = useState(
    () => authoredScenePromptFromTimedPrompts(master) || scene.prompt || "",
  );
  const [bindings, setBindings] = useState<ReferenceBindingView[]>([]);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [generatorError, setGeneratorError] = useState<string | null>(null);
  const [durationError, setDurationError] = useState<string | null>(null);
  const [timedPromptOffer, setTimedPromptOffer] = useState<{
    start: number;
    length: number;
    neededSceneSec: number;
    message: string;
  } | null>(null);
  const [turboPending, setTurboPending] = useState<boolean | null>(null);
  const [spokenLanguagePending, setSpokenLanguagePending] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setGeneratorLoad("loading");
    void loadTimelineVideoGenerators()
      .then((rows) => {
        if (!alive) return;
        setGeneratorOptions(rows);
        setGeneratorLoad("ready");
      })
      .catch(() => {
        if (!alive) return;
        setGeneratorOptions([]);
        setGeneratorLoad("error");
      });
    return () => {
      alive = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    const authored = authoredTimedPrompt.trim();
    const stored = (scene.prompt || "").trim();
    if (!authored) {
      setScenePromptDraftBase(scene.prompt || "");
      return;
    }
    if (stored === authored) {
      syncedScenePromptKey.current = `${scene.id}:${authored}`;
      setScenePromptDraftBase(authored);
    }
  }, [scene.id, scene.prompt, authoredTimedPrompt]);

  useEffect(() => {
    setTurboPending(null);
  }, [master?.turboLora]);

  useEffect(() => {
    setSpokenLanguagePending(null);
  }, [master?.sceneLanguage, master?.spokenLanguage?.sceneLanguage, scene.id]);

  const storedPromptBindingKey = useMemo(
    () => collectPromptBindingIds(timeline?.promptSegments).sort().join(","),
    [timeline?.promptSegments],
  );

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      loadTimelineReferenceCatalog({
        projectId: project.id,
        sceneId: scene.id,
        bindingIds: storedPromptBindingKey ? storedPromptBindingKey.split(",") : [],
      }),
      api.listCharacterProfiles(project.id).catch(() => ({ items: [] as { id: string; name?: string }[] })),
    ])
      .then(async ([catalog, characters]) => {
        if (cancelled) return;
        const profiles = new Map(
          (characters.items || []).map((profile) => [profile.id, String(profile.name || "").trim()]),
        );
        const items = catalog.map((binding) =>
          labelCharacterBindingFromIdentity(binding, profiles.get(binding.identity_id || "")),
        );
        const boundIdentities = new Set(items.map((item) => item.identity_id).filter(Boolean));
        const extra: ReferenceBindingView[] = [];
        for (const profile of characters.items || []) {
          if (boundIdentities.has(profile.id)) continue;
          const name = String(profile.name || "").trim();
          if (!name) continue;
          const refs = await api.listCharacterReferences(project.id, profile.id).catch(() => ({ items: [] as { asset_id?: string; reference_role?: string; approval_status?: string; canonical?: boolean }[] }));
          const hero =
            (refs.items || []).find(
              (row) =>
                (row.reference_role === "hero_identity" || row.reference_role === "hero_portrait") &&
                String(row.approval_status || "").toLowerCase() === "approved" &&
                row.canonical,
            ) ||
            (refs.items || []).find(
              (row) =>
                (row.reference_role === "hero_identity" || row.reference_role === "hero_portrait") &&
                String(row.approval_status || "").toLowerCase() === "approved",
            );
          extra.push({
            id: `character:${profile.id}`,
            asset_id: hero?.asset_id || "",
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
  }, [project.assets, project.id, reloadKey, scene.id, storedPromptBindingKey]);

  useEffect(() => {
    const apply = (incoming: TimelineBoardView | null) => {
      if (!incoming) return;
      setTimeline({
        ...incoming,
        promptSegments: dropTombstonedPrompts(incoming.promptSegments || []),
      });
    };
    apply(getBoundShellTimeline());
    return subscribeShellTimelineSnapshot(apply);
  }, [project.id, scene.id]);

  /* Phase 0: directorTimelineCameraCatalog fetch removed */

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
    () => {
      // PHASE23_INSPECTOR_MASTER_READ: prefer Master batch.promptSegments as Timed Prompt authority.
      if (selection.kind === "promptSeg" && master?.batchBlocks) {
        for (const batch of master.batchBlocks) {
          const hit = (batch.promptSegments || []).find(
            (seg) =>
              seg.id === selection.id ||
              (seg as { legacyPromptSegmentId?: string }).legacyPromptSegmentId === selection.id,
          );
          if (hit) {
            return {
              id: (hit as { legacyPromptSegmentId?: string }).legacyPromptSegmentId || hit.id,
              start: Number(hit.start) || 0,
              length: Number(hit.length) || 0,
              text: hit.text || "",
              reference_binding_ids: (hit as { referenceBindingIds?: string[] }).referenceBindingIds || [],
              reference_name_bindings: (hit as { referenceNameBindings?: unknown }).referenceNameBindings,
              production_prompt: (hit as { productionPrompt?: string | null }).productionPrompt ?? null,
              dialogue: (hit as { dialogue?: string | null }).dialogue ?? null,
              movement_segment_ref: (hit as { movementSegmentRef?: PromptSegment["movement_segment_ref"] })
                .movementSegmentRef ?? null,
              movement_segment_revision: (
                hit as { movementSegmentRevision?: number | null }
              ).movementSegmentRevision ?? null,
            } as PromptSegment;
          }
        }
      }
      return undefined;
    },
    [timeline, selection.id, selection.kind, master?.batchBlocks],
  );
  const selectedImage = useMemo(() => {
    if (!timeline) return undefined;
    if (selection.kind === "imageClip") {
      return timeline.imageClips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "videoClip") {
      return timeline.videoClips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "audio") {
      return timeline.audioClips.find((clip) => clip.id === selection.id);
    }
    if (selection.kind === "sfx") {
      return timeline.sfxClips.find((clip) => clip.id === selection.id);
    }
    return undefined;
  }, [selection.id, selection.kind, timeline]);
  /* Phase 0: camera-clip Inspector chrome removed; detect legacy selection only */
  const legacyCameraSelected = selection.kind === "camera";
  const selectedBatch = useMemo(
    () => master?.batchBlocks.find((batch) => batch.id === selection.id),
    [master, selection.id],
  );
  /** Execution window bound to the selected Timed Prompt (scene-time overlap). */
  const boundWindow = useMemo(() => {
    if (selection.kind !== "promptSeg" || !selectedPrompt) return null;
    return resolveExecutionWindowForPrompt(master?.batchBlocks, selectedPrompt);
  }, [master?.batchBlocks, selectedPrompt, selection.kind]);
  const boundWindowSpan = useMemo(() => {
    if (!boundWindow) return null;
    const hit = executionWindowSpans(master?.batchBlocks).find((row) => row.batch.id === boundWindow.id);
    return hit ? { start: hit.start, end: hit.end } : null;
  }, [boundWindow, master?.batchBlocks]);
  const selectedGenerator = useMemo(
    () =>
      resolveGeneratorOption(
        generatorOptions,
        boundWindow?.generatorId,
        selectedBatch?.generatorId,
        master?.batchBlocks[0]?.generatorId,
        master?.sceneGeneratorId,
        scene.engine,
      ),
    [generatorOptions, master?.batchBlocks, master?.sceneGeneratorId, scene.engine, selectedBatch?.generatorId, boundWindow?.generatorId],
  );
  const draftPathway = selectedGenerator?.draftPathway || "none";
  const draftAvailable = draftPathway !== "none";
  const promptBindingCounts = useMemo(() => {
    const ids = [
      ...(timeline?.promptSegments || []).flatMap((seg) => seg.reference_binding_ids || []),
    ];
    return countBindingsByKind(ids, bindings);
  }, [bindings, timeline?.promptSegments]);
  const videoMotionSupported = supportsVideoMotionReferences(selectedGenerator);
  const videoRefBlocked = Boolean(
    selectedGenerator &&
      promptBindingCounts.video > 0 &&
      (!videoMotionSupported || promptBindingCounts.video > selectedGenerator.maximumReferenceVideos),
  );
  /* Phase 0: cameraVideoUnsupported removed with camera-clip chrome */
  const imageRefBlocked = Boolean(
    selectedGenerator && promptBindingCounts.image > (selectedGenerator.maximumReferenceImages || 0),
  );
  useEffect(() => {
    setDraftMode(draftAvailable);
  }, [draftAvailable, selectedBatch?.id, selectedBatch?.generatorId]);
  const staleDownstream = useMemo(
    () => (master?.batchBlocks || []).filter((batch) => batch.downstreamStale),
    [master],
  );
  const selectedRepair = useMemo(
    () => master?.batchBlocks.flatMap((batch) => batch.repairRanges.map((repair) => ({ batch, repair }))).find((entry) => entry.repair.id === selection.id),
    [master, selection.id],
  );
  /* Phase 0: motion/rig Inspector groups removed */

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
    const { director_json: _ignored, ...safe } = { ...scene, ...patch };
    await api.updateScene(project.id, scene.id, safe);
    if (opts?.refresh === false) return;
    await onRefresh();
  };

  const updatePrompt = async (
    segment: PromptSegment,
    patch: Partial<PromptSegment>,
    opts?: { refresh?: boolean },
  ) => {
    // A03_SINGLE_AUTHORING_SOURCE: Inspector edits must reach generation input
    // (master batch.promptSegments), not only legacy director_tl.promptSegments.
    if (master) {
      const { patchMasterPrompt } = await import("../../timelineMaster/masterTimelineMutate");
      await patchMasterPrompt(project.id, scene.id, master, {
        id: segment.id,
        start: Number(patch.start ?? segment.start) || 0,
        length: Number(patch.length ?? segment.length) || 0,
        text: patch.text ?? segment.text,
        referenceBindingIds: patch.reference_binding_ids || segment.reference_binding_ids || [],
        referenceNameBindings:
          patch.reference_name_bindings !== undefined
            ? patch.reference_name_bindings
            : undefined,
        productionPrompt: patch.production_prompt !== undefined ? patch.production_prompt : undefined,
        dialogue: patch.dialogue !== undefined ? patch.dialogue : undefined,
        movementSegmentRef:
          patch.movement_segment_ref !== undefined ? patch.movement_segment_ref : undefined,
        movementSegmentRevision:
          patch.movement_segment_revision !== undefined
            ? patch.movement_segment_revision
            : undefined,
        strength: patch.weight !== undefined ? Number(patch.weight) : undefined,
      });
      if (opts?.refresh !== false) await onRefresh();
      return;
    }
    await mutateTimeline(
      (current) => current,
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

  useEffect(() => {
    const authored = authoredTimedPrompt.trim();
    if (!authored || scenePromptField.isDirty) return;
    if ((scene.prompt || "").trim() === authored) return;
    const key = `${scene.id}:${authored}`;
    if (syncedScenePromptKey.current === key) return;
    syncedScenePromptKey.current = key;
    setScenePromptDraftBase(authored);
    void persistScenePrompt(authored);
  }, [authoredTimedPrompt, scene.id, scene.prompt, scenePromptField.isDirty, persistScenePrompt]);

  const persistPromptSegText = useCallback(
    async (text: string) => {
      if (!selectedPrompt || isPromptTombstoned(selectedPrompt.id)) return;
      await updatePrompt(selectedPrompt, { text, production_prompt: null }, { refresh: false });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selectedPrompt?.id],
  );

  const promptSegField = useDraftField(selectedPrompt?.text || "", persistPromptSegText, {
    identity: `prompt-seg-${selectedPrompt?.id || "none"}`,
    idleMs: 400,
  });

  const updateClip = async (clip: TimelineClip, key: "imageClips" | "videoClips" | "audioClips" | "sfxClips", patch: Partial<TimelineClip>) => {
    await mutateTimeline((current) => ({
      ...current,
      [key]: (current[key] || []).map((item) => (item.id === clip.id ? { ...item, ...patch } : item)),
    }));
  };

  const mediaLane =
    selection.kind === "audio" ? "audioClips" : selection.kind === "sfx" ? "sfxClips" : null;
  const mediaResolved = useMemo(() => {
    if (!selectedImage || !mediaLane) return null;
    const asset = project.assets.find((row) => row.id === selectedImage.asset_id);
    return resolveMediaClipLabels({
      kind: selection.kind === "sfx" ? "sfx" : "audio",
      clip: {
        title: selectedImage.title,
        description: selectedImage.description,
        label: selectedImage.label,
        asset_id: selectedImage.asset_id,
      },
      asset: asset ? { tag: asset.tag, filename: asset.filename } : null,
    });
  }, [mediaLane, project.assets, selectedImage, selection.kind]);
  const persistMediaField = (patch: Partial<TimelineClip>) => {
    if (!selectedImage || !mediaLane) return;
    void updateClip(selectedImage, mediaLane, patch);
  };
  const mediaTitleField = useDraftField(
    selectedImage?.title || mediaResolved?.title || "",
    (value) => persistMediaField({ title: value }),
    { identity: `media-title-${selectedImage?.id || "none"}`, idleMs: 400 },
  );
  const mediaDescriptionField = useDraftField(
    selectedImage?.description || mediaResolved?.description || "",
    (value) => persistMediaField({ description: value }),
    { identity: `media-description-${selectedImage?.id || "none"}`, idleMs: 400 },
  );
  const mediaLabelField = useDraftField(
    selectedImage?.label || mediaResolved?.label || "",
    (value) => persistMediaField({ label: value }),
    { identity: `media-label-${selectedImage?.id || "none"}`, idleMs: 400 },
  );

  /* Phase 0: updateCamera* removed — no camera-clip Inspector writes */

  /** Scene-level quality authority: patch every batch so request_builder reads the same field. */
  const persistSceneQuality = async (patch: Record<string, unknown>) => {
    const batches = master?.batchBlocks || [];
    if (!batches.length) return;
    for (const batch of batches) {
      await api.directorTimelinePatchBatch(project.id, scene.id, batch.id, patch);
    }
    await onRefresh();
  };

  const persistSceneDuration = useCallback(
    async (v: string) => {
      const n = Number(v);
      const sanitized = sanitizeSceneDurationSec(n);
      if (!sanitized.ok) {
        setDurationError(sanitized.error || "Enter how long this scene should be.");
        return;
      }
      setDurationError(null);
      const gen = resolveGeneratorOption(
        generatorOptions,
        master?.sceneGeneratorId,
        master?.batchBlocks[0]?.generatorId,
        scene.engine,
      );
      const result = await persistCanonicalSceneDuration({
        projectId: project.id,
        sceneId: scene.id,
        durationSec: sanitized.durationSec,
        generatorId: gen?.id || master?.sceneGeneratorId || scene.engine,
        mutateTimeline,
      });
      if (result.ok === false) {
        setDurationError(
          String(result.message || result.error || "Could not update the scene length. Your value was saved — Generate will continue from there."),
        );
      }
      await onRefresh();
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [generatorOptions, master?.sceneGeneratorId, master?.batchBlocks, scene.engine, scene.id, project.id, mutateTimeline, onRefresh],
  );

  const previewPromptRange = (start: number, length: number) => {
    const sceneDur = liveSceneClockSec(scene, timeline);
    const decision = decideTimedPromptRange(start, length, sceneDur, scene.name || "Scene 1");
    setTimedPromptOffer(
      !decision.ok && decision.reason === "overflow"
        ? { start, length, neededSceneSec: decision.neededSceneSec, message: decision.message }
        : null,
    );
    return decision.ok;
  };

  const applyPromptRange = async (segment: PromptSegment, start: number, length: number) => {
    if (!previewPromptRange(start, length)) return;
    await updatePrompt(segment, { start, length });
  };

  const acceptTimedPromptExtend = async () => {
    if (!timedPromptOffer || !selectedPrompt) return;
    const gen = resolveGeneratorOption(
      generatorOptions,
      master?.sceneGeneratorId,
      master?.batchBlocks[0]?.generatorId,
      scene.engine,
    );
    const result = await persistCanonicalSceneDuration({
      projectId: project.id,
      sceneId: scene.id,
      durationSec: timedPromptOffer.neededSceneSec,
      generatorId: gen?.id || master?.sceneGeneratorId || scene.engine,
      mutateTimeline,
    });
    if (result.ok === false) {
      setDurationError(String(result.message || result.error || "Could not extend the scene."));
      return;
    }
    await updatePrompt(selectedPrompt, { start: timedPromptOffer.start, length: timedPromptOffer.length });
    setTimedPromptOffer(null);
    await onRefresh();
  };

  const sceneNameField = useDraftField(scene.name, (v) => void updateScene({ name: v }, { refresh: false }), {
    identity: `scene-name-${scene.id}`,
    idleMs: 500,
  });

  const sceneDurationField = useDraftField(String(Number(scene.duration_sec.toFixed(2))), (v) => void persistSceneDuration(v), {
    identity: `scene-duration-${scene.id}`,
    idleMs: 500,
  });
  const sceneSpokenLanguage = spokenLanguagePending ?? sceneSpokenLanguageFromMaster(master);
  const spokenLanguageCustom =
    Boolean(sceneSpokenLanguage) &&
    !SPOKEN_LANGUAGE_OPTIONS.some((option) => option.code === sceneSpokenLanguage);

  return (
    <section className="timeline-inspector panel" data-testid="timeline-inspector">
      <div className="timeline-inspector__eyebrow">
        {selection.kind === "scene" || selection.kind === null
          ? "Scene Inspector"
          : selection.kind === "promptSeg"
            ? "Timed Prompt"
            : selection.kind === "imageClip"
              ? "Image Clip"
              : selection.kind === "videoClip"
                ? "Video Clip"
                : selection.kind === "camera"
                  ? "Camera (retired)"
                  : selection.kind === "audio"
                    ? "Audio Clip"
                    : selection.kind === "sfx"
                      ? "SFX Clip"
                      : selection.kind === "lipsyncTrack"
                        ? "Clip"
                        : selection.kind === "lipsyncClip"
                          ? "Clip"
                          : selection.kind === "batch"
                            ? "Generation window"
                            : selection.kind === "repair"
                              ? "Repair Range"
                              : "Scene Inspector"}
      </div>

      <SceneProductionReadinessPanel
        project={project}
        scene={scene}
        reloadKey={reloadKey}
        preflightStatus={preflightStatus}
        preflightSummary={preflightSummary}
        preflightFindings={preflightFindings}
        onRunPreflight={onPreflightRecheck}
      />
      {(selection.kind === "scene" || selection.kind === null) && master ? (
        <GenerationDetailsReadOnly master={master} />
      ) : null}

      {(selection.kind === null || selection.kind === "scene" || selection.kind === "promptSeg") && (
        <div className="timeline-inspector__stack">
          {(selection.kind === null || selection.kind === "scene") && (
          <InspectorAccordion title="Scene" testId="timeline-inspector-scene" defaultOpen>
          <label className="field">
            <span>Name</span>
            <input
              data-testid="timeline-inspector-scene-name"
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
            <ScenePromptTemplateBar
              projectId={project.id}
              workingText={scenePromptField.value}
              isDirty={scenePromptField.isDirty}
              sourceSceneId={scene.id}
              suggestedName={scene.name}
              generatorFamily={
                selectedGenerator
                  ? canonicalGeneratorId(selectedGenerator.id) || selectedGenerator.locality || ""
                  : ""
              }
              generatorId={selectedGenerator?.id || undefined}
              onLoadText={async (text) => {
                scenePromptField.onChange(text);
                scenePromptField.flush();
                await persistScenePrompt(text);
              }}
              testIdPrefix="timeline-scene-prompt-template"
            />
          </label>
          <PromptIntelligencePanel
            creatorPrompt={scenePromptField.value || scene.prompt || ""}
            domain="video"
            engineId={scene.engine}
            projectId={project.id}
            sceneId={scene.id}
            negativePrompt={project.negative_prompt}
            compact
            onApply={({ finalProviderPrompt, record }) => {
              void (async () => {
                await api.updateScene(project.id, scene.id, { prompt: finalProviderPrompt });
                await api.directorTimelinePatchSceneMetadata(project.id, scene.id, {
                  promptIntelligence: record,
                });
                await onRefresh();
              })();
            }}
          />
          </InspectorAccordion>
          )}

          <InspectorAccordion title="Generation" testId="timeline-inspector-generation" defaultOpen>
          <label className="field">
            <span>
              Spoken Language{" "}
              <HelpTip text="The language characters speak in this scene. Needed when someone has a line." />
            </span>
            <select
              data-testid="timeline-spoken-language"
              value={sceneSpokenLanguage}
              onChange={(event) => {
                const language = event.target.value;
                if (!language) return;
                setSpokenLanguagePending(language);
                void api
                  .directorTimelinePutSceneSpokenLanguage(project.id, scene.id, language)
                  .then(() => onRefresh())
                  .catch((err) => {
                    setSpokenLanguagePending(null);
                    onActionError?.(
                      err instanceof Error && err.message
                        ? err.message
                        : "Could not save spoken language. Try again.",
                    );
                  });
              }}
            >
              <option value="">Choose language…</option>
              {SPOKEN_LANGUAGE_OPTIONS.map((option) => (
                <option key={option.code} value={option.code}>
                  {option.label}
                </option>
              ))}
              {spokenLanguageCustom ? <option value={sceneSpokenLanguage}>{sceneSpokenLanguage}</option> : null}
            </select>
          </label>
          <label className="field">
            <span>Generator</span>
            <select
              data-testid="timeline-inspector-generator"
              value={
                resolveGeneratorOption(
                  generatorOptions,
                  master?.sceneGeneratorId,
                  master?.batchBlocks[0]?.generatorId,
                  scene.engine,
                )?.id || ""
              }
              onChange={(event) => {
                const generatorId = event.target.value;
                if (!generatorId) return;
                setGeneratorError(null);
                h3PrewarmOnGeneratorSelect(generatorId);
                void applyTimelineSceneGenerator({
                  projectId: project.id,
                  scene,
                  master,
                  timeline,
                  options: generatorOptions,
                  generatorId,
                  trim: false,
                  mutateTimeline,
                  onRefresh,
                }).catch((err) => {
                  setGeneratorError(
                    err instanceof Error && err.message
                      ? err.message
                      : "Could not save the engine. Try again.",
                  );
                });
              }}
            >
              <option value="">{generatorOptions.length ? "Choose an engine" : "No local engines ready"}</option>
              {generatorOptions.map((option) => (
                <option
                  key={option.id}
                  value={option.id}
                  disabled={!option.executable}
                  title={option.disabledReason || option.notes}
                >
                  {creatorGeneratorLine(option)}
                </option>
              ))}
            </select>
          </label>
          <GeneratorQualityControls
            option={selectedGenerator}
            h3Resolution={master?.batchBlocks[0]?.h3Resolution || selectedBatch?.h3Resolution}
            ltxQuality={master?.batchBlocks[0]?.ltxQuality || selectedBatch?.ltxQuality}
            draftMode={draftMode}
            megapixelsTestId="timeline-inspector-megapixels"
            megapixelsSelectTestId="timeline-inspector-megapixels-select"
            megapixelsAutoTestId="timeline-inspector-megapixels-auto-dims"
            qualityTestId="timeline-inspector-quality"
            qualitySelectTestId="timeline-inspector-quality-select"
            megapixelsLabel={t("megapixelsLabel")}
            megapixelsTip={t("megapixelsTip")}
            qualityLabel={t("qualityLabel")}
            qualityTip={t("qualityTip")}
            onH3Change={(next) => void persistSceneQuality({ h3Resolution: next })}
            onLtxChange={(tier) => void persistSceneQuality({ ltxQuality: tier })}
          />
          <NativeAudioCapability
            option={selectedGenerator}
            loadState={generatorLoad}
            hasTimelineAudio={
              Boolean((timeline?.audioClips || []).length) || Boolean((timeline?.sfxClips || []).length)
            }
          />
          {supportsTurboLora(
            resolveGeneratorOption(
              generatorOptions,
              master?.sceneGeneratorId,
              master?.batchBlocks[0]?.generatorId,
              scene.engine,
            ),
          ) && master ? (
            <div className="timeline-v2__turbo-lora" data-testid="timeline-inspector-turbo-lora">
              <ActionWithHelp
                help={{
                  label: "What is Turbo LoRA?",
                  content:
                    "Turbo LoRA accelerates supported video generation while preserving the normal generator workflow as closely as possible. Available only on supported models.",
                  text: "Turbo LoRA accelerates supported video generation while preserving the normal generator workflow as closely as possible. Available only on supported models.",
                }}
              >
                <span className="timeline-v2__turbo-lora-label">
                  Turbo LoRA: {(turboPending ?? master.turboLora) ? "On" : "Off"}
                </span>
              </ActionWithHelp>
              <input
                className="timeline-v2__turbo-lora-toggle"
                type="checkbox"
                role="switch"
                data-testid="timeline-inspector-turbo-lora-toggle"
                aria-label="Turbo LoRA"
                checked={turboPending ?? Boolean(master.turboLora)}
                onChange={(event) => {
                  const enabled = event.target.checked;
                  setTurboPending(enabled);
                  setGeneratorError(null);
                  void applyTimelineTurboLora({
                    projectId: project.id,
                    sceneId: scene.id,
                    master,
                    options: generatorOptions,
                    enabled,
                    onRefresh,
                  }).catch((err) => {
                    setTurboPending(null);
                    setGeneratorError(
                      err instanceof Error && err.message ? err.message : "Could not save Turbo LoRA.",
                    );
                  });
                }}
              />
            </div>
          ) : null}
          {generatorError ? (
            <p className="scene-meta" role="alert" data-testid="timeline-inspector-generator-error">
              {generatorError}
            </p>
          ) : null}
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
            <HelpTip text="How wide the picture is. 16:9 is standard landscape. 9:16 is vertical. 21:9 is extra wide. Changing this updates the Viewer immediately." />
          </label>
          <label className="field">
            <span>Duration <HelpTip text={sceneDurationHelp(scene.engine, scene.duration_sec)} /></span>
            <input
              type="number"
              min={0.1}
              step={0.1}
              data-testid="timeline-inspector-duration"
              value={sceneDurationField.value}
              onChange={(e) => sceneDurationField.onChange(e.target.value)}
              onFocus={sceneDurationField.onFocus}
              onBlur={sceneDurationField.onBlur}
            />
            {isMinimaxH3Engine(scene.engine) && scene.duration_sec > H3_NATIVE_GENERATION_SEC + 1e-6 ? (
              <p className="scene-meta" data-testid="timeline-inspector-h3-extension-plan">
                MiniMax H3 continues this scene as{" "}
                {h3ExtensionWindows(scene.duration_sec)
                  .map((window) => `${formatSceneClockSec(window.start)}–${formatSceneClockSec(window.end)}s`)
                  .join(" then ")}
                .
              </p>
            ) : null}
            {durationError ? (
              <p className="scene-meta" data-testid="timeline-inspector-duration-error">
                {durationError}
              </p>
            ) : null}
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
              {showProjectStyle ? <p className="scene-meta">{(project as any).visual_style || project.global_prompt || "No project visual style set."}</p> : null}
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
            <SceneContinuityPolicy
              projectId={project.id}
              sceneId={scene.id}
              master={master}
              selectedBatch={selectedBatch}
              onRefresh={onRefresh}
            />
          </InspectorAccordion>
          <InspectorAccordion title="Takes" testId="timeline-inspector-retake" defaultOpen>
            {master ? (
              <TimelineSceneTakesPanel
                projectId={project.id}
                sceneId={scene.id}
                master={master}
                previewTakeId={previewTakeId}
                onPreviewTake={onPreviewTake || (() => undefined)}
                onRefresh={onRefresh}
                onError={onActionError}
                onGenerationStandby={onGenerationStandby}
              />
            ) : (
              <p className="scene-meta">
                A new take remakes the whole scene. To change only a part of the video, use Re-Take on the Preview Monitor.
              </p>
            )}
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
            {master?.sceneFinalCheck ? (
              <div data-testid="timeline-advanced-final-check">
                <p className="scene-meta">Final Check status and issues</p>
                <FinalCheckPanel
                  open
                  state={
                    master.sceneFinalCheck
                      ? {
                          ...master.sceneFinalCheck,
                          categories: (master.sceneFinalCheck.categories || []).map((c) => ({
                            ...c,
                            findings: (c.findings ?? []).map((f) => ({
                              ...f,
                              taxonomy: f.taxonomy ?? null,
                            })),
                          })),
                        } as SceneFinalCheckState
                      : null
                  }
                  onRepairDecision={async (decision, nextGate) => {
                    try {
                      await api.directorTimelineFinalCheckDecision(project.id, scene.id, {
                        decision,
                        runtimeKind: nextGate.runtimeKind,
                      });
                      await onRefresh();
                    } catch (error) {
                      onActionError?.(
                        error instanceof Error && error.message
                          ? error.message
                          : "Final Check decision failed",
                      );
                    }
                  }}
                />
              </div>
            ) : (
              <p className="scene-meta" data-testid="timeline-advanced-final-check-empty">
                No Final Check results yet. They appear here after stitch / Final Check runs.
              </p>
            )}
            <LoRASelector
              modelFamily={scene.engine}
              modality="video"
              value={loraSelection}
              onChange={(selection) => void applySceneLora(selection)}
            />
          </InspectorAccordion>
        </div>
      )}

      {selection.kind === "promptSeg" && selectedPrompt ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">{t("timedPromptClip")}</div>
          <TimeStepperField
            label="Start"
            value={selectedPrompt.start}
            min={0}
            step={0.1}
            testId="timeline-timed-prompt-start"
            onDraft={(start) => {
              if (start == null) return;
              previewPromptRange(start, selectedPrompt.length);
            }}
            onChange={(start) => void applyPromptRange(selectedPrompt, start, selectedPrompt.length)}
          />
          <TimeStepperField
            label="Length"
            value={selectedPrompt.length}
            min={0.1}
            step={0.1}
            testId="timeline-timed-prompt-length"
            onDraft={(length) => {
              if (length == null) return;
              previewPromptRange(selectedPrompt.start, length);
            }}
            onChange={(length) => void applyPromptRange(selectedPrompt, selectedPrompt.start, length)}
          />
          {timedPromptOffer ? (
            <div className="timeline-inspector__stack" data-testid="timeline-timed-prompt-overflow">
              <p className="scene-meta" role="status">
                {timedPromptOffer.message}
              </p>
              <button
                type="button"
                data-testid="timeline-timed-prompt-extend-scene"
                onClick={() => void acceptTimedPromptExtend()}
              >
                Extend scene to {formatSceneClockSec(timedPromptOffer.neededSceneSec)}s
              </button>
            </div>
          ) : null}
          <TimeStepperField
            label="Weight"
            value={selectedPrompt.weight ?? 1}
            min={0.1}
            max={2}
            step={0.1}
            testId="timeline-timed-prompt-weight"
            suffix=""
            onChange={(weight) => void updatePrompt(selectedPrompt, { weight })}
          />
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
          <TimedPromptReferenceBindingsEditor
            compact
            projectId={project.id}
            value={hydrateTimedPromptNameBindings({
              nameBindings: selectedPrompt.reference_name_bindings,
              bindingIds: selectedPrompt.reference_binding_ids,
              bindings,
            })}
            bindings={bindings}
            onValidationError={setTokenError}
            onChange={(rows, error) => {
              setTokenError(error);
              // Prompt Name commits only (blur / idle / structural) — never per keystroke.
              if (error) return;
              void updatePrompt(
                selectedPrompt,
                {
                  reference_name_bindings: rows,
                  reference_binding_ids: bindingIdsFromNameBindings(rows),
                },
                { refresh: false },
              );
            }}
          />
          {tokenError ? (
            <p className="scene-meta" data-testid="timeline-reference-type-error">
              {tokenError}
            </p>
          ) : null}
          <label className="field">
            <span>Prompt (Timed Prompt / Input Text)</span>
            <textarea
              data-testid="timeline-prompt-instruction"
              aria-label="Timed Prompt"
              value={promptSegField.value}
              onChange={(e) => promptSegField.onChange(e.target.value)}
              onFocus={promptSegField.onFocus}
              onBlur={promptSegField.onBlur}
            />
            <p className="scene-meta" data-testid="timed-prompt-authority-hint">
              This Timed Prompt is the one Timeline will generate from.
            </p>
            <ScenePromptTemplateBar
              projectId={project.id}
              workingText={promptSegField.value}
              isDirty={promptSegField.isDirty}
              sourceSceneId={scene.id}
              suggestedName={scene.name}
              generatorFamily={
                selectedGenerator
                  ? canonicalGeneratorId(selectedGenerator.id) || selectedGenerator.locality || ""
                  : ""
              }
              generatorId={
                selectedGenerator?.id || (selectedPrompt as any)?.generatorId || undefined
              }
              onLoadText={async (text) => {
                promptSegField.onChange(text);
                promptSegField.flush();
                if (!selectedPrompt || isPromptTombstoned(selectedPrompt.id)) return;
                await updatePrompt(selectedPrompt, { text, production_prompt: null }, { refresh: false });
              }}
              testIdPrefix="scene-prompt-template"
            />
            {imageRefBlocked || videoRefBlocked ? (
              <p className="scene-meta" data-testid="prompt-ref-capability-warning">
                {videoRefBlocked
                  ? "Selected generator does not support Video Reference."
                  : "This generator cannot use all stored image references. Stored references are kept; generation is refused until you switch models or remove extras."}
              </p>
            ) : null}
          </label>

          {boundWindow && boundWindowSpan ? (
            <TimedPromptWindowInspector
              projectId={project.id}
              sceneId={scene.id}
              master={master}
              windowBatch={boundWindow}
              windowSpan={boundWindowSpan}
              selectedGenerator={selectedGenerator}
              videoRefBlocked={videoRefBlocked}
              onRefresh={onRefresh}
              onActionError={onActionError}
            />
          ) : selection.kind === "promptSeg" ? (
            <p className="scene-meta" data-testid="timeline-timed-prompt-window-unbound">
              No generation association for this Timed Prompt yet. Associations come from the Co-Director plan after rematerialize.
            </p>
          ) : null}
        </div>
      ) : null}

      {selection.kind === "imageClip" && selectedImage ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">Visual Clip</div>
          <TimeStepperField label="Start" value={selectedImage.start} min={0} step={0.1} testId="timeline-image-clip-start" onChange={(start) => void updateClip(selectedImage, "imageClips", { start })} />
          <TimeStepperField label="Length" value={selectedImage.length} min={0.1} step={0.1} testId="timeline-image-clip-length" onChange={(length) => void updateClip(selectedImage, "imageClips", { length })} />
          <label className="field">
            <span>Asset</span>
            <select value={selectedImage.asset_id || ""} onChange={(e) => void updateClip(selectedImage, "imageClips", { asset_id: e.target.value || null })}>
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
          <TimeStepperField label="Start" value={selectedImage.start} min={0} step={0.1} testId="timeline-video-clip-start" onChange={(start) => void updateClip(selectedImage, "videoClips", { start })} />
          <TimeStepperField label="Length" value={selectedImage.length} min={0.1} step={0.1} testId="timeline-video-clip-length" onChange={(length) => void updateClip(selectedImage, "videoClips", { length })} />
          <TimeStepperField label="Trim Start" value={selectedImage.trim_start || 0} min={0} step={0.1} testId="timeline-video-clip-trim" onChange={(trim_start) => void updateClip(selectedImage, "videoClips", { trim_start })} />
        </div>
      ) : null}

      {(selection.kind === "audio" || selection.kind === "sfx") && selectedImage ? (
        <div className="timeline-inspector__stack">
          <div className="timeline-inspector__eyebrow">{selection.kind === "audio" ? "Audio Clip" : "SFX Clip"}</div>
          <label className="field">
            <span>Title</span>
            <input
              data-testid="timeline-inspector-media-title"
              value={mediaTitleField.value}
              onChange={(e) => mediaTitleField.onChange(e.target.value)}
              onFocus={mediaTitleField.onFocus}
              onBlur={mediaTitleField.onBlur}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              data-testid="timeline-inspector-media-description"
              value={mediaDescriptionField.value}
              onChange={(e) => mediaDescriptionField.onChange(e.target.value)}
              onFocus={mediaDescriptionField.onFocus}
              onBlur={mediaDescriptionField.onBlur}
              rows={3}
            />
          </label>
          <label className="field">
            <span>Label (clip face)</span>
            <input
              data-testid="timeline-inspector-media-label"
              value={mediaLabelField.value}
              onChange={(e) => mediaLabelField.onChange(e.target.value)}
              onFocus={mediaLabelField.onFocus}
              onBlur={mediaLabelField.onBlur}
            />
          </label>
          <TimeStepperField
            label="Start"
            value={selectedImage.start}
            min={0}
            step={0.1}
            testId="timeline-media-clip-start"
            onChange={(start) => void updateClip(selectedImage, mediaLane || "audioClips", { start })}
          />
          <TimeStepperField
            label="Length"
            value={selectedImage.length}
            min={0.1}
            step={0.1}
            testId="timeline-media-clip-length"
            onChange={(length) => void updateClip(selectedImage, mediaLane || "audioClips", { length })}
          />
          <TimeStepperField
            label="Volume"
            value={selectedImage.volume ?? 1}
            min={0}
            max={2}
            step={0.1}
            testId="timeline-media-clip-volume"
            suffix=""
            onChange={(volume) => void updateClip(selectedImage, mediaLane || "audioClips", { volume })}
          />
        </div>
      ) : null}

      {legacyCameraSelected ? (
        <div className="timeline-inspector__stack" data-testid="timeline-inspector-camera-retired">
          <p className="scene-meta">
            The Timeline Camera track has been removed. Timed Prompt is the sole camera authority —
            write shot movement and motion direction in Timed Prompt. Prior camera clips remain in
            project data for provenance and are not mounted as a creator lane.
          </p>
        </div>
      ) : null}

      {selection.kind === "batch" && selectedBatch ? (
        <div className="timeline-inspector__section" data-testid="timeline-inspector-generation-window">
          <h4>Generation details (read-only)</h4>
          <p className="scene-meta">
            Select a Timed Prompt clip for takes and generation actions. This legacy view is read-only.
          </p>
          <div><strong>{selectedBatch.label}</strong></div>
          <div className="scene-meta">
            Status: {formatBatchStatus(selectedBatch.status)} · Planned{" "}
            {Number(selectedBatch.duration.plannedDuration || 0).toFixed(2)}s
            {selectedBatch.generatorId ? ` · ${selectedBatch.generatorId}` : ""}
          </div>
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
          <p className="scene-meta" data-testid="timeline-inspector-retake-status">
            Use Re-Take on the Preview Monitor to change a video range. Shared Library assets stay in the project.
          </p>
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

