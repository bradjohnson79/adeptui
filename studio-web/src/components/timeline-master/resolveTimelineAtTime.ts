/**
 * resolveTimelineAtTime — TIMELINE_DRIVEN_PREVIEW
 *
 * Resolves the active clips at a given playhead position so the Preview Monitor
 * can display the active image/video clip and the corresponding prompt as a
 * lower-third overlay (without burning it into the asset).
 *
 * Pure function — no side effects — trivial to test. Resolves not just the
 * batch and clips, but also the relative time within the active batch/clip so
 * video preview and later audio synchronization have what they need.
 */
import type { DirectorTimeline } from "../DirectorTracks";
import type { BatchBlock } from "../../timelineMaster/contracts";

export interface ResolvedTimelineFrame {
  /** Active batch at playhead (by cumulative planned duration), if any. */
  activeBatch: BatchBlock | null;
  /** Time within the active batch (seconds from batch start). */
  batchLocalTime: number;
  /** Active visual clip (image or video) intersecting the playhead. */
  activeVisual:
    | { kind: "image" | "video"; clipId: string; assetId: string | null; label: string }
    | null;
  /** Time within the active visual clip. */
  visualLocalTime: number;
  /** Active prompt segment intersecting the playhead, if any. */
  activePrompt:
    | { segmentId: string; text: string; label: string }
    | null;
  /** Active audio clip intersecting the playhead, if any. */
  activeAudio:
    | { clipId: string; assetId: string | null; label: string }
    | null;
  /** Time within the active audio clip. */
  audioLocalTime: number;
  /** Active SFX clip intersecting the playhead, if any. */
  activeSfx: { clipId: string; assetId: string | null; label: string } | null;
  /** Active camera instruction clip intersecting the playhead, if any. */
  activeCameraInstruction:
    | { clipId: string; motionType: string | null; rig: string | null; label: string }
    | null;
}

function intersects(start: number, length: number, t: number): boolean {
  return t >= start && t < start + length;
}

/**
 * Resolve the active batch by cumulative planned duration. Batches are ordered
 * by `order`; each batch occupies [cursor, cursor + plannedDuration).
 */
export function resolveBatchAtTime(
  batches: BatchBlock[],
  t: number,
): { batch: BatchBlock; localTime: number } | null {
  const sorted = batches.slice().sort((a, b) => a.order - b.order);
  let cursor = 0;
  for (const batch of sorted) {
    const len = Math.max(0.1, batch.duration.plannedDuration || 0);
    if (t >= cursor && t < cursor + len) {
      return { batch, localTime: t - cursor };
    }
    cursor += len;
  }
  return null;
}

export function resolveTimelineAtTime(
  timeline: DirectorTimeline | null,
  master: { batchBlocks?: BatchBlock[] } | null,
  playheadSec: number,
): ResolvedTimelineFrame {
  const t = Math.max(0, playheadSec || 0);

  const batchRes = master?.batchBlocks?.length
    ? resolveBatchAtTime(master.batchBlocks, t)
    : null;
  const activeBatch = batchRes?.batch ?? null;
  const batchLocalTime = batchRes?.localTime ?? 0;

  // Visual: prefer batch-owned visualClips, else legacy scene-global tracks.
  let activeVisual: ResolvedTimelineFrame["activeVisual"] = null;
  let visualLocalTime = 0;
  if (activeBatch && (activeBatch.visualClips || []).length) {
    const clip = (activeBatch.visualClips || []).find((c) =>
      intersects(c.start, c.length, batchLocalTime),
    );
    if (clip && clip.assetId) {
      activeVisual = {
        kind: clip.kind === "video" ? "video" : "image",
        clipId: clip.id,
        assetId: clip.assetId,
        label: clip.label || "",
      };
      visualLocalTime = batchLocalTime - clip.start;
    }
  }
  if (!activeVisual && timeline) {
    const videoClip = (timeline.video_clips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (videoClip && videoClip.asset_id) {
      activeVisual = {
        kind: "video",
        clipId: videoClip.id,
        assetId: videoClip.asset_id,
        label: videoClip.label || "",
      };
      visualLocalTime = t - videoClip.start;
    } else {
      const imageClip = (timeline.image_clips || []).find((c) =>
        intersects(c.start, c.length, t),
      );
      if (imageClip && imageClip.asset_id) {
        activeVisual = {
          kind: "image",
          clipId: imageClip.id,
          assetId: imageClip.asset_id,
          label: imageClip.label || imageClip.role || "",
        };
        visualLocalTime = t - imageClip.start;
      }
    }
  }

  // Prompt: prefer batch-owned promptSegments (relative to batch), else legacy.
  let activePrompt: ResolvedTimelineFrame["activePrompt"] = null;
  if (activeBatch && (activeBatch.promptSegments || []).length) {
    const seg = (activeBatch.promptSegments || []).find((s) =>
      intersects(s.start, s.length, batchLocalTime),
    );
    if (seg && seg.text) {
      activePrompt = { segmentId: seg.id, text: seg.text, label: "" };
    }
  }
  if (!activePrompt && timeline) {
    const seg = (timeline.prompt_segments || []).find((s) =>
      intersects(s.start, s.length, t),
    );
    if (seg && seg.text) {
      activePrompt = { segmentId: seg.id, text: seg.text, label: "" };
    }
  }

  // Audio
  let activeAudio: ResolvedTimelineFrame["activeAudio"] = null;
  let audioLocalTime = 0;
  if (activeBatch && (activeBatch.audioClips || []).length) {
    const clip = (activeBatch.audioClips || []).find((c) =>
      intersects(c.start, c.length, batchLocalTime),
    );
    if (clip && clip.assetId) {
      activeAudio = { clipId: clip.id, assetId: clip.assetId, label: clip.label || "" };
      audioLocalTime = batchLocalTime - clip.start;
    }
  }
  if (!activeAudio && timeline) {
    const clip = (timeline.audio_clips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (clip && clip.asset_id) {
      activeAudio = { clipId: clip.id, assetId: clip.asset_id, label: clip.label || "" };
      audioLocalTime = t - clip.start;
    }
  }

  // SFX
  let activeSfx: ResolvedTimelineFrame["activeSfx"] = null;
  if (activeBatch && (activeBatch.sfxClips || []).length) {
    const clip = (activeBatch.sfxClips || []).find((c) =>
      intersects(c.start, c.length, batchLocalTime),
    );
    if (clip && clip.assetId) {
      activeSfx = { clipId: clip.id, assetId: clip.assetId, label: clip.label || "" };
    }
  }
  if (!activeSfx && timeline) {
    const clip = (timeline.sfx_clips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (clip && clip.asset_id) {
      activeSfx = { clipId: clip.id, assetId: clip.asset_id, label: clip.label || "" };
    }
  }

  // Camera
  let activeCameraInstruction: ResolvedTimelineFrame["activeCameraInstruction"] = null;
  if (activeBatch && (activeBatch.cameraInstructions || []).length) {
    const clip = (activeBatch.cameraInstructions || []).find((c) =>
      intersects(c.start, c.length, batchLocalTime),
    );
    if (clip) {
      activeCameraInstruction = {
        clipId: clip.id,
        motionType: clip.motion_type ?? null,
        rig: clip.rig ?? null,
        label: clip.label || "",
      };
    }
  }
  if (!activeCameraInstruction && timeline) {
    const clip = (timeline.camera_clips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (clip) {
      activeCameraInstruction = {
        clipId: clip.id,
        motionType: clip.motion_type ?? null,
        rig: clip.rig ?? null,
        label: clip.label || "",
      };
    }
  }

  return {
    activeBatch,
    batchLocalTime,
    activeVisual,
    visualLocalTime,
    activePrompt,
    activeAudio,
    audioLocalTime,
    activeSfx,
    activeCameraInstruction,
  };
}
