import { useEffect, useMemo, useRef, useState } from "react";
import type { AudioMasterOutput, AudioMixClipState, MusicStemSet } from "../../audioStudio/contracts";
import { HelpTip } from "../HelpTip";
import { Button } from "../ui";
import "./../../styles/audio-studio/audio-studio.css";

export type AudioMixerClipDescriptor = {
  clipId: string;
  label: string;
  category?: string;
  assetId?: string | null;
  previewUrl?: string;
  startSeconds?: number;
  durationSeconds?: number;
  defaultTrackRoute?: string;
  stemsSupported?: boolean;
  musicStemSet?: MusicStemSet | null;
};

type AudioMixerLocalClipState = AudioMixClipState & {
  musicStemSet?: MusicStemSet | null;
};

export type AudioMixerMixState = {
  master: AudioMasterOutput;
  clips: Record<string, AudioMixerLocalClipState>;
};

type AudioMixerPanelProps = {
  clips: AudioMixerClipDescriptor[];
  mix: AudioMixerMixState;
  busy?: boolean;
  status?: string;
  emptyMessage?: string;
  onSavePatch: (body: {
    master?: Record<string, unknown>;
    clips?: Record<string, Record<string, unknown>>;
    clip?: Record<string, unknown>;
  }) => Promise<void>;
  onReload?: () => Promise<void> | void;
  onRequestStemReplace?: (clip: AudioMixerClipDescriptor, stemRole?: string) => void;
};

const ROUTE_OPTIONS = [
  { value: "master", label: "Master" },
  { value: "dialogue", label: "Dialogue" },
  { value: "sfx", label: "Sound Effects" },
  { value: "ambience", label: "Ambience" },
  { value: "music", label: "Music" },
] as const;

function asNumber(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  }
  return undefined;
}

function asBoolean(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return undefined;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function formatDb(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)} dB`;
}

function formatSeconds(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  return `${value.toFixed(1)}s`;
}

function formatLufs(master: AudioMasterOutput, livePreviewing: boolean) {
  const masterRecord = master as unknown as Record<string, unknown>;
  const shortTerm = asNumber(master.lufsShortTerm, masterRecord.lufs_short_term);
  const integrated = asNumber(master.lufsIntegrated, masterRecord.lufs_integrated);
  if (typeof shortTerm === "number") return `${shortTerm.toFixed(1)} LUFS short-term`;
  if (typeof integrated === "number") return `${integrated.toFixed(1)} LUFS integrated`;
  if (livePreviewing) return "Unavailable during browser preview";
  return "Unavailable";
}

function normalizeStemSet(raw: unknown): MusicStemSet | null {
  if (!raw || typeof raw !== "object") return null;
  const value = raw as Record<string, unknown>;
  const stems = Array.isArray(value.stems)
    ? value.stems
        .map((stem) => {
          if (!stem || typeof stem !== "object") return null;
          const item = stem as Record<string, unknown>;
          const assetId = typeof item.assetId === "string" ? item.assetId : typeof item.asset_id === "string" ? item.asset_id : "";
          const role = typeof item.role === "string" ? item.role : "";
          if (!assetId || !role) return null;
          return {
            role: role as MusicStemSet["stems"][number]["role"],
            assetId,
            muted: Boolean(item.muted),
          };
        })
        .filter(Boolean)
    : [];
  return {
    parentVersionId:
      typeof value.parentVersionId === "string"
        ? value.parentVersionId
        : typeof value.parent_version_id === "string"
          ? value.parent_version_id
          : "",
    stems: stems as MusicStemSet["stems"],
    stemsSupported: Boolean(
      value.stemsSupported ??
        value.stems_supported ??
        stems.length
    ),
  };
}

function resolveStemSet(...sources: Array<unknown>) {
  for (const source of sources) {
    if (!source || typeof source !== "object") continue;
    const record = source as Record<string, unknown>;
    const nestedCandidates = [
      record.musicStemSet,
      record.music_stem_set,
      record.stemSet,
      record.stem_set,
      record.stems,
      record.lineage && typeof record.lineage === "object" ? (record.lineage as Record<string, unknown>).stems : null,
      record.audioLineage && typeof record.audioLineage === "object"
        ? (record.audioLineage as Record<string, unknown>).stems
        : null,
      record.audio_lineage && typeof record.audio_lineage === "object"
        ? (record.audio_lineage as Record<string, unknown>).stems
        : null,
      record.provenance && typeof record.provenance === "object"
        ? (record.provenance as Record<string, unknown>).stems
        : null,
    ];
    for (const candidate of nestedCandidates) {
      const normalized = normalizeStemSet(candidate);
      if (normalized) return normalized;
    }
  }
  return null;
}

function resolveStemsSupported(clip: AudioMixerLocalClipState, descriptor: AudioMixerClipDescriptor) {
  const stemSet = resolveStemSet(clip, descriptor);
  const clipRecord = clip as unknown as Record<string, unknown>;
  if (stemSet?.stems.length) return true;
  return Boolean(
    descriptor.stemsSupported ??
      clip.musicStemSet?.stemsSupported ??
      clipRecord.stemsSupported ??
      clipRecord.stems_supported
  );
}

function normalizeClipState(descriptor: AudioMixerClipDescriptor, raw: unknown): AudioMixerLocalClipState {
  const record = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const stemSet = resolveStemSet(record, descriptor);
  return {
    clipId: descriptor.clipId,
    gain: clamp(asNumber(record.gain, 1) ?? 1, 0, 4),
    pan: clamp(asNumber(record.pan, 0) ?? 0, -1, 1),
    mute: Boolean(asBoolean(record.mute, false)),
    solo: Boolean(asBoolean(record.solo, false)),
    normalize: Boolean(asBoolean(record.normalize, false)),
    fadeInMs: clamp(asNumber(record.fadeInMs, record.fade_in_ms, 0) ?? 0, 0, 60000),
    fadeOutMs: clamp(asNumber(record.fadeOutMs, record.fade_out_ms, 0) ?? 0, 0, 60000),
    crossfadeToClipId:
      typeof record.crossfadeToClipId === "string"
        ? record.crossfadeToClipId
        : typeof record.crossfade_to_clip_id === "string"
          ? record.crossfade_to_clip_id
          : null,
    trackRoute:
      typeof record.trackRoute === "string"
        ? record.trackRoute
        : typeof record.track_route === "string"
          ? record.track_route
          : descriptor.defaultTrackRoute || "master",
    loop: Boolean(asBoolean(record.loop, false)),
    peak: asNumber(record.peak) ?? null,
    lufs: asNumber(record.lufs) ?? null,
    musicStemSet: stemSet,
  };
}

export function normalizeAudioMixerMix(mix: unknown, clips: AudioMixerClipDescriptor[]): AudioMixerMixState {
  const record = mix && typeof mix === "object" ? (mix as Record<string, unknown>) : {};
  const master = record.master && typeof record.master === "object" ? (record.master as Record<string, unknown>) : {};
  const rawClips = record.clips && typeof record.clips === "object" ? (record.clips as Record<string, unknown>) : {};
  return {
    master: {
      gain: clamp(asNumber(master.gain, 1) ?? 1, 0, 4),
      peak: asNumber(master.peak) ?? null,
      lufsIntegrated: asNumber(master.lufsIntegrated, master.lufs_integrated) ?? null,
      lufsShortTerm: asNumber(master.lufsShortTerm, master.lufs_short_term) ?? null,
    },
    clips: Object.fromEntries(
      clips.map((descriptor) => [descriptor.clipId, normalizeClipState(descriptor, rawClips[descriptor.clipId])])
    ),
  };
}

function toMasterPatch(master: AudioMasterOutput) {
  return {
    gain: clamp(asNumber(master.gain, 1) ?? 1, 0, 4),
    peak: master.peak ?? null,
    lufs_integrated: master.lufsIntegrated ?? null,
    lufs_short_term: master.lufsShortTerm ?? null,
  };
}

function toClipPatch(clip: AudioMixerLocalClipState) {
  const patch: Record<string, unknown> = {
    clip_id: clip.clipId,
    gain: clamp(asNumber(clip.gain, 1) ?? 1, 0, 4),
    pan: clamp(asNumber(clip.pan, 0) ?? 0, -1, 1),
    mute: Boolean(clip.mute),
    solo: Boolean(clip.solo),
    normalize: Boolean(clip.normalize),
    fade_in_ms: clamp(asNumber(clip.fadeInMs, 0) ?? 0, 0, 60000),
    fade_out_ms: clamp(asNumber(clip.fadeOutMs, 0) ?? 0, 0, 60000),
    track_route: clip.trackRoute || "master",
    loop: Boolean(clip.loop),
  };
  if (clip.crossfadeToClipId) patch.crossfade_to_clip_id = clip.crossfadeToClipId;
  if (clip.musicStemSet) patch.musicStemSet = clip.musicStemSet;
  return patch;
}

export function AudioMixerPanel({
  clips,
  mix,
  busy = false,
  status = "",
  emptyMessage = "Add approved audio clips to the timeline to start mixing.",
  onSavePatch,
  onReload,
  onRequestStemReplace,
}: AudioMixerPanelProps) {
  const [draftMix, setDraftMix] = useState<AudioMixerMixState>(() => normalizeAudioMixerMix(mix, clips));
  const [expandedStemIds, setExpandedStemIds] = useState<Record<string, boolean>>({});
  const [previewClipId, setPreviewClipId] = useState<string | null>(clips[0]?.previewUrl ? clips[0].clipId : null);
  const [livePeak, setLivePeak] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const meterFrameRef = useRef<number | null>(null);
  const meterBufferRef = useRef<Float32Array<ArrayBuffer> | null>(null);

  useEffect(() => {
    setDraftMix(normalizeAudioMixerMix(mix, clips));
  }, [clips, mix]);

  useEffect(() => {
    setPreviewClipId((current) => {
      if (current && clips.some((clip) => clip.clipId === current && clip.previewUrl)) return current;
      return clips.find((clip) => clip.previewUrl)?.clipId || null;
    });
  }, [clips]);

  useEffect(() => {
    return () => {
      if (meterFrameRef.current) {
        cancelAnimationFrame(meterFrameRef.current);
      }
      const context = audioContextRef.current;
      if (context) {
        void context.close().catch(() => undefined);
      }
    };
  }, []);

  const previewClip = useMemo(
    () => clips.find((clip) => clip.clipId === previewClipId && clip.previewUrl) || null,
    [clips, previewClipId]
  );

  const stopMeter = () => {
    if (meterFrameRef.current) {
      cancelAnimationFrame(meterFrameRef.current);
      meterFrameRef.current = null;
    }
    setLivePeak(null);
  };

  const tickMeter = () => {
    const analyser = analyserRef.current;
    const audio = audioRef.current;
    const buffer = meterBufferRef.current;
    if (!analyser || !audio || !buffer || audio.paused || audio.ended) {
      stopMeter();
      return;
    }
    analyser.getFloatTimeDomainData(buffer);
    let peak = 0;
    for (const sample of buffer) {
      peak = Math.max(peak, Math.abs(sample));
    }
    const nextPeak = peak > 0 ? 20 * Math.log10(peak) : -60;
    setLivePeak(Number.isFinite(nextPeak) ? nextPeak : null);
    meterFrameRef.current = requestAnimationFrame(tickMeter);
  };

  const startMeter = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    const AudioContextCtor = (window as any).AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextCtor) return;
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContextCtor();
    }
    const context = audioContextRef.current;
    if (!context) return;
    if (!sourceRef.current) {
      sourceRef.current = context.createMediaElementSource(audio);
      analyserRef.current = context.createAnalyser();
      analyserRef.current.fftSize = 2048;
      meterBufferRef.current = new Float32Array(analyserRef.current.fftSize) as Float32Array<ArrayBuffer>;
      sourceRef.current.connect(analyserRef.current);
      analyserRef.current.connect(context.destination);
    }
    if (context.state === "suspended") {
      await context.resume().catch(() => undefined);
    }
    stopMeter();
    meterFrameRef.current = requestAnimationFrame(tickMeter);
  };

  const updateMasterLocal = (patch: Partial<AudioMasterOutput>) => {
    setDraftMix((current) => ({
      ...current,
      master: { ...current.master, ...patch },
    }));
  };

  const saveMaster = async (patch: Partial<AudioMasterOutput>) => {
    const nextMaster = { ...draftMix.master, ...patch };
    updateMasterLocal(patch);
    await onSavePatch({ master: toMasterPatch(nextMaster) });
  };

  const updateClipLocal = (clipId: string, patch: Partial<AudioMixerLocalClipState>) => {
    setDraftMix((current) => ({
      ...current,
      clips: {
        ...current.clips,
        [clipId]: { ...current.clips[clipId], ...patch },
      },
    }));
  };

  const saveClip = async (descriptor: AudioMixerClipDescriptor, patch: Partial<AudioMixerLocalClipState>) => {
    const base = draftMix.clips[descriptor.clipId] || normalizeClipState(descriptor, null);
    const nextClip = { ...base, ...patch };
    updateClipLocal(descriptor.clipId, patch);
    await onSavePatch({ clip: toClipPatch(nextClip) });
  };

  const peakLabel = livePeak !== null ? `${formatDb(livePeak)} live` : formatDb(draftMix.master.peak);
  const lufsLabel = formatLufs(draftMix.master, livePeak !== null);

  return (
    <section className="audio-studio-panel audio-mixer-panel" data-testid="audio-mixer-panel">
      <div className="audio-studio-panel__hero">
        <div>
          <p className="audio-studio-panel__eyebrow">Audio Mixer</p>
          <h3>Balance your project audio before final delivery.</h3>
          <p className="muted">
            Shape loudness, placement, fades, and stem behavior for the clips already on your timeline.
          </p>
        </div>
        <div className="audio-studio-panel__hero-actions">
          <div className="audio-inline-note">
            <HelpTip text="Peak updates live during browser preview when the clip can be analyzed locally. LUFS stays server-truth only unless the browser can measure it." />
            <span>{busy ? "Saving mixer…" : `${clips.length} clip${clips.length === 1 ? "" : "s"} ready`}</span>
          </div>
          {onReload ? (
            <Button variant="ghost" disabled={busy} onClick={() => void onReload()}>
              Reload
            </Button>
          ) : null}
        </div>
      </div>

      {status ? <p className="audio-status-pill">{status}</p> : null}

      <div className="audio-mixer-master">
        <div>
          <p className="audio-mixer-master__eyebrow">Master output</p>
          <strong>Final level</strong>
          <p className="muted">Keep the overall level comfortable before you tweak individual clips.</p>
        </div>
        <div className="audio-form-grid audio-form-grid--compact">
          <label className="audio-field">
            <span className="audio-field__label">
              Master gain
              <HelpTip text="Use this to raise or lower the full project mix without changing each clip by hand." />
            </span>
            <input
              data-testid="audio-mixer-master-gain"
              type="number"
              min={0}
              max={4}
              step={0.05}
              value={draftMix.master.gain}
              onChange={(e) => updateMasterLocal({ gain: clamp(Number(e.target.value) || 0, 0, 4) })}
              onBlur={() => void saveMaster({ gain: draftMix.master.gain })}
            />
          </label>
        </div>

        <div className="audio-mixer-meter-grid">
          <div className="audio-mixer-meter">
            <span className="audio-mixer-meter__label">Peak</span>
            <strong data-testid="audio-mixer-peak">{peakLabel}</strong>
          </div>
          <div className="audio-mixer-meter">
            <span className="audio-mixer-meter__label">LUFS</span>
            <strong data-testid="audio-mixer-lufs">{lufsLabel}</strong>
          </div>
        </div>

        {previewClip ? (
          <div className="audio-mixer-preview">
            <div>
              <p className="audio-preview-rail__eyebrow">Preview source</p>
              <strong>{previewClip.label}</strong>
              <p className="muted">Play a clip here to watch the live peak meter when the browser can read it.</p>
            </div>
            <audio
              ref={audioRef}
              controls
              src={previewClip.previewUrl}
              className="audio-preview-rail__player"
              onPlay={() => void startMeter()}
              onPause={stopMeter}
              onEnded={stopMeter}
            />
          </div>
        ) : (
          <div className="audio-empty-state">
            <strong>Preview unavailable.</strong>
            <p className="muted">Add clips with playable project audio to unlock browser-level peak metering.</p>
          </div>
        )}
      </div>

      {clips.length ? (
        <div className="audio-library-list">
          {clips.map((descriptor) => {
            const clip = draftMix.clips[descriptor.clipId] || normalizeClipState(descriptor, null);
            const stemSet = resolveStemSet(clip, descriptor);
            const stemsSupported = resolveStemsSupported(clip, descriptor);
            const stemExpanded = Boolean(expandedStemIds[descriptor.clipId]);
            return (
              <article key={descriptor.clipId} className="audio-library-card audio-mixer-clip" data-testid="audio-mixer-clip">
                <div className="audio-library-card__meta">
                  <div>
                    <h4>{descriptor.label}</h4>
                    <p className="muted">
                      {(descriptor.category || "audio").replace(/_/g, " ")}
                      {descriptor.startSeconds !== undefined ? ` · starts ${formatSeconds(descriptor.startSeconds)}` : ""}
                      {descriptor.durationSeconds !== undefined ? ` · ${formatSeconds(descriptor.durationSeconds)}` : ""}
                    </p>
                  </div>
                  <div className="audio-candidate-card__chips">
                    {descriptor.assetId ? <span className="audio-chip audio-chip--subtle">Asset ready</span> : null}
                    {stemsSupported ? <span className="audio-chip audio-chip--subtle">Stems aware</span> : null}
                  </div>
                </div>

                <div className="audio-candidate-card__actions">
                  {descriptor.previewUrl ? (
                    <Button
                      variant="ghost"
                      disabled={busy}
                      onClick={() => setPreviewClipId(descriptor.clipId)}
                    >
                      {previewClipId === descriptor.clipId ? "Previewing" : "Preview"}
                    </Button>
                  ) : null}
                  <button
                    type="button"
                    className={`audio-chip${clip.mute ? " is-selected" : ""}`}
                    disabled={busy}
                    onClick={() => void saveClip(descriptor, { mute: !clip.mute })}
                  >
                    {clip.mute ? "Muted" : "Mute"}
                  </button>
                  <button
                    type="button"
                    className={`audio-chip${clip.solo ? " is-selected" : ""}`}
                    disabled={busy}
                    onClick={() => void saveClip(descriptor, { solo: !clip.solo })}
                  >
                    {clip.solo ? "Soloed" : "Solo"}
                  </button>
                  <button
                    type="button"
                    className={`audio-chip${clip.normalize ? " is-selected" : ""}`}
                    disabled={busy}
                    onClick={() => void saveClip(descriptor, { normalize: !clip.normalize })}
                  >
                    {clip.normalize ? "Normalized" : "Normalize"}
                  </button>
                </div>

                <div className="audio-form-grid">
                  <label className="audio-field">
                    <span className="audio-field__label">Clip gain</span>
                    <input
                      type="number"
                      min={0}
                      max={4}
                      step={0.05}
                      value={clip.gain}
                      onChange={(e) => updateClipLocal(descriptor.clipId, { gain: clamp(Number(e.target.value) || 0, 0, 4) })}
                      onBlur={() => void saveClip(descriptor, { gain: clip.gain })}
                    />
                  </label>

                  <label className="audio-field">
                    <span className="audio-field__label">Pan</span>
                    <input
                      type="number"
                      min={-1}
                      max={1}
                      step={0.05}
                      value={clip.pan}
                      onChange={(e) => updateClipLocal(descriptor.clipId, { pan: clamp(Number(e.target.value) || 0, -1, 1) })}
                      onBlur={() => void saveClip(descriptor, { pan: clip.pan })}
                    />
                  </label>

                  <label className="audio-field">
                    <span className="audio-field__label">Fade in</span>
                    <input
                      type="number"
                      min={0}
                      max={60000}
                      step={50}
                      value={clip.fadeInMs || 0}
                      onChange={(e) =>
                        updateClipLocal(descriptor.clipId, { fadeInMs: clamp(Number(e.target.value) || 0, 0, 60000) })
                      }
                      onBlur={() => void saveClip(descriptor, { fadeInMs: clip.fadeInMs || 0 })}
                    />
                  </label>

                  <label className="audio-field">
                    <span className="audio-field__label">Fade out</span>
                    <input
                      type="number"
                      min={0}
                      max={60000}
                      step={50}
                      value={clip.fadeOutMs || 0}
                      onChange={(e) =>
                        updateClipLocal(descriptor.clipId, { fadeOutMs: clamp(Number(e.target.value) || 0, 0, 60000) })
                      }
                      onBlur={() => void saveClip(descriptor, { fadeOutMs: clip.fadeOutMs || 0 })}
                    />
                  </label>

                  <label className="audio-field">
                    <span className="audio-field__label">
                      Track route
                      <HelpTip text="Choose where this clip should feed inside the project mix bus." />
                    </span>
                    <select
                      value={clip.trackRoute || "master"}
                      onChange={(e) => {
                        const trackRoute = e.target.value;
                        updateClipLocal(descriptor.clipId, { trackRoute });
                        void saveClip(descriptor, { trackRoute });
                      }}
                    >
                      {ROUTE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="audio-toggle">
                    <input
                      type="checkbox"
                      checked={Boolean(clip.loop)}
                      onChange={(e) => {
                        const loop = e.target.checked;
                        updateClipLocal(descriptor.clipId, { loop });
                        void saveClip(descriptor, { loop });
                      }}
                    />
                    <span>Loop</span>
                  </label>
                </div>

                {stemsSupported ? (
                  <div className="audio-mixer-stems">
                    <div className="audio-mixer-stems__header">
                      <div>
                        <strong>Stem controls</strong>
                        <p className="muted">
                          {stemSet?.stems.length
                            ? "Only attached lineage stems are shown here."
                            : "This source can carry stems, but no attached stem files are available in the current lineage."}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="audio-chip"
                        onClick={() =>
                          setExpandedStemIds((current) => ({
                            ...current,
                            [descriptor.clipId]: !current[descriptor.clipId],
                          }))
                        }
                      >
                        {stemExpanded ? "Hide" : "Expand"}
                      </button>
                    </div>

                    {stemExpanded ? (
                      stemSet?.stems.length ? (
                        <div className="audio-mixer-stem-list">
                          {stemSet.stems.map((stem, index) => (
                            <div key={`${descriptor.clipId}-${stem.role}-${index}`} className="audio-mixer-stem-row">
                              <div>
                                <strong>{stem.role}</strong>
                                <p className="muted">{stem.assetId}</p>
                              </div>
                              <div className="audio-candidate-card__actions">
                                <button
                                  type="button"
                                  className={`audio-chip${stem.muted ? " is-selected" : ""}`}
                                  disabled={busy}
                                  onClick={() => {
                                    const nextStemSet: MusicStemSet = {
                                      ...stemSet,
                                      stems: stemSet.stems.map((item, itemIndex) =>
                                        itemIndex === index ? { ...item, muted: !item.muted } : item
                                      ),
                                    };
                                    void saveClip(descriptor, { musicStemSet: nextStemSet });
                                  }}
                                >
                                  {stem.muted ? "Muted" : "Mute"}
                                </button>
                                <Button
                                  variant="secondary"
                                  disabled={!onRequestStemReplace}
                                  onClick={() => onRequestStemReplace?.(descriptor, stem.role)}
                                >
                                  Replace
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="audio-empty-state">
                          <strong>No attached stems yet.</strong>
                          <p className="muted">
                            This clip reports stem support, but the current lineage does not expose real stem files to the mixer.
                          </p>
                          {onRequestStemReplace ? (
                            <Button variant="secondary" onClick={() => onRequestStemReplace(descriptor)}>
                              Replace
                            </Button>
                          ) : null}
                        </div>
                      )
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="audio-empty-state">
          <strong>Audio Mixer is ready when your timeline is.</strong>
          <p className="muted">{emptyMessage}</p>
        </div>
      )}
    </section>
  );
}
