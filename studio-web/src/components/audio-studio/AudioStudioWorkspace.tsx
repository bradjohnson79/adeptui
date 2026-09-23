import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { findSameTrackIntersection } from "../../timelineMaster/sameTrackNoOverlap";
import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import "./../../styles/audio-studio/audio-studio.css";
import { AmbiencePanel } from "./AmbiencePanel";
import { approvedIdsFromBatches, classifyLibraryAudio, extractCandidates, latestBatchForKind, probeAudioDurationSec } from "./audioStudioCandidates";
import { audioTabFromSearch, sourceStatusFromProviders, withAudioTab } from "./audioStudioSource";
import { MusicPanel } from "./MusicPanel";
import { ProjectAudioPanel } from "./ProjectAudioPanel";
import { SfxPanel } from "./SfxPanel";
import { defaultSfxIntent, toGenerateIntentPayload, type SfxDirectorIntent } from "./sfxIntent";
import { ProviderSourceSelector } from "../audioProvider/ProviderSourceSelector";
import { useAudioStudioProviderSource } from "../../audioProvider/useProviderSource";
import type {
  AudioCandidate,
  AudioGenerationProgress,
  AudioLibraryAsset,
  AudioStudioGenerationKind,
  AudioStudioTab,
  AudioStudioTrack,
  AudioStudioWorkspaceProps,
} from "./types";

const TAB_LABELS: { id: AudioStudioTab; label: string }[] = [
  { id: "music", label: "Music" },
  { id: "sfx", label: "Sound Effects" },
  { id: "ambience", label: "Ambience" },
  { id: "library", label: "Project Audio" },
];

function firstString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function firstNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return undefined;
}

function asArray(value: unknown): any[] {
  return Array.isArray(value) ? value : [];
}

function normalizeAsset(asset: any): AudioLibraryAsset {
  const normalized = asset || {};
  return {
    ...normalized,
    kind: normalized.kind || "audio",
    title: firstString(normalized.title, normalized.tag, normalized.filename, normalized.name),
    url: firstString(normalized.url, normalized.file_url, normalized.previewUrl, normalized.preview_url) || api.assetUrl(normalized.id),
    durationSec: firstNumber(normalized.durationSec, normalized.duration_sec, normalized.length, normalized.seconds),
  };
}

export function AudioStudioWorkspace({ project, onChange, onGo }: AudioStudioWorkspaceProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const tab = audioTabFromSearch(location.search);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [generationProgress, setGenerationProgress] = useState<AudioGenerationProgress | null>(null);
  const [generatingKind, setGeneratingKind] = useState<AudioStudioGenerationKind | null>(null);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [projectAudio, setProjectAudio] = useState<AudioLibraryAsset[]>([]);
  const [previewSelection, setPreviewSelection] = useState<{ assetId?: string; title: string; url?: string; track: AudioStudioTrack } | null>(null);
  const [approvedAssetIds, setApprovedAssetIds] = useState<Record<string, boolean>>({});
  const [musicCandidates, setMusicCandidates] = useState<AudioCandidate[]>([]);
  const [sfxCandidates, setSfxCandidates] = useState<AudioCandidate[]>([]);
  const [ambienceCandidates, setAmbienceCandidates] = useState<AudioCandidate[]>([]);
  const [musicSource, setMusicSource] = useState(() => sourceStatusFromProviders("music", {}));
  const [soundSource, setSoundSource] = useState(() => sourceStatusFromProviders("sfx", {}));
  const audioProvider = useAudioStudioProviderSource();

  const elevenLabsPanel = (() => {
    if (audioProvider.source !== "elevenlabs") return null;
    const health = audioProvider.health;
    if (audioProvider.healthBusy && !health) {
      return { ready: false, label: "Checking API — ElevenLabs…" };
    }
    if (!health?.configured) {
      return { ready: false, label: "API — ElevenLabs unavailable" };
    }
    const fail = ["error", "fail", "failed", "unreachable", "offline"].some((s) =>
      String(health.connectionStatus || "").toLowerCase().includes(s),
    );
    if (fail) return { ready: false, label: "API — ElevenLabs route failed" };
    return { ready: true, label: "API — ElevenLabs" };
  })();

  const [musicMood, setMusicMood] = useState("Tense");
  const [musicGenre, setMusicGenre] = useState("Orchestral");
  const [musicDuration, setMusicDuration] = useState(8);
  const [musicEnergy, setMusicEnergy] = useState("Rising");
  const [musicInstrumentation, setMusicInstrumentation] = useState("");
  const [musicLoop, setMusicLoop] = useState(false);
  const [musicPrompt, setMusicPrompt] = useState("");
  const [musicCount, setMusicCount] = useState<1 | 2 | 3>(1);

  const [sfxDuration, setSfxDuration] = useState(3);
  const [sfxIntensity, setSfxIntensity] = useState("Normal");
  const [sfxEventType, setSfxEventType] = useState("");
  const [sfxPrompt, setSfxPrompt] = useState("");
  const [sfxCount, setSfxCount] = useState<1 | 2 | 3>(1);
  const [sfxAdvancedOpen, setSfxAdvancedOpen] = useState(false);
  const [sfxIntent, setSfxIntent] = useState<SfxDirectorIntent>(() =>
    defaultSfxIntent({ durationSec: 3, intensity: "Normal" }),
  );
  const [sfxRefiningOp, setSfxRefiningOp] = useState<string | null>(null);

  const [ambienceDuration, setAmbienceDuration] = useState(8);
  const [ambienceIntensity, setAmbienceIntensity] = useState("Quiet");
  const [ambienceLoop, setAmbienceLoop] = useState(true);
  const [ambiencePrompt, setAmbiencePrompt] = useState("");
  const [ambienceCount, setAmbienceCount] = useState<1 | 2 | 3>(1);

  const previewAssetId = previewSelection?.assetId || null;

  const setTab = (next: AudioStudioTab) => {
    const search = withAudioTab(location.search, next);
    if (search !== location.search) {
      navigate({ pathname: location.pathname, search }, { replace: true });
    }
  };

  const refreshLibrary = async () => {
    const response = await api.library(project.id).catch(() => null);
    const next = asArray(response?.items).map(normalizeAsset).filter((asset) => {
      const kind = String(asset.kind || "").toLowerCase();
      return kind === "audio" || kind === "voice" || String(asset.libraryKey || "").startsWith("audio");
    });
    setProjectAudio(next);
    return next;
  };

  const applyBatch = (batch: any, kind: AudioStudioGenerationKind) => {
    const next = extractCandidates(batch, kind);
    if (kind === "music") setMusicCandidates(next);
    if (kind === "sfx") setSfxCandidates(next);
    if (kind === "ambience") setAmbienceCandidates(next);
    return next;
  };

  const hydrateWorkspace = async () => {
    const [workspace, musicProviders, soundProviders] = await Promise.all([
      api.audioStudioWorkspace(project.id).catch(() => null),
      api.audioStudioProviders(project.id, "music").catch(() => null),
      api.audioStudioProviders(project.id, "sfx").catch(() => null),
    ]);
    const musicPayload = musicProviders || workspace?.providers || null;
    const soundPayload = soundProviders || workspace?.providers || musicPayload;
    if (musicPayload) setMusicSource(sourceStatusFromProviders("music", musicPayload));
    if (soundPayload) setSoundSource(sourceStatusFromProviders("sfx", soundPayload));
    if (!workspace) return;
    const batches = asArray(workspace.batches);
    setApprovedAssetIds(approvedIdsFromBatches(batches));
    const music = latestBatchForKind(batches, "music");
    const sfx = latestBatchForKind(batches, "sfx");
    const ambience = latestBatchForKind(batches, "ambience");
    if (music) applyBatch(music, "music");
    if (sfx) applyBatch(sfx, "sfx");
    if (ambience) applyBatch(ambience, "ambience");
    const library = asArray(workspace.library).map(normalizeAsset);
    if (library.length) setProjectAudio(library);
  };

  useEffect(() => {
    void refreshLibrary();
    void hydrateWorkspace();
  }, [project.id]);

  const tabCountLabel = useMemo(() => {
    if (tab === "music") return `${musicCandidates.length} tracks`;
    if (tab === "sfx") return `${sfxCandidates.length} sounds`;
    if (tab === "ambience") return `${ambienceCandidates.length} beds`;
    return `${projectAudio.length} saved`;
  }, [ambienceCandidates.length, musicCandidates.length, projectAudio.length, sfxCandidates.length, tab]);

  const selectPreview = (asset: { id?: string; assetId?: string; title?: string; url?: string; audioUrl?: string }, track: AudioStudioTrack) => {
    const assetId = asset.assetId || "";
    setPreviewSelection({
      assetId: assetId || undefined,
      title: asset.title || "Selected audio",
      url: asset.audioUrl || asset.url || (assetId ? api.assetUrl(assetId) : ""),
      track,
    });
  };

  const applyProgressFromBatch = (batch: any, kind: AudioStudioGenerationKind) => {
    const progress = batch?.progress || {};
    const total = Number(progress.total || (batch?.candidates || []).length || 1);
    const completed = Number(progress.completed || 0);
    const percent = Number(progress.percent ?? Math.round((100 * completed) / Math.max(1, total)));
    const statusValue = String(batch?.status || progress.status || "");
    const active = statusValue === "queued" || statusValue === "running";
    setGenerationProgress({
      visible: true,
      active,
      percent: Number.isFinite(percent) ? percent : 0,
      label: String(progress.label || (active ? "Generating…" : "Complete")),
      completed,
      total,
      batchId: String(batch?.id || ""),
    });
    applyBatch(batch, kind);
  };

  const pollBatchUntilComplete = async (batchId: string, kind: AudioStudioGenerationKind) => {
    const started = Date.now();
    const timeoutMs = 15 * 60 * 1000;
    while (Date.now() - started < timeoutMs) {
      const batch = await api.audioStudioGetBatch(project.id, batchId);
      applyProgressFromBatch(batch, kind);
      const statusValue = String(batch?.status || "");
      if (statusValue === "complete" || statusValue === "failed" || statusValue === "cancelled") {
        return batch;
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("Generation timed out while waiting for the takes to finish.");
  };

  const cancelGeneration = async () => {
    if (cancelling) return;
    setCancelling(true);
    try {
      if (activeBatchId) {
        const result = await api.audioStudioCancelBatch(project.id, activeBatchId);
        applyProgressFromBatch(result?.batch || result, generatingKind || "music");
        setStatus("Stopped. The worker was cancelled.");
      } else {
        await api.audioStudioCancelGenerations(project.id);
        setStatus("Stopped in-progress audio work.");
      }
      setGenerationProgress((current) => current ? { ...current, active: false, label: "Cancelled" } : current);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not cancel.");
    } finally {
      setCancelling(false);
      setBusy(false);
      setGeneratingKind(null);
      setActiveBatchId(null);
    }
  };

  const generateForKind = async (kind: AudioStudioGenerationKind) => {
    if (audioProvider.source === "elevenlabs") {
      const health = audioProvider.health || (await audioProvider.refreshHealth());
      if (!health?.configured) {
        setStatus(health?.message || "API — ElevenLabs is unavailable. Configure fal, Kie, or WaveSpeed in Setup Wizard → Hosted Providers. Generation blocked — Local is not used as a silent fallback.");
        return;
      }
      const fail = ["error", "fail", "failed", "unreachable", "offline"].some((s) =>
        String(health.connectionStatus || "").toLowerCase().includes(s),
      );
      if (fail) {
        setStatus(health.message || "API — ElevenLabs route failed. Generation blocked — Local is not used as a silent fallback.");
        return;
      }
    } else {
      const source = kind === "music" ? musicSource : soundSource;
      if (!source.ready) {
        setStatus(`${source.label} is not ready. ${source.detail}`);
        return;
      }
    }
    setBusy(true);
    setGeneratingKind(kind);
    setStatus("");
    setActiveBatchId(null);
    const count = kind === "music" ? musicCount : kind === "sfx" ? sfxCount : ambienceCount;
    setGenerationProgress({
      visible: true,
      active: true,
      percent: 0,
      label: "Starting…",
      completed: 0,
      total: count,
    });
    try {
      const payload =
        kind === "music"
          ? {
              prompt: musicPrompt,
              durationSec: musicDuration,
              mood: musicMood,
              genre: musicGenre,
              energy: musicEnergy,
              instrumentation: musicInstrumentation,
              loop: musicLoop,
              candidateCount: musicCount,
              asyncMode: true,
              allowProviderSwitch: false,
              allowCpuFallback: false,
            }
          : kind === "sfx"
            ? (() => {
                const intentPayload = toGenerateIntentPayload(sfxIntent, {
                  prompt: sfxPrompt,
                  eventType: sfxEventType,
                  durationSec: sfxDuration,
                  intensity: sfxIntensity,
                  candidateCount: sfxCount,
                });
                return {
                  prompt: sfxPrompt,
                  durationSec: sfxDuration,
                  category: "sfx",
                  intensity: sfxIntensity,
                  eventType: intentPayload.physicalEvent || undefined,
                  physicalEvent: intentPayload.physicalEvent || undefined,
                  material: intentPayload.material,
                  context: intentPayload.context,
                  temporal: intentPayload.temporal,
                  negatives: intentPayload.negatives,
                  distance: intentPayload.distance,
                  environment: intentPayload.environment,
                  reverb: intentPayload.reverb,
                  perspective: intentPayload.perspective,
                  adherence: intentPayload.adherence,
                  loop: false,
                  candidateCount: sfxCount,
                  asyncMode: true,
                  allowProviderSwitch: false,
                  allowCpuFallback: false,
                  intent: intentPayload,
                  sfxIntent: intentPayload,
                };
              })()
            : {
                prompt: ambiencePrompt,
                durationSec: ambienceDuration,
                category: "ambience",
                intensity: ambienceIntensity,
                loop: ambienceLoop,
                loopRequired: true,
                candidateCount: ambienceCount,
                asyncMode: true,
                allowProviderSwitch: false,
                allowCpuFallback: false,
              };

      const started = await api.audioStudioGenerate(project.id, {
        kind,
        ...payload,
        ...(audioProvider.source === "elevenlabs"
          ? { preferredProvider: "elevenlabs", allowProviderSwitch: false, allowCpuFallback: false }
          : {}),
      });
      applyProgressFromBatch(started, kind);
      const batchId = String(started?.id || "");
      if (batchId) setActiveBatchId(batchId);
      const result = batchId ? await pollBatchUntilComplete(batchId, kind) : started;
      await refreshLibrary();
      const nextCandidates = extractCandidates(result, kind);
      applyBatch(result, kind);

      if (String(result?.status || "") === "cancelled") {
        setStatus("Stopped. The worker was cancelled.");
        return;
      }

      const ready = nextCandidates.find((c) => c.assetId && c.status !== "failed" && c.status !== "cancelled");
      if (ready) {
        selectPreview(ready, kind);
        if (ready.batchId) {
          await api.audioStudioSelectCandidate(project.id, ready.batchId, ready.id);
        }
      }
      const failed = nextCandidates.filter((c) => c.status === "failed").length;
      const engine = kind === "music" ? musicSource.label : soundSource.label;
      if (!nextCandidates.length) {
        setStatus(`${engine} finished without a playable take.`);
      } else if (failed) {
        setStatus(`${engine}: ${nextCandidates.length - failed} ready, ${failed} failed. Nothing was swapped silently.`);
      } else {
        setStatus(`${engine} finished. Play a take, then approve the one you want.`);
      }
      setGenerationProgress({
        visible: true,
        active: false,
        percent: 100,
        label: failed ? `Finished with ${failed} failure(s)` : "Complete",
        completed: nextCandidates.length,
        total: nextCandidates.length || count,
        batchId,
      });
      await onChange?.();
    } catch (error) {
      const engine = kind === "music" ? musicSource.label : soundSource.label;
      setStatus(error instanceof Error ? `${engine}: ${error.message}` : `${engine} could not generate.`);
      setGenerationProgress((current) =>
        current ? { ...current, active: false, label: error instanceof Error ? error.message : "Generation failed" } : null,
      );
    } finally {
      setBusy(false);
      setGeneratingKind(null);
      setActiveBatchId(null);
    }
  }

  const refineSfxIntent = async (op: string) => {
    if (!sfxPrompt.trim()) {
      setStatus("Type What happens before refining.");
      return;
    }
    setBusy(true);
    setSfxRefiningOp(op);
    setStatus(`Refining (${op})…`);
    const intentPayload = toGenerateIntentPayload(sfxIntent, {
      prompt: sfxPrompt,
      eventType: sfxEventType,
      durationSec: sfxDuration,
      intensity: sfxIntensity,
      candidateCount: sfxCount,
    });
    const selected =
      sfxCandidates.find((c) => (c.assetId || c.id) === previewAssetId) ||
      sfxCandidates.find((c) => c.status !== "failed") ||
      sfxCandidates[0];
    const batchId = String(selected?.batchId || activeBatchId || "");
    const candidateId = String(selected?.id || "");
    try {
      let mutateResult: Record<string, unknown> | null = null;
      if (batchId && candidateId) {
        try {
          mutateResult = await api.audioStudioMutateSfxCandidateIntent(project.id, batchId, candidateId, {
            op,
            generate: true,
            candidateCount: sfxCount,
            intent: intentPayload,
          });
        } catch (candidateErr: any) {
          const msg = String(candidateErr?.message || candidateErr || "");
          const status = Number(candidateErr?.status || candidateErr?.statusCode || 0);
          if (!(status === 404 || /404|not found/i.test(msg))) throw candidateErr;
          // Candidate convenience route not live yet — fall back to ratified /sfx/mutate-intent.
          mutateResult = await api.audioStudioMutateSfxIntent(project.id, {
            intent: intentPayload,
            op,
            generate: true,
            candidateCount: sfxCount,
          });
        }
      } else {
        mutateResult = await api.audioStudioMutateSfxIntent(project.id, {
          intent: intentPayload,
          op,
          generate: true,
          candidateCount: sfxCount,
        });
      }

      const patched =
        (mutateResult?.patchedIntent as SfxDirectorIntent | undefined) ||
        (mutateResult?.intent as SfxDirectorIntent | undefined) ||
        null;
      if (patched && typeof patched === "object") {
        const merged: SfxDirectorIntent = {
          ...defaultSfxIntent({ durationSec: sfxDuration, intensity: sfxIntensity }),
          ...sfxIntent,
          ...patched,
          temporal: {
            ...sfxIntent.temporal,
            ...(patched.temporal || {}),
            durationSec: Number(patched.temporal?.durationSec ?? sfxDuration),
          },
          negatives: Array.isArray(patched.negatives) ? patched.negatives.map(String) : sfxIntent.negatives,
          refinementOps: Array.isArray(patched.refinementOps)
            ? patched.refinementOps.map(String)
            : sfxIntent.refinementOps,
        };
        setSfxIntent(merged);
        if (merged.physicalEvent) setSfxEventType(merged.physicalEvent);
        if (merged.temporal?.durationSec) setSfxDuration(Number(merged.temporal.durationSec));
        if (merged.intensity) {
          const label = String(merged.intensity).charAt(0).toUpperCase() + String(merged.intensity).slice(1);
          if (["Subtle", "Normal", "Bold", "Aggressive"].includes(label)) setSfxIntensity(label === "Aggressive" ? "Bold" : label);
        }
      }

      const returnedBatch = mutateResult?.batch as Record<string, unknown> | undefined;
      const returnedBatchId = String(mutateResult?.batchId || returnedBatch?.id || "");
      if (returnedBatchId || returnedBatch) {
        const batch = returnedBatch || (await api.audioStudioGetBatch(project.id, returnedBatchId));
        applyProgressFromBatch(batch, "sfx");
        if (returnedBatchId) setActiveBatchId(returnedBatchId);
        const result = returnedBatchId ? await pollBatchUntilComplete(returnedBatchId, "sfx") : batch;
        await refreshLibrary();
        applyBatch(result, "sfx");
        setStatus(`Refined (${op}) via mutate-intent.`);
        return;
      }

      // Routes may return patched intent only — regenerate with patched structure; do not rewrite What happens.
      setStatus(`Intent updated (${op}). Generating…`);
      const nextIntent = patched
        ? {
            ...sfxIntent,
            ...patched,
            temporal: {
              ...sfxIntent.temporal,
              ...(patched.temporal || {}),
              durationSec: Number(patched.temporal?.durationSec ?? sfxDuration),
            },
          }
        : sfxIntent;
      const genIntent = toGenerateIntentPayload(nextIntent as SfxDirectorIntent, {
        prompt: sfxPrompt,
        eventType: (nextIntent as SfxDirectorIntent).physicalEvent || sfxEventType,
        durationSec: Number((nextIntent as SfxDirectorIntent).temporal?.durationSec ?? sfxDuration),
        intensity: sfxIntensity,
        candidateCount: sfxCount,
      });
      setGeneratingKind("sfx");
      setGenerationProgress({
        visible: true,
        active: true,
        percent: 0,
        label: "Starting…",
        completed: 0,
        total: sfxCount,
      });
      const started = await api.audioStudioGenerate(project.id, {
        kind: "sfx",
        prompt: sfxPrompt,
        durationSec: genIntent.temporal?.durationSec || sfxDuration,
        category: "sfx",
        intensity: sfxIntensity,
        eventType: genIntent.physicalEvent || undefined,
        physicalEvent: genIntent.physicalEvent || undefined,
        material: genIntent.material,
        context: genIntent.context,
        temporal: genIntent.temporal,
        negatives: genIntent.negatives,
        distance: genIntent.distance,
        environment: genIntent.environment,
        reverb: genIntent.reverb,
        perspective: genIntent.perspective,
        adherence: genIntent.adherence,
        loop: false,
        candidateCount: sfxCount,
        asyncMode: true,
        allowProviderSwitch: false,
        allowCpuFallback: false,
        intent: genIntent,
        sfxIntent: genIntent,
      });
      applyProgressFromBatch(started, "sfx");
      const batchIdNext = String(started?.id || "");
      if (batchIdNext) setActiveBatchId(batchIdNext);
      const result = batchIdNext ? await pollBatchUntilComplete(batchIdNext, "sfx") : started;
      await refreshLibrary();
      applyBatch(result, "sfx");
      setStatus(`Refined (${op}) and regenerated.`);
    } catch (error: any) {
      const msg = String(error?.message || error || "");
      if (/404|not found|Failed to fetch/i.test(msg) || error?.status === 404) {
        setStatus("Refine pending: Systems mutate-intent route not live yet. Advanced fields still send on Generate.");
      } else {
        setStatus(error instanceof Error ? error.message : `Refine failed (${op}).`);
      }
    } finally {
      setSfxRefiningOp(null);
      setBusy(false);
    }
  };
;

;

  const selectForPreview = async (candidate: AudioCandidate, track: AudioStudioTrack) => {
    selectPreview(candidate, track);
    if (candidate.batchId && candidate.id) {
      try {
        await api.audioStudioSelectCandidate(project.id, candidate.batchId, candidate.id);
        setStatus(`Selected ${candidate.title}. Approval is still separate.`);
      } catch {
        /* preview still works locally */
      }
    }
  };

  const approveAsset = async (asset: AudioLibraryAsset | AudioCandidate) => {
    const candidate = asset as AudioCandidate;
    const assetId = candidate.assetId || asset.id;
    if (!assetId) {
      setStatus("This take does not have a saved file yet.");
      return;
    }
    if (!candidate.batchId || !candidate.id) {
      setStatus("Approve is for a generated take. This clip is already in the project shelf.");
      return;
    }

    setBusy(true);
    setStatus("");
    try {
      const approved = await api.audioStudioApproveCandidate(project.id, candidate.batchId, candidate.id);
      const nextId = String(approved?.assetId || assetId);
      setApprovedAssetIds((current) => ({ ...current, [nextId]: true, [assetId]: true }));
      setStatus("Approved. It now lives on this project’s audio shelf.");
      await onChange?.();
      await refreshLibrary();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Approve failed.");
    } finally {
      setBusy(false);
    }
  };

  const addToTimeline = async (asset: AudioLibraryAsset | AudioCandidate, fallbackTrack: AudioStudioTrack) => {
    const assetId = asset.assetId || asset.id;
    if (!assetId) {
      setStatus("This take needs a saved file before it can go on the Timeline.");
      return;
    }

    setBusy(true);
    setStatus("");
    try {
      const classified = classifyLibraryAudio(asset);
      const track: AudioStudioTrack =
        classified === "sfx" || classified === "ambience" || classified === "music" ? classified : fallbackTrack;
      await api.audioStudioPlace(project.id, {
        assetId,
        category: track,
        startMs: 0,
        loop: Boolean((asset as AudioCandidate).loop || track === "ambience"),
      });
      const sceneId = project.scenes?.[0]?.id;
      if (!sceneId) {
        setStatus("Approved and saved. This project has no scene yet, so Timeline cannot hold the clip.");
        return;
      }
      // SINGLE-STORE: legacy getDirector no longer needed for clip add.
      const measured = await probeAudioDurationSec(
        firstString((asset as AudioCandidate).audioUrl, (asset as AudioLibraryAsset).url) ||
          (assetId ? api.assetUrl(assetId) : ""),
      );
      const duration =
        firstNumber(asset.durationSec, (asset as AudioLibraryAsset).duration_sec, measured, 5) || 5;
      const label =
        firstString(asset.title, (asset as AudioLibraryAsset).tag, (asset as AudioLibraryAsset).filename) ||
        (track === "sfx" ? "SFX" : track === "ambience" ? "Bed" : "Music");
      const clip = {
        id: `clip-${crypto.randomUUID?.() || Math.random().toString(36).slice(2, 10)}`,
        asset_id: assetId,
        start: 0,
        length: duration,
        label,
        volume: 1,
      };
      // SINGLE-STORE: audio/sfx clips persist to Master batch clip arrays.
      // PUT /director is retired (410 Gone).
      const masterResp = await api.directorTimelineMaster(project.id, sceneId);
      const master = masterResp?.master;
      const batches = [...(master?.batchBlocks || [])].sort((a, b) => a.order - b.order);
      const root = batches[0];
      if (!root) {
        setStatus("Timeline has no execution windows yet. Rematerialize windows before adding audio.");
        return;
      }
      if (track === "sfx") {
        const clips = [...(root.sfxClips || [])];
        clip.start = Math.max(0, ...clips.map((item: any) => Number(item.start || 0) + Number(item.length || 0)), 0);
        if (findSameTrackIntersection(clips, clip)) {
          setStatus("Cannot add to Timeline — that time is already occupied on the SFX track.");
          return;
        }
        await api.directorTimelinePatchBatch(project.id, sceneId, root.id, {
          sfxClips: [...clips, clip],
        });
      } else {
        const clips = [...(root.audioClips || [])];
        clip.start = Math.max(0, ...clips.map((item: any) => Number(item.start || 0) + Number(item.length || 0)), 0);
        if (findSameTrackIntersection(clips, clip)) {
          setStatus("Cannot add to Timeline — that time is already occupied on the Audio track.");
          return;
        }
        await api.directorTimelinePatchBatch(project.id, sceneId, root.id, {
          audioClips: [...clips, clip],
        });
      }
      setStatus(`Added to the ${track === "sfx" ? "SFX" : "Audio"} track.`);
      await onChange?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not add to Timeline.");
    } finally {
      setBusy(false);
    }
  };

  const currentPanel = (() => {
    if (tab === "music") {
      return (
        <MusicPanel
          busy={busy}
          sourceReady={elevenLabsPanel ? elevenLabsPanel.ready : musicSource.ready}
          sourceLabel={
            elevenLabsPanel
              ? elevenLabsPanel.label
              : musicSource.ready
                ? musicSource.label
                : musicSource.checking
                  ? `Checking ${musicSource.label}`
                  : `${musicSource.label} unavailable`
          }
          mood={musicMood}
          genre={musicGenre}
          durationSec={musicDuration}
          energy={musicEnergy}
          instrumentation={musicInstrumentation}
          loop={musicLoop}
          prompt={musicPrompt}
          candidateCount={musicCount}
          candidates={musicCandidates}
          previewAssetId={previewAssetId}
          approvedAssetIds={approvedAssetIds}
          onMoodChange={setMusicMood}
          onGenreChange={setMusicGenre}
          onDurationChange={setMusicDuration}
          onEnergyChange={setMusicEnergy}
          onInstrumentationChange={setMusicInstrumentation}
          onLoopChange={setMusicLoop}
          onPromptChange={setMusicPrompt}
          onCandidateCountChange={setMusicCount}
          generationProgress={
            generatingKind === "music" || (tab === "music" && generationProgress?.visible)
              ? generationProgress
              : null
          }
          onGenerate={() => generateForKind("music")}
          onCancelGeneration={
            generatingKind === "music" && (busy || Boolean(activeBatchId))
              ? () => cancelGeneration()
              : undefined
          }
          onPreview={(candidate) => void selectForPreview(candidate, "music")}
          onApprove={approveAsset}
          onAddToTimeline={(candidate) => addToTimeline(candidate, "music")}
        />
      );
    }
    if (tab === "sfx") {
      return (
        <SfxPanel
          busy={busy}
          sourceReady={elevenLabsPanel ? elevenLabsPanel.ready : soundSource.ready}
          sourceLabel={
            elevenLabsPanel
              ? elevenLabsPanel.label
              : soundSource.ready
                ? soundSource.label
                : soundSource.checking
                  ? `Checking ${soundSource.label}`
                  : `${soundSource.label} unavailable`
          }
          generationProgress={
            generatingKind === "sfx" || (tab === "sfx" && generationProgress?.visible)
              ? generationProgress
              : null
          }
          durationSec={sfxDuration}
          intensity={sfxIntensity}
          eventType={sfxEventType}
          prompt={sfxPrompt}
          candidateCount={sfxCount}
          intent={sfxIntent}
          advancedOpen={sfxAdvancedOpen}
          refiningOp={sfxRefiningOp}
          candidates={sfxCandidates}
          previewAssetId={previewAssetId}
          approvedAssetIds={approvedAssetIds}
          onDurationChange={setSfxDuration}
          onIntensityChange={setSfxIntensity}
          onEventTypeChange={setSfxEventType}
          onPromptChange={setSfxPrompt}
          onCandidateCountChange={setSfxCount}
          onIntentChange={setSfxIntent}
          onAdvancedToggle={() => setSfxAdvancedOpen((open) => !open)}
          onGenerate={() => generateForKind("sfx")}
          onRefine={(op) => refineSfxIntent(op)}
          onCancelGeneration={
            generatingKind === "sfx" && (busy || Boolean(activeBatchId))
              ? () => cancelGeneration()
              : undefined
          }
          onPreview={(candidate) => void selectForPreview(candidate, "sfx")}
          onApprove={approveAsset}
          onAddToTimeline={(candidate) => addToTimeline(candidate, "sfx")}
        />
      );
    }
    if (tab === "ambience") {
      return (
        <AmbiencePanel
          busy={busy}
          sourceReady={elevenLabsPanel ? elevenLabsPanel.ready : soundSource.ready}
          sourceLabel={
            elevenLabsPanel
              ? elevenLabsPanel.label
              : soundSource.ready
                ? soundSource.label
                : soundSource.checking
                  ? `Checking ${soundSource.label}`
                  : `${soundSource.label} unavailable`
          }
          generationProgress={
            generatingKind === "ambience" || (tab === "ambience" && generationProgress?.visible)
              ? generationProgress
              : null
          }
          durationSec={ambienceDuration}
          intensity={ambienceIntensity}
          loop={ambienceLoop}
          prompt={ambiencePrompt}
          candidateCount={ambienceCount}
          candidates={ambienceCandidates}
          previewAssetId={previewAssetId}
          approvedAssetIds={approvedAssetIds}
          onDurationChange={setAmbienceDuration}
          onIntensityChange={setAmbienceIntensity}
          onLoopChange={setAmbienceLoop}
          onPromptChange={setAmbiencePrompt}
          onCandidateCountChange={setAmbienceCount}
          onGenerate={() => generateForKind("ambience")}
          onCancelGeneration={
            generatingKind === "ambience" && (busy || Boolean(activeBatchId))
              ? () => cancelGeneration()
              : undefined
          }
          onPreview={(candidate) => void selectForPreview(candidate, "ambience")}
          onApprove={approveAsset}
          onAddToTimeline={(candidate) => addToTimeline(candidate, "ambience")}
        />
      );
    }

    return (
      <ProjectAudioPanel
        assets={projectAudio}
        busy={busy}
        approvedAssetIds={approvedAssetIds}
        onAddToTimeline={(asset) => addToTimeline(asset, classifyLibraryAudio(asset) === "sfx" ? "sfx" : classifyLibraryAudio(asset) === "ambience" ? "ambience" : "music")}
        onGoLibrary={() => onGo("library")}
        onGoTimeline={() => onGo("timeline")}
      />
    );
  })();

  return (
    <div className="audio-studio-workspace" data-testid="audio-studio-workspace">
      <header className="audio-studio-shell">
        <div>
          <p className="audio-studio-shell__eyebrow">Audio Studio</p>
          <h2>Music, sounds, and beds for this project.</h2>
          <p className="muted">
            Stay in <strong>{project.name || "this project"}</strong>. Generate, play, approve, then send it to Timeline.
          </p>
        </div>
        <div className="audio-studio-shell__actions">
          <ProviderSourceSelector
            id="audio-studio"
            label="Provider"
            source={audioProvider.source}
            onChange={audioProvider.setSource}
            health={audioProvider.health}
            healthBusy={audioProvider.healthBusy}
          />
          <div className="audio-inline-note">
            <HelpTip text="Music uses the Music Engine. Sound Effects and Ambience use the Sound Engine. Project Audio is this project’s shelf. Footer Dock AUDIO provider syncs with this selector." />
            <span>{tabCountLabel}</span>
          </div>
          <Button variant="ghost" onClick={() => onGo("timeline")}>
            Open Timeline
          </Button>
        </div>
      </header>

      <nav className="audio-tab-bar" aria-label="Audio Studio sections">
        {TAB_LABELS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`audio-tab${tab === item.id ? " is-active" : ""}`}
            data-testid={`audio-studio-tab-${item.id === "library" ? "library" : item.id}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {status ? <p className="audio-status-pill" data-testid="audio-studio-status">{status}</p> : null}

      {currentPanel}
    </div>
  );
}
