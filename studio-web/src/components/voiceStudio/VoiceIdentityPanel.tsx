import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";

function libraryModalProject(id: string, name: string): Project {
  return {
    id,
    name,
    engine_default: "auto",
    global_prompt: "",
    negative_prompt: "",
    width: 0,
    height: 0,
    fps: 0,
    seed: 0,
    preset: "draft",
    vram_gb: 0,
    spatial_map_json: "",
    created_at: "",
    updated_at: "",
    scenes: [],
    assets: [],
  };
}
import { Button } from "../ui";
import { PanelHeading } from "../HelpTip";
import { AddFromProjectLibraryModal } from "../timeline-master/AddFromProjectLibraryModal";
import { VoiceMethodCards } from "./VoiceMethodCards";
import { ElevenLabsVoiceWorkflow, type ElevenLabsGeneratedSample } from "./ElevenLabsVoiceWorkflow";
import { VoiceEngineLabel } from "./VoiceEngineLabel";
import { useVoiceStudioProviderSource } from "../../audioProvider/useProviderSource";
import { setElevenLabsVoiceId, setVoiceStudioProvider } from "../../audioProvider/voiceStudioProviderStore";
import { ApprovedVoicePlayer } from "./ApprovedVoicePlayer";
import { VoiceSamplePlayers, type VoiceSamplePlayerItem } from "./VoiceSamplePlayers";
import { VoiceStudioSelect } from "./VoiceStudioSelect";
import {
  compileVoiceCloneGenerateBody,
  compileVoiceIdentityGenerateBody,
  pickNewestGeneratedSample,
  pickRestorableVoiceCandidates,
  voiceStudioErrorMessage,
} from "./voiceIdentityBrief";
import {
  approvedDefaultVoiceMessage,
  approvedVoiceBannerSubtitle,
  approvedVoiceBannerTitle,
  approvedVoiceVersionLabel,
  noApprovedDefaultVoiceMessage,
  unassignVoiceConfirm,
  unassignVoiceExplain,
} from "./defaultVoiceCopy";
import { choosePortraitAssetId } from "./voicePortrait";
import { voiceIdentityAction, type VoiceIdentityMethod } from "./voiceIdentityRoute";
import { isCurrentCharacterRequest } from "./voiceStudioCharacter";
import "./VoiceIdentityPanel.css";

const AGE_OPTIONS = [
  "Child 5-8", "Child 9-12", "Young Teen 13-15", "Teen 16-19",
  "Young Adult 20-24", "Young Adult 25-29", "Adult 30-34", "Adult 35-39",
  "Adult 40-44", "Adult 45-49", "Mature 50-54", "Mature 55-59",
  "Senior 60-64", "Senior 65-69", "Senior 70-79", "Elder 80+",
] as const;

const ARCHETYPES = [
  "Hero", "Antihero", "Villain", "Mentor", "Leader", "Rebel", "Trickster",
  "Explorer", "Scientist", "Mystic", "Caregiver", "Outsider", "Royal",
  "Warrior", "Scholar", "Detective", "Comedian", "Romantic", "Guardian",
  "Inventor", "Diplomat", "Survivor", "Dreamer", "Commander", "Everyperson",
  "Custom",
] as const;

const ACCENTS = [
  "Neutral American", "General American", "Southern American", "New York",
  "Boston", "Midwestern American", "Canadian", "British RP", "London",
  "Northern English", "Scottish", "Irish", "Welsh", "Australian",
  "New Zealand", "French-accented English", "German-accented English",
  "Italian-accented English", "Spanish-accented English", "Eastern European",
  "Russian-accented English", "Indian English", "South African", "Caribbean",
  "Custom",
] as const;

type GeneratedSample = VoiceSamplePlayerItem;

type Props = {
  projectId: string;
  characterId: string;
  characterName?: string;
  variant?: "standard" | "express";
  preferredMethod?: VoiceIdentityMethod | null;
  onMsg: (m: string) => void;
  onVoiceApproved?: () => void;
  onNavigate?: (tab: string) => void;
  onRefresh?: () => void;
  onOpenFullStudio?: (characterId: string) => void;
  onCharacterChange?: (characterId: string) => void;
};

export function VoiceIdentityPanel({
  projectId,
  characterId,
  characterName,
  variant = "standard",
  preferredMethod = null,
  onMsg,
  onVoiceApproved,
  onNavigate: _onNavigate,
  onRefresh,
  onOpenFullStudio,
  onCharacterChange,
}: Props) {
  const voiceProvider = useVoiceStudioProviderSource();
  const [characters, setCharacters] = useState<any[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState(characterId);
  const [selectedCharacterName, setSelectedCharacterName] = useState(characterName || "");
  const [portraitUrl, setPortraitUrl] = useState("");
  const [creatingCharacter, setCreatingCharacter] = useState(false);
  const [newCharName, setNewCharName] = useState("");

  const [method, setMethod] = useState<VoiceIdentityMethod | null>(null);
  const [sex, setSex] = useState<"female" | "male">("female");
  const [age, setAge] = useState<string>(AGE_OPTIONS[4]);
  const [script, setScript] = useState("");
  const [promptDetails, setPromptDetails] = useState("");

  const [emotion, setEmotion] = useState(0);
  const [intensity, setIntensity] = useState(0);
  const [speed, setSpeed] = useState(0);
  const [pitch, setPitch] = useState(0);

  const [archetype, setArchetype] = useState<string>(ARCHETYPES[0]);
  const [accent, setAccent] = useState<string>(ACCENTS[0]);
  const [sampleCount, setSampleCount] = useState<1 | 2 | 3 | 4>(4);
  const sampleCountRef = useRef<1 | 2 | 3 | 4>(4);
  const scriptRef = useRef("");
  sampleCountRef.current = sampleCount;
  scriptRef.current = script;

  const [generationState, setGenerationState] = useState<"idle" | "generating" | "done">("idle");
  const [voiceJob, setVoiceJob] = useState<{
    jobId?: string | null;
    status?: string;
    phase?: string;
    label?: string;
    percent?: number;
    sampleCount?: number;
    sampleIndex?: number;
    completedSamples?: number;
    error?: string | null;
    candidates?: unknown[];
    voiceId?: string | null;
  } | null>(null);
  const generatingRef = useRef(false);
  const approvingRef = useRef(false);
  const [samples, setSamples] = useState<GeneratedSample[]>([]);
  const [playableSamples, setPlayableSamples] = useState<GeneratedSample[]>([]);
  const [unassignArmed, setUnassignArmed] = useState(false);
  const [approvedVoice, setApprovedVoice] = useState<any | null>(null);
  const [hasApprovedVoice, setHasApprovedVoice] = useState(false);
  const [previousApprovedVoices, setPreviousApprovedVoices] = useState<any[]>([]);
  const [approveState, setApproveState] = useState<"idle" | "approving" | "approved">("idle");
  const [expanded, setExpanded] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [existingVoices, setExistingVoices] = useState<any[]>([]);
  const [activeVoice, setActiveVoice] = useState<any | null>(null);
  const [voicesCharacterId, setVoicesCharacterId] = useState("");
  const [existingVoiceId, setExistingVoiceId] = useState("");
  const [libraryPickerOpen, setLibraryPickerOpen] = useState(false);
  const [assigningReference, setAssigningReference] = useState(false);
  const [cloneFile, setCloneFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);

  const [refineLoading, setRefineLoading] = useState(false);
  const [refinePreview, setRefinePreview] = useState<string | null>(null);

  const [voiceId, setVoiceId] = useState("");
  const [boundCharacterId, setBoundCharacterId] = useState("");
  const selectedCharacterIdRef = useRef(selectedCharacterId);
  const selectedCharacterNameRef = useRef(selectedCharacterName);
  selectedCharacterIdRef.current = selectedCharacterId;
  selectedCharacterNameRef.current = selectedCharacterName;

  const loadCharacters = useCallback(async () => {
    try {
      const res = await api.listCharacterProfiles(projectId);
      setCharacters(res.items || []);
    } catch {
      /* ignore */
    }
  }, [projectId]);

  const applyApprovedFromWorkspace = useCallback((ws: any, fallbackName: string) => {
    const active = ws?.activeVoice;
    const approved = Boolean(
      ws?.activeVoiceProfileId
      && String(active?.approval_status || "").toLowerCase() === "approved",
    );
    const previous = Array.isArray(ws?.previousApprovedVoices) ? ws.previousApprovedVoices : [];
    setPreviousApprovedVoices(previous);
    if (!approved) {
      setHasApprovedVoice(false);
      setApprovedVoice(null);
      return;
    }
    const previewId = String(active?.approved_preview_asset_id || active?.approvedPreviewAssetId || "");
    setHasApprovedVoice(true);
    setApprovedVoice({
      id: String(ws.activeVoiceProfileId),
      name: String(active?.name || fallbackName || "Approved Voice"),
      characterName: fallbackName,
      versionNumber: active?.version_number,
      previewAssetId: previewId,
      provider: String(active?.provider || ""),
      modelId: String(active?.providerModelId || active?.model_id || ""),
      audioUrl: previewId ? api.assetUrl(previewId, undefined, projectId) : undefined,
    });
  }, [projectId]);

  const loadPortrait = useCallback(async (cid: string) => {
    try {
      const refs = await api.listCharacterReferences(projectId, cid);
      if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
      const assetId = choosePortraitAssetId(refs.items);
      setPortraitUrl(assetId ? api.assetUrl(assetId, undefined, projectId) : "");
    } catch {
      if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
      setPortraitUrl("");
    }
  }, [projectId]);

  const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const pollVoiceJob = useCallback(async (cid: string) => {
    const started = Date.now();
    while (Date.now() - started < 40 * 60 * 1000) {
      if (selectedCharacterIdRef.current !== cid) return null;
      const job = await api.getCharacterVoiceGenerateStatus(projectId, cid);
      setVoiceJob(job);
      const status = String(job?.status || "");
      if (status === "complete" || status === "failed" || status === "idle") {
        return job;
      }
      await sleep(800);
    }
    return null;
  }, [projectId]);

  const loadExistingVoices = useCallback(async (cid: string, fallbackName: string) => {
    try {
      const live = await api.getCharacterVoiceGenerateStatus(projectId, cid).catch(() => null);
      if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
      if (live && live.status === "complete" && Array.isArray(live.candidates) && live.candidates.length) {
        if (String(live.mode || "") === "clone") setMethod("clone");
        else setMethod("create");
        setVoiceJob(live);
        setVoiceId(String(live.voiceId || ""));
        setBoundCharacterId(cid);
        const next = (live.candidates || []).map((candidate: any, index: number) => {
          const assetId = candidate?.assetId || candidate?.asset_id || (typeof candidate === "string" ? candidate : "");
          return {
            id: String(candidate?.id || assetId || `sample-${index}`),
            status: candidate?.status || (assetId ? "ready" : "failed"),
            assetId: assetId ? String(assetId) : undefined,
            audioUrl: assetId ? api.assetUrl(String(assetId), undefined, projectId) : undefined,
          };
        });
        setSamples(next);
        setGenerationState("done");
      }
      if (live && (live.status === "queued" || live.status === "running")) {
        generatingRef.current = true;
        setGenerationState("generating");
        setVoiceJob(live);
        if (String(live.mode || "") === "clone") setMethod("clone");
        else setMethod("create");
        const finished = await pollVoiceJob(cid);
        if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
        generatingRef.current = false;
        if (finished?.status === "complete") {
          setVoiceId(String(finished.voiceId || ""));
          setBoundCharacterId(cid);
          const next = (finished.candidates || []).map((candidate: any, index: number) => {
            const assetId = candidate?.assetId || candidate?.asset_id || (typeof candidate === "string" ? candidate : "");
            return {
              id: String(candidate?.id || assetId || `sample-${index}`),
              status: candidate?.status || (assetId ? "ready" : "failed"),
              assetId: assetId ? String(assetId) : undefined,
              audioUrl: assetId ? api.assetUrl(String(assetId), undefined, projectId) : undefined,
            };
          });
          setSamples(next);
          setGenerationState("done");
        }
        if (finished?.status === "failed") {
          setErrors([String(finished.error || "Voice generation failed.")]);
          setGenerationState("idle");
          return;
        }
      }
      const ws = await api.getCharacterVoiceWorkspace(projectId, cid);
      if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
      const voices = ws?.voices || [];
      setExistingVoices(voices);
      setActiveVoice(ws?.activeVoice || null);
      setPlayableSamples(mapPlayableSamples(ws?.playableSamples || []));
      setVoicesCharacterId(cid);
      applyApprovedFromWorkspace(ws, fallbackName || String(ws?.characterName || ""));
      const restored = pickRestorableVoiceCandidates(voices);
      if (!restored) return;
      const next = mapCandidates(restored.candidates);
      if (!next.some((sample) => sample.audioUrl)) return;
      setVoiceId(restored.voiceId);
      setBoundCharacterId(cid);
      setSamples(next);
      setGenerationState("done");
      if (restored.sourceMode.toUpperCase() === "CLONE") setMethod("clone");
      else if (restored.sourceMode.toUpperCase() === "DESIGN") setMethod("create");
    } catch {
      if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
      setExistingVoices([]);
      setHasApprovedVoice(false);
      setApprovedVoice(null);
    }
  }, [applyApprovedFromWorkspace, pollVoiceJob, projectId]);

  useEffect(() => {
    setSelectedCharacterId(characterId);
  }, [characterId]);

  useEffect(() => {
    if (preferredMethod) setMethod(preferredMethod);
  }, [preferredMethod]);

  useEffect(() => {
    const match = characters.find((c) => c.id === selectedCharacterId);
    if (match) setSelectedCharacterName(match.name || match.characterName || characterName || "");
    else if (characterName) setSelectedCharacterName(characterName);
  }, [characters, selectedCharacterId, characterName]);

  useEffect(() => {
    void loadCharacters();
  }, [loadCharacters]);

  useEffect(() => {
    if (!selectedCharacterId) {
      setHasApprovedVoice(false);
      setApprovedVoice(null);
      setPortraitUrl("");
      setVoicesCharacterId("");
      setVoiceStudioProvider("local");
      return;
    }
    setVoicesCharacterId("");
    setHasApprovedVoice(false);
    setApprovedVoice(null);
    setPreviousApprovedVoices([]);
    setApproveState("idle");
    setPortraitUrl("");
    setVoiceId("");
    setSamples([]);
    setPlayableSamples([]);
    setUnassignArmed(false);
    setBoundCharacterId("");
    setGenerationState("idle");
    setErrors([]);
    void loadPortrait(selectedCharacterId);
    void loadExistingVoices(selectedCharacterId, selectedCharacterNameRef.current);
  }, [selectedCharacterId, loadPortrait, loadExistingVoices]);

  useEffect(() => {
    if (!selectedCharacterId || voicesCharacterId !== selectedCharacterId) return;
    if (activeVoice?.provider === "elevenlabs" && activeVoice?.providerVoiceId) {
      setVoiceStudioProvider("elevenlabs");
      setElevenLabsVoiceId(String(activeVoice.providerVoiceId));
      setMethod("elevenlabs");
      return;
    }
    setVoiceStudioProvider("local");
  }, [selectedCharacterId, voicesCharacterId, activeVoice]);

  const handleCreateCharacter = useCallback(async () => {
    if (!newCharName.trim()) return;
    try {
      const created = await api.createCharacterProfile(projectId, { name: newCharName.trim() });
      const id = created?.id || created?.characterId || created?.item?.id || "";
      if (id) {
        setSelectedCharacterId(id);
        setSelectedCharacterName(newCharName.trim());
        setCreatingCharacter(false);
        setNewCharName("");
        onCharacterChange?.(id);
        await loadCharacters();
      }
    } catch {
      /* ignore */
    }
  }, [newCharName, projectId, loadCharacters, onCharacterChange]);

  const handleRefinePrompt = useCallback(async () => {
    if (!promptDetails.trim()) return;
    setRefineLoading(true);
    try {
      const res = await api.codirectorChat({
        messages: [
          {
            role: "user",
            content: "Improve this voice prompt for character \"" + selectedCharacterName + "\":\n\n" + promptDetails,
          },
        ],
        project_id: projectId,
        mode: "prompt",
      });
      if (res?.reply) setRefinePreview(res.reply);
    } catch {
      onMsg("Failed to refine prompt with Co-Director.");
    } finally {
      setRefineLoading(false);
    }
  }, [promptDetails, selectedCharacterName, projectId, onMsg]);

  const validate = useCallback((): string[] => {
    const errs: string[] = [];
    if (!selectedCharacterId) errs.push("Please select a character.");
    if (!method) errs.push("Please select a voice method.");
    if (method === "create") {
      if (!sex) errs.push("Please select a voice type.");
      if (!age) errs.push("Please select an age range.");
    }
    if (method === "existing" && !existingVoiceId) errs.push("Pick a saved voice from the list.");
    if (method === "clone" && !cloneFile) errs.push("Choose a recording to clone.");
    if (method === "clone" && !consent) {
      errs.push("Confirm you have permission to clone this recording.");
    }
    if ((method === "clone" || method === "create") && !scriptRef.current.trim()) {
      errs.push("Enter the line the voice should speak.");
    }
    return errs;
  }, [selectedCharacterId, method, sex, age, existingVoiceId, cloneFile, consent]);

  const mapPlayableSamples = (items: any[]): GeneratedSample[] =>
    (items || []).flatMap((candidate: any) => {
      const assetId = String(candidate?.assetId || candidate?.asset_id || "");
      if (!assetId) return [];
      return [{
        id: String(candidate?.id || assetId),
        status: String(candidate?.status || "ready"),
        assetId,
        audioUrl: api.assetUrl(assetId, undefined, projectId),
        voiceProfileId: String(candidate?.voiceProfileId || ""),
        provider: String(candidate?.provider || ""),
        name: String(candidate?.name || ""),
        modelId: String(candidate?.modelId || ""),
        providerVoiceId: String(candidate?.providerVoiceId || ""),
        createdAt: String(candidate?.createdAt || ""),
      }];
    });

  const mapCandidates = (items: any[], voiceProfileId = ""): GeneratedSample[] =>
    (items || []).map((candidate: any, index: number) => {
      if (typeof candidate === "string") {
        return {
          id: candidate,
          status: "ready",
          assetId: candidate,
          audioUrl: api.assetUrl(candidate, undefined, projectId),
          voiceProfileId,
          provider: "local",
        };
      }
      const assetId = candidate.assetId || candidate.asset_id;
      return {
        id: String(candidate.id || assetId || `sample-${index}`),
        status: candidate.status || (assetId ? "ready" : "failed"),
        assetId: assetId ? String(assetId) : undefined,
        audioUrl: assetId ? api.assetUrl(assetId, undefined, projectId) : undefined,
        error: candidate.error ? String(candidate.error) : undefined,
        voiceProfileId: String(candidate.voiceProfileId || voiceProfileId || ""),
        provider: String(candidate.provider || "local"),
        name: String(candidate.name || ""),
        modelId: String(candidate.modelId || ""),
        createdAt: String(candidate.createdAt || ""),
      };
    });

  const handleGenerate = useCallback(async () => {
    const errs = validate();
    setErrors(errs);
    if (errs.length > 0) return;
    if (generatingRef.current || generationState === "generating") return;
    const action = voiceIdentityAction(method);
    if (action === "none") {
      onMsg("Pick a saved voice. Generate is for new samples.");
      return;
    }
    generatingRef.current = true;
    setGenerationState("generating");
    setApproveState("idle");
    setErrors([]);
    setSamples([]);
    setVoiceJob({
      status: "queued",
      phase: "preparing",
      label: "Preparing recording",
      percent: 6,
      sampleCount: sampleCountRef.current,
      sampleIndex: 0,
      completedSamples: 0,
    });
    const cid = selectedCharacterId;
    try {
      let started: any = null;
      if (action === "clone" && cloneFile) {
        const uploaded = await api.uploadAsset(projectId, cloneFile, "voice-clone-ref", "audio");
        started = await api.cloneCharacterVoiceWorkspace(
          projectId,
          cid,
          {
            ...compileVoiceCloneGenerateBody({
              name: selectedCharacterName + " Clone",
              characterName: selectedCharacterName,
              referencePath: uploaded.path || "",
              referenceAssetId: uploaded.id,
              testLine: scriptRef.current.trim(),
              sampleCount: sampleCountRef.current,
              consentConfirmed: consent,
            }),
            asyncJob: true,
          },
        );
      } else {
        started = await api.generateCharacterVoiceCandidates(
          projectId,
          cid,
          {
            ...compileVoiceIdentityGenerateBody({
              sex,
              age,
              accent,
              archetype,
              script: scriptRef.current,
              promptDetails,
              sampleCount: sampleCountRef.current,
            }),
            asyncJob: true,
          },
        );
      }
      if (started?.async || started?.jobId) {
        setVoiceJob(started);
        const finished = await pollVoiceJob(cid);
        if (!isCurrentCharacterRequest(cid, selectedCharacterIdRef.current)) return;
        if (finished?.status === "complete") {
          setVoiceId(String(finished.voiceId || started.voiceId || ""));
          setBoundCharacterId(cid);
          const next = mapCandidates(finished.candidates || []);
          setSamples(next);
          setGenerationState("done");
          setVoiceJob(finished);
          return;
        }
        const reason = String(finished?.error || "Voice generation failed.");
        setVoiceJob(finished || { status: "failed", phase: "failed", percent: started?.percent || 0, error: reason });
        setGenerationState("idle");
        setErrors([reason]);
        onMsg(reason);
        return;
      }
      setVoiceId(started?.id || started?.voice?.id || "");
      setBoundCharacterId(cid);
      const next = mapCandidates(started?.candidates || started?.items || []);
      setSamples(next);
      setGenerationState("done");
      setVoiceJob({
        status: "complete",
        phase: "complete",
        label: "Voice samples ready",
        percent: 100,
        sampleCount: next.length,
        completedSamples: next.length,
      });
    } catch (error: unknown) {
      setGenerationState("idle");
      const reason = voiceStudioErrorMessage(error);
      setVoiceJob((prev) => ({
        ...(prev || {}),
        status: "failed",
        phase: "failed",
        label: "Voice generation failed",
        error: reason,
        percent: prev?.percent && prev.percent < 100 ? prev.percent : 8,
      }));
      setErrors([reason]);
      onMsg(reason);
    } finally {
      generatingRef.current = false;
    }
  }, [
    validate, method, cloneFile, consent, projectId, generationState, pollVoiceJob,
    selectedCharacterId, selectedCharacterName, sex, age, accent, archetype, promptDetails, onMsg,
  ]);

  const handleApprove = useCallback(
    async (sample: GeneratedSample | ElevenLabsGeneratedSample) => {
      if (boundCharacterId && boundCharacterId !== selectedCharacterId) {
        const reason = "That sample belongs to another character. It was not approved here.";
        onMsg(reason);
        throw new Error(reason);
      }
      if (approvingRef.current) return;
      const assetId = String(sample.assetId || "");
      const explicitCandidate = "candidateId" in sample ? String(sample.candidateId || "") : "";
      const listedId = "id" in sample ? String((sample as GeneratedSample).id || "") : "";
      const candidateId = explicitCandidate || (listedId && listedId !== assetId ? listedId : "");
      const profileId = String(sample.voiceProfileId || voiceId || "");
      if (!assetId && !candidateId) {
        const reason = "Approve needs this generated sample.";
        onMsg(reason);
        throw new Error(reason);
      }
      try {
        approvingRef.current = true;
        setApproveState("approving");
        setErrors([]);
        const approved = candidateId && profileId
          ? await api.approveCharacterVoiceCandidate(projectId, selectedCharacterId, {
              voiceId: profileId,
              candidateId,
            })
          : await api.approveCharacterVoiceCandidate(projectId, selectedCharacterId, {
              assetId,
            });
        const previewAssetId = String(
          approved?.voice?.approved_preview_asset_id
          || approved?.voice?.approvedPreviewAssetId
          || assetId
          || "",
        );
        setApprovedVoice({
          id: String(approved?.voice?.id || profileId || ""),
          name: String(approved?.voice?.name || `${selectedCharacterName} Voice`),
          characterName: selectedCharacterName,
          versionNumber: approved?.voice?.version_number,
          previewAssetId,
          provider: String(approved?.voice?.provider || sample.provider || ""),
          modelId: String(approved?.voice?.providerModelId || approved?.voice?.model_id || sample.modelId || ""),
          audioUrl: previewAssetId
            ? api.assetUrl(previewAssetId, undefined, projectId)
            : ("audioUrl" in sample ? sample.audioUrl : undefined),
        });
        setHasApprovedVoice(true);
        setApproveState("approved");
        setUnassignArmed(false);
        onVoiceApproved?.();
        onRefresh?.();
        onMsg(approvedDefaultVoiceMessage(selectedCharacterName));
        void loadExistingVoices(selectedCharacterId, selectedCharacterName);
      } catch (error: unknown) {
        setApproveState("idle");
        const reason = voiceStudioErrorMessage(error, "Failed to approve voice candidate.");
        setErrors([reason]);
        onMsg(reason);
        throw error instanceof Error ? error : new Error(reason);
      } finally {
        approvingRef.current = false;
      }
    },
    [
      boundCharacterId, selectedCharacterId, voiceId,
      projectId, selectedCharacterName, onMsg, onVoiceApproved, onRefresh, loadExistingVoices,
    ],
  );

  const handleUnassign = useCallback(async () => {
    if (!selectedCharacterId || approvingRef.current) return;
    try {
      approvingRef.current = true;
      setErrors([]);
      await api.unassignCharacterVoice(projectId, selectedCharacterId);
      setUnassignArmed(false);
      setHasApprovedVoice(false);
      setApprovedVoice(null);
      onMsg(noApprovedDefaultVoiceMessage(selectedCharacterName));
      onVoiceApproved?.();
      onRefresh?.();
      await loadExistingVoices(selectedCharacterId, selectedCharacterName);
    } catch (error: unknown) {
      onMsg(voiceStudioErrorMessage(error, "Could not unassign this voice."));
    } finally {
      approvingRef.current = false;
    }
  }, [selectedCharacterId, projectId, selectedCharacterName, onMsg, onVoiceApproved, onRefresh, loadExistingVoices]);

  const handleAssignLibraryVoice = useCallback(
    async (assetId: string) => {
      if (!assetId || assigningReference || !selectedCharacterId) return;
      try {
        setAssigningReference(true);
        setErrors([]);
        await api.setCharacterVoiceReference(projectId, selectedCharacterId, assetId);
        onMsg(`${selectedCharacterName || "This character"} now uses that Library audio as their voice reference.`);
        onVoiceApproved?.();
        onRefresh?.();
        await loadExistingVoices(selectedCharacterId, selectedCharacterName);
      } catch (error: unknown) {
        onMsg(voiceStudioErrorMessage(error, "Could not assign that Library audio."));
      } finally {
        setAssigningReference(false);
      }
    },
    [
      assigningReference, selectedCharacterId, projectId, selectedCharacterName,
      onMsg, onVoiceApproved, onRefresh, loadExistingVoices,
    ],
  );

  const handleUseExisting = useCallback(async (voiceOverride?: string) => {
    const targetId = voiceOverride || existingVoiceId;
    if (!targetId || approvingRef.current) return;
    try {
      approvingRef.current = true;
      setApproveState("approving");
      setErrors([]);
      const approved = await api.approveCharacterVoiceCandidate(projectId, selectedCharacterId, {
        voiceId: targetId,
      });
      setHasApprovedVoice(true);
      setApproveState("approved");
      onVoiceApproved?.();
      onRefresh?.();
      onMsg(approvedDefaultVoiceMessage(selectedCharacterName));
      void loadExistingVoices(selectedCharacterId, selectedCharacterName);
      if (approved?.voice) {
        const previewId = String(approved.voice.approved_preview_asset_id || approved.voice.approvedPreviewAssetId || "");
        setApprovedVoice({
          id: String(approved.voice.id || targetId),
          name: String(approved.voice.name || selectedCharacterName || "Approved Voice"),
          characterName: selectedCharacterName,
          versionNumber: approved.voice.version_number,
          audioUrl: previewId ? api.assetUrl(previewId, undefined, projectId) : undefined,
        });
      }
    } catch (error: unknown) {
      setApproveState("idle");
      onMsg(voiceStudioErrorMessage(error, "Could not use that saved voice."));
    } finally {
      approvingRef.current = false;
    }
  }, [existingVoiceId, projectId, selectedCharacterId, selectedCharacterName, onMsg, onVoiceApproved, onRefresh, loadExistingVoices]);

  const newestGenerated = pickNewestGeneratedSample(playableSamples);
  const currentPreviewAssetId = String(approvedVoice?.previewAssetId || "");
  const historySamples = (() => {
    const seen = new Set<string>();
    const rows: GeneratedSample[] = [];
    for (const sample of [...playableSamples, ...samples]) {
      const key = String(sample.assetId || sample.id || "");
      if (!key || seen.has(key)) continue;
      if (sample.assetId && sample.assetId === newestGenerated?.assetId) continue;
      seen.add(key);
      rows.push(sample);
    }
    return rows;
  })();
  const approvedHistoryId = historySamples.find(
    (sample) => sample.assetId && sample.assetId === currentPreviewAssetId,
  )?.id || "";
  const currentProviderLine = (() => {
    const provider = String(approvedVoice?.provider || "");
    const model = String(approvedVoice?.modelId || "");
    if (provider === "elevenlabs") {
      const modelLabel = model === "eleven_v4" ? "Eleven v4" : (model.replaceAll("_", " ") || "ElevenLabs");
      return `ElevenLabs · ${modelLabel}`;
    }
    if (provider === "local" || provider === "qwen3-tts") return "Local voice";
    return provider;
  })();

  return (
    <section className="voice-identity-panel" data-testid="voice-identity-panel">
      <div className="vip-identity-hero">
        <div className="vip-identity-portrait" data-testid="vip-character-portrait">
          {portraitUrl ? (
            <img src={portraitUrl} alt={selectedCharacterName || "Character"} />
          ) : (
            <div className="vip-identity-portrait-fallback">
              {(selectedCharacterName || "?").slice(0, 1).toUpperCase()}
            </div>
          )}
        </div>
        <div>
          <PanelHeading
            title={variant === "express" ? "Voice Creator" : "Voice Identity"}
            tip={
              variant === "express"
                ? "Create or assign this character's default voice. Timeline and Co-Director will use it automatically when the character speaks."
                : "Create, select, or approve this character's default voice."
            }
            as="h2"
          />
          <p className="muted">{selectedCharacterName || "Choose a character"}</p>
        </div>
      </div>

      {hasApprovedVoice && approvedVoice ? (
        <div className="vip-approved-banner" data-testid="vip-approved-voice">
          <div className="vip-approved-banner__header">
            <strong data-testid="vip-approved-title">
              {approvedVoiceBannerTitle(String(approvedVoice.name || ""), selectedCharacterName)}
            </strong>
            {approvedVoiceVersionLabel(approvedVoice.versionNumber) ? (
              <span className="vip-approved-version" data-testid="vip-approved-version">
                Current {approvedVoiceVersionLabel(approvedVoice.versionNumber)}
              </span>
            ) : (
              <span className="vip-approved-version" data-testid="vip-approved-version">Current</span>
            )}
          </div>
          <p className="muted" data-testid="vip-approved-subtitle">{approvedVoiceBannerSubtitle()}</p>
          {currentProviderLine ? (
            <p data-testid="vip-approved-provider">{currentProviderLine}</p>
          ) : null}
          {approvedVoice.audioUrl ? (
            <ApprovedVoicePlayer
              audioUrl={approvedVoice.audioUrl}
              label={String(approvedVoice.name || selectedCharacterName || "approved voice")}
            />
          ) : null}
          <div className="vip-approved-banner__actions">
            {unassignArmed ? (
              <>
                <p data-testid="vip-unassign-confirm-copy">{unassignVoiceConfirm(selectedCharacterName)}</p>
                <p className="muted">{unassignVoiceExplain(selectedCharacterName)}</p>
                <Button
                  data-testid="vip-unassign-confirm"
                  onClick={() => void handleUnassign()}
                >
                  Unassign
                </Button>
                <Button data-testid="vip-unassign-cancel" onClick={() => setUnassignArmed(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button
                data-testid="vip-unassign-voice"
                onClick={() => setUnassignArmed(true)}
              >
                Unassign
              </Button>
            )}
          </div>
          {previousApprovedVoices.length > 0 ? (
            <div className="vip-voice-history" data-testid="vip-voice-history">
              <p className="muted">Previous versions</p>
              {previousApprovedVoices.map((voice) => (
                <div key={String(voice.id)} className="vip-voice-history__row">
                  <span>
                    {String(voice.name || "Approved voice")}
                    {approvedVoiceVersionLabel(voice.version_number)
                      ? ` ${approvedVoiceVersionLabel(voice.version_number)}`
                      : ""}
                  </span>
                  <Button
                    data-testid={`vip-use-version-${voice.id}`}
                    disabled={approveState === "approving"}
                    onClick={() => void handleUseExisting(String(voice.id))}
                  >
                    Use this version
                  </Button>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : selectedCharacterId ? (
        <div className="vip-empty-voice" data-testid="vip-no-approved-voice">
          <strong>No approved default voice</strong>
          <p className="muted">{noApprovedDefaultVoiceMessage(selectedCharacterName)}</p>
        </div>
      ) : null}

      {errors.length > 0 && (
        <div className="vip-errors" data-testid="vip-errors">
          {errors.map((e, i) => (
            <p key={i} className="vip-error">
              {e}
            </p>
          ))}
        </div>
      )}

      <div className="vip-section" data-testid="voice-provider">
        <VoiceEngineLabel
          id="voice-provider"
          label="Voice Provider"
          projectId={projectId}
          characterId={selectedCharacterId}
          voiceProfileId={approvedVoice?.id}
          boundVoiceId={
            activeVoice?.provider === "elevenlabs" ? activeVoice?.providerVoiceId : undefined
          }
          boundVoiceName={
            activeVoice?.provider === "elevenlabs" ? activeVoice?.voiceName || activeVoice?.name : undefined
          }
          boundModelId={
            activeVoice?.provider === "elevenlabs" ? activeVoice?.providerModelId : undefined
          }
          showVoiceControls={false}
          onProviderChange={(next) => {
            voiceProvider.setSource(next);
            if (next === "elevenlabs") setMethod("elevenlabs");
            else if (method === "elevenlabs") setMethod(null);
            if (!selectedCharacterId) return;
            void api.activateCharacterVoiceProvider(projectId, selectedCharacterId, next).then(() => {
              void loadExistingVoices(selectedCharacterId, selectedCharacterName);
            }).catch((error: any) => {
              if (next === "elevenlabs") {
                onMsg(error?.message || "Choose an ElevenLabs voice and save it to this character.");
              }
            });
          }}
        />
      </div>

      {variant === "express" ? (
      <div className="vip-section" data-testid="vip-character-section">
        <span className="vip-label">
          Select Character
          <VoiceStudioSelect
            ariaLabel="Select Character"
            testId="vs-character-select"
            value={creatingCharacter ? "__new__" : selectedCharacterId}
            options={[
              { value: "", label: "Select a character..." },
              ...characters.map((c) => ({
                value: String(c.id),
                label: String(c.name || c.characterName || c.id),
              })),
              { value: "__new__", label: "Create New Character" },
            ]}
            onChange={(val) => {
              if (val === "__new__") {
                setCreatingCharacter(true);
              } else {
                setSelectedCharacterId(val);
                setCreatingCharacter(false);
                if (val) onCharacterChange?.(val);
              }
            }}
          />
        </span>
        {creatingCharacter && (
          <div className="vip-inline-create">
            <input
              className="vip-input"
              data-testid="vs-new-character-name"
              placeholder="New character name"
              value={newCharName}
              onChange={(e) => setNewCharName(e.target.value)}
            />
            <Button data-testid="vs-create-character-btn" onClick={handleCreateCharacter}>
              Create
            </Button>
          </div>
        )}
      </div>
      ) : null}

      <div className="vip-section" data-testid="vip-method-section">
        <PanelHeading title="Choose Voice Method" tip="Pick one way to get a voice." as="h3" />
        <VoiceMethodCards
          method={method}
          disabledReasons={
            voiceProvider.health && !voiceProvider.health.configured
              ? { elevenlabs: voiceProvider.health.message || "ElevenLabs API key not configured." }
              : undefined
          }
          onSelect={(next) => {
            setMethod(next);
            setErrors([]);
            if (next === "elevenlabs") voiceProvider.setSource("elevenlabs");
          }}
        />
      </div>

      {method === "elevenlabs" ? (
        <ElevenLabsVoiceWorkflow
          projectId={projectId}
          characterId={selectedCharacterId}
          configured={Boolean(voiceProvider.health?.configured)}
          savedVoiceId={activeVoice?.provider === "elevenlabs" ? String(activeVoice.providerVoiceId || "") : ""}
          savedVoiceName={activeVoice?.provider === "elevenlabs" ? String(activeVoice.voiceName || activeVoice.name || "") : ""}
          savedModelId={activeVoice?.provider === "elevenlabs" ? String(activeVoice.providerModelId || "") : ""}
          restoredSample={newestGenerated ? {
            assetId: newestGenerated.assetId,
            candidateId: newestGenerated.id && newestGenerated.id !== newestGenerated.assetId ? newestGenerated.id : "",
            voiceProfileId: newestGenerated.voiceProfileId,
            provider: "elevenlabs",
            modelId: newestGenerated.modelId,
            voiceName: newestGenerated.name,
            providerVoiceId: newestGenerated.providerVoiceId,
          } : null}
          approvedAssetId={currentPreviewAssetId}
          onSampleReady={() => {
            if (selectedCharacterId) void loadExistingVoices(selectedCharacterId, selectedCharacterName);
          }}
          onApproveSample={handleApprove}
          onSaved={() => {
            if (selectedCharacterId) void loadExistingVoices(selectedCharacterId, selectedCharacterName);
            onVoiceApproved?.();
            onRefresh?.();
          }}
          onMsg={onMsg}
        />
      ) : null}

      {method === "existing" && (
        <div className="vip-section" data-testid="vip-existing-section">
          {String(activeVoice?.approvedVoiceReferenceAssetId || "") ? (
            <div className="vip-existing-assigned" data-testid="vs-existing-assigned">
              <div className="vip-existing-assigned__header">
                <strong>Existing Voice</strong>
                <span className="vip-existing-assigned__state" data-testid="vs-existing-assigned-state">Assigned</span>
              </div>
              <p className="vip-existing-assigned__name" data-testid="vs-existing-assigned-name">
                {String(activeVoice?.approvedVoiceReferenceAssetName || "Library audio")}
              </p>
              <audio
                controls
                preload="metadata"
                className="vip-existing-assigned__player"
                data-testid="vs-existing-assigned-player"
                src={api.assetUrl(String(activeVoice.approvedVoiceReferenceAssetId), undefined, projectId)}
              />
            </div>
          ) : null}
          <span className="vip-label">
            Saved voices for {selectedCharacterName || "this character"}
            <VoiceStudioSelect
              ariaLabel="Saved voices"
              testId="vs-existing-voice"
              value={existingVoiceId}
              options={[
                { value: "", label: "Choose a saved voice…" },
                ...existingVoices.map((voice) => ({
                  value: String(voice.id),
                  label: [
                    voice.name || voice.id,
                    approvedVoiceVersionLabel(voice.version_number),
                    voice.id === approvedVoice?.id ? "current" : "",
                    voice.approval_status === "approved" && voice.id !== approvedVoice?.id ? "approved" : "",
                  ].filter(Boolean).join(" · "),
                })),
              ]}
              onChange={setExistingVoiceId}
            />
          </span>
          <div className="vip-actions">
            <Button
              variant="primary"
              data-testid="vs-use-existing"
              disabled={!existingVoiceId || approveState === "approving"}
              onClick={() => void handleUseExisting()}
            >
              {approveState === "approving" ? "Approving..." : "Use this voice"}
            </Button>
            <Button
              data-testid="vs-existing-library"
              disabled={assigningReference || !selectedCharacterId}
              onClick={() => setLibraryPickerOpen(true)}
            >
              {assigningReference ? "Assigning..." : "Select from Library"}
            </Button>
          </div>
          <p className="muted">
            Select from Library assigns a Project Library audio as this character's approved voice reference.
          </p>
        </div>
      )}

      {method === "clone" && (
        <div className="vip-section" data-testid="vip-clone-section">
          <label className="vip-label">
            Recording
            <input
              className="vip-input"
              type="file"
              accept="audio/*"
              data-testid="vs-clone-file"
              onChange={(e) => setCloneFile(e.target.files?.[0] || null)}
            />
          </label>
          <label className="vip-consent">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} data-testid="vs-consent" />
            I have permission to clone this recording for {selectedCharacterName || "this character"}.
          </label>
        </div>
      )}

      {method === "create" && (
        <div className="vip-section" data-testid="vip-basics-section">
          <PanelHeading title="Voice Basics" tip="Set the fundamental voice characteristics." as="h3" />
          <label className="vip-label">
            Sex
            <div className="vip-toggle-group" data-testid="vs-sex">
              <button type="button" className={"vip-toggle" + (sex === "female" ? " selected" : "")} onClick={() => setSex("female")}>
                Female
              </button>
              <button type="button" className={"vip-toggle" + (sex === "male" ? " selected" : "")} onClick={() => setSex("male")}>
                Male
              </button>
            </div>
          </label>
          <span className="vip-label">
            Age Range
            <VoiceStudioSelect
              ariaLabel="Age Range"
              testId="vs-age"
              value={age}
              options={AGE_OPTIONS.map((option) => ({ value: option, label: option }))}
              onChange={setAge}
            />
          </span>
        </div>
      )}

      {(method === "create" || method === "clone") && (
      <div className="vip-section" data-testid="vip-script-section">
        <label className="vip-label">
          Script / Sample Text
          <textarea
            className="vip-textarea"
            rows={3}
            data-testid="vs-script"
            placeholder="Enter the line the character should speak..."
            value={script}
            onChange={(e) => setScript(e.target.value)}
          />
        </label>
      </div>
      )}

      {method === "create" && (
        <div className="vip-section" data-testid="vip-prompt-section">
          <label className="vip-label">
            Voice Prompt Details
            <textarea
              className="vip-textarea"
              rows={3}
              data-testid="vs-prompt-details"
              placeholder="Describe what the voice should sound like..."
              value={promptDetails}
              onChange={(e) => setPromptDetails(e.target.value)}
            />
          </label>
          <div className="vip-actions">
            <Button data-testid="vs-refine-prompt" disabled={refineLoading || !promptDetails.trim()} onClick={handleRefinePrompt}>
              {refineLoading ? "Refining..." : "Refine with Co-Director"}
            </Button>
          </div>
          {refinePreview !== null && (
            <div className="vip-refine-preview" data-testid="vip-refine-preview">
              <p className="vip-refine-preview__text">{refinePreview}</p>
              <div className="vip-actions">
                <Button data-testid="vip-accept-refine" variant="primary" onClick={() => { setPromptDetails(refinePreview); setRefinePreview(null); }}>
                  Accept
                </Button>
                <Button data-testid="vip-reject-refine" onClick={() => setRefinePreview(null)}>
                  Reject
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {method === "create" && (
      <details
        className="vip-accordion"
        open={expanded}
        onToggle={(e) => setExpanded((e.target as HTMLDetailsElement).open)}
        data-testid="vs-advanced-controls"
      >
        <summary>Advanced Voice Controls</summary>
        <div className="vip-gauge" data-testid="vs-emotion">
          <label className="vip-gauge-label">Emotional Expression</label>
          <input type="range" min={-2} max={2} step={1} value={emotion} onChange={(e) => setEmotion(Number(e.target.value))} />
        </div>
        <div className="vip-gauge" data-testid="vs-intensity">
          <label className="vip-gauge-label">Emotional Intensity</label>
          <input type="range" min={-5} max={5} step={1} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} />
        </div>
        <div className="vip-gauge" data-testid="vs-speed">
          <label className="vip-gauge-label">Speaking Speed</label>
          <input type="range" min={-5} max={5} step={1} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} />
        </div>
        <div className="vip-gauge" data-testid="vs-pitch">
          <label className="vip-gauge-label">Pitch</label>
          <input type="range" min={-5} max={5} step={1} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} />
        </div>
      </details>
      )}

      {method === "create" && (
      <div className="vip-section" data-testid="vip-archetype-section">
        <span className="vip-label">
          Character Archetype
          <VoiceStudioSelect
            ariaLabel="Character Archetype"
            testId="vs-archetype"
            value={archetype}
            options={ARCHETYPES.map((option) => ({ value: option, label: option }))}
            onChange={setArchetype}
          />
        </span>
      </div>
      )}

      {method === "create" && (
      <div className="vip-section" data-testid="vip-accent-section">
        <span className="vip-label">
          Accent
          <VoiceStudioSelect
            ariaLabel="Accent"
            testId="vs-accent"
            value={accent}
            options={ACCENTS.map((option) => ({ value: option, label: option }))}
            onChange={setAccent}
          />
        </span>
      </div>
      )}

      {(method === "create" || method === "clone") && (
      <div className="vip-section" data-testid="vip-sample-count-section">
        <div className="vip-label">
          Number of Samples
          <div className="vip-sample-count-selector" data-testid="vs-sample-count">
            {([1, 2, 3, 4] as const).map((n) => (
              <button
                key={n}
                type="button"
                className={"vip-sample-count-btn" + (sampleCount === n ? " selected" : "")}
                aria-pressed={sampleCount === n}
                disabled={generationState === "generating"}
                onClick={() => {
                  sampleCountRef.current = n;
                  setSampleCount(n);
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
      </div>
      )}

      {(method === "create" || method === "clone" || generationState === "generating" || voiceJob?.status === "failed") && (
      <div className="vip-section" data-testid="vip-generate-section">
        {(method === "create" || method === "clone") && (
        <Button
          variant="primary"
          className="vip-generate-btn"
          data-testid="vs-generate"
          disabled={generationState === "generating"}
          onClick={handleGenerate}
        >
          {generationState === "generating" ? "GENERATING..." : "GENERATE VOICE SAMPLES"}
        </Button>
        )}
        {voiceJob && (generationState === "generating" || voiceJob.status === "failed" || voiceJob.status === "complete") ? (
          <div
            className={"vip-progress" + (voiceJob.status === "failed" ? " vip-progress--failed" : "")}
            data-testid="vs-generate-progress"
            data-status={voiceJob.status || ""}
            data-phase={voiceJob.phase || ""}
          >
            <p className="vip-progress__title">
              {voiceJob.status === "failed"
                ? "Voice generation failed"
                : voiceJob.status === "complete"
                  ? "Voice samples ready"
                  : "Generating voice samples"}
            </p>
            <div
              className="vip-progress__track"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.max(0, Math.min(100, Number(voiceJob.percent || 0)))}
            >
              <div
                className="vip-progress__fill"
                style={{ width: `${Math.max(0, Math.min(100, Number(voiceJob.percent || 0)))}%` }}
              />
            </div>
            <p className="vip-progress__pct">{Math.round(Number(voiceJob.percent || 0))}%</p>
            <p className="vip-progress__status" data-testid="vs-generate-status">
              {voiceJob.status === "failed"
                ? String(voiceJob.error || "Voice generation failed.")
                : voiceJob.label || "Generating voice samples"}
            </p>
            {Number(voiceJob.sampleCount || 0) > 0 && voiceJob.status !== "failed" ? (
              <p className="vip-progress__samples">
                Sample {Math.max(Number(voiceJob.sampleIndex || voiceJob.completedSamples || 0), 0)} of {Number(voiceJob.sampleCount)}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
      )}

      {historySamples.length > 0 && (
        <VoiceSamplePlayers
          samples={historySamples}
          characterName={selectedCharacterName}
          approvedSampleId={approvedHistoryId}
          onApprove={(sample) => { void handleApprove(sample); }}
          approveDisabled={approveState === "approving"}
          replacingApproved={hasApprovedVoice}
        />
      )}

      {variant === "express" && onOpenFullStudio ? (
        <div className="vip-section vip-express-footer">
          <Button
            data-testid="voice-creator-open-full-studio"
            onClick={() => onOpenFullStudio(selectedCharacterId)}
          >
            Open Full Voice Studio
          </Button>
        </div>
      ) : null}

      {libraryPickerOpen ? (
        <AddFromProjectLibraryModal
          project={libraryModalProject(projectId, selectedCharacterName)}
          alreadyIds={
            String(activeVoice?.approvedVoiceReferenceAssetId || "")
              ? [String(activeVoice.approvedVoiceReferenceAssetId)]
              : []
          }
          mediaKind="audio"
          single
          confirmLabel="Use this Voice"
          onAdd={(ids) => {
            setLibraryPickerOpen(false);
            const next = ids[0] || "";
            if (next) void handleAssignLibraryVoice(next);
          }}
          onClose={() => setLibraryPickerOpen(false)}
        />
      ) : null}
    </section>
  );
}
