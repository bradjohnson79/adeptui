import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type {
  VoicePerformanceCapabilities,
  VoicePerformanceComparison,
  VoicePerformanceDirectionMode,
  VoicePerformanceEmotionPreset,
  VoicePerformanceEmotionSource,
  VoicePerformanceEmotionVector,
  VoicePerformanceEmotionVectorKey,
  VoicePerformanceLipsyncResult,
  VoicePerformancePlan,
  VoicePerformanceRecord,
  VoicePerformanceRuntimeStatus,
  VoicePerformanceTake,
  VoicePerformanceTimelinePlacement,
} from "../../contracts/voicePerformanceM410";
import { Button } from "../ui";
import { HelpTip, PanelHeading } from "../HelpTip";
import {
  VOICE_PERFORMANCE_EMOTION_PRESETS,
  VOICE_PERFORMANCE_EMOTION_PRESET_LABELS,
} from "./emotionPresets";

const DEFAULT_DIALOGUE = `Light circuitry, not tattoos, doofus.
I developed them with my sister in the Abode.`;

const TAKE_OPTIONS = [1, 2, 3, 4] as const;
const ADVANCED_EMOTION_KEYS: VoicePerformanceEmotionVectorKey[] = [
  "joy",
  "sadness",
  "anger",
  "fear",
  "surprise",
  "disgust",
  "contempt",
];

const EMOTION_SOURCE_OPTIONS: { id: VoicePerformanceEmotionSource; label: string; hint: string }[] = [
  {
    id: "codirector",
    label: "Co-Director Performance",
    hint: "Let Co-Director read the line and recommend the emotional shape.",
  },
  {
    id: "preset",
    label: "Emotion Preset",
    hint: "Start from a curated emotional performance recipe.",
  },
  {
    id: "emotional_reference_audio",
    label: "Emotional Reference Audio",
    hint: "Use a short reference clip to steer tone and breath.",
  },
  {
    id: "voice_reference_emotion",
    label: "Voice Reference Emotion",
    hint: "Stay close to the approved voice identity's natural emotional range.",
  },
  {
    id: "advanced_mix",
    label: "Advanced Emotion Mix",
    hint: "Blend raw IndexTTS2 emotion vectors under Advanced.",
  },
];

type VoiceIdentitySummary = {
  id: string;
  name: string;
  version?: string | number | null;
};

type Props = {
  projectId: string;
  characterId: string;
  characterName: string;
  activeView: "performance" | "sceneDialogue" | "takes";
  approvedVoiceIdentity?: VoiceIdentitySummary | null;
  initialDialogue?: string;
  onMsg: (m: string) => void;
  onOpenVoiceIdentity: () => void;
};

function emptyPlan(seed?: Partial<VoicePerformancePlan>): VoicePerformancePlan {
  return {
    source: "manual",
    summary: "",
    emotionLabel: "",
    intensity: "medium",
    delivery: "",
    pacing: "",
    breath: "",
    emphasis: "",
    subtext: "",
    performanceReference: "",
    notes: "",
    editable: true,
    presetId: "",
    emotionVector: {},
    ...seed,
  };
}

function normalizeEmotionSource(value: string | null | undefined): VoicePerformanceEmotionSource {
  if (value === "preset") return "preset";
  if (value === "emotional_reference_audio") return "emotional_reference_audio";
  if (value === "voice_reference_emotion") return "voice_reference_emotion";
  if (value === "advanced_mix") return "advanced_mix";
  return "codirector";
}

function normalizePlan(plan: Record<string, unknown> | null | undefined, mode: VoicePerformanceDirectionMode) {
  const input = (plan || {}) as VoicePerformancePlan;
  return emptyPlan({
    ...input,
    source: mode,
    summary: typeof input.summary === "string" ? input.summary : "",
    emotionLabel: typeof input.emotionLabel === "string" ? input.emotionLabel : "",
    intensity: typeof input.intensity === "string" && input.intensity ? input.intensity : "medium",
    delivery: typeof input.delivery === "string" ? input.delivery : "",
    pacing: typeof input.pacing === "string" ? input.pacing : "",
    breath: typeof input.breath === "string" ? input.breath : "",
    emphasis: typeof input.emphasis === "string" ? input.emphasis : "",
    subtext: typeof input.subtext === "string" ? input.subtext : "",
    performanceReference: typeof input.performanceReference === "string" ? input.performanceReference : "",
    notes: typeof input.notes === "string" ? input.notes : "",
    presetId: typeof input.presetId === "string" ? input.presetId : "",
    emotionVector:
      input.emotionVector && typeof input.emotionVector === "object"
        ? (input.emotionVector as VoicePerformanceEmotionVector)
        : {},
  });
}

function topEmotionLabel(vector: VoicePerformanceEmotionVector) {
  const top = Object.entries(vector || {}).sort((a, b) => Number(b[1]) - Number(a[1]))[0];
  return top ? top[0].replace(/^\w/, (char) => char.toUpperCase()) : "Nuanced";
}

function formatTakeStatus(status: VoicePerformanceTake["status"]) {
  if (status === "completed") return "Ready";
  if (status === "approved") return "Approved";
  return status.replace(/^\w/, (char) => char.toUpperCase());
}

function takeSort(a: VoicePerformanceTake, b: VoicePerformanceTake) {
  return a.takeNumber - b.takeNumber || a.createdAt.localeCompare(b.createdAt);
}

export function VoicePerformanceStudio({
  projectId,
  characterId,
  characterName,
  activeView,
  approvedVoiceIdentity,
  initialDialogue,
  onMsg,
  onOpenVoiceIdentity,
}: Props) {
  const [runtimeStatus, setRuntimeStatus] = useState<VoicePerformanceRuntimeStatus | null>(null);
  const [capabilities, setCapabilities] = useState<VoicePerformanceCapabilities | null>(null);
  const [presets, setPresets] = useState<VoicePerformanceEmotionPreset[]>(VOICE_PERFORMANCE_EMOTION_PRESETS);
  const [record, setRecord] = useState<VoicePerformanceRecord | null>(null);
  const [dialogueText, setDialogueText] = useState(initialDialogue?.trim() || DEFAULT_DIALOGUE);
  const [directionMode, setDirectionMode] = useState<VoicePerformanceDirectionMode>("codirector");
  const [codirectorPlan, setCodirectorPlan] = useState<VoicePerformancePlan>(
    emptyPlan({ source: "codirector", summary: "Co-Director will recommend a performance plan for this line." }),
  );
  const [manualPlan, setManualPlan] = useState<VoicePerformancePlan>(emptyPlan({ source: "manual" }));
  const [emotionSource, setEmotionSource] = useState<VoicePerformanceEmotionSource>("codirector");
  const [emotionVector, setEmotionVector] = useState<VoicePerformanceEmotionVector>({});
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [emotionalReferenceAssetId, setEmotionalReferenceAssetId] = useState("");
  const [emotionalReferenceName, setEmotionalReferenceName] = useState("");
  const [emotionalReferenceStrength, setEmotionalReferenceStrength] = useState(0.65);
  const [takeCount, setTakeCount] = useState<(typeof TAKE_OPTIONS)[number]>(4);
  const [takes, setTakes] = useState<VoicePerformanceTake[]>([]);
  const [approvedTakeId, setApprovedTakeId] = useState("");
  const [comparison, setComparison] = useState<VoicePerformanceComparison | null>(null);
  const [timelineResult, setTimelineResult] = useState<VoicePerformanceTimelinePlacement | null>(null);
  const [lipsyncResult, setLipsyncResult] = useState<VoicePerformanceLipsyncResult | null>(null);
  const [busyAction, setBusyAction] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [timelineNeedsConfirm, setTimelineNeedsConfirm] = useState(false);
  const [lipsyncNeedsConfirm, setLipsyncNeedsConfirm] = useState(false);

  const dialogueRef = useRef<HTMLElement | null>(null);
  const performanceRef = useRef<HTMLElement | null>(null);
  const takesRef = useRef<HTMLElement | null>(null);

  const hasApprovedVoiceIdentity = Boolean(approvedVoiceIdentity?.id);
  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === selectedPresetId) || null,
    [presets, selectedPresetId],
  );
  const activePlan = directionMode === "manual" ? manualPlan : codirectorPlan;
  const visibleTakes = useMemo(() => [...takes].sort(takeSort).slice(-4), [takes]);
  const activeRuntimeMessage = runtimeStatus?.message || capabilities?.message || "";
  const canGenerateTakes = hasApprovedVoiceIdentity && Boolean(capabilities?.ready);

  const recordNeedsReplacement = useCallback(
    (existing: VoicePerformanceRecord | null) =>
      !existing
      || existing.voiceIdentityId !== approvedVoiceIdentity?.id
      || existing.characterId !== characterId
      || existing.dialogueText !== dialogueText,
    [approvedVoiceIdentity?.id, characterId, dialogueText],
  );

  const serializePlan = useCallback(
    (plan: VoicePerformancePlan, mode: VoicePerformanceDirectionMode): VoicePerformancePlan => ({
      ...plan,
      source: mode,
      editable: true,
      emotionLabel:
        plan.emotionLabel
        || selectedPreset?.name
        || topEmotionLabel(emotionVector),
      presetId: selectedPresetId || plan.presetId || "",
      emotionVector,
    }),
    [emotionVector, selectedPreset?.name, selectedPresetId],
  );

  const syncRecordFromApi = useCallback(
    (nextRecord: VoicePerformanceRecord) => {
      setRecord(nextRecord);
      setDialogueText(nextRecord.dialogueText || initialDialogue?.trim() || DEFAULT_DIALOGUE);
      setDirectionMode(nextRecord.directionMode || "codirector");
      const nextManual = normalizePlan(nextRecord.manualPlan, "manual");
      const nextCodirector = normalizePlan(nextRecord.codirectorPlan || nextRecord.performancePlan, "codirector");
      setManualPlan(nextManual);
      setCodirectorPlan(nextCodirector);
      setEmotionSource(normalizeEmotionSource(nextRecord.emotionSource));
      setEmotionVector(nextRecord.emotionVector || {});
      setSelectedPresetId(
        String(nextRecord.performancePlan?.presetId || nextManual.presetId || nextCodirector.presetId || ""),
      );
      setEmotionalReferenceAssetId(String(nextRecord.emotionalReferenceAssetId || ""));
      setEmotionalReferenceStrength(nextRecord.emotionalReferenceStrength ?? 0.65);
      setTakes([...(nextRecord.takes || [])].sort(takeSort));
      setApprovedTakeId(String(nextRecord.approvedTakeId || ""));
      setTimelineResult(null);
      setLipsyncResult(null);
    },
    [initialDialogue],
  );

  const loadTakes = useCallback(async () => {
    if (!record?.id) return;
    const next = await api.voicePerformanceM410.listTakes(record.id);
    setTakes([...(next.takes || [])].sort(takeSort));
    setApprovedTakeId(String(next.approvedTakeId || ""));
  }, [record?.id]);

  useEffect(() => {
    const target =
      activeView === "sceneDialogue"
        ? dialogueRef.current
        : activeView === "takes"
          ? takesRef.current
          : performanceRef.current;
    target?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, [activeView]);

  useEffect(() => {
    if (!record?.id || !takes.some((take) => take.status === "queued" || take.status === "running")) return;
    const interval = window.setInterval(() => {
      void loadTakes().catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(interval);
  }, [loadTakes, record?.id, takes]);

  useEffect(() => {
    void (async () => {
      try {
        const [runtime, caps, presetResponse] = await Promise.all([
          api.voicePerformanceM410.runtimeStatus(),
          api.voicePerformanceM410.capabilities(),
          api.voicePerformanceM410.emotionPresets(),
        ]);
        setRuntimeStatus(runtime);
        setCapabilities(caps);
        setPresets(presetResponse.presets?.length ? presetResponse.presets : VOICE_PERFORMANCE_EMOTION_PRESETS);
      } catch (error: any) {
        onMsg(error?.message || "Voice Performance runtime details could not be loaded.");
      }
    })();
  }, [onMsg]);

  useEffect(() => {
    if (!hasApprovedVoiceIdentity) {
      setRecord(null);
      setTakes([]);
      setApprovedTakeId("");
      return;
    }
    void (async () => {
      try {
        const response = await api.voicePerformanceM410.listProjectRecords(projectId);
        const matching = (response.records || []).filter((item) => item.characterId === characterId);
        const preferred =
          matching.find((item) => item.voiceIdentityId === approvedVoiceIdentity?.id)
          || matching[0]
          || null;
        if (preferred) {
          syncRecordFromApi(preferred);
          return;
        }
        setRecord(null);
        setTakes([]);
        setApprovedTakeId("");
        setDirectionMode("codirector");
        setCodirectorPlan(
          emptyPlan({ source: "codirector", summary: "Co-Director will recommend a performance plan for this line." }),
        );
        setManualPlan(emptyPlan({ source: "manual" }));
      } catch (error: any) {
        onMsg(error?.message || "Voice Performance records could not be loaded.");
      }
    })();
  }, [approvedVoiceIdentity?.id, characterId, hasApprovedVoiceIdentity, onMsg, projectId, syncRecordFromApi]);

  useEffect(() => {
    if (!record && initialDialogue?.trim()) {
      setDialogueText((current) => (current.trim() ? current : initialDialogue.trim()));
    }
  }, [initialDialogue, record]);

  const updateActivePlan = useCallback(
    (patch: Partial<VoicePerformancePlan>) => {
      if (directionMode === "manual") {
        setManualPlan((current) => ({ ...current, ...patch, source: "manual" }));
        return;
      }
      setCodirectorPlan((current) => ({ ...current, ...patch, source: "codirector" }));
    },
    [directionMode],
  );

  const ensureRecord = useCallback(async () => {
    if (!approvedVoiceIdentity?.id) {
      throw new Error("Voice Identity Required");
    }
    if (record && !recordNeedsReplacement(record)) {
      return record;
    }
    const created = await api.voicePerformanceM410.createRecord({
      projectId,
      characterId,
      voiceIdentityId: approvedVoiceIdentity.id,
      voiceIdentityVersion:
        approvedVoiceIdentity.version == null ? undefined : String(approvedVoiceIdentity.version),
      dialogueText,
      directionMode,
      performancePlan: serializePlan(activePlan, directionMode),
      manualPlan: serializePlan(manualPlan, "manual"),
      codirectorPlan: serializePlan(codirectorPlan, "codirector"),
      emotionSource,
      emotionVector,
      emotionalReferenceAssetId: emotionalReferenceAssetId || undefined,
      emotionalReferenceStrength,
      consentAck: {
        source: "voice-performance-studio",
        acknowledgedAt: new Date().toISOString(),
      },
    });
    syncRecordFromApi(created);
    return created;
  }, [
    activePlan,
    approvedVoiceIdentity,
    characterId,
    codirectorPlan,
    dialogueText,
    directionMode,
    emotionalReferenceAssetId,
    emotionalReferenceStrength,
    emotionSource,
    emotionVector,
    manualPlan,
    projectId,
    record,
    recordNeedsReplacement,
    serializePlan,
    syncRecordFromApi,
  ]);

  const persistCurrentPlan = useCallback(async () => {
    const existing = record;
    if (!existing || recordNeedsReplacement(existing)) {
      return ensureRecord();
    }
    const updated = await api.voicePerformanceM410.patchPerformancePlan(existing.id, {
      performancePlan: serializePlan(activePlan, directionMode),
      mode: directionMode,
      emotionSource,
      emotionVector,
    });
    syncRecordFromApi(updated);
    return updated;
  }, [
    activePlan,
    directionMode,
    emotionSource,
    emotionVector,
    ensureRecord,
    record,
    recordNeedsReplacement,
    serializePlan,
    syncRecordFromApi,
  ]);

  const refreshCodirectorPlan = useCallback(async () => {
    setBusyAction("plan");
    try {
      const base = await ensureRecord();
      const refreshed = await api.voicePerformanceM410.generatePerformancePlan(base.id, {
        context: {
          presetId: emotionSource === "preset" ? selectedPresetId || undefined : undefined,
          parenthetical: activePlan.subtext || undefined,
          sceneProgression: activePlan.performanceReference || undefined,
        },
      });
      syncRecordFromApi(refreshed);
      onMsg("Co-Director refreshed the performance plan.");
    } catch (error: any) {
      onMsg(error?.message || "Co-Director could not refresh the plan.");
    } finally {
      setBusyAction("");
    }
  }, [activePlan.performanceReference, activePlan.subtext, emotionSource, ensureRecord, onMsg, selectedPresetId, syncRecordFromApi]);

  const switchDirectionMode = useCallback(
    async (nextMode: VoicePerformanceDirectionMode) => {
      if (nextMode === directionMode) return;
      setDirectionMode(nextMode);
      if (!record || recordNeedsReplacement(record)) return;
      setBusyAction("mode");
      try {
        const targetPlan = nextMode === "manual" ? manualPlan : codirectorPlan;
        const updated = await api.voicePerformanceM410.setDirectionMode(record.id, {
          directionMode: nextMode,
          performancePlan: serializePlan(targetPlan, nextMode),
        });
        syncRecordFromApi(updated);
      } catch (error: any) {
        onMsg(error?.message || "Direction mode could not be switched.");
      } finally {
        setBusyAction("");
      }
    },
    [
      codirectorPlan,
      directionMode,
      manualPlan,
      onMsg,
      record,
      recordNeedsReplacement,
      serializePlan,
      syncRecordFromApi,
    ],
  );

  const handlePresetChange = useCallback(
    (presetId: string) => {
      setSelectedPresetId(presetId);
      const preset = presets.find((item) => item.id === presetId);
      if (!preset) return;
      setEmotionSource("preset");
      setEmotionVector(preset.emotionVector);
      updateActivePlan({
        emotionLabel: preset.name,
        intensity: preset.intensity,
        delivery: preset.delivery,
        pacing: preset.pacing,
        breath: preset.breath,
        notes: preset.notes,
        summary: preset.summary,
        presetId: preset.id,
      });
    },
    [presets, updateActivePlan],
  );

  const uploadEmotionalReference = useCallback(
    async (file: File | null) => {
      if (!file) return;
      setBusyAction("reference");
      try {
        const uploaded = await api.uploadAsset(projectId, file, "voice_emotional_reference", "audio");
        setEmotionSource("emotional_reference_audio");
        setEmotionalReferenceAssetId(String(uploaded.id || ""));
        setEmotionalReferenceName(file.name);
        onMsg("Emotional reference audio added to the project library.");
      } catch (error: any) {
        onMsg(error?.message || "Reference audio could not be uploaded.");
      } finally {
        setBusyAction("");
      }
    },
    [onMsg, projectId],
  );

  const generateTakeLabels = useCallback(
    (count: number) => {
      const startingNumber = visibleTakes.length ? visibleTakes[visibleTakes.length - 1].takeNumber + 1 : 1;
      return Array.from({ length: count }, (_, index) => `Take ${startingNumber + index}`);
    },
    [visibleTakes],
  );

  const generateTakes = useCallback(async () => {
    if (!hasApprovedVoiceIdentity) {
      onMsg("Voice Identity Required");
      return;
    }
    if (!capabilities?.ready) {
      onMsg(capabilities?.message || "Voice Performance runtime is not ready yet.");
      return;
    }
    setBusyAction("takes");
    try {
      if (directionMode === "codirector" && (emotionSource === "codirector" || emotionSource === "preset")) {
        const base = await ensureRecord();
        const refreshed = await api.voicePerformanceM410.generatePerformancePlan(base.id, {
          context: {
            presetId: emotionSource === "preset" ? selectedPresetId || undefined : undefined,
            parenthetical: activePlan.subtext || undefined,
            sceneProgression: activePlan.performanceReference || undefined,
          },
        });
        syncRecordFromApi(refreshed);
      } else {
        await persistCurrentPlan();
      }
      const usableRecord = await ensureRecord();
      await api.voicePerformanceM410.generateTakes(usableRecord.id, {
        count: takeCount,
        labels: generateTakeLabels(takeCount),
      });
      await loadTakes();
      setComparison(null);
      onMsg(`${takeCount} take${takeCount === 1 ? "" : "s"} queued for generation.`);
    } catch (error: any) {
      onMsg(error?.message || "Takes could not be generated.");
    } finally {
      setBusyAction("");
    }
  }, [
    activePlan.performanceReference,
    activePlan.subtext,
    capabilities?.message,
    capabilities?.ready,
    directionMode,
    emotionSource,
    ensureRecord,
    generateTakeLabels,
    hasApprovedVoiceIdentity,
    loadTakes,
    onMsg,
    persistCurrentPlan,
    selectedPresetId,
    syncRecordFromApi,
    takeCount,
  ]);

  const compareTakes = useCallback(async () => {
    if (!record?.id) return;
    setBusyAction("compare");
    try {
      const next = await api.voicePerformanceM410.compare(record.id, {
        takeIds: visibleTakes.map((take) => take.id),
      });
      setComparison(next);
    } catch (error: any) {
      onMsg(error?.message || "Takes could not be compared.");
    } finally {
      setBusyAction("");
    }
  }, [onMsg, record?.id, visibleTakes]);

  const approveTake = useCallback(
    async (takeId: string) => {
      if (!record?.id) return;
      setBusyAction(`approve-${takeId}`);
      try {
        const next = await api.voicePerformanceM410.approveTake(record.id, takeId, { approvedBy: "owner" });
        setTakes([...(next.takes || [])].sort(takeSort));
        setApprovedTakeId(next.approvedTakeId || takeId);
        setRecord((current) => (current ? { ...current, approvedTakeId: next.approvedTakeId || takeId } : current));
        onMsg("Take approved for Timeline and Lip Sync.");
      } catch (error: any) {
        onMsg(error?.message || "Take could not be approved.");
      } finally {
        setBusyAction("");
      }
    },
    [onMsg, record?.id],
  );

  const sendToTimeline = useCallback(async () => {
    if (!record?.id) return;
    setBusyAction("timeline");
    try {
      const next = await api.voicePerformanceM410.sendToTimeline(record.id, {
        trackId: "dialogue-main",
        startMs: 0,
        confirmReplace: timelineNeedsConfirm,
      });
      setTimelineNeedsConfirm(false);
      setTimelineResult(next);
      setRecord((current) =>
        current ? { ...current, timelineLinkage: next.timelineLinkage || current.timelineLinkage } : current,
      );
      onMsg(next.wouldReplace ? "Timeline dialogue replaced with the approved take." : "Approved take sent to Timeline.");
    } catch (error: any) {
      const code = String(error?.detail?.code || error?.detail?.error_code || error?.code || "");
      if (code.toLowerCase().includes("timeline_replace_confirm_required")) {
        setTimelineNeedsConfirm(true);
        onMsg("Existing dialogue is already on the Timeline. Press Send to Timeline again to replace it.");
      } else {
        onMsg(error?.message || "Timeline placement failed.");
      }
    } finally {
      setBusyAction("");
    }
  }, [onMsg, record?.id, timelineNeedsConfirm]);

  const prepareLipsync = useCallback(async () => {
    if (!record?.id) return;
    setBusyAction("lipsync");
    try {
      const next = await api.voicePerformanceM410.prepareLipsync(record.id, {
        confirm: lipsyncNeedsConfirm,
        setSceneAudioAsset: true,
      });
      setLipsyncNeedsConfirm(false);
      setLipsyncResult(next);
      setRecord((current) =>
        current ? { ...current, lipsyncLinkage: next.lipsyncLinkage || current.lipsyncLinkage } : current,
      );
      onMsg("Approved take prepared for Lip Sync.");
    } catch (error: any) {
      const code = String(error?.detail?.code || error?.detail?.error_code || error?.code || "");
      if (code.toLowerCase().includes("confirm_required")) {
        setLipsyncNeedsConfirm(true);
        onMsg("This will replace an existing scene audio link. Press Prepare for Lip Sync again to continue.");
      } else {
        onMsg(error?.message || "Lip Sync preparation failed.");
      }
    } finally {
      setBusyAction("");
    }
  }, [lipsyncNeedsConfirm, onMsg, record?.id]);

  return (
    <section className="panel voice-studio voice-performance-studio" data-testid="voice-performance-studio">
      <header className="voice-performance-studio__header">
        <PanelHeading
          title={`Voice Performance Studio — ${characterName}`}
          tip="Direct dialogue like a professional performance session: shape emotion, delivery, pacing, breath, emphasis, and subtext before generating takes."
          as="h3"
        />
        <div className="voice-performance-studio__meta">
          <p className="muted">
            {approvedVoiceIdentity
              ? `Approved voice identity: ${approvedVoiceIdentity.name}`
              : "Voice Identity Required"}
          </p>
          {activeRuntimeMessage ? <p className="muted">{activeRuntimeMessage}</p> : null}
        </div>
      </header>

      {!hasApprovedVoiceIdentity ? (
        <section
          className="voice-performance-studio__identity-gate"
          data-testid="vp-voice-identity-required"
        >
          <PanelHeading
            title="Voice Identity Required"
            tip="Performance takes only use approved voice identities. The studio will never create one silently for you."
            as="h4"
          />
          <p className="muted">
            Approve a Voice Identity first, then come back here to direct dialogue performance.
          </p>
          <Button
            type="button"
            variant="primary"
            className="voice-studio-primary-cta"
            data-testid="vp-open-voice-identity"
            onClick={onOpenVoiceIdentity}
          >
            Open Voice Identity
          </Button>
        </section>
      ) : (
        <>
          <section
            ref={performanceRef}
            className={`voice-performance-studio__workspace${
              activeView === "performance" ? " is-active-anchor" : ""
            }`}
          >
            <div className="voice-performance-studio__main">
              <section
                ref={dialogueRef}
                className={`voice-performance-studio__dialogue${
                  activeView === "sceneDialogue" ? " is-active-anchor" : ""
                }`}
              >
                <PanelHeading
                  title="Scene Dialogue"
                  tip="Keep the spoken line dominant in the workspace. Performance decisions should support this text, not bury it."
                  as="h4"
                />
                <label className="voice-performance-studio__field">
                  <span>
                    Dialogue
                    <HelpTip
                      label="Dialogue"
                      content="Write the exact line to direct. Changing the line creates a fresh performance record so earlier takes stay intact."
                    />
                  </span>
                  <textarea
                    className="voice-studio-dialogue"
                    rows={7}
                    data-testid="vp-dialogue"
                    value={dialogueText}
                    onChange={(event) => setDialogueText(event.target.value)}
                  />
                </label>
              </section>

              <section className="voice-performance-studio__performance-panel" data-testid="vp-performance-plan">
                <PanelHeading
                  title="Performance Plan"
                  tip="Shape how the actor should play the line. Co-Director Recommended gives you a creative starting point; Manual Direction lets you steer every note yourself."
                  as="h4"
                />

                <div className="voice-performance-studio__direction">
                  <span className="voice-performance-studio__label">Direction Mode</span>
                  <div className="workspace-tabs" role="tablist">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={directionMode === "codirector"}
                      className={directionMode === "codirector" ? "primary" : ""}
                      data-testid="vp-direction-codirector"
                      onClick={() => void switchDirectionMode("codirector")}
                    >
                      Co-Director Recommended
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={directionMode === "manual"}
                      className={directionMode === "manual" ? "primary" : ""}
                      data-testid="vp-direction-manual"
                      onClick={() => void switchDirectionMode("manual")}
                    >
                      Manual Direction
                    </button>
                  </div>
                </div>

                <label className="voice-performance-studio__field">
                  <span>
                    Emotion Source
                    <HelpTip
                      label="Emotion Source"
                      content="Choose where the emotional starting point comes from. Raw vector blending stays tucked into Advanced."
                    />
                  </span>
                  <select
                    data-testid="vp-emotion-source"
                    value={emotionSource}
                    onChange={(event) => setEmotionSource(event.target.value as VoicePerformanceEmotionSource)}
                  >
                    {EMOTION_SOURCE_OPTIONS.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <span className="muted">
                    {EMOTION_SOURCE_OPTIONS.find((option) => option.id === emotionSource)?.hint}
                  </span>
                </label>

                <div className="voice-performance-studio__grid">
                  <label className="voice-performance-studio__field">
                    <span>
                      Emotion
                      <HelpTip
                        label="Emotion"
                        content="Describe the emotional beat the performer should chase. If you choose an Emotion Preset, this can inherit the preset label."
                      />
                    </span>
                    <input
                      data-testid="vp-emotion"
                      value={activePlan.emotionLabel || ""}
                      onChange={(event) => updateActivePlan({ emotionLabel: event.target.value })}
                      placeholder="Warm reassurance, contained anger, tender vulnerability..."
                    />
                  </label>

                  <label className="voice-performance-studio__field">
                    <span>
                      Intensity
                      <HelpTip
                        label="Intensity"
                        content="How strongly the line should land emotionally, not how loud it should be."
                      />
                    </span>
                    <input
                      data-testid="vp-intensity"
                      value={activePlan.intensity || ""}
                      onChange={(event) => updateActivePlan({ intensity: event.target.value })}
                      placeholder="low, medium, high"
                    />
                  </label>

                  <label className="voice-performance-studio__field">
                    <span>
                      Delivery
                      <HelpTip
                        label="Delivery"
                        content="Describe the performance texture: clipped, intimate, open-hearted, dry, unamused, and so on."
                      />
                    </span>
                    <input
                      data-testid="vp-delivery"
                      value={activePlan.delivery || ""}
                      onChange={(event) => updateActivePlan({ delivery: event.target.value })}
                      placeholder="tight, precise, clipped"
                    />
                  </label>

                  <label className="voice-performance-studio__field">
                    <span>
                      Pacing
                      <HelpTip
                        label="Pacing"
                        content="Guide the rhythm of the line: patient, brisk, halting, accelerating, or relaxed."
                      />
                    </span>
                    <input
                      data-testid="vp-pacing"
                      value={activePlan.pacing || ""}
                      onChange={(event) => updateActivePlan({ pacing: event.target.value })}
                      placeholder="steady and patient"
                    />
                  </label>

                  <label className="voice-performance-studio__field">
                    <span>
                      Breath
                      <HelpTip
                        label="Breath"
                        content="Call out breath behavior when it matters emotionally: held, open, compressed, shaky, or clean."
                      />
                    </span>
                    <input
                      data-testid="vp-breath"
                      value={activePlan.breath || ""}
                      onChange={(event) => updateActivePlan({ breath: event.target.value })}
                      placeholder="soft catches between phrases"
                    />
                  </label>

                  <label className="voice-performance-studio__field">
                    <span>
                      Emphasis
                      <HelpTip
                        label="Emphasis"
                        content="Name which words or ideas deserve the performer’s strongest weight."
                      />
                    </span>
                    <input
                      data-testid="vp-emphasis"
                      value={activePlan.emphasis || ""}
                      onChange={(event) => updateActivePlan({ emphasis: event.target.value })}
                      placeholder="Land 'sister' with pride."
                    />
                  </label>
                </div>

                <label className="voice-performance-studio__field">
                  <span>
                    Subtext
                    <HelpTip
                      label="Subtext"
                      content="What the character means or hides underneath the spoken words."
                    />
                  </span>
                  <textarea
                    rows={3}
                    data-testid="vp-subtext"
                    value={activePlan.subtext || ""}
                    onChange={(event) => updateActivePlan({ subtext: event.target.value })}
                    placeholder="She wants to sound casual, but the line is secretly protective of her sister."
                  />
                </label>

                <label className="voice-performance-studio__field">
                  <span>
                    Performance Reference
                    <HelpTip
                      label="Performance Reference"
                      content="Reference the acting energy you want: dry teasing, exhausted resolve, intimate honesty, measured authority, and so on."
                    />
                  </span>
                  <textarea
                    rows={2}
                    value={activePlan.performanceReference || ""}
                    onChange={(event) => updateActivePlan({ performanceReference: event.target.value })}
                    placeholder="Dry playful sarcasm first, then quiet pride on the second line."
                  />
                </label>

                <label className="voice-performance-studio__field">
                  <span>
                    Co-Director Notes
                    <HelpTip
                      label="Co-Director Notes"
                      content="Keep a short plan summary or creative note for what should happen emotionally inside the line."
                    />
                  </span>
                  <textarea
                    rows={3}
                    value={activePlan.notes || activePlan.summary || ""}
                    onChange={(event) =>
                      updateActivePlan({
                        notes: event.target.value,
                        summary: event.target.value,
                      })
                    }
                    placeholder="Play the first sentence with dry wit, then let the second sentence soften into earned pride."
                  />
                </label>

                {emotionSource === "preset" ? (
                  <label className="voice-performance-studio__field">
                    <span>
                      Emotion Preset
                      <HelpTip
                        label="Emotion Preset"
                        content="Preset labels match the approved backend presets so what you choose here maps cleanly to the server."
                      />
                    </span>
                    <select value={selectedPresetId} onChange={(event) => handlePresetChange(event.target.value)}>
                      <option value="">Choose a preset</option>
                      {VOICE_PERFORMANCE_EMOTION_PRESET_LABELS.map((preset) => (
                        <option key={preset.id} value={preset.id}>
                          {preset.label}
                        </option>
                      ))}
                    </select>
                    {selectedPreset ? <span className="muted">{selectedPreset.summary}</span> : null}
                  </label>
                ) : null}

                {emotionSource === "emotional_reference_audio" ? (
                  <div className="voice-performance-studio__field">
                    <span>
                      Emotional Reference Audio
                      <HelpTip
                        label="Emotional Reference Audio"
                        content="Upload a short clip that demonstrates emotional energy, pacing, or breath. This guides emotion only, not identity creation."
                      />
                    </span>
                    <input
                      type="file"
                      accept="audio/*"
                      data-testid="vp-emotion-ref-upload"
                      onChange={(event) => void uploadEmotionalReference(event.target.files?.[0] || null)}
                    />
                    {emotionalReferenceName ? <span className="muted">{emotionalReferenceName}</span> : null}
                    <label className="voice-performance-studio__field">
                      <span>Reference Strength</span>
                      <input
                        type="range"
                        min={0}
                        max={1}
                        step={0.05}
                        value={emotionalReferenceStrength}
                        onChange={(event) => setEmotionalReferenceStrength(Number(event.target.value))}
                      />
                    </label>
                  </div>
                ) : null}

                {emotionSource === "voice_reference_emotion" ? (
                  <p className="muted">
                    This will keep emotional interpretation close to the approved voice identity while still honoring your manual direction.
                  </p>
                ) : null}

                <div className="voice-studio-actions">
                  {directionMode === "codirector" ? (
                    <Button
                      type="button"
                      loading={busyAction === "plan"}
                      onClick={() => void refreshCodirectorPlan()}
                    >
                      Refresh Co-Director Recommendation
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    loading={busyAction === "plan-save"}
                    onClick={() => {
                      setBusyAction("plan-save");
                      void persistCurrentPlan()
                        .then(() => onMsg("Performance plan saved."))
                        .catch((error: any) => onMsg(error?.message || "Performance plan could not be saved."))
                        .finally(() => setBusyAction(""));
                    }}
                  >
                    Save Performance Plan
                  </Button>
                </div>

                <details
                  className="voice-studio-advanced"
                  open={advancedOpen}
                  onToggle={(event) => setAdvancedOpen((event.target as HTMLDetailsElement).open)}
                >
                  <summary data-testid="vp-advanced-toggle">
                    Advanced
                    <HelpTip
                      label="Advanced"
                      content="Raw IndexTTS2 emotion vectors stay here on purpose so the main workspace stays artist-facing."
                    />
                  </summary>
                  <div className="voice-performance-studio__advanced">
                    <div className="voice-performance-studio__advanced-grid">
                      {ADVANCED_EMOTION_KEYS.map((emotion) => (
                        <label key={emotion} className="voice-performance-studio__field">
                          <span>{emotion.replace(/^\w/, (char) => char.toUpperCase())}</span>
                          <input
                            type="range"
                            min={0}
                            max={1}
                            step={0.05}
                            value={emotionVector[emotion] ?? 0}
                            onChange={(event) => {
                              setEmotionSource("advanced_mix");
                              setEmotionVector((current) => ({
                                ...current,
                                [emotion]: Number(event.target.value),
                              }));
                            }}
                          />
                        </label>
                      ))}
                    </div>
                    <pre className="voice-studio-json">
                      {JSON.stringify(
                        {
                          providerId: capabilities?.providerId || runtimeStatus?.providerId || "index-tts2-local",
                          ready: Boolean(capabilities?.ready),
                          emotionSource,
                          emotionVector,
                          emotionalReferenceAssetId: emotionalReferenceAssetId || null,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </div>
                </details>
              </section>
            </div>

            <aside
              ref={takesRef}
              className={`voice-performance-studio__takes${
                activeView === "takes" ? " is-active-anchor" : ""
              }`}
            >
              <PanelHeading
                title="Takes"
                tip="Generate up to four takes, compare them side by side, approve one, then send it to Timeline or prepare it for Lip Sync."
                as="h4"
              />

              <div className="voice-performance-studio__take-count">
                <span className="voice-performance-studio__label">Generate</span>
                <div className="voice-studio-chip-row">
                  {TAKE_OPTIONS.map((count) => (
                    <button
                      key={count}
                      type="button"
                      className={`voice-studio-chip${takeCount === count ? " selected" : ""}`}
                      onClick={() => setTakeCount(count)}
                    >
                      {count}
                    </button>
                  ))}
                </div>
              </div>

              <div className="voice-studio-actions">
                <Button
                  type="button"
                  variant="primary"
                  className="voice-studio-primary-cta"
                  data-testid="vp-generate-takes"
                  loading={busyAction === "takes"}
                  disabled={!canGenerateTakes}
                  onClick={() => void generateTakes()}
                >
                  Generate Takes
                </Button>
                <Button
                  type="button"
                  data-testid="vp-compare"
                  disabled={!visibleTakes.length}
                  loading={busyAction === "compare"}
                  onClick={() => void compareTakes()}
                >
                  Compare
                </Button>
              </div>

              {!capabilities?.ready ? (
                <p className="muted">
                  Live generation is unavailable until the local runtime reports ready. This UI does not pretend otherwise.
                </p>
              ) : null}

              <div className="voice-performance-studio__take-list">
                {visibleTakes.map((take) => (
                  <article key={take.id} className="voice-studio-candidate-card" data-testid="vp-take-card">
                    <div className="voice-performance-studio__take-header">
                      <strong>{take.label}</strong>
                      <span className="muted">
                        {formatTakeStatus(take.status)}
                        {take.durationMs ? ` · ${Math.round(take.durationMs / 10) / 100}s` : ""}
                      </span>
                    </div>
                    {take.audioAssetId ? <audio controls src={api.assetUrl(take.audioAssetId)} /> : null}
                    {take.errorMessage ? <p className="muted">{take.errorMessage}</p> : null}
                    <div className="voice-studio-actions">
                      <Button
                        type="button"
                        data-testid="vp-approve-take"
                        disabled={take.status !== "completed" && take.status !== "approved"}
                        loading={busyAction === `approve-${take.id}`}
                        onClick={() => void approveTake(take.id)}
                      >
                        {approvedTakeId === take.id ? "Approved Take" : "Approve Take"}
                      </Button>
                    </div>
                  </article>
                ))}
              </div>

              {comparison ? (
                <section className="voice-studio-compare">
                  <strong>Comparison</strong>
                  <p className="muted">{comparison.comparison.dialogueText}</p>
                  <div className="voice-studio-compare-slots">
                    {comparison.comparison.takes.map((take) => (
                      <div key={take.id}>
                        <strong>{take.label}</strong>
                        <p className="muted">
                          {formatTakeStatus(take.status)}
                          {take.durationMs ? ` · ${Math.round(take.durationMs / 10) / 100}s` : ""}
                          {take.isApproved ? " · approved" : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}

              <div className="voice-studio-actions">
                <Button
                  type="button"
                  data-testid="vp-send-timeline"
                  disabled={!approvedTakeId}
                  loading={busyAction === "timeline"}
                  onClick={() => void sendToTimeline()}
                >
                  {timelineNeedsConfirm ? "Replace Existing Dialogue on Timeline" : "Send to Timeline"}
                </Button>
                <Button
                  type="button"
                  data-testid="vp-prepare-lipsync"
                  disabled={!approvedTakeId}
                  loading={busyAction === "lipsync"}
                  onClick={() => void prepareLipsync()}
                >
                  {lipsyncNeedsConfirm ? "Confirm Lip Sync Replacement" : "Prepare for Lip Sync"}
                </Button>
              </div>

              {timelineResult ? (
                <p className="muted">
                  Timeline ready on track <code>{timelineResult.trackId}</code>.
                </p>
              ) : null}
              {lipsyncResult ? (
                <p className="muted">
                  Lip Sync prepared for scene audio asset <code>{lipsyncResult.lipsyncLinkage.audioAssetId || "—"}</code>.
                </p>
              ) : null}
            </aside>
          </section>
        </>
      )}
    </section>
  );
}
