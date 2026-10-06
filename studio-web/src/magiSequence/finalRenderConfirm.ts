import { frameToTimecode } from "./engine";
import type { MagiClip, MagiSequenceDocument } from "./types";

const PICTURE_KINDS = new Set(["video", "image"]);

const COLOR_LABELS: Record<string, string> = {
  cinematic_neutral: "Cinematic Neutral",
  cinematic_warm: "Warm Cinematic",
  cinematic_cool: "Cool Cinematic",
  golden_hour: "Golden Hour",
  teal_orange: "Teal & Orange",
  film_print: "Film Print",
  vintage: "Vintage",
  high_contrast: "High Contrast",
  low_contrast: "Low Contrast",
  bleach_bypass: "Bleach Bypass",
  dreamy: "Dreamy",
  noir: "Noir",
  anime_vibrant: "Anime Vibrant",
  muted_drama: "Muted Drama",
  night_moonlight: "Night / Moonlight",
};

const LIGHTING_LABELS: Record<string, string> = {
  soft_bright: "Soft Bright",
  warm: "Warm",
  cool: "Cool",
  high_contrast: "High Contrast",
  low_light_lift: "Low Light Lift",
};

const ENGINE_LABELS: Record<string, string> = {
  "ffmpeg-scale": "FFmpeg (fast)",
  "realesrgan-ncnn-vulkan": "Real-ESRGAN (GPU)",
};

const MODEL_LABELS: Record<string, string> = {
  lanczos: "Lanczos (general)",
  bicubic: "Bicubic (soft)",
  "realesrgan-x4plus": "General 4x",
  "realesr-animevideov3": "Anime Video",
  "realesrgan-x4plus-anime": "Anime 4x",
};

const ADJUSTMENT_LABELS: Record<string, string> = {
  brightness: "Exposure",
  contrast: "Contrast",
  saturation: "Saturation",
  highlights: "Highlights",
  shadows: "Shadows",
  temperature: "Temperature",
  gamma: "Gamma",
};

export type FinalRenderSection = {
  id: "video" | "upscale" | "audio" | "output";
  title: string;
  rows: { label: string; value: string }[];
};

export type FinalRenderUpscale =
  | { enabled: false }
  | { enabled: true; engine: string; model: string; target: string };

export type FinalRenderRequest = {
  profile: "final";
  range: string;
  clipId?: string;
  includeColor: true;
  includeAudio: true;
  includeOverlays: true;
  upscale: FinalRenderUpscale;
  /** Library title. The file stem is this title; the caller does not send .mp4. */
  outputName: string;
};

export type RenderStageNote = {
  stage: string;
  message: string;
  progress?: number;
  failed?: boolean;
};

export type FinalRenderSession = {
  phase: "confirm" | "running" | "done" | "failed";
  jobId: string | null;
  progress: number;
  stage: string;
  message: string;
  error: string | null;
  assetId: string | null;
  log: RenderStageNote[];
  outputName: string;
  outputFile: string;
};

type NamedAsset = { id: string; filename?: string; tag?: string | null };

export function pictureClipsForRender(sequence: MagiSequenceDocument): MagiClip[] {
  const tracks = new Map(sequence.tracks.map((track) => [track.id, track]));
  const selected: MagiClip[] = [];
  for (const clip of sequence.clips) {
    if (!clip.assetId) continue;
    const track = tracks.get(clip.trackId);
    const kind = track?.kind || "";
    if (sequence.tracks.length && kind && !PICTURE_KINDS.has(kind)) continue;
    if (track?.hidden) continue;
    selected.push(clip);
  }
  return selected;
}

function renderClips(sequence: MagiSequenceDocument, range: string, selectedClipId?: string | null): MagiClip[] {
  const clips = pictureClipsForRender(sequence);
  if ((range === "clip" || range === "selected") && selectedClipId) {
    const match = clips.filter((clip) => clip.id === selectedClipId);
    return match.length ? match : clips.slice(0, 1);
  }
  return clips;
}

function trackMuted(sequence: MagiSequenceDocument, kind: string): boolean {
  return sequence.tracks.some((track) => track.kind === kind && Boolean(track.muted));
}

function assetName(assets: NamedAsset[], id?: string | null): string {
  if (!id) return "";
  const asset = assets.find((item) => item.id === id);
  const label = asset?.tag || asset?.filename || "";
  return label.trim();
}

function stemRow(sequence: MagiSequenceDocument, assets: NamedAsset[], kind: "music" | "sfx", assetId?: string | null): string {
  if (!assetId) return "Not added";
  if (trackMuted(sequence, kind)) return "Muted";
  const name = assetName(assets, assetId);
  return name ? `Included · ${name}` : "Included";
}

const KNOWN_ASPECTS = new Set(["1:1", "4:3", "3:4", "16:9", "9:16", "21:9", "2.39:1"]);

function displayAspect(aspect?: string): string {
  return aspect && KNOWN_ASPECTS.has(aspect) ? ` · ${aspect}` : "";
}

function labelOf(table: Record<string, string>, id?: string | null): string {
  const key = String(id || "").trim();
  if (!key) return "";
  return table[key] || key;
}

export function buildFinalRenderConfirm(input: {
  sequence: MagiSequenceDocument;
  range: string;
  selectedClipId?: string | null;
  upscaleEnabled: boolean;
  upscaleEngine: string;
  upscaleModel: string;
  upscaleTarget: string;
  resolvedUpscale: { id: string; width: number; height: number; aspect?: string } | null;
  assets: NamedAsset[];
  outputName?: string;
}): { request: FinalRenderRequest; sections: FinalRenderSection[] } {
  const range = input.range || "entire";
  const clips = renderClips(input.sequence, range, input.selectedClipId);
  const gradeClip = clips[0];
  const grade = (gradeClip && input.sequence.finishing?.clipGrades?.[gradeClip.id]) || {};
  const preset = labelOf(COLOR_LABELS, grade.presetId);
  const lighting = labelOf(LIGHTING_LABELS, grade.lightingPresetId);
  const adjustments = Object.entries(grade.params || {})
    .filter(([, value]) => Number(value) !== 0)
    .map(([key]) => ADJUSTMENT_LABELS[key] || key);
  const clipName = gradeClip?.name || "the first picture clip";
  const colorValue = preset || (adjustments.length ? "Custom look" : "None");
  const rangeLabel = range === "clip" || range === "selected" ? "Selected clip" : "Entire edit";
  const fps = input.sequence.frameRate || 24;
  const durationFrames =
    range === "clip" || range === "selected"
      ? gradeClip?.durationFrames || input.sequence.durationFrames
      : input.sequence.durationFrames;
  const audio = input.sequence.finishing?.audio;
  const upscale: FinalRenderUpscale = input.upscaleEnabled
    ? {
        enabled: true,
        engine: input.upscaleEngine,
        model: input.upscaleModel,
        target: input.upscaleTarget,
      }
    : { enabled: false };
  const size = input.resolvedUpscale;
  const upscaleRows: { label: string; value: string }[] = [
    { label: "Video upscale", value: input.upscaleEnabled ? "On" : "Off" },
  ];
  if (input.upscaleEnabled) {
    upscaleRows.push(
      { label: "Method", value: labelOf(ENGINE_LABELS, input.upscaleEngine) || input.upscaleEngine },
      { label: "Model", value: labelOf(MODEL_LABELS, input.upscaleModel) || input.upscaleModel },
      {
        label: "Output size",
        value: size
          ? `${size.width}×${size.height}${displayAspect(size.aspect)} · ${size.id || input.upscaleTarget}`
          : input.upscaleTarget || "Current target",
      },
    );
  } else {
    upscaleRows.push({ label: "Output size", value: "Source size" });
  }

  return {
    request: {
      profile: "final",
      range,
      ...(input.selectedClipId ? { clipId: input.selectedClipId } : {}),
      includeColor: true,
      includeAudio: true,
      includeOverlays: true,
      upscale,
      outputName: String(input.outputName || "").trim(),
    },
    sections: [
      {
        id: "video",
        title: "Video",
        rows: [
          { label: "Range", value: rangeLabel },
          { label: "Picture", value: range === "clip" || range === "selected" ? clipName : `${clips.length || 0} picture clip${clips.length === 1 ? "" : "s"}` },
          { label: "Color grade", value: gradeClip ? `${colorValue} on ${clipName}` : "None" },
          { label: "Lighting", value: lighting || "None" },
          { label: "Adjustments", value: adjustments.length ? adjustments.join(", ") : "None" },
          { label: "Titles and objects", value: "Burned in when this scene has them" },
        ],
      },
      { id: "upscale", title: "Upscale", rows: upscaleRows },
      {
        id: "audio",
        title: "Audio",
        rows: [
          { label: "Audio", value: "Included" },
          { label: "Range", value: rangeLabel },
          { label: "Source audio", value: trackMuted(input.sequence, "audio") ? "Muted" : "On" },
          { label: "Music", value: stemRow(input.sequence, input.assets, "music", audio?.musicAssetId) },
          { label: "Sound effects", value: stemRow(input.sequence, input.assets, "sfx", audio?.sfxAssetId) },
        ],
      },
      {
        id: "output",
        title: "Output",
        rows: [
          { label: "Duration", value: frameToTimecode(durationFrames || 0, fps) },
          { label: "Frame rate", value: `${fps} fps` },
          { label: "Profile", value: "Final" },
        ],
      },
    ],
  };
}

export function progressPercent(progress: unknown, status: string): number {
  if (status === "done") return 100;
  const value = typeof progress === "number" ? progress : Number(progress);
  if (!Number.isFinite(value)) return 0;
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return Math.min(99, pct);
}

export function mergeStageLog(existing: RenderStageNote[], incoming: RenderStageNote[]): RenderStageNote[] {
  const next = [...existing];
  for (const note of incoming) {
    const message = String(note.message || note.stage || "").trim();
    const stage = String(note.stage || message).trim();
    if (!message && !stage) continue;
    const last = next[next.length - 1];
    if (last && last.stage === stage && last.message === message && Boolean(last.failed) === Boolean(note.failed)) continue;
    next.push({ stage, message: message || stage, progress: note.progress, failed: note.failed });
  }
  return next.slice(-24);
}

export function humanJobError(message: string): string {
  const text = String(message || "").trim();
  if (!text) return "Final render stopped before it finished.";
  if (text.includes("Traceback") || text.includes('File "')) {
    const lines = text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const last = lines[lines.length - 1] || "";
    const cleaned = last.replace(/^[\w.]*Error:\s*/, "").trim();
    return cleaned || "Final render stopped before it finished.";
  }
  return text;
}

export function parseRenderHistory(raw: unknown): { stages: RenderStageNote[]; assetId: string | null } {
  let parsed: unknown = raw;
  if (typeof raw === "string") {
    if (!raw.trim()) return { stages: [], assetId: null };
    try {
      parsed = JSON.parse(raw);
    } catch {
      return { stages: [], assetId: null };
    }
  }
  if (!parsed || typeof parsed !== "object") return { stages: [], assetId: null };
  const record = parsed as Record<string, unknown>;
  const stages = Array.isArray(record.stages)
    ? record.stages
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => ({
          stage: String(item.stage || ""),
          message: String(item.message || item.stage || ""),
          progress: typeof item.progress === "number" ? item.progress : undefined,
        }))
        .filter((item) => item.stage || item.message)
    : [];
  const assetId = String(record.assetId || record.output_asset_id || "").trim() || null;
  return { stages, assetId };
}

const TERMINAL_FAILURE = new Set(["failed", "cancelled", "canceled", "timed_out"]);

export function applyFinalRenderJob(session: FinalRenderSession, job: Record<string, unknown>): FinalRenderSession {
  const status = String(job.status || "");
  const stage = String(job.stage || "");
  const message = String(job.message || "");
  const history = parseRenderHistory(job.history);
  let log = history.stages.length ? history.stages.map((note) => ({ ...note })) : [...session.log];
  const assetId = history.assetId || session.assetId;
  const jobId = String(job.jobId || session.jobId || "").trim() || null;
  const terminal = status === "done" || TERMINAL_FAILURE.has(status);
  if (!terminal && (stage || message)) {
    log = mergeStageLog(log, [{ stage: stage || message, message: message || stage }]);
  }
  if (status === "done") {
    log = mergeStageLog(log, [{ stage: "Completed", message: "Complete" }]);
    return {
      ...session,
      phase: "done",
      progress: 1,
      stage: "Completed",
      message: "Final Render Complete",
      error: null,
      assetId,
      jobId,
      log,
    };
  }
  if (TERMINAL_FAILURE.has(status)) {
    const error = humanJobError(message);
    log = mergeStageLog(log, [{ stage: stage || "Failed", message: error, failed: true }]);
    return {
      ...session,
      phase: "failed",
      progress: progressPercent(job.progress, status) / 100,
      stage: stage || "Failed",
      message: error,
      error,
      assetId,
      jobId,
      log,
    };
  }
  return {
    ...session,
    phase: "running",
    progress: progressPercent(job.progress, status) / 100,
    stage,
    message: message || stage,
    error: null,
    assetId,
    jobId,
    log,
  };
}

/** The Preview Monitor shows an explicit finished asset ahead of the playhead clip. */
export function monitorPreviewAssetId(
  pinAssetId: string | null | undefined,
  playheadAssetId: string | null | undefined,
  viewerAssetId: string | null | undefined,
): string | null {
  const pin = String(pinAssetId || "").trim();
  if (pin) return pin;
  return String(playheadAssetId || "").trim() || String(viewerAssetId || "").trim() || null;
}

export function emptyFinalRenderSession(): FinalRenderSession {
  return {
    phase: "confirm",
    jobId: null,
    progress: 0,
    stage: "",
    message: "",
    error: null,
    assetId: null,
    log: [],
    outputName: "",
    outputFile: "",
  };
}
