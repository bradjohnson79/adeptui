import {
  DEFAULT_TRACK_BLUEPRINT,
  type MagiClip,
  type MagiEditCommand,
  type MagiSequenceDocument,
  type MagiTrack,
} from "./types";

function uid(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

/** Stable id generator for any clip created by MAGI (m4: FX/ADJ passes route
 * through the same uid() path so clip ids never collide or repeat patterns). */
export function nextClipId(): string {
  return uid("clip");
}

function nowIso(): string {
  return new Date().toISOString();
}

export function createEmptySequence(projectId: string, frameRate = 24): MagiSequenceDocument {
  const tracks: MagiTrack[] = DEFAULT_TRACK_BLUEPRINT.map((item, index) => ({
    id: uid(`trk_${item.label.toLowerCase()}`),
    kind: item.kind,
    label: item.label,
    order: index,
  }));
  return {
    id: uid("seq"),
    projectId,
    frameRate,
    durationFrames: frameRate * 60,
    playheadFrame: 0,
    tracks,
    clips: [],
    markers: [],
    snapEnabled: true,
    revision: 1,
    updatedAt: nowIso(),
    recipeId: null,
    exportLedger: {},
  };
}

function bump(doc: MagiSequenceDocument, patch: Partial<MagiSequenceDocument>): MagiSequenceDocument {
  return {
    ...doc,
    ...patch,
    revision: doc.revision + 1,
    updatedAt: nowIso(),
  };
}

function clipEnd(clip: MagiClip): number {
  return clip.startFrame + clip.durationFrames;
}

/** m3: resolve the clip whose timeline span contains `frame` on a track, or
 * null when no clip covers that frame. Used to drive frame-synced preview. */
export function clipUnderPlayhead(
  doc: MagiSequenceDocument,
  frame: number,
  trackKind?: MagiTrack["kind"],
): MagiClip | null {
  for (const clip of doc.clips) {
    if (clip.startFrame > frame || clipEnd(clip) <= frame) continue;
    if (!trackKind) return clip;
    const track = doc.tracks.find((t) => t.id === clip.trackId);
    if (track?.kind === trackKind) return clip;
  }
  return null;
}

/** m3: timeline-relative source time for a clip at a given playhead frame
 * (in media frames). Returns null when the playhead is outside the clip. */
export function clipSourceFrame(clip: MagiClip, playheadFrame: number): number | null {
  if (playheadFrame < clip.startFrame || playheadFrame >= clipEnd(clip)) return null;
  const offset = playheadFrame - clip.startFrame;
  return Math.max(0, clip.inPoint + offset);
}

export function recomputeDuration(doc: MagiSequenceDocument): number {
  const maxClip = doc.clips.reduce((acc, clip) => Math.max(acc, clipEnd(clip)), 0);
  return Math.max(doc.frameRate * 10, maxClip + doc.frameRate);
}

export function applyEditCommand(
  doc: MagiSequenceDocument,
  command: MagiEditCommand,
  selection: string[],
): { doc: MagiSequenceDocument; selection: string[] } {
  const kind = command.kind;
  const payload = command.payload || {};

  if (kind === "SetPlayhead") {
    const frame = Math.max(0, Number(payload.frame ?? doc.playheadFrame));
    return { doc: bump(doc, { playheadFrame: frame }), selection };
  }

  if (kind === "Select") {
    const ids = Array.isArray(payload.ids) ? (payload.ids as string[]) : [];
    return { doc, selection: ids };
  }

  if (kind === "Deselect") {
    return { doc, selection: [] };
  }

  if (kind === "Insert" || kind === "Overwrite") {
    const trackId = String(payload.trackId || doc.tracks[0]?.id || "");
    const assetId = String(payload.assetId || "");
    if (!trackId || !assetId) return { doc, selection };
    const durationFrames = Math.max(1, Number(payload.durationFrames ?? doc.frameRate * 3));
    const startFrame =
      payload.startFrame != null ? Number(payload.startFrame) : doc.playheadFrame;
    let clips = [...doc.clips];
    if (kind === "Overwrite") {
      const end = startFrame + durationFrames;
      clips = clips.flatMap((clip) => {
        if (clip.trackId !== trackId) return [clip];
        const cEnd = clipEnd(clip);
        if (cEnd <= startFrame || clip.startFrame >= end) return [clip];
        // Simple overwrite: drop overlapping clips on the track.
        return [];
      });
    }
    const clip: MagiClip = {
      id: nextClipId(),
      trackId,
      assetId,
      name: String(payload.name || "Clip"),
      startFrame,
      durationFrames,
      inPoint: Number(payload.inPoint ?? 0),
      outPoint: Number(payload.outPoint ?? durationFrames),
      batchBlockId: payload.batchBlockId != null ? String(payload.batchBlockId) : undefined,
      generationId: payload.generationId != null ? String(payload.generationId) : undefined,
      takeId: payload.takeId != null ? String(payload.takeId) : undefined,
      sourceClipId: payload.sourceClipId != null ? String(payload.sourceClipId) : undefined,
      sceneId: payload.sceneId != null ? String(payload.sceneId) : undefined,
    };
    clips.push(clip);
    const next = bump(doc, {
      clips,
      playheadFrame: startFrame + durationFrames,
      durationFrames: recomputeDuration({ ...doc, clips }),
    });
    return { doc: next, selection: [clip.id] };
  }

  if (kind === "RippleDelete" || kind === "Lift" || kind === "Extract") {
    const ids = selection.length ? selection : [];
    if (!ids.length) return { doc, selection };
    const removing = new Set(ids);
    const removed = doc.clips.filter((clip) => removing.has(clip.id));
    let clips = doc.clips.filter((clip) => !removing.has(clip.id));
    if (kind === "RippleDelete" || kind === "Extract") {
      for (const gone of removed) {
        const gap = gone.durationFrames;
        clips = clips.map((clip) => {
          if (clip.trackId !== gone.trackId) return clip;
          if (clip.startFrame >= clipEnd(gone)) {
            return { ...clip, startFrame: Math.max(0, clip.startFrame - gap) };
          }
          return clip;
        });
      }
    }
    const next = bump(doc, {
      clips,
      durationFrames: recomputeDuration({ ...doc, clips }),
    });
    return { doc: next, selection: [] };
  }

  if (kind === "Trim") {
    const clipId = String(payload.clipId || selection[0] || "");
    const edge = String(payload.edge || "right");
    const delta = Number(payload.deltaFrames || 0);
    if (!clipId || !delta) return { doc, selection };
    const clips = doc.clips.map((clip) => {
      if (clip.id !== clipId) return clip;
      if (edge === "left") {
        const nextStart = Math.max(0, clip.startFrame + delta);
        const shrink = nextStart - clip.startFrame;
        return {
          ...clip,
          startFrame: nextStart,
          durationFrames: Math.max(1, clip.durationFrames - shrink),
          inPoint: Math.max(0, clip.inPoint + shrink),
        };
      }
      return {
        ...clip,
        durationFrames: Math.max(1, clip.durationFrames + delta),
        outPoint: Math.max(clip.inPoint + 1, clip.outPoint + delta),
      };
    });
    return {
      doc: bump(doc, { clips, durationFrames: recomputeDuration({ ...doc, clips }) }),
      selection,
    };
  }

  if (kind === "Split") {
    const clipId = String(payload.clipId || selection[0] || "");
    const at = Number(payload.frame ?? doc.playheadFrame);
    const target = doc.clips.find((clip) => clip.id === clipId);
    if (!target || at <= target.startFrame || at >= clipEnd(target)) {
      return { doc, selection };
    }
    const leftDur = at - target.startFrame;
    const rightDur = clipEnd(target) - at;
    const left: MagiClip = { ...target, durationFrames: leftDur, outPoint: target.inPoint + leftDur };
    const right: MagiClip = {
      ...target,
      id: nextClipId(),
      startFrame: at,
      durationFrames: rightDur,
      inPoint: target.inPoint + leftDur,
      outPoint: target.outPoint,
    };
    const clips = doc.clips.flatMap((clip) => (clip.id === clipId ? [left, right] : [clip]));
    return { doc: bump(doc, { clips }), selection: [left.id, right.id] };
  }

  if (kind === "Move") {
    const clipId = String(payload.clipId || selection[0] || "");
    const startFrame = Number(payload.startFrame);
    const trackId = payload.trackId != null ? String(payload.trackId) : undefined;
    if (!clipId || !Number.isFinite(startFrame)) return { doc, selection };
    const clips = doc.clips.map((clip) =>
      clip.id === clipId
        ? { ...clip, startFrame: Math.max(0, startFrame), trackId: trackId || clip.trackId }
        : clip,
    );
    return {
      doc: bump(doc, { clips, durationFrames: recomputeDuration({ ...doc, clips }) }),
      selection,
    };
  }

  if (kind === "Duplicate" || kind === "Paste") {
    const sourceIds =
      kind === "Paste" && Array.isArray(payload.ids)
        ? (payload.ids as string[])
        : selection;
    const offset = Number(payload.offsetFrames ?? doc.frameRate);
    const created: MagiClip[] = [];
    for (const id of sourceIds) {
      const src = doc.clips.find((clip) => clip.id === id);
      if (!src) continue;
      created.push({
        ...src,
        id: nextClipId(),
        startFrame: src.startFrame + offset,
        name: `${src.name || "Clip"} copy`,
      });
    }
    if (!created.length) return { doc, selection };
    const clips = [...doc.clips, ...created];
    return {
      doc: bump(doc, { clips, durationFrames: recomputeDuration({ ...doc, clips }) }),
      selection: created.map((clip) => clip.id),
    };
  }

  if (kind === "AddMarker") {
    const frame = Number(payload.frame ?? doc.playheadFrame);
    const markers = [
      ...doc.markers,
      { id: uid("mk"), frame, label: String(payload.label || "Marker") },
    ];
    return { doc: bump(doc, { markers }), selection };
  }

  if (kind === "AddTrack") {
    const trackKind = (payload.kind as MagiTrack["kind"]) || "video";
    const label = String(payload.label || trackKind.toUpperCase());
    const tracks = [
      ...doc.tracks,
      { id: uid("trk"), kind: trackKind, label, order: doc.tracks.length },
    ];
    return { doc: bump(doc, { tracks }), selection };
  }

  if (kind === "ApplyTransition") {
    const clipId = String(payload.clipId || selection[0] || "");
    const transitionId = String(payload.transitionId || "crossfade");
    const edge = String(payload.edge || "out");
    const clips = doc.clips.map((clip) => {
      if (clip.id !== clipId) return clip;
      return edge === "in"
        ? { ...clip, transitionInId: transitionId }
        : { ...clip, transitionOutId: transitionId };
    });
    return { doc: bump(doc, { clips }), selection };
  }

  return { doc, selection };
}

export function frameToTimecode(frame: number, fps: number): string {
  const totalSec = Math.max(0, frame) / Math.max(1, fps);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = Math.floor(totalSec % 60);
  const f = Math.floor(Math.max(0, frame) % Math.max(1, fps));
  const pad = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}
