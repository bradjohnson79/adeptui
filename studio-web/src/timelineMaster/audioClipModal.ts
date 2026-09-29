/**
 * Audio / SFX clip modal draft.
 * One draft for the + button and for double-click. Master batch.audioClips /
 * batch.sfxClips stay the store. Title and description live on the clip's
 * existing metadata bag so Inspector and the modal read the same clip.
 */

export const TIMELINE_AUDIO_FILE_ACCEPT = ".wav,.mp3,.ogg,.flac,.m4a,.aac";

export type AudioClipModalKind = "audio" | "sfx";

export type AudioClipDraft = {
  id: string | null;
  kind: AudioClipModalKind;
  title: string;
  description: string;
  label: string;
  start: number;
  length: number;
  volume: number;
  assetId: string | null;
  pendingFileName: string | null;
};

const GENERIC_FACE = new Set(["audio", "sfx", "music", "sound effect"]);

export function filenameStem(name: string): string {
  const base = (name || "").split(/[/\\]/).pop() || name || "";
  const stem = base.replace(/\.[^.]+$/, "").trim();
  return stem;
}

export function roundTimelineSec(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round(value * 100) / 100;
}

/** Same ratio the Timeline lane already uses: pointer across the lane width. */
export function laneTimeFromPointer(
  clientX: number,
  lane: { left: number; width: number },
  durationSec: number,
): number {
  const width = Math.max(1, lane.width);
  const ratio = Math.min(1, Math.max(0, (clientX - lane.left) / width));
  return roundTimelineSec(ratio * Math.max(0, durationSec));
}

export function blankAudioClipDraft(kind: AudioClipModalKind, start: number): AudioClipDraft {
  return {
    id: null,
    kind,
    title: "",
    description: "",
    label: "",
    start: roundTimelineSec(Math.max(0, start)),
    length: 0,
    volume: 1,
    assetId: null,
    pendingFileName: null,
  };
}

export function applySelectedAudioFile(
  draft: AudioClipDraft,
  fileName: string,
  durationSec: number | null,
): AudioClipDraft {
  const stem = filenameStem(fileName);
  const title = draft.title.trim() ? draft.title : stem;
  const face = draft.label.trim();
  const label = face && !GENERIC_FACE.has(face.toLowerCase()) ? draft.label : stem || face;
  const length =
    durationSec != null && Number.isFinite(durationSec) && durationSec > 0
      ? roundTimelineSec(durationSec)
      : draft.length;
  return {
    ...draft,
    title,
    label,
    length,
    pendingFileName: fileName,
  };
}

export function audioClipMetadata(clip: {
  title?: string | null;
  description?: string | null;
  metadata?: Record<string, unknown> | null;
}): Record<string, unknown> {
  const prev = { ...((clip.metadata as Record<string, unknown> | null) || {}) };
  prev.title = typeof clip.title === "string" ? clip.title : typeof prev.title === "string" ? prev.title : "";
  prev.description =
    typeof clip.description === "string"
      ? clip.description
      : typeof prev.description === "string"
        ? prev.description
        : "";
  return prev;
}

export function textFromAudioMetadata(
  metadata: Record<string, unknown> | null | undefined,
  key: "title" | "description",
): string {
  const value = metadata?.[key];
  return typeof value === "string" ? value : "";
}

/** Read the file's own length. Does not invent a duration. */
export function readAudioFileDuration(file: Blob): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();
    let settled = false;
    const finish = (value: number | null) => {
      if (settled) return;
      settled = true;
      URL.revokeObjectURL(url);
      audio.removeAttribute("src");
      audio.load();
      resolve(value);
    };
    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const duration = audio.duration;
      finish(Number.isFinite(duration) && duration > 0 ? roundTimelineSec(duration) : null);
    };
    audio.onerror = () => finish(null);
    window.setTimeout(() => finish(null), 8000);
    audio.src = url;
  });
}
