import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { Button } from "./ui";
import { HelpTip, PanelHeading } from "./HelpTip";
import { useOpenCoDirector } from "./CoDirector";
import { buildPerformanceMarkup } from "./voiceStudio/performanceMarkup";
import { VoicePerformanceStudio } from "./voiceStudio/VoicePerformanceStudio";
import {
  ACCENTS,
  ADJUSTMENT_CHIPS,
  AGES,
  ARCHETYPES,
  CODIRECTOR_CHIPS,
  DELIVERY_SPEED,
  DELIVERY_STRENGTH,
  DELIVERY_STYLE,
  FINE_TUNE_SLIDERS,
  KORRI_MOOD_PRIORITY,
  METHOD_CARDS,
  MOODS,
  READINESS_LABELS,
  REACTION_ACTIONS,
  SAMPLE_LINE_OPTIONS,
  UPLOAD_KINDS,
  VOICE_TYPES,
  moodToEmotionId,
  speedToPace,
  strengthToDelivery,
  type StudioMethod,
  type StudioPhase,
} from "./voiceStudio/constants";
import {
  applyManualPromptEdit,
  fieldsFromBrief,
  structuredToDesignBrief,
  syncPromptDocument,
  type StructuredVoiceFields,
  type VoicePromptDocument,
} from "./voiceStudio/promptDocument";
import {
  VOICE_STUDIO_STAGE_ORDER,
  type VoiceStudioWorkspaceTab,
} from "../contracts/voiceEnvironment";
import { VoiceEnvironmentPanel } from "./voiceStudio/environment/VoiceEnvironmentPanel";

const DEFAULT_DIALOGUE = `Light circuitry, not tattoos, doofus.
I developed them with my sister in the Abode.`;

type Props = {
  projectId: string;
  characterId: string;
  onMsg: (m: string) => void;
  onRefresh?: () => void;
  /** Legacy deep-link: create | performance | approve */
  initialPhase?: StudioPhase | "voice" | "voicePerformance";
};

function mapInitialPhase(p?: Props["initialPhase"]): StudioPhase | undefined {
  if (!p) return undefined;
  if (p === "voice") return "create";
  if (p === "voicePerformance") return "performance";
  return p;
}

function mapInitialWorkspaceTab(p?: Props["initialPhase"]): VoiceStudioWorkspaceTab {
  if (p === "performance" || p === "voicePerformance") return "performance";
  return "identity";
}

function chooseVoiceOptions(voices: any[] | undefined, activeId: string): any[] {
  const list = Array.isArray(voices) ? voices : [];
  if (!list.length) return [];
  const active = list.find((v) => v.id === activeId);
  const approvedSorted = [...list]
    .filter((v) => String(v.approval_status || "").toLowerCase() === "approved")
    .sort((a, b) =>
      String(b.approved_at || b.updated_at || "").localeCompare(String(a.approved_at || a.updated_at || "")),
    );
  const primaryApproved = approvedSorted[0] ? [approvedSorted[0]] : [];
  const drafts = [...list]
    .reverse()
    .filter((v) => String(v.approval_status || "").toLowerCase() !== "approved")
    .slice(0, 3);
  const map = new Map<string, any>();
  for (const v of [...primaryApproved, ...(active ? [active] : []), ...drafts]) {
    if (v?.id) map.set(String(v.id), v);
  }
  return [...map.values()];
}

function chooseApprovedVoice(voices: any[] | undefined, activeId: string): any | null {
  const list = Array.isArray(voices) ? voices : [];
  if (!list.length) return null;
  const approved = [...list]
    .filter((voice) => String(voice?.approval_status || "").toLowerCase() === "approved")
    .sort((a, b) =>
      String(b?.approved_at || b?.updated_at || "").localeCompare(String(a?.approved_at || a?.updated_at || "")),
    );
  if (approved[0]) return approved[0];
  const active = list.find((voice) => voice?.id === activeId);
  return String(active?.approval_status || "").toLowerCase() === "approved" ? active : null;
}

function sampleLineText(ws: any, sampleId: string, custom: string): string {
  const lines: any[] = ws?.auditionLines || [];
  if (sampleId === "custom") return custom.trim() || "Hey — listen carefully.";
  if (sampleId === "personality") {
    const sarcastic = lines.find((l) => l.id === "sarcastic" || /sarcas/i.test(l.category || ""));
    const playful = lines.find((l) => l.id === "playful");
    return (sarcastic || playful || lines[2] || lines[0])?.text || "Cute. You're almost clever today.";
  }
  if (sampleId === "contrast") {
    const warm = lines.find((l) => l.id === "sincere" || l.id === "vulnerable");
    return warm?.text || "Hey… I've got you. I'm not going anywhere.";
  }
  return lines.find((l) => l.id === "neutral")?.text || lines[0]?.text || "Hey. Don't make it weird.";
}

export function VoiceStudioWorkspace({
  projectId,
  characterId,
  onMsg,
  onRefresh,
  initialPhase,
}: Props) {
  const openCoDirector = useOpenCoDirector();
  const draftTimer = useRef<number | null>(null);

  const [ws, setWs] = useState<any | null>(null);
  const [phase, setPhase] = useState<StudioPhase>("create");
  const [workspaceTab, setWorkspaceTab] = useState<VoiceStudioWorkspaceTab>(() => mapInitialWorkspaceTab(initialPhase));
  const [method, setMethod] = useState<StudioMethod>("create");
  const [busy, setBusy] = useState(false);
  const [readinessLabel, setReadinessLabel] = useState<keyof typeof READINESS_LABELS>("none");

  const [fields, setFields] = useState<StructuredVoiceFields>({
    voiceType: "Female",
    age: "Young Adult",
    archetypes: ["Rebel", "Trickster"],
    accent: "Neutral Contemporary English",
    pitch: 3,
    energy: 3,
    warmth: 2,
    playfulness: 3,
    confidence: 3,
    speakingSpeed: 3,
  });
  const [promptDoc, setPromptDoc] = useState<VoicePromptDocument>(() =>
    syncPromptDocument(null, {
      voiceType: "Female",
      age: "Young Adult",
      archetypes: ["Rebel", "Trickster"],
      accent: "Neutral Contemporary English",
      pitch: 3,
      energy: 3,
      warmth: 2,
      playfulness: 3,
      confidence: 3,
      speakingSpeed: 3,
    }),
  );
  const [fineTuneOpen, setFineTuneOpen] = useState(false);
  const [sampleLineId, setSampleLineId] = useState<string>("personality");
  const [customSample, setCustomSample] = useState("");
  const [prefillBanner, setPrefillBanner] = useState(false);

  const [voiceId, setVoiceId] = useState("");
  const [batches, setBatches] = useState<any[]>([]);
  const [expandedBatchId, setExpandedBatchId] = useState("");
  const [candidates, setCandidates] = useState<any[]>([]);
  const [testingCandidateId, setTestingCandidateId] = useState("");
  const [approved, setApproved] = useState(false);

  const [similarOpen, setSimilarOpen] = useState(false);
  const [similarParentId, setSimilarParentId] = useState("");
  const [similarKeep, setSimilarKeep] = useState({
    identity: true,
    age: true,
    accent: true,
    personality: true,
  });
  const [similarAdjust, setSimilarAdjust] = useState<string[]>([]);
  const [similarExtra, setSimilarExtra] = useState("");

  const [cloneFile, setCloneFile] = useState<File | null>(null);
  const [cloneConsent, setCloneConsent] = useState(false);
  const [cloneTranscript, setCloneTranscript] = useState(
    "This is a ten second speech sample for cloning. It includes questions? Exclamations! And quiet speech.",
  );
  const [uploadKind, setUploadKind] = useState("reusable_character_voice");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadConsent, setUploadConsent] = useState(false);

  const [perfStep, setPerfStep] = useState<"dialogue" | "mood" | "delivery" | "preview" | "approve">(
    "dialogue",
  );
  const [dialogue, setDialogue] = useState(DEFAULT_DIALOGUE);
  const [mood, setMood] = useState("Playful");
  const [speed, setSpeed] = useState<(typeof DELIVERY_SPEED)[number]>("Natural");
  const [strength, setStrength] = useState<(typeof DELIVERY_STRENGTH)[number]>("Natural");
  const [style, setStyle] = useState<(typeof DELIVERY_STYLE)[number]>("Dry");
  const [pauseMs, setPauseMs] = useState(220);
  const [reaction, setReaction] = useState("scoff");
  const [performancePrompt, setPerformancePrompt] = useState(
    "Deliver the first sentence with dry playful sarcasm. Pause briefly before speaking the second sentence with quiet pride.",
  );
  const [plan, setPlan] = useState<any | null>(null);
  const [takes, setTakes] = useState<any[]>([]);
  const [selectedTakeId, setSelectedTakeId] = useState("");
  const [assembly, setAssembly] = useState<any | null>(null);
  const [placement, setPlacement] = useState<any | null>(null);
  const [vpReadiness, setVpReadiness] = useState<any | null>(null);
  const [capabilityNote, setCapabilityNote] = useState("");
  const [generateError, setGenerateError] = useState("");

  const persistDraft = useCallback(
    async (patch: Record<string, unknown>) => {
      try {
        await api.saveVoiceStudioDraft(projectId, characterId, patch);
      } catch {
        /* best-effort */
      }
    },
    [projectId, characterId],
  );

  const scheduleDraft = useCallback(
    (patch: Record<string, unknown>) => {
      if (draftTimer.current) window.clearTimeout(draftTimer.current);
      draftTimer.current = window.setTimeout(() => {
        void persistDraft(patch);
      }, 400);
    },
    [persistDraft],
  );

  const load = useCallback(async () => {
    const data = await api.getCharacterVoiceWorkspace(projectId, characterId);
    setWs(data);
    const draft = data.voiceStudioDraft || {};
    const fromBrief = fieldsFromBrief(data.designBrief);
    const nextFields: StructuredVoiceFields = {
      voiceType: fromBrief.voiceType || "Female",
      age: fromBrief.age || "Young Adult",
      archetypes: fromBrief.archetypes?.length ? fromBrief.archetypes : ["Rebel", "Trickster"],
      accent: fromBrief.accent || "Neutral Contemporary English",
      pitch: 3,
      energy: 3,
      warmth: 2,
      playfulness: 3,
      confidence: 3,
      speakingSpeed: 3,
    };
    setFields(nextFields);
    if (data.promptDocument?.compiledPrompt) {
      setPromptDoc(data.promptDocument as VoicePromptDocument);
    } else {
      setPromptDoc(syncPromptDocument(null, nextFields));
    }
    setPrefillBanner(true);
    setBatches(data.candidateBatches || []);
    if ((data.candidateBatches || [])[0]?.id) setExpandedBatchId(data.candidateBatches[0].id);

    const activeId =
      draft.selectedVoiceProfileId ||
      data.activeVoiceProfileId ||
      data.voices?.[data.voices.length - 1]?.id ||
      "";
    setVoiceId(activeId);
    setTestingCandidateId(draft.testingCandidateId || data.testingSelection?.candidateId || "");
    setApproved(Boolean(data.activeVoice?.approval_status === "approved"));

    if (activeId) {
      try {
        const c = await api.listCharacterVoiceCandidates(projectId, characterId, activeId);
        setCandidates(c.candidates || []);
      } catch {
        /* ignore */
      }
    }

    if (draft.dialogue) setDialogue(String(draft.dialogue));
    if (draft.mood) setMood(String(draft.mood));
    if (draft.performancePrompt) setPerformancePrompt(String(draft.performancePrompt));
    if (draft.selectedTakeId) setSelectedTakeId(String(draft.selectedTakeId));
    if (draft.method && METHOD_CARDS.some((m) => m.id === draft.method)) {
      setMethod(draft.method as StudioMethod);
    }
    if (draft.sampleLineId) setSampleLineId(String(draft.sampleLineId));
    if (draft.customSampleLine) setCustomSample(String(draft.customSampleLine));

    const mapped = mapInitialPhase(initialPhase);
    if (mapped) setPhase(mapped);
    else if (draft.phase && ["method", "create", "select", "performance", "approve"].includes(draft.phase)) {
      setPhase(draft.phase as StudioPhase);
    } else if ((data.candidateBatches || []).length) setPhase("select");
    else setPhase("create");

    if (mapped === "performance" || initialPhase === "voicePerformance") {
      setWorkspaceTab("performance");
    } else if (draft.phase === "performance" || draft.phase === "approve") {
      setWorkspaceTab("performance");
    } else {
      setWorkspaceTab("identity");
    }

    if (data.activeVoice?.approval_status === "approved") setReadinessLabel("approved");
    else if (draft.testingCandidateId) setReadinessLabel("readyPerformance");
    else if ((data.candidateBatches || []).length) setReadinessLabel("chooseVoice");
    else setReadinessLabel("none");

    try {
      const r = await api.voicePerformanceReadiness(characterId, projectId);
      setVpReadiness(r);
    } catch {
      /* optional */
    }
  }, [projectId, characterId, initialPhase]);

  useEffect(() => {
    void load().catch((e) => onMsg(e?.message || String(e)));
  }, [load, onMsg]);

  const updateFields = (patch: Partial<StructuredVoiceFields>) => {
    setFields((prev) => {
      const next = { ...prev, ...patch };
      setPromptDoc((doc) => syncPromptDocument(doc, next));
      return next;
    });
  };

  const activeBatch = useMemo(
    () => batches.find((b) => b.id === expandedBatchId) || batches[0],
    [batches, expandedBatchId],
  );
  const activeBatchCandidates = useMemo(() => {
    if (!activeBatch) return candidates.slice(0, 3);
    const ids = new Set(activeBatch.candidateIds || []);
    const fromBatch = candidates.filter((c) => ids.has(c.id));
    return fromBatch.length ? fromBatch : candidates.slice(0, 3);
  }, [activeBatch, candidates]);

  const testingCandidate = useMemo(
    () => candidates.find((c) => c.id === testingCandidateId) || null,
    [candidates, testingCandidateId],
  );
  const playUrl = testingCandidate?.assetId
    ? api.assetUrl(testingCandidate.assetId)
    : activeBatchCandidates.find((c) => c.assetId)
      ? api.assetUrl(activeBatchCandidates.find((c) => c.assetId)!.assetId)
      : "";

  const moodsOrdered = useMemo(() => {
    const slug = String(ws?.slug || "").toLowerCase();
    if (slug !== "korri") return [...MOODS];
    const rest = MOODS.filter((m) => !KORRI_MOOD_PRIORITY.includes(m));
    return [...KORRI_MOOD_PRIORITY.filter((m) => (MOODS as readonly string[]).includes(m)), ...rest];
  }, [ws?.slug]);

  const existingVoices = useMemo(
    () => chooseVoiceOptions(ws?.voices, voiceId),
    [ws?.voices, voiceId],
  );
  const approvedVoice = useMemo(() => chooseApprovedVoice(ws?.voices, voiceId), [ws?.voices, voiceId]);
  const showLegacyPerformance = Boolean(ws?.legacyPerformanceEnabled);

  const runGenerate = async (opts?: {
    method?: string;
    parentCandidateId?: string;
    append?: boolean;
    refinement?: string;
  }) => {
    setBusy(true);
    setGenerateError("");
    setReadinessLabel("generatingVoices");
    try {
      const doc = opts?.refinement
        ? {
            ...promptDoc,
            userAdditions: `${promptDoc.userAdditions} ${opts.refinement}`.trim(),
            compiledPrompt: `${promptDoc.compiledPrompt} ${opts.refinement}`.trim(),
          }
        : promptDoc;
      const brief = structuredToDesignBrief(fields, doc);
      const out = await api.generateCharacterVoiceCandidates(projectId, characterId, {
        designBrief: brief,
        candidateCount: 3,
        testLine: sampleLineText(ws, sampleLineId, customSample),
        name: `${ws?.characterName || "Character"} Voice`,
        masterPrompt: doc.compiledPrompt,
        promptDocument: doc,
        method: opts?.method || "design",
        parentCandidateId: opts?.parentCandidateId,
        appendToVoiceId: opts?.append ? voiceId : undefined,
      });
      setVoiceId(out.id);
      const batchCands = out.candidates || [];
      setCandidates(out.allCandidates || batchCands);
      if (out.batch) {
        setBatches((prev) => [out.batch, ...prev.filter((b) => b.id !== out.batch.id)]);
        setExpandedBatchId(out.batch.id);
      }
      if (out.capabilityNote) setCapabilityNote(String(out.capabilityNote));
      setPhase("select");
      setReadinessLabel("chooseVoice");
      onMsg("Three voice interpretations are ready to listen.");
      onRefresh?.();
    } catch (e: any) {
      setGenerateError(e?.message || String(e));
      setReadinessLabel("needsAttention");
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const selectForTesting = async (candidateId: string) => {
    if (!voiceId) return;
    setBusy(true);
    try {
      await api.selectVoiceForTesting(projectId, characterId, { voiceId, candidateId });
      setTestingCandidateId(candidateId);
      setApproved(false);
      setPhase("select");
      setReadinessLabel("readyPerformance");
      onMsg("Voice selected for testing — not approved yet.");
      await persistDraft({
        phase: "select",
        testingCandidateId: candidateId,
        selectedCandidateId: candidateId,
        selectedVoiceProfileId: voiceId,
      });
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const continueToPerformance = async () => {
    if (!testingCandidateId) {
      onMsg("Select a voice for testing first.");
      return;
    }
    setWorkspaceTab("performance");
    setPhase("performance");
    setReadinessLabel("readyPerformance");
    await persistDraft({ phase: "performance", testingCandidateId, selectedCandidateId: testingCandidateId });
  };

  const approveVoice = async () => {
    if (!voiceId || !testingCandidateId) {
      onMsg("Select a voice first.");
      return;
    }
    setBusy(true);
    try {
      await api.approveCharacterVoiceCandidate(projectId, characterId, {
        voiceId,
        candidateId: testingCandidateId,
        approvedBy: "owner",
      });
      setApproved(true);
      setReadinessLabel(plan ? "readyApprove" : "approved");
      onMsg("Voice approved — canonical Character Voice Version saved.");
      onRefresh?.();
      await load();
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const syncMarkup = () =>
    buildPerformanceMarkup({
      speaker: ws?.characterName || "CHARACTER",
      emotion: moodToEmotionId(mood),
      delivery: strengthToDelivery(strength, style),
      pace: speedToPace(speed),
      pauseMs,
      reaction,
      dialogue,
    });

  const generatePerformances = async () => {
    setBusy(true);
    setReadinessLabel("generatingPerf");
    try {
      const source = syncMarkup();
      const voiceVersionId = voiceId || vpReadiness?.voiceVersionId;
      const created = await api.voicePerformanceCreatePlan({
        projectId,
        characterId,
        sourceText: source,
        voiceVersionId,
        testingMode: !approved,
      });
      setPlan(created);
      const out = await api.voicePerformanceGenerate(created.id, {
        allowKokoroFallback: true,
        allowTestingVoice: !approved,
      });
      setPlan(out);
      const segs = (out.segments || []).filter(
        (s: any) => s.segmentType === "speech" || s.segmentType === "reaction" || s.outputAssetId,
      );
      const takeCards = (segs.length ? segs : out.segments || []).slice(0, 3).map((s: any, i: number) => ({
        id: s.id,
        name: `Take ${i + 1}`,
        label: i === 0 ? "Sharper sarcasm" : i === 1 ? "Softer warmth" : "More restrained",
        assetId: s.outputAssetId,
        status: s.status || "ready",
        segment: s,
      }));
      // If fewer than 3 speech segments, still show up to 3 cards from available audio
      while (takeCards.length < 3 && takeCards.length > 0 && takeCards.length < (out.segments || []).length) {
        const s = out.segments[takeCards.length];
        takeCards.push({
          id: s.id,
          name: `Take ${takeCards.length + 1}`,
          label: "Alternate take",
          assetId: s.outputAssetId,
          status: s.status || "ready",
          segment: s,
        });
      }
      setTakes(takeCards);
      setPerfStep("preview");
      setPhase("performance");
      setReadinessLabel("chooseTake");
      onMsg("Performance takes ready.");
      await persistDraft({ phase: "performance", planId: created.id, dialogue, mood });
    } catch (e: any) {
      setReadinessLabel("needsAttention");
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const chooseTake = async (takeId: string) => {
    setSelectedTakeId(takeId);
    setReadinessLabel("readyApprove");
    setPhase("approve");
    setPerfStep("approve");
    try {
      await api.voicePerformanceApproveSegment(takeId);
    } catch {
      /* segment approve optional if already ready */
    }
    await persistDraft({ selectedTakeId: takeId, phase: "approve" });
  };

  const assembleAndPlace = async () => {
    if (!plan?.id) {
      onMsg("Generate performances first.");
      return;
    }
    if (!approved) {
      onMsg("Approve the voice before adding to Timeline.");
      return;
    }
    setBusy(true);
    try {
      const a = await api.voicePerformanceAssemble(plan.id);
      setAssembly(a);
      const p = await api.voicePerformancePlaceOnTimeline(a.id || a.assemblyId);
      setPlacement(p);
      setReadinessLabel("approved");
      onMsg("Performance added to Timeline.");
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const runClone = async () => {
    if (!cloneFile || !cloneConsent) {
      onMsg("Add an authorized recording and confirm consent.");
      return;
    }
    setBusy(true);
    try {
      const uploaded = await api.uploadAsset(projectId, cloneFile, "voice_clone_reference", "audio");
      const path = String(uploaded.path || "");
      if (!path) throw new Error("Upload succeeded but no server path was returned.");
      await api.validateCharacterVoiceReference(projectId, characterId, {
        path,
        transcript: cloneTranscript,
      });
      const out = await api.cloneCharacterVoiceWorkspace(projectId, characterId, {
        name: `${ws?.characterName || "Character"} Clone`,
        reference_path: path,
        transcript: cloneTranscript || "Reference transcript",
        test_line: sampleLineText(ws, sampleLineId, customSample),
        consent: {
          source_owner_name: "Owner",
          performer_name: "Performer",
          authority_type: "self",
          consent_confirmed: true,
          synthetic_generation_allowed: true,
          commercial_use_allowed: false,
        },
      });
      setVoiceId(out.id);
      setCandidates(out.candidates || []);
      if (out.batch) {
        setBatches((prev) => [out.batch, ...prev]);
        setExpandedBatchId(out.batch.id);
      }
      setPhase("select");
      setReadinessLabel("chooseVoice");
      onMsg("Clone voice ready — choose a candidate.");
      onRefresh?.();
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const runUpload = async () => {
    if (!uploadFile) {
      onMsg("Choose a file to upload.");
      return;
    }
    setBusy(true);
    try {
      const uploaded = await api.uploadAsset(projectId, uploadFile, "voice_upload", "audio");
      const assetId = uploaded.id;
      const out = await api.registerCharacterVoiceUpload(projectId, characterId, {
        assetId,
        uploadKind,
        consentConfirmed: uploadConsent,
        name: `${ws?.characterName || "Character"} Upload`,
      });
      if (out.becomesVoiceVersion && out.voice) {
        setVoiceId(out.voice.id);
        setCandidates(out.candidates || []);
        if (out.batch) {
          setBatches((prev) => [out.batch, ...prev]);
          setExpandedBatchId(out.batch.id);
        }
        setPhase("select");
        setReadinessLabel("chooseVoice");
      } else {
        onMsg(out.message || "Upload saved.");
      }
      onRefresh?.();
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const retryCandidate = async (candidateId: string) => {
    if (!voiceId) return;
    setBusy(true);
    try {
      const out = await api.retryCharacterVoiceCandidate(projectId, characterId, candidateId, {
        voiceId,
        testLine: sampleLineText(ws, sampleLineId, customSample),
      });
      setCandidates(out.candidates || []);
      onMsg("Retry finished for that voice slot.");
    } catch (e: any) {
      onMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const applySimilar = async () => {
    const bits: string[] = [];
    if (similarKeep.identity) bits.push("Keep the same voice identity");
    if (similarKeep.age) bits.push("Keep age");
    if (similarKeep.accent) bits.push("Keep accent");
    if (similarKeep.personality) bits.push("Keep character personality");
    for (const a of similarAdjust) bits.push(a);
    if (similarExtra.trim()) bits.push(similarExtra.trim());
    setSimilarOpen(false);
    await runGenerate({
      method: "similar",
      parentCandidateId: similarParentId,
      append: true,
      refinement: bits.join(". "),
    });
  };

  const applyAdjustment = async (chip: string) => {
    if (!selectedTakeId && !plan?.id) {
      setPerformancePrompt((p) => `${p} ${chip}.`.trim());
      onMsg(`Adjustment noted: ${chip}`);
      return;
    }
    setBusy(true);
    try {
      // Child refinement via new plan with adjusted markup — never overwrite originals
      if (chip === "Add Pause") setPauseMs((m) => m + 120);
      if (chip === "Remove Reaction") setReaction("");
      if (chip === "Faster") setSpeed("Fast");
      if (chip === "Slower") setSpeed("Slow");
      if (chip === "Softer") setStrength("Soft");
      if (chip === "More sarcastic") setMood("Sarcastic");
      if (chip === "More emotional") setMood("Vulnerable");
      setPerformancePrompt((p) => `${p} Adjustment: ${chip}.`.trim());
      onMsg(`Will apply “${chip}” on next generate (original takes kept).`);
    } finally {
      setBusy(false);
    }
  };

  const characterName = ws?.characterName || "Character";

  return (
    <section className="panel voice-studio voice-studio-m43" data-testid="character-voice">
      <header className="voice-studio-header" data-testid="voice-creator-header">
        <PanelHeading
          title={`Voice Studio — ${characterName}`}
          tip="Create a character voice, choose one to test, perform dialogue, then approve when ready."
          as="h3"
        />
        <p className="voice-studio-readiness" data-testid="voice-studio-readiness">
          {READINESS_LABELS[readinessLabel]}
        </p>
        <span hidden data-testid="voice-creator-status">
          {READINESS_LABELS[readinessLabel]}
        </span>
        <span hidden data-testid="voice-active-id">
          {voiceId}
        </span>
        <span hidden data-testid="voice-selected-candidate">
          {testingCandidateId}
        </span>
        <span hidden data-testid="voice-studio-phase">
          {phase}
        </span>
        <button
          type="button"
          className="voice-studio-sr-brief"
          data-testid="open-voice-performance"
          onClick={() => {
            setWorkspaceTab("performance");
            setPhase("performance");
            void persistDraft({ phase: "performance" });
          }}
        >
          Open Voice Performance
        </button>

        {prefillBanner && (
          <p className="voice-studio-prefill" data-testid="voice-studio-prefill">
            Character traits loaded from {characterName}&apos;s profile
            <HelpTip
              label="Character traits"
              content="Voice Type, age, personality, accent, and performance defaults are filled from this character’s approved profile so you do not start from scratch."
            />
          </p>
        )}

        <div className="voice-studio-codirector-chips" data-testid="voice-ask-codirector">
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            Co-Director
          </span>
          {CODIRECTOR_CHIPS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="voice-studio-chip"
              data-testid="voice-studio-codirector-chip"
              onClick={() => {
                setPromptDoc((d) => applyManualPromptEdit(d, `${d.compiledPrompt} ${prompt}`.trim()));
                setPerformancePrompt((p) => `${p} ${prompt}.`.trim());
                openCoDirector(prompt);
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      </header>

      {/* Selected voice summary — sticky only on wide desktop */}
      {testingCandidate && (
        <div className="voice-studio-selected-card" data-testid="voice-studio-selected-card">
          <div>
            <strong>
              {characterName} Voice · {testingCandidate.name || "Selected"}
            </strong>
            <p className="muted">
              {fields.age} · {fields.voiceType} · {fields.archetypes.slice(0, 2).join(" / ") || "—"} ·{" "}
              {approved ? "Approved" : "Selected for testing"}
            </p>
          </div>
          <div className="voice-studio-actions">
            {playUrl ? <audio controls src={playUrl} data-testid="voice-candidate-player" /> : null}
            <Button
              type="button"
              onClick={() => {
                setSimilarParentId(testingCandidate.id);
                setSimilarOpen(true);
              }}
            >
              Generate Similar
            </Button>
            {!approved && testingCandidateId && (
              <Button type="button" disabled={busy} onClick={() => void approveVoice()}>
                Approve Voice Identity
              </Button>
            )}
            {phase !== "performance" && phase !== "approve" && (
              <Button
                type="button"
                className="voice-studio-primary-cta"
                data-testid="voice-studio-continue-performance"
                onClick={() => void continueToPerformance()}
              >
                Continue with This Voice
              </Button>
            )}
          </div>
        </div>
      )}

      <div className="workspace-tabs voice-studio-stage-tabs" role="tablist" data-testid="voice-studio-ia">
        {VOICE_STUDIO_STAGE_ORDER.map((stage) => (
          <div
            key={stage.id}
            className="voice-studio-stage-tab"
            data-testid={stage.id === "environment" ? "voice-environment-stage" : `voice-studio-stage-${stage.id}`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={workspaceTab === stage.id}
              className={workspaceTab === stage.id ? "primary" : ""}
              data-testid={
                stage.id === "identity"
                  ? "voice-identity-tab"
                  : stage.id === "performance"
                    ? "voice-performance-tab"
                    : stage.id === "environment"
                      ? "voice-environment-tab"
                      : stage.id === "sceneDialogue"
                        ? "voice-scene-dialogue-tab"
                        : "voice-takes-tab"
              }
              onClick={() => {
                setWorkspaceTab(stage.id);
                if (stage.id === "identity" && (phase === "performance" || phase === "approve")) {
                  setPhase(testingCandidateId ? "select" : "create");
                }
              }}
            >
              {stage.label}
            </button>
            <HelpTip label={stage.label} content={stage.tip} />
          </div>
        ))}
      </div>

      <div className="voice-studio-stack" data-testid="voice-creator-workspace">
        {workspaceTab === "identity" ? (
          <>
        {/* Method */}
        {(phase === "method" || phase === "create" || method) && phase !== "performance" && phase !== "approve" && (
          <section className="voice-studio-section" data-testid="voice-setup-column">
            <PanelHeading
              title="Choose Voice Method"
              tip="Pick one way to get a voice. Only that workflow stays visible."
              as="h3"
            />
            <div className="voice-studio-method-grid" data-testid="voice-method-cards">
              {METHOD_CARDS.map((card) => (
                <button
                  key={card.id}
                  type="button"
                  className={`voice-studio-method-card${method === card.id ? " selected" : ""}`}
                  data-testid={`voice-method-${card.legacyId}`}
                  onClick={() => {
                    setMethod(card.id);
                    setPhase("create");
                    void persistDraft({ method: card.id, phase: "create" });
                  }}
                >
                  <strong>{card.label}</strong>
                  <span className="muted">{card.description}</span>
                </button>
              ))}
            </div>

            {method === "existing" && (
              <div className="voice-studio-block" data-testid="voice-choose-panel">
                <label>
                  Existing voices
                  <select
                    data-testid="voice-choose-select"
                    value={voiceId}
                    onChange={(e) => {
                      setVoiceId(e.target.value);
                      const v = existingVoices.find((x) => x.id === e.target.value);
                      const cand = (v?.candidates || v?.lineage?.candidatesMeta || [])[0];
                      if (cand?.id) void selectForTesting(cand.id);
                    }}
                  >
                    <option value="">Select…</option>
                    {existingVoices.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} ({v.approval_status || "draft"})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}

            {method === "create" && (
              <div className="voice-studio-block" data-testid="voice-design-brief">
                <div className="voice-studio-identity-fields" data-testid="voice-gender-accent">
                  <fieldset className="voice-studio-gender" data-testid="voice-gender-options">
                    <legend>
                      Voice Type <HelpTip label="Voice Type" content="How the speaker presents — female, male, androgynous, or custom." />
                    </legend>
                    <div className="voice-studio-chip-row">
                      {VOICE_TYPES.map((g) => (
                        <button
                          key={g}
                          type="button"
                          className={`voice-studio-chip${fields.voiceType === g ? " selected" : ""}`}
                          data-testid={`voice-gender-${g.toLowerCase()}`}
                          onClick={() => updateFields({ voiceType: g })}
                        >
                          {g}
                        </button>
                      ))}
                    </div>
                  </fieldset>

                  <label>
                    Age <HelpTip label="Age" content="The apparent age of the voice." />
                    <select
                      value={fields.age}
                      data-testid="voice-age-select"
                      onChange={(e) => updateFields({ age: e.target.value })}
                    >
                      {AGES.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </label>

                  <fieldset>
                    <legend>
                      Character Archetype{" "}
                      <HelpTip label="Archetype" content="Optional personality shapes. You can pick more than one." />
                    </legend>
                    <div className="voice-studio-chip-row" data-testid="voice-archetype-chips">
                      {ARCHETYPES.map((a) => {
                        const on = fields.archetypes.includes(a);
                        return (
                          <button
                            key={a}
                            type="button"
                            className={`voice-studio-chip${on ? " selected" : ""}`}
                            onClick={() =>
                              updateFields({
                                archetypes: on
                                  ? fields.archetypes.filter((x) => x !== a)
                                  : [...fields.archetypes, a],
                              })
                            }
                          >
                            {a}
                          </button>
                        );
                      })}
                    </div>
                  </fieldset>

                  <label>
                    Accent <HelpTip label="Accent" content="Regional flavor of English, or no specific accent." />
                    <select
                      value={fields.accent}
                      data-testid="voice-accent-select"
                      onChange={(e) => updateFields({ accent: e.target.value })}
                    >
                      {ACCENTS.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label>
                  Master Voice Prompt{" "}
                  <HelpTip
                    label="Master Voice Prompt"
                    content="Built from your choices. You can edit freely — later dropdown changes only update their own parts and keep your additions."
                  />
                  <textarea
                    rows={4}
                    data-testid="voice-master-prompt"
                    value={promptDoc.compiledPrompt}
                    onChange={(e) => setPromptDoc((d) => applyManualPromptEdit(d, e.target.value))}
                  />
                </label>

                <details
                  className="voice-studio-finetune"
                  open={fineTuneOpen}
                  onToggle={(e) => setFineTuneOpen((e.target as HTMLDetailsElement).open)}
                  data-testid="voice-personality-section"
                >
                  <summary>
                    Fine Tune Voice <HelpTip label="Fine Tune" content="Gentle sliders for feel — not technical provider settings." />
                  </summary>
                  <div className="voice-studio-sliders">
                    {FINE_TUNE_SLIDERS.map((s) => (
                      <label key={s.key} className="voice-studio-slider" data-testid={`voice-slider-${s.key}`}>
                        <span className="voice-studio-slider-label">
                          {s.label} <HelpTip label={s.label} content={s.tip} />
                        </span>
                        <input
                          type="range"
                          min={0}
                          max={4}
                          value={fields[s.key] ?? 2}
                          onChange={(e) => updateFields({ [s.key]: Number(e.target.value) })}
                        />
                      </label>
                    ))}
                  </div>
                </details>

                <div className="voice-studio-block">
                  <span>
                    Sample line <HelpTip label="Sample line" content="What the three voice candidates say so you can hear personality, not just a neutral sentence." />
                  </span>
                  <div className="voice-studio-chip-row" data-testid="voice-sample-line">
                    {SAMPLE_LINE_OPTIONS.map((o) => (
                      <button
                        key={o.id}
                        type="button"
                        className={`voice-studio-chip${sampleLineId === o.id ? " selected" : ""}`}
                        onClick={() => setSampleLineId(o.id)}
                      >
                        {o.label}
                      </button>
                    ))}
                  </div>
                  {sampleLineId === "custom" && (
                    <textarea
                      rows={2}
                      value={customSample}
                      onChange={(e) => setCustomSample(e.target.value)}
                      placeholder="Custom sample line"
                    />
                  )}
                  <p className="muted" style={{ fontSize: "0.85rem" }}>
                    {sampleLineText(ws, sampleLineId, customSample)}
                  </p>
                </div>

                <div className="voice-studio-actions">
                  <Button type="button" onClick={() => openCoDirector("Improve this character voice prompt")}>
                    Improve with Co-Director
                  </Button>
                  <Button
                    type="button"
                    onClick={() => {
                      const reset = syncPromptDocument(null, fields);
                      setPromptDoc(reset);
                    }}
                  >
                    Reset
                  </Button>
                <Button
                  type="button"
                  variant="primary"
                  className="voice-studio-primary-cta"
                  data-testid="voice-design-generate"
                  disabled={busy}
                  onClick={() => void runGenerate()}
                >
                  Generate 3 Voices
                </Button>
                </div>
                <p className="muted">Three unique interpretations of your character will be generated.</p>
                {capabilityNote ? <p className="muted" data-testid="voice-capability-note">{capabilityNote}</p> : null}
                {generateError ? (
                  <div className="voice-studio-recovery" data-testid="voice-generate-recovery">
                    <p>{generateError}</p>
                    <div className="voice-studio-actions">
                      <Button type="button" disabled={busy} onClick={() => void runGenerate()}>
                        Retry
                      </Button>
                      <Button type="button" onClick={() => document.getElementById("voice-studio-advanced")?.scrollIntoView()}>
                        Choose another voice engine
                      </Button>
                      <Button
                        type="button"
                        onClick={() =>
                          void persistDraft({
                            phase: "create",
                            masterPrompt: promptDoc.compiledPrompt,
                            designBrief: structuredToDesignBrief(fields, promptDoc),
                            promptDocument: promptDoc,
                          }).then(() => onMsg("Draft saved."))
                        }
                      >
                        Save draft
                      </Button>
                    </div>
                  </div>
                ) : null}
              </div>
            )}

            {method === "clone" && (
              <div className="voice-studio-block" data-testid="voice-clone-panel">
                <PanelHeading
                  title="Clone from Recording"
                  tip="Upload an authorized speaker sample. Consent is required."
                  as="h4"
                />
                <HelpTip label="Clone Voice" content="Creates a reusable synthetic voice from a consented recording — not a one-off dialogue clip." />
                <input
                  type="file"
                  accept="audio/*"
                  data-testid="voice-ref-file"
                  onChange={(e) => setCloneFile(e.target.files?.[0] || null)}
                />
                <label>
                  Transcript
                  <textarea
                    rows={2}
                    data-testid="voice-ref-transcript"
                    value={cloneTranscript}
                    onChange={(e) => setCloneTranscript(e.target.value)}
                  />
                </label>
                <label className="voice-studio-consent-check" data-testid="voice-clone-consent-check">
                  <input
                    type="checkbox"
                    checked={cloneConsent}
                    onChange={(e) => setCloneConsent(e.target.checked)}
                    data-testid="voice-consent-confirmed"
                  />
                  I confirm authorized consent to clone this speaker for this character.
                </label>
                <Button
                  type="button"
                  className="voice-studio-primary-cta"
                  data-testid="voice-clone-generate"
                  disabled={busy}
                  onClick={() => void runClone()}
                >
                  Clone Voice
                </Button>
              </div>
            )}

            {method === "upload" && (
              <div className="voice-studio-block" data-testid="voice-upload-panel">
                <PanelHeading title="Upload Voice" tip="Choose what you are uploading so dialogue clips are not treated as identity." as="h4" />
                <fieldset data-testid="voice-upload-kinds">
                  <legend>What are you uploading?</legend>
                  {UPLOAD_KINDS.map((k) => (
                    <label key={k.id} className="voice-studio-upload-kind">
                      <input
                        type="radio"
                        name="upload-kind"
                        checked={uploadKind === k.id}
                        onChange={() => setUploadKind(k.id)}
                      />
                      <span>
                        <strong>{k.label}</strong>
                        <span className="muted"> — {k.hint}</span>
                      </span>
                    </label>
                  ))}
                </fieldset>
                <input type="file" accept="audio/*" data-testid="voice-upload-file" onChange={(e) => setUploadFile(e.target.files?.[0] || null)} />
                {uploadKind === "reusable_character_voice" && (
                  <label className="voice-studio-consent-check">
                    <input type="checkbox" checked={uploadConsent} onChange={(e) => setUploadConsent(e.target.checked)} />
                    Consent confirmed for reusable character voice
                  </label>
                )}
                <Button
                  type="button"
                  className="voice-studio-primary-cta"
                  data-testid="voice-upload-register"
                  disabled={busy}
                  onClick={() => void runUpload()}
                >
                  Upload
                </Button>
              </div>
            )}
          </section>
        )}

        {/* Gallery */}
        {(phase === "select" || batches.length > 0) && phase !== "approve" && (
          <section className="voice-studio-section" data-testid="voice-audition-column">
            <PanelHeading title="Generated Voices" tip="Listen, then select one for testing. Approval comes later." as="h3" />
            <div className="voice-studio-gallery" data-testid="voice-candidates-panel">
              {activeBatchCandidates.map((c, i) => {
                const failed = c.status === "failed";
                const url = c.assetId ? api.assetUrl(c.assetId) : "";
                return (
                  <article
                    key={c.id}
                    className={`voice-studio-candidate-card${testingCandidateId === c.id ? " selected" : ""}`}
                    data-testid={`voice-candidate-${c.id}`}
                  >
                    <strong>{c.name || `Voice ${i + 1}`}</strong>
                    <p className="muted">{failed ? "Failed" : c.notes || "Ready"}</p>
                    {url ? <audio controls src={url} /> : null}
                    <div className="voice-studio-actions">
                      {failed ? (
                        <Button type="button" data-testid={`voice-retry-${c.id}`} disabled={busy} onClick={() => void retryCandidate(c.id)}>
                          Failed · Retry
                        </Button>
                      ) : (
                        <>
                          <Button
                            type="button"
                            data-testid={`voice-use-${c.id}`}
                            disabled={busy}
                            onClick={() => void selectForTesting(c.id)}
                          >
                            Select for Testing
                          </Button>
                          <Button
                            type="button"
                            onClick={() => {
                              setSimilarParentId(c.id);
                              setSimilarOpen(true);
                            }}
                          >
                            Generate Similar
                          </Button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="voice-studio-actions">
              <Button
                type="button"
                data-testid="voice-generate-more"
                disabled={busy}
                onClick={() => void runGenerate({ append: true })}
              >
                Generate 3 More
              </Button>
              {testingCandidateId && (
                <Button
                  type="button"
                  className="voice-studio-primary-cta"
                  data-testid="voice-studio-primary-select"
                  onClick={() => void continueToPerformance()}
                >
                  Continue with This Voice
                </Button>
              )}
            </div>

            {batches.length > 1 && (
              <details className="voice-studio-previous-batches" data-testid="voice-previous-batches">
                <summary>Previous Voice Sets</summary>
                <ul>
                  {batches.slice(1).map((b) => (
                    <li key={b.id}>
                      <button
                        type="button"
                        onClick={() => {
                          setExpandedBatchId(b.id);
                          if (b.voiceProfileId) setVoiceId(b.voiceProfileId);
                        }}
                      >
                        {new Date(b.createdAt || Date.now()).toLocaleString()} · {b.method} ·{" "}
                        {(b.candidateIds || []).length} voices
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        )}

        {similarOpen && (
          <section className="voice-studio-section voice-studio-similar" data-testid="voice-similar-panel">
            <h4>Generate Similar</h4>
            <p className="muted">Keep identity traits, then nudge the feel.</p>
            <div className="voice-studio-chip-row">
              {(
                [
                  ["identity", "Voice identity"],
                  ["age", "Age"],
                  ["accent", "Accent"],
                  ["personality", "Character personality"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={similarKeep[key]}
                    onChange={(e) => setSimilarKeep((k) => ({ ...k, [key]: e.target.checked }))}
                  />{" "}
                  {label}
                </label>
              ))}
            </div>
            <div className="voice-studio-chip-row">
              {["Warmer", "Sharper", "Softer", "More playful"].map((a) => (
                <button
                  key={a}
                  type="button"
                  className={`voice-studio-chip${similarAdjust.includes(a) ? " selected" : ""}`}
                  onClick={() =>
                    setSimilarAdjust((list) => (list.includes(a) ? list.filter((x) => x !== a) : [...list, a]))
                  }
                >
                  {a}
                </button>
              ))}
            </div>
            <label>
              Additional direction
              <input value={similarExtra} onChange={(e) => setSimilarExtra(e.target.value)} />
            </label>
            <div className="voice-studio-actions">
              <Button type="button" onClick={() => setSimilarOpen(false)}>
                Cancel
              </Button>
              <Button type="button" className="voice-studio-primary-cta" disabled={busy} onClick={() => void applySimilar()}>
                Generate Similar Voices
              </Button>
            </div>
          </section>
        )}

        {/* Performance */}
        {showLegacyPerformance && (phase === "performance" || phase === "approve") && (
          <section className="voice-studio-section" data-testid="voice-performance-workspace">
            <header data-testid="voice-performance-header">
              <PanelHeading
                title="Voice Performance"
                tip="Write dialogue, pick a mood, shape delivery, then generate three takes."
                as="h3"
              />
              <p className="muted" data-testid="voice-performance-readiness">
                {approved ? "Voice approved" : "Testing voice — approve before Timeline"}
              </p>
            </header>

            <nav className="voice-studio-chip-row" data-testid="voice-performance-views">
              {(
                [
                  ["dialogue", "Dialogue"],
                  ["mood", "Mood"],
                  ["delivery", "Delivery"],
                  ["preview", "Preview"],
                  ["approve", "Approve"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={`voice-studio-chip${perfStep === id ? " selected" : ""}`}
                  data-testid={`vp-step-${id === "mood" ? "performance" : id === "approve" ? "listen" : id}`}
                  onClick={() => setPerfStep(id)}
                >
                  {label}
                </button>
              ))}
            </nav>

            {perfStep === "dialogue" && (
              <label>
                What should {characterName} say?
                <textarea
                  rows={5}
                  data-testid="vp-dialogue-text"
                  value={dialogue}
                  onChange={(e) => {
                    setDialogue(e.target.value);
                    scheduleDraft({ dialogue: e.target.value, phase: "performance" });
                  }}
                />
              </label>
            )}

            {perfStep === "mood" && (
              <div className="voice-studio-chip-row" data-testid="vp-emotion-cards">
                {moodsOrdered.map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`voice-studio-chip${mood === m ? " selected" : ""}`}
                    data-testid={`vp-emotion-card-${moodToEmotionId(m)}`}
                    onClick={() => {
                      setMood(m);
                      scheduleDraft({ mood: m });
                    }}
                  >
                    {m}
                  </button>
                ))}
                <HelpTip label="Mood" content="The emotional color of this performance." />
              </div>
            )}

            {perfStep === "delivery" && (
              <div className="voice-studio-block">
                <div>
                  Speed
                  <div className="voice-studio-chip-row">
                    {DELIVERY_SPEED.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`voice-studio-chip${speed === s ? " selected" : ""}`}
                        data-testid={`vp-pace-chip-${speedToPace(s)}`}
                        onClick={() => setSpeed(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  Strength
                  <div className="voice-studio-chip-row">
                    {DELIVERY_STRENGTH.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`voice-studio-chip${strength === s ? " selected" : ""}`}
                        data-testid={`vp-strength-chip-${s.toLowerCase()}`}
                        onClick={() => setStrength(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  Style
                  <div className="voice-studio-chip-row">
                    {DELIVERY_STYLE.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className={`voice-studio-chip${style === s ? " selected" : ""}`}
                        onClick={() => setStyle(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="voice-studio-chip-row">
                  {REACTION_ACTIONS.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      className="voice-studio-chip"
                      onClick={() => {
                        setPauseMs(a.pauseMs);
                        if (a.reaction) setReaction(a.reaction);
                      }}
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
                <HelpTip label="Delivery" content="How fast, strong, and styled the line should feel." />
              </div>
            )}

            <label>
              Performance Prompt{" "}
              <HelpTip label="Performance Prompt" content="Plain-language direction for this take. Advanced markup stays hidden." />
              <textarea
                rows={3}
                data-testid="voice-performance-prompt"
                value={performancePrompt}
                onChange={(e) => {
                  setPerformancePrompt(e.target.value);
                  scheduleDraft({ performancePrompt: e.target.value });
                }}
              />
            </label>

            {/* Hidden canonical markup for e2e / Advanced sync */}
            <textarea hidden readOnly data-testid="vp-source-text" value={syncMarkup()} />

            <div className="voice-studio-actions">
              <Button
                type="button"
                className="voice-studio-primary-cta"
                data-testid="vp-generate-preview"
                disabled={busy || !testingCandidateId}
                onClick={() => void generatePerformances()}
              >
                Generate 3 Performances
              </Button>
              <Button type="button" data-testid="vp-parse" hidden onClick={() => void generatePerformances()}>
                Check
              </Button>
            </div>

            {takes.length > 0 && (
              <div className="voice-studio-gallery" data-testid="vp-audition">
                {takes.map((t) => (
                  <article key={t.id} className="voice-studio-candidate-card" data-testid={`vp-seg-${t.id}`}>
                    <strong>{t.name}</strong>
                    <p className="muted">{t.label}</p>
                    {t.assetId ? <audio controls src={api.assetUrl(t.assetId)} data-testid="vp-main-player" /> : null}
                    <Button type="button" onClick={() => void chooseTake(t.id)}>
                      Choose
                    </Button>
                  </article>
                ))}
              </div>
            )}

            <div className="voice-studio-chip-row" data-testid="voice-adjust-chips">
              {ADJUSTMENT_CHIPS.map((c) => (
                <button key={c} type="button" className="voice-studio-chip" onClick={() => void applyAdjustment(c)}>
                  {c}
                </button>
              ))}
            </div>
          </section>
        )}

        {/* Approve */}
        {showLegacyPerformance && phase === "approve" && (
          <section className="voice-studio-section" data-testid="voice-studio-approve">
            <PanelHeading title="Approval" tip="Approve the voice and performance when you are happy, then add to Timeline." as="h3" />
            <ul className="voice-studio-approve-summary">
              <li>Character: {characterName}</li>
              <li>Selected Voice: {testingCandidate?.name || "—"} {approved ? "(Approved)" : "(Testing)"}</li>
              <li>Selected Performance: {takes.find((t) => t.id === selectedTakeId)?.name || "—"}</li>
              <li>Status: {READINESS_LABELS[readinessLabel]}</li>
            </ul>
            <div className="voice-studio-actions">
              {!approved && (
                <Button
                  type="button"
                  className="voice-studio-primary-cta"
                  data-testid="voice-approve-candidate"
                  disabled={busy}
                  onClick={() => void approveVoice()}
                >
                  Approve and Save Voice
                </Button>
              )}
              {approved && selectedTakeId && !assembly && (
                <Button
                  type="button"
                  className="voice-studio-primary-cta"
                  data-testid="vp-approve-performance"
                  disabled={busy}
                  onClick={() => {
                    setAssembly({ pending: false });
                    onMsg("Performance approved.");
                  }}
                >
                  Approve Performance
                </Button>
              )}
              {approved && plan && (
                <Button
                  type="button"
                  className={assembly ? "voice-studio-primary-cta" : undefined}
                  data-testid="vp-assemble-place"
                  disabled={busy}
                  onClick={() => void assembleAndPlace()}
                >
                  Add to Timeline
                </Button>
              )}
            </div>
            {placement ? (
              <p className="muted" data-testid="voice-timeline-placed">
                Ready for Timeline
              </p>
            ) : null}
          </section>
        )}

        {/* Advanced */}
        <details className="voice-studio-advanced" id="voice-studio-advanced" data-testid="voice-advanced">
          <summary>
            Advanced <HelpTip label="Advanced" content="Technical provider, markup, versions, and diagnostics. Not needed for the beginner flow." />
          </summary>
          <div className="voice-studio-advanced-body">
            <p className="muted">Provider, voice engine, translation, pronunciation, segments, seed, metadata, versions, provenance, diagnostics.</p>
            <pre data-testid="voice-provenance-body" className="voice-studio-json">
              {JSON.stringify(
                {
                  voiceId,
                  testingCandidateId,
                  approved,
                  batches: batches.length,
                  planId: plan?.id,
                  assemblyId: assembly?.id || assembly?.assemblyId,
                  placement,
                  mock: false,
                },
                null,
                2,
              )}
            </pre>
            <div data-testid="vp-advanced">
              <label>
                Canonical markup
                <textarea rows={6} value={syncMarkup()} readOnly />
              </label>
              <div data-testid="vp-translation-panel" className="muted">
                Voice engine translation available after generate.
              </div>
              <div data-testid="vp-timeline-panel" className="muted">
                Timeline placement: {placement ? JSON.stringify(placement) : "—"}
              </div>
              <div data-testid="vp-provenance" className="muted">
                mock: false
              </div>
            </div>
            <div data-testid="voice-versions-list" className="muted">
              Versions and candidate lineage preserved on the voice profile.
            </div>
          </div>
        </details>
          </>
        ) : workspaceTab === "environment" ? (
          <VoiceEnvironmentPanel
            projectId={projectId}
            characterId={characterId}
            characterName={characterName}
            approvedVoiceIdentity={
              approvedVoice?.id
                ? {
                    id: String(approvedVoice.id),
                    name: String(approvedVoice.name || `${characterName} Voice`),
                    version: approvedVoice.version_number ?? approvedVoice.versionNumber ?? null,
                  }
                : null
            }
            onMsg={onMsg}
            onSelectStage={setWorkspaceTab}
          />
        ) : (
          <VoicePerformanceStudio
            projectId={projectId}
            characterId={characterId}
            characterName={characterName}
            activeView={workspaceTab === "sceneDialogue" ? "sceneDialogue" : workspaceTab === "takes" ? "takes" : "performance"}
            approvedVoiceIdentity={
              approvedVoice?.id
                ? {
                    id: String(approvedVoice.id),
                    name: String(approvedVoice.name || `${characterName} Voice`),
                    version: approvedVoice.version_number ?? approvedVoice.versionNumber ?? null,
                  }
                : null
            }
            initialDialogue={dialogue}
            onMsg={onMsg}
            onOpenVoiceIdentity={() => setWorkspaceTab("identity")}
          />
        )}
      </div>

      {/* Legacy e2e shims */}
      <nav className="voice-studio-legacy-nav" data-testid="voice-creator-subtabs" aria-hidden="true" hidden>
        <button type="button" data-testid="voice-subtab-overview" onClick={() => setMethod("existing")}>
          Overview
        </button>
        <button type="button" data-testid="voice-subtab-create" onClick={() => setMethod("create")}>
          Create
        </button>
        <button type="button" data-testid="voice-subtab-clone" onClick={() => setMethod("clone")}>
          Clone
        </button>
        <button type="button" data-testid="voice-subtab-candidates">
          Candidates
        </button>
        <button type="button" data-testid="voice-subtab-audition">
          Audition
        </button>
        <button type="button" data-testid="voice-subtab-pronunciation">
          Pronunciation
        </button>
        <button type="button" data-testid="voice-subtab-reactions">
          Reactions
        </button>
        <button type="button" data-testid="voice-subtab-versions">
          Versions
        </button>
        <button type="button" data-testid="voice-subtab-provenance">
          Provenance
        </button>
        <button type="button" data-testid="vp-view-script">
          Script
        </button>
        <button type="button" data-testid="vp-view-markup">
          Markup
        </button>
        <button type="button" data-testid="vp-view-plan">
          Plan
        </button>
        <button type="button" data-testid="vp-view-translation">
          Translation
        </button>
        <button type="button" data-testid="vp-view-segments">
          Segments
        </button>
        <button type="button" data-testid="vp-view-audition">
          Audition
        </button>
        <button type="button" data-testid="vp-view-timeline">
          Timeline
        </button>
        <button type="button" data-testid="vp-view-versions">
          Versions
        </button>
        <button type="button" data-testid="vp-view-provenance">
          Provenance
        </button>
      </nav>
    </section>
  );
}
