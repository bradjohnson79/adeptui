import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import "./../../styles/audio-studio/audio-studio.css";
import { PromptIntelligencePanel } from "../CoDirector/PromptIntelligencePanel";
import { AdvancedDrawer } from "./AdvancedDrawer";
import { AmbiencePanel } from "./AmbiencePanel";
import { MusicPanel } from "./MusicPanel";
import { ProjectAudioPanel } from "./ProjectAudioPanel";
import { SfxPanel } from "./SfxPanel";
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

const DEFAULT_ADVANCED_SUMMARY: Record<AudioStudioTab, string> = {
  music: "Fine-tune the first pass without exposing engineering jargon.",
  sfx: "Dial in strength and texture only when you need extra control.",
  ambience: "Keep beds loopable and scene-friendly before layering more detail.",
  library: "Manage your approved project sounds and place them into the timeline.",
};

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
    title: firstString(normalized.title, normalized.tag, normalized.filename),
    url: firstString(normalized.url, normalized.file_url, normalized.previewUrl, normalized.preview_url) || api.assetUrl(normalized.id),
    durationSec: firstNumber(normalized.durationSec, normalized.duration_sec, normalized.length, normalized.seconds),
  };
}

function inferTrack(asset: Partial<AudioLibraryAsset> | AudioCandidate, fallback: AudioStudioTrack = "music"): AudioStudioTrack {
  const haystack = [
    asset.title,
    asset.subtitle,
    asset.description,
    (asset as AudioLibraryAsset).tag,
    (asset as AudioLibraryAsset).filename,
    (asset as AudioLibraryAsset).kind,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (haystack.includes("ambience") || haystack.includes("ambient") || haystack.includes("bed") || haystack.includes("room tone")) {
    return "ambience";
  }
  if (
    haystack.includes("sfx") ||
    haystack.includes("sound effect") ||
    haystack.includes("foley") ||
    haystack.includes("impact") ||
    haystack.includes("transition") ||
    haystack.includes("mechanical")
  ) {
    return "sfx";
  }
  if (haystack.includes("music") || haystack.includes("score") || haystack.includes("track")) {
    return "music";
  }
  return fallback;
}

function candidateFromAsset(asset: AudioLibraryAsset, kind: AudioStudioTrack, index: number): AudioCandidate {
  const title = asset.title || asset.tag || asset.filename || `${kind} idea ${index + 1}`;
  return {
    id: asset.id || `${kind}-${index + 1}`,
    assetId: asset.id,
    title,
    subtitle: firstString(asset.tag, asset.filename),
    description: firstString(asset.prompt, asset.description, asset.summary),
    prompt: firstString(asset.prompt, asset.description),
    durationSec: firstNumber(asset.durationSec, asset.duration_sec),
    loop: Boolean(asset.loop ?? asset.isLoop ?? asset.loopable),
    audioUrl: asset.url || api.assetUrl(asset.id),
    typeLabel: kind === "music" ? "Track" : kind === "sfx" ? "Sound" : "Bed",
    raw: asset,
  };
}

function extractCandidates(result: any, library: AudioLibraryAsset[], kind: AudioStudioTrack): AudioCandidate[] {
  const batchId = firstString(result?.id, result?.batchId, result?.batch_id);
  const rawItems = [
    ...asArray(result?.candidates),
    ...asArray(result?.items),
    ...asArray(result?.assets),
    ...asArray(result?.tracks),
    ...asArray(result?.sounds),
    ...asArray(result?.beds),
  ];

  if (!rawItems.length && result?.assetId) {
    rawItems.push({ id: result.assetId, assetId: result.assetId });
  }

  const normalized = rawItems
    .map((item, index) => {
      const candidateId = firstString(item?.id, item?.candidateId, item?.candidate_id) || `${kind}-${index + 1}`;
      const assetId = firstString(item?.asset_id, item?.assetId);
      const matchingLibrary = assetId ? library.find((asset) => asset.id === assetId) : undefined;
      const base = matchingLibrary || normalizeAsset(item);
      const variationIndex = firstNumber(item?.variation_index, item?.variationIndex) || index + 1;
      const variationHint = firstString(item?.variation_hint, item?.variationHint);
      const title =
        firstString(item?.title, item?.name, base.title, base.tag, base.filename) ||
        `${kind === "music" ? "Track" : kind === "sfx" ? "Sound" : "Bed"} ${variationIndex}`;
      // Prefer asset id — never bind preview URL to the candidate row id (that 200s JSON error).
      const resolvedAssetId = assetId || (matchingLibrary ? matchingLibrary.id : "") || "";
      const audioUrl = resolvedAssetId
        ? firstString(item?.audio_url, item?.audioUrl, matchingLibrary?.url) || api.assetUrl(resolvedAssetId)
        : "";

      return {
        id: candidateId,
        batchId: batchId || firstString(item?.batch_id, item?.batchId) || undefined,
        assetId: resolvedAssetId || undefined,
        title,
        subtitle:
          firstString(item?.subtitle, item?.error, variationHint, base.tag, base.filename) ||
          (typeof item?.seed === "number" ? `Seed ${item.seed}` : undefined),
        description: firstString(item?.description, item?.summary, item?.prompt, variationHint, base.description),
        prompt: firstString(item?.prompt, base.prompt),
        durationSec: firstNumber(item?.durationSec, item?.duration_sec, base.durationSec),
        loop: Boolean(item?.loop ?? (kind === "ambience" ? true : base.loop)),
        audioUrl,
        typeLabel: kind === "music" ? "Track" : kind === "sfx" ? "Sound" : "Bed",
        status: firstString(item?.status),
        stemsSupported: Boolean(item?.stems_supported ?? item?.stemsSupported),
        seed: firstNumber(item?.seed),
        variationIndex,
        variationHint: variationHint || undefined,
        raw: item,
      } satisfies AudioCandidate;
    })
    .filter(
      (candidate) =>
        candidate.audioUrl ||
        candidate.assetId ||
        ["failed", "queued", "generating", "ready", "selected", "approved"].includes(String(candidate.status || "")),
    );

  if (normalized.length) return normalized.slice(0, 6);

  const fallbackAssets = [...library]
    .filter((asset) => asset.kind === "audio")
    .sort((a, b) => {
      const left = firstString(b.createdAt, b.created_at);
      const right = firstString(a.createdAt, a.created_at);
      return left.localeCompare(right);
    })
    .slice(0, 3);

  return fallbackAssets.map((asset, index) => candidateFromAsset(asset, kind, index));
}

export function AudioStudioWorkspace({ project, onChange, onGo }: AudioStudioWorkspaceProps) {
  const [tab, setTab] = useState<AudioStudioTab>("music");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [generationProgress, setGenerationProgress] = useState<AudioGenerationProgress | null>(null);
  const [generatingKind, setGeneratingKind] = useState<AudioStudioGenerationKind | null>(null);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [projectAudio, setProjectAudio] = useState<AudioLibraryAsset[]>([]);
  const [previewSelection, setPreviewSelection] = useState<{ assetId?: string; title: string; url?: string; track: AudioStudioTrack } | null>(null);
  const [approvedAssetIds, setApprovedAssetIds] = useState<Record<string, boolean>>({});
  const [musicCandidates, setMusicCandidates] = useState<AudioCandidate[]>([]);
  const [sfxCandidates, setSfxCandidates] = useState<AudioCandidate[]>([]);
  const [ambienceCandidates, setAmbienceCandidates] = useState<AudioCandidate[]>([]);

  const [musicMood, setMusicMood] = useState("Hopeful");
  const [musicGenre, setMusicGenre] = useState("Cinematic");
  const [musicDuration, setMusicDuration] = useState(20);
  const [musicEnergy, setMusicEnergy] = useState("Steady");
  const [musicInstrumentation, setMusicInstrumentation] = useState("Warm strings, piano, light pulses");
  const [musicLoop, setMusicLoop] = useState(false);
  const [musicPrompt, setMusicPrompt] = useState("A cinematic rise that feels warm, hopeful, and ready for the next chapter.");

  const [sfxCategory, setSfxCategory] = useState("Foley");
  const [sfxDuration, setSfxDuration] = useState(4);
  const [sfxIntensity, setSfxIntensity] = useState("Natural");
  const [sfxPrompt, setSfxPrompt] = useState("Footsteps on old wood with a close, believable texture.");

  const [ambiencePreset, setAmbiencePreset] = useState("Forest Morning");
  const [ambienceDuration, setAmbienceDuration] = useState(45);
  const [ambienceLoop, setAmbienceLoop] = useState(true);
  const [ambiencePrompt, setAmbiencePrompt] = useState("Soft birds, distant leaves, and a calm early-morning breeze.");

  const previewAssetId = previewSelection?.assetId || null;

  const refreshLibrary = async () => {
    const response = await api.library(project.id).catch(() => null);
    const next = asArray(response?.items).map(normalizeAsset).filter((asset) => asset.kind === "audio");
    setProjectAudio(next);
    return next;
  };

  useEffect(() => {
    void refreshLibrary();
  }, [project.id, project.assets?.length]);

  const currentAdvancedSummary = DEFAULT_ADVANCED_SUMMARY[tab];

  const tabCountLabel = useMemo(() => {
    if (tab === "music") return `${musicCandidates.length} track ideas`;
    if (tab === "sfx") return `${sfxCandidates.length} sound ideas`;
    if (tab === "ambience") return `${ambienceCandidates.length} bed ideas`;
    return `${projectAudio.length} saved clips`;
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
    const total = Number(progress.total || (batch?.candidates || []).length || 3);
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
    const nextCandidates = extractCandidates(batch, [], kind);
    if (kind === "music") setMusicCandidates(nextCandidates);
    if (kind === "sfx") setSfxCandidates(nextCandidates);
    if (kind === "ambience") setAmbienceCandidates(nextCandidates);
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
    throw new Error("Generation timed out while waiting for batch progress.");
  };

  const cancelGeneration = async () => {
    if (cancelling) return;
    setCancelling(true);
    setGenerationProgress((current) =>
      current
        ? { ...current, label: "Cancelling at source (terminating GPU worker)…", active: true }
        : {
            visible: true,
            active: true,
            percent: 0,
            label: "Cancelling at source (terminating GPU worker)…",
          },
    );
    try {
      if (activeBatchId) {
        const result = await api.audioStudioCancelBatch(project.id, activeBatchId);
        applyProgressFromBatch(result?.batch || result, generatingKind || "music");
        setStatus("Generation cancelled at source — GPU/RAM workers terminated.");
        setGenerationProgress({
          visible: true,
          active: false,
          percent: Number((result as any)?.batch?.progress?.percent ?? generationProgress?.percent ?? 0),
          label: "Cancelled — worker terminated at source",
          batchId: activeBatchId,
        });
      } else {
        await api.audioStudioCancelGenerations(project.id);
        setStatus("Cancel sent — in-flight and orphan audio workers terminated at source.");
        setGenerationProgress({
          visible: true,
          active: false,
          percent: 0,
          label: "Cancelled — worker terminated at source",
        });
      }
    } catch (error) {
      try {
        await api.audioStudioCancelGenerations(project.id);
        setStatus("Emergency cancel sent — orphan audio workers terminated at source.");
      } catch {
        setStatus(error instanceof Error ? error.message : "Cancel failed.");
      }
      setGenerationProgress((current) =>
        current ? { ...current, active: false, label: "Cancelled" } : current,
      );
    } finally {
      setCancelling(false);
      setBusy(false);
      setGeneratingKind(null);
      setActiveBatchId(null);
    }
  };

  const generateForKind = async (kind: AudioStudioGenerationKind) => {
    setBusy(true);
    setGeneratingKind(kind);
    setStatus("");
    setActiveBatchId(null);
    setGenerationProgress({
      visible: true,
      active: true,
      percent: 0,
      label: "Starting generation…",
      completed: 0,
      total: 3,
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
              candidateCount: 3,
              asyncMode: true,
              runPromptIntelligence: true,
            }
          : kind === "sfx"
            ? {
                prompt: sfxPrompt,
                durationSec: sfxDuration,
                category: sfxCategory,
                intensity: sfxIntensity,
                loop: false,
                candidateCount: 3,
                asyncMode: true,
                runPromptIntelligence: true,
              }
            : {
                prompt: ambiencePrompt || ambiencePreset,
                durationSec: ambienceDuration,
                category: "ambience",
                loop: ambienceLoop,
                loopRequired: true,
                candidateCount: 3,
                asyncMode: true,
                runPromptIntelligence: true,
              };

      const started = await api.audioStudioGenerate(project.id, { kind, ...payload });
      applyProgressFromBatch(started, kind);
      const batchId = String(started?.id || "");
      if (batchId) setActiveBatchId(batchId);
      const result = batchId ? await pollBatchUntilComplete(batchId, kind) : started;
      const nextLibrary = await refreshLibrary();
      const nextCandidates = extractCandidates(result, nextLibrary, kind);

      if (kind === "music") setMusicCandidates(nextCandidates);
      if (kind === "sfx") setSfxCandidates(nextCandidates);
      if (kind === "ambience") setAmbienceCandidates(nextCandidates);

      if (String(result?.status || "") === "cancelled") {
        setStatus("Generation cancelled at source — GPU/RAM workers terminated.");
        setGenerationProgress({
          visible: true,
          active: false,
          percent: Number((result as any)?.progress?.percent || 0),
          label: "Cancelled — worker terminated at source",
          batchId,
        });
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
      const doneLabel =
        failed
          ? `${nextCandidates.length - failed} ready, ${failed} failed — retry available. Preview ≠ Approve.`
          : `${kind === "music" ? "Three track ideas" : kind === "sfx" ? "Three sounds" : "Three ambience beds"} ready. Select for Preview is separate from Approve.`;
      setStatus(doneLabel);
      setGenerationProgress({
        visible: true,
        active: false,
        percent: 100,
        label: failed ? `Finished with ${failed} failure(s)` : "Complete — 3 of 3",
        completed: nextCandidates.length,
        total: nextCandidates.length || 3,
        batchId,
      });
      await onChange?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Audio generation failed.");
      setGenerationProgress((current) =>
        current
          ? { ...current, active: false, label: error instanceof Error ? error.message : "Generation failed" }
          : null,
      );
    } finally {
      setBusy(false);
      setGeneratingKind(null);
      setActiveBatchId(null);
    }
  };

  const selectForPreview = async (candidate: AudioCandidate, track: AudioStudioTrack) => {
    selectPreview(candidate, track);
    if (candidate.batchId && candidate.id) {
      try {
        await api.audioStudioSelectCandidate(project.id, candidate.batchId, candidate.id);
        setStatus(`Selected for Preview: ${candidate.title}. Approval is still separate.`);
      } catch {
        /* preview still works locally */
      }
    }
  };

  const approveAsset = async (asset: AudioLibraryAsset | AudioCandidate) => {
    const candidate = asset as AudioCandidate;
    const assetId = candidate.assetId || asset.id;
    if (!assetId) {
      setStatus("This take does not have a saved asset yet.");
      return;
    }

    setBusy(true);
    setStatus("");
    try {
      if (candidate.batchId && candidate.id) {
        await api.audioStudioApproveCandidate(project.id, candidate.batchId, candidate.id);
      } else {
        throw new Error("Approve requires a candidate from a generation batch (select ≠ approve).");
      }

      setApprovedAssetIds((current) => ({ ...current, [assetId]: true }));
      setStatus("Approved and ready to reuse in your project.");
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
      setStatus("This take needs a saved asset before it can go on the timeline.");
      return;
    }

    setBusy(true);
    setStatus("");
    try {
      const track = inferTrack(asset, fallbackTrack);
      // Persist mix + placement authority via Audio Studio, then mirror into editor tracks.
      await api.audioStudioPlace(project.id, {
        assetId,
        category: track,
        startMs: 0,
        loop: Boolean((asset as AudioCandidate).loop || track === "ambience"),
      });
      const editor = await api.getEditor(project.id);
      const clips = [...(editor.tracks?.[track] || [])];
      const duration = firstNumber(asset.durationSec, (asset as AudioLibraryAsset).duration_sec, 5) || 5;
      const start = Math.max(0, ...clips.map((clip: any) => Number(clip.start || 0) + Number(clip.length || 0)), 0);
      clips.push({
        id: `clip-${Math.random().toString(36).slice(2, 10)}`,
        asset_id: assetId,
        start,
        length: duration,
        trim_start: 0,
        label: firstString(asset.title, (asset as AudioLibraryAsset).tag, (asset as AudioLibraryAsset).filename) || "Audio",
        placeholder: false,
      });
      await api.putEditor(project.id, {
        ...editor,
        tracks: { ...editor.tracks, [track]: clips },
      });
      setStatus(`Added to the ${track} track with mix state persisted.`);
      await onChange?.();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not add to timeline.");
    } finally {
      setBusy(false);
    }
  };

  const currentPanel = (() => {
    if (tab === "music") {
      return (
        <>
          <PromptIntelligencePanel
            creatorPrompt={musicPrompt}
            domain="music"
            providerId="audio-studio"
            projectId={project.id}
            compact
            onApply={({ finalProviderPrompt }) => setMusicPrompt(finalProviderPrompt)}
          />
          <MusicPanel
            busy={busy}
            mood={musicMood}
            genre={musicGenre}
            durationSec={musicDuration}
            energy={musicEnergy}
            instrumentation={musicInstrumentation}
            loop={musicLoop}
            prompt={musicPrompt}
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
            generationProgress={
              generatingKind === "music" || (tab === "music" && !generatingKind && generationProgress?.visible)
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
            onOpenAdvanced={() => setAdvancedOpen((open) => !open)}
          />
        </>
      );
    }
    if (tab === "sfx") {
      return (
        <SfxPanel
          busy={busy}
          generationProgress={
            generatingKind === "sfx" || (tab === "sfx" && !generatingKind && generationProgress?.visible)
              ? generationProgress
              : null
          }
          category={sfxCategory}
          durationSec={sfxDuration}
          intensity={sfxIntensity}
          prompt={sfxPrompt}
          candidates={sfxCandidates}
          previewAssetId={previewAssetId}
          approvedAssetIds={approvedAssetIds}
          onCategoryChange={setSfxCategory}
          onDurationChange={setSfxDuration}
          onIntensityChange={setSfxIntensity}
          onPromptChange={setSfxPrompt}
          onGenerate={() => generateForKind("sfx")}
          onCancelGeneration={
            generatingKind === "sfx" && (busy || Boolean(activeBatchId))
              ? () => cancelGeneration()
              : undefined
          }
          onPreview={(candidate) => void selectForPreview(candidate, "sfx")}
          onApprove={approveAsset}
          onAddToTimeline={(candidate) => addToTimeline(candidate, "sfx")}
          onOpenAdvanced={() => setAdvancedOpen((open) => !open)}
        />
      );
    }
    if (tab === "ambience") {
      return (
        <AmbiencePanel
          busy={busy}
          generationProgress={
            generatingKind === "ambience" ||
            (tab === "ambience" && !generatingKind && generationProgress?.visible)
              ? generationProgress
              : null
          }
          preset={ambiencePreset}
          durationSec={ambienceDuration}
          loop={ambienceLoop}
          prompt={ambiencePrompt}
          candidates={ambienceCandidates}
          previewAssetId={previewAssetId}
          approvedAssetIds={approvedAssetIds}
          onPresetChange={setAmbiencePreset}
          onDurationChange={setAmbienceDuration}
          onLoopChange={setAmbienceLoop}
          onPromptChange={setAmbiencePrompt}
          onGenerate={() => generateForKind("ambience")}
          onCancelGeneration={
            generatingKind === "ambience" && (busy || Boolean(activeBatchId))
              ? () => cancelGeneration()
              : undefined
          }
          onPreview={(candidate) => void selectForPreview(candidate, "ambience")}
          onApprove={approveAsset}
          onAddToTimeline={(candidate) => addToTimeline(candidate, "ambience")}
          onOpenAdvanced={() => setAdvancedOpen((open) => !open)}
        />
      );
    }

    return (
      <ProjectAudioPanel
        assets={projectAudio}
        busy={busy}
        previewAssetId={previewAssetId}
        approvedAssetIds={approvedAssetIds}
        onPreview={(asset) => selectPreview(asset, inferTrack(asset, "music"))}
        onApprove={approveAsset}
        onAddToTimeline={(asset) => addToTimeline(asset, inferTrack(asset, "music"))}
        onGoLibrary={() => onGo("library")}
        onGoTimeline={() => onGo("timeline")}
        onGoMixer={() => onGo("editor")}
      />
    );
  })();

  return (
    <div className="audio-studio-workspace" data-testid="audio-studio-workspace">
      <header className="audio-studio-shell">
        <div>
          <p className="audio-studio-shell__eyebrow">Audio Studio</p>
          <h2>Create music, scene beds, and story sounds in one place.</h2>
          <p className="muted">
            Everything stays attached to <strong>{project.name || "this project"}</strong> so creators can audition, approve, and place audio without jumping into engineering tools.
          </p>
        </div>
        <div className="audio-studio-shell__actions">
          <div className="audio-inline-note">
            <HelpTip text="Music builds score ideas, Sound Effects handles one-shot details, Ambience creates loopable scene beds, and Project Audio keeps everything you saved for the project." />
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
            onClick={() => {
              setTab(item.id);
              setAdvancedOpen(false);
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {status ? <p className="audio-status-pill">{status}</p> : null}

      <AdvancedDrawer
        open={advancedOpen}
        summary={currentAdvancedSummary}
        onToggle={() => setAdvancedOpen((open) => !open)}
      >
        {tab === "music" ? (
          <div className="audio-advanced-grid">
            <div>
              <strong>Composer guidance</strong>
              <p className="muted">Lead with emotion first, then name only the instruments that really matter.</p>
            </div>
            <div>
              <strong>Loop advice</strong>
              <p className="muted">Use looping for menus, recaps, and longer scenes that need a bed underneath edits.</p>
            </div>
            <div>
              <strong>Timeline note</strong>
              <p className="muted">Approved tracks can still be trimmed or stacked later. Approval just marks your current favorite.</p>
            </div>
          </div>
        ) : tab === "sfx" ? (
          <div className="audio-advanced-grid">
            <div>
              <strong>Texture prompt</strong>
              <p className="muted">Mention distance, material, and point of view: close, airy, metallic, distant, muffled.</p>
            </div>
            <div>
              <strong>Category tip</strong>
              <p className="muted">Choose Custom only when the sound spans more than one family.</p>
            </div>
            <div>
              <strong>Placement note</strong>
              <p className="muted">Short effects land on the SFX track so they stay easy to spot and nudge later.</p>
            </div>
          </div>
        ) : tab === "ambience" ? (
          <div className="audio-advanced-grid">
            <div>
              <strong>Bed shaping</strong>
              <p className="muted">Describe the environment first, then add subtle emotional guidance like lonely, safe, tense, or calm.</p>
            </div>
            <div>
              <strong>Loop default</strong>
              <p className="muted">Loop stays on so a bed can stretch under a scene without extra setup.</p>
            </div>
            <div>
              <strong>Timeline note</strong>
              <p className="muted">Ambience beds go to the ambience lane when that track already exists in the editor.</p>
            </div>
          </div>
        ) : (
          <div className="audio-advanced-grid">
            <div>
              <strong>Project shelf</strong>
              <p className="muted">This tab only shows assets already saved to the project library with kind set to audio.</p>
            </div>
            <div>
              <strong>Approvals</strong>
              <p className="muted">If a dedicated approve endpoint is missing, the UI still keeps a clear local approved state for review.</p>
            </div>
            <div>
              <strong>Placement</strong>
              <p className="muted">Track choice is inferred from the asset name and metadata, then written with the existing editor pattern.</p>
            </div>
          </div>
        )}
      </AdvancedDrawer>

      {currentPanel}
    </div>
  );
}
