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
import type { TimelineBoardView } from "../DirectorTracks";
import type { BatchBlock, SceneTimelineMaster } from "../../timelineMaster/contracts";
import { filterVideoClipsForSceneTake, resolveSceneTake } from "../../timelineMaster/playableVisualTakes";
import { isImageFrameClip } from "../../timelineMaster/imageFrameVisual";

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
  for (let i = 0; i < sorted.length; i += 1) {
    const batch = sorted[i];
    const len = Math.max(0.1, batch.duration.plannedDuration || 0);
    const start = cursor;
    const end = cursor + len;
    const isLast = i === sorted.length - 1;
    // Exclusive end except the last batch, so the scene-end playhead still
    // resolves Batch N instead of falling through to a leftover single clip.
    if (t >= start && (t < end || (isLast && t <= end))) {
      return { batch, localTime: Math.min(Math.max(0, t - start), Math.max(0, len - 1e-3)) };
    }
    cursor = end;
  }
  return null;
}

export function resolveTimelineAtTime(
  timeline: TimelineBoardView | null,
  master: { batchBlocks?: BatchBlock[] } | null,
  playheadSec: number,
  options?: { takeId?: string | null },
): ResolvedTimelineFrame {
  const t = Math.max(0, playheadSec || 0);
  const sceneMaster = master as SceneTimelineMaster | null;
  const sceneTake = resolveSceneTake(sceneMaster, options?.takeId);
  const previewingOther = Boolean(options?.takeId && options.takeId !== sceneMaster?.currentSceneTakeId);

  const batchRes = master?.batchBlocks?.length
    ? resolveBatchAtTime(master.batchBlocks, t)
    : null;
  const activeBatch = batchRes?.batch ?? null;
  const batchLocalTime = batchRes?.localTime ?? 0;

  // Visual: Timeline videoClips (Generation A|Retake|B) are authoritative when
  // present — same contract as resolveVisualVideoClips. Source local time is
  // timelineLocal + trim_start (field name trim_start only; never sourceIn).
  let activeVisual: ResolvedTimelineFrame["activeVisual"] = null;
  let visualLocalTime = 0;
  const timelineVideoClips = previewingOther
    ? []
    : filterVideoClipsForSceneTake(timeline?.videoClips || [], sceneTake);
  if (timelineVideoClips.length > 0) {
    const videoClip = timelineVideoClips.find((c) => intersects(c.start, c.length, t));
    if (videoClip && videoClip.asset_id) {
      // Image-Frame still: media_type=image / imgclip_ / role=image_frame until rtclip_ lands.
      const still = isImageFrameClip(videoClip);
      activeVisual = {
        kind: still ? "image" : "video",
        clipId: videoClip.id,
        assetId: videoClip.asset_id,
        label: videoClip.label || "",
      };
      const timelineLocal = Math.max(0, t - (videoClip.start || 0));
      // Stills ignore source scrub offset (trim_start stays 0 on imgclip_).
      visualLocalTime = still ? timelineLocal : timelineLocal + Number(videoClip.trim_start || 0);
    }
  }
  const visualPlacementAuthoritative = timeline?.media_mode === "video";
  const hasManagedVisuals = Boolean(
    activeBatch &&
      (activeBatch.visualClips || []).some((clip) => (clip.kind === "video" || clip.kind === "image") && clip.assetId),
  );
  if (
    !activeVisual &&
    sceneTake &&
    activeBatch &&
    (previewingOther || (!visualPlacementAuthoritative && !hasManagedVisuals))
  ) {
    const member = (sceneTake.batches || []).find((row) => row.batchId === activeBatch.id && row.assetId);
    if (member?.assetId) {
      activeVisual = {
        kind: "video",
        clipId: `${activeBatch.id}-scene-take`,
        assetId: member.assetId,
        label: activeBatch.label || "Take",
      };
      visualLocalTime = batchLocalTime;
    }
  }
  // Batch-owned visualClips when director Visual track is empty.
  if (
    !activeVisual &&
    !visualPlacementAuthoritative &&
    !previewingOther &&
    activeBatch &&
    (activeBatch.visualClips || []).length
  ) {
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
      const timelineLocal = Math.max(0, batchLocalTime - clip.start);
      visualLocalTime = timelineLocal + Number(clip.trimStart || 0);
    }
  }
  // Playable take when visualClips was never written: approved first, else
  // the latest finished candidate so a draft generate still plays on Visual.
  if (!activeVisual && !visualPlacementAuthoritative && !previewingOther && activeBatch?.approvedClip?.assetId) {
    activeVisual = {
      kind: "video",
      clipId: `${activeBatch.id}-approved`,
      assetId: activeBatch.approvedClip.assetId,
      label: activeBatch.label || "Approved take",
    };
    visualLocalTime = batchLocalTime;
  }
  if (!activeVisual && !visualPlacementAuthoritative && !previewingOther && activeBatch) {
    const latest = [...(activeBatch.candidateVersions || [])]
      .filter((candidate) => candidate.assetId)
      .sort((a, b) => String(a.createdAt || "").localeCompare(String(b.createdAt || "")))
      .at(-1);
    if (latest?.assetId) {
      activeVisual = {
        kind: "video",
        clipId: `${activeBatch.id}-candidate`,
        assetId: latest.assetId,
        label: latest.label || activeBatch.label || "Latest take",
      };
      visualLocalTime = batchLocalTime;
    }
  }
  if (!activeVisual && timeline) {
    const imageClip = (timeline.imageClips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (imageClip && imageClip.asset_id) {
      activeVisual = {
        kind: "image",
        clipId: imageClip.id,
        assetId: imageClip.asset_id,
        label: imageClip.label || imageClip.role || "",
      };
      const timelineLocal = Math.max(0, t - (imageClip.start || 0));
      visualLocalTime = timelineLocal + Number(imageClip.trim_start || 0);
    }
  }

  // Prompt: Master batch.promptSegments only (single store). Legacy retired.
  let activePrompt: ResolvedTimelineFrame["activePrompt"] = null;
  if (activeBatch && (activeBatch.promptSegments || []).length) {
    const seg = (activeBatch.promptSegments || []).find((s) =>
      intersects(s.start, s.length, batchLocalTime),
    );
    if (seg && seg.text) {
      activePrompt = { segmentId: seg.id, text: seg.text, label: "" };
    }
  }

  // Audio — batch-owned authority when any batch has audioClips (WYSIWYG).
  let activeAudio: ResolvedTimelineFrame["activeAudio"] = null;
  let audioLocalTime = 0;
  const anyBatchAudio = (master?.batchBlocks || []).some((b) => (b.audioClips || []).length > 0);
  if (anyBatchAudio) {
    if (activeBatch) {
      const clip = (activeBatch.audioClips || []).find((c) =>
        intersects(c.start, c.length, batchLocalTime),
      );
      if (clip && clip.assetId) {
        activeAudio = { clipId: clip.id, assetId: clip.assetId, label: clip.label || "" };
        audioLocalTime = batchLocalTime - clip.start;
      }
    }
  } else if (timeline) {
    const clip = (timeline.audioClips || []).find((c) =>
      intersects(c.start, c.length, t),
    );
    if (clip && clip.asset_id) {
      activeAudio = { clipId: clip.id, assetId: clip.asset_id, label: clip.label || "" };
      audioLocalTime = t - clip.start;
    }
  }

  // SFX — same batch-owned authority rule.
  let activeSfx: ResolvedTimelineFrame["activeSfx"] = null;
  const anyBatchSfx = (master?.batchBlocks || []).some((b) => (b.sfxClips || []).length > 0);
  if (anyBatchSfx) {
    if (activeBatch) {
      const clip = (activeBatch.sfxClips || []).find((c) =>
        intersects(c.start, c.length, batchLocalTime),
      );
      if (clip && clip.assetId) {
        activeSfx = { clipId: clip.id, assetId: clip.assetId, label: clip.label || "" };
      }
    }
  } else if (timeline) {
    const clip = (timeline.sfxClips || []).find((c) =>
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
    const clip = (timeline.cameraClips || []).find((c) =>
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
