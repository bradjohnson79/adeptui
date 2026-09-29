/** Master-only Timeline mutations. No DirectorTimeline persist store. */

import { api } from "../api";
import type { BatchBlock, BatchClip, SceneTimelineMaster, TimelinePromptSegment } from "./contracts";
import { textFromAudioMetadata } from "./audioClipModal";
import { executionWindowSpans } from "./resolveExecutionWindowForPrompt";
import { assertNoSameTrackOverlap, USER_FACING_TRACK_OCCUPIED, SameTrackOverlapError } from "./sameTrackNoOverlap";

export function flattenMasterPrompts(master: SceneTimelineMaster | null | undefined): TimelinePromptSegment[] {
  const out: TimelinePromptSegment[] = [];
  for (const batch of [...(master?.batchBlocks || [])].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))) {
    for (const seg of batch.promptSegments || []) out.push(seg);
  }
  return out;
}

export function startContainingBatch(
  master: SceneTimelineMaster | null | undefined,
  start: number,
): BatchBlock | null {
  const spans = executionWindowSpans(master?.batchBlocks);
  if (!spans.length) return null;
  const t = Number(start) || 0;
  for (const { batch, start: a, end } of spans) {
    if (t + 1e-6 >= a && t < end - 1e-9) return batch;
  }
  return spans[spans.length - 1]?.batch || spans[0]?.batch || null;
}

function clipKey(clip: BatchClip): string {
  return String(clip.id || clip.legacyClipId || "");
}

export function findMasterPrompt(
  master: SceneTimelineMaster | null | undefined,
  id: string,
): { batch: BatchBlock; segment: TimelinePromptSegment } | null {
  if (!master || !id) return null;
  for (const batch of master.batchBlocks || []) {
    for (const segment of batch.promptSegments || []) {
      if (segment.id === id || segment.legacyPromptSegmentId === id) return { batch, segment };
    }
  }
  return null;
}

export async function patchMasterPrompt(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster,
  next: Partial<TimelinePromptSegment> & { start?: number; length?: number; text?: string; id?: string },
): Promise<void> {
  const start = Number(next.start ?? 0);
  const target = startContainingBatch(master, start);
  if (!target) return;
  // Cross-window move: the segment may currently live in a different batch.
  // Find it anywhere, and remove it from the source batch when it moves.
  const located = next.id ? findMasterPrompt(master, next.id) : null;
  if (located && located.batch.id !== target.id) {
    const sourceAfter = (located.batch.promptSegments || []).filter((ps) => ps !== located.segment);
    await api.directorTimelinePatchBatch(projectId, sceneId, located.batch.id, { promptSegments: sourceAfter });
  }
  const existing = [...(target.promptSegments || [])];
  const hit =
    located && located.batch.id === target.id
      ? located.segment
      : existing.find((ps) => ps.id === next.id || ps.legacyPromptSegmentId === next.id);
  const row: TimelinePromptSegment = hit
    ? {
        ...hit,
        text: next.text !== undefined ? next.text : hit.text,
        start,
        length: Number(next.length ?? hit.length) || 0,
        referenceBindingIds: next.referenceBindingIds ?? hit.referenceBindingIds ?? [],
        referenceNameBindings: next.referenceNameBindings ?? hit.referenceNameBindings,
        productionPrompt: next.productionPrompt !== undefined ? next.productionPrompt : hit.productionPrompt,
        userDirection: next.userDirection !== undefined ? next.userDirection : hit.userDirection,
        dialogue: next.dialogue !== undefined ? next.dialogue : hit.dialogue,
        movementSegmentRef:
          next.movementSegmentRef !== undefined ? next.movementSegmentRef : (hit.movementSegmentRef ?? null),
        movementSegmentRevision:
          next.movementSegmentRevision !== undefined
            ? next.movementSegmentRevision
            : (hit.movementSegmentRevision ?? null),
        strength:
          next.strength !== undefined && Number.isFinite(Number(next.strength))
            ? Number(next.strength)
            : hit.strength,
      }
    : ({
        id: next.id || `ps_${Math.random().toString(36).slice(2, 10)}`,
        start,
        length: Number(next.length) || Number(target.duration?.plannedDuration || 0) || 2,
        text: next.text || "",
        role: "primary",
        anchorIds: [],
        executionStrategy: "compiled",
        versionId: `psv_${Math.random().toString(36).slice(2, 10)}`,
        referenceBindingIds: next.referenceBindingIds || [],
        referenceNameBindings: next.referenceNameBindings,
        productionPrompt: next.productionPrompt !== undefined ? next.productionPrompt : null,
        userDirection: next.userDirection !== undefined ? next.userDirection : null,
        dialogue: next.dialogue !== undefined ? next.dialogue : null,
        movementSegmentRef: next.movementSegmentRef !== undefined ? next.movementSegmentRef : null,
        movementSegmentRevision:
          next.movementSegmentRevision !== undefined ? next.movementSegmentRevision : null,
        strength:
          next.strength !== undefined && Number.isFinite(Number(next.strength))
            ? Number(next.strength)
            : 1,
      } as TimelinePromptSegment);
  const promptSegments = hit ? existing.map((ps) => (ps === hit ? row : ps)) : [...existing, row];
  // Same-track law: Timed Prompt lane is scene-absolute across all windows.
  // Intersection helper excludes the candidate's own id (move/resize safe).
  try {
    assertNoSameTrackOverlap(flattenMasterPrompts(master), row, "prompt");
  } catch (err) {
    if (err instanceof SameTrackOverlapError) {
      throw new SameTrackOverlapError(USER_FACING_TRACK_OCCUPIED);
    }
    throw err;
  }
  await api.directorTimelinePatchBatch(projectId, sceneId, target.id, { promptSegments });
}


/** Pure Master projection after removing Timed Prompt ids (Instant Update). */
export function applyPromptRemovalToMaster(
  master: SceneTimelineMaster,
  ids: Iterable<string>,
): SceneTimelineMaster {
  const removed = new Set(Array.from(ids).filter(Boolean));
  if (!removed.size) return master;
  return {
    ...master,
    batchBlocks: (master.batchBlocks || []).map((batch) => ({
      ...batch,
      promptSegments: (batch.promptSegments || []).filter(
        (seg) => !removed.has(seg.id) && !removed.has(seg.legacyPromptSegmentId || ""),
      ),
    })),
  };
}

export async function removeMasterPrompts(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster,
  ids: Iterable<string>,
): Promise<void> {
  const removed = ids instanceof Set ? ids : new Set(ids);
  if (!removed.size) return;
  for (const batch of master.batchBlocks || []) {
    const before = batch.promptSegments || [];
    const after = before.filter((s) => !removed.has(s.id) && !removed.has(s.legacyPromptSegmentId || ""));
    if (after.length === before.length) continue;
    await api.directorTimelinePatchBatch(projectId, sceneId, batch.id, { promptSegments: after });
  }
}

type MasterClipAttr = "visualClips" | "audioClips" | "sfxClips" | "cameraInstructions";

/**
 * BATCH-LOCAL COORDINATE LAW: BatchClip.start is stored BATCH-LOCAL (0 = the
 * owning batch's window start). The view projects scene-absolute starts. All
 * writes through here accept SCENE-ABSOLUTE view starts and convert to
 * batch-local before persisting; reads (projectMasterPreviewClips) add the
 * window offset back. Backend managed takes (bbvclip_/rtclip_/imgclip_) are
 * already batch-local — this keeps creator/CD-placed clips on the same law.
 */
function batchWindowStarts(master: SceneTimelineMaster | null | undefined): Map<string, number> {
  const offsets = new Map<string, number>();
  for (const span of executionWindowSpans(master?.batchBlocks)) {
    offsets.set(span.batch.id, span.start);
  }
  return offsets;
}

/**
 * Atomic Master clip sync: removals + upserts composed against the same base
 * state, one PATCH per changed batch. Upsert starts are scene-absolute view
 * coordinates (converted to batch-local on write). A clip whose id already
 * exists in a DIFFERENT batch (cross-window drag) is moved, never duplicated.
 */
export async function syncMasterClips(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster,
  opts: {
    attr: MasterClipAttr;
    upserts?: Array<Partial<BatchClip> & { start: number; length: number; kind: BatchClip["kind"] }>;
    removeIds?: Iterable<string>;
  },
): Promise<void> {
  const { attr } = opts;
  const removed = opts.removeIds ? (opts.removeIds instanceof Set ? opts.removeIds : new Set(opts.removeIds)) : new Set<string>();
  const offsets = batchWindowStarts(master);
  const byBatch = new Map<string, BatchClip[]>();
  for (const batch of master.batchBlocks || []) {
    const stored = (batch[attr] as BatchClip[]) || [];
    byBatch.set(
      batch.id,
      removed.size ? stored.filter((c) => !removed.has(c.id) && !removed.has(c.legacyClipId || "")) : [...stored],
    );
  }
  for (const clip of opts.upserts || []) {
    const viewStart = Number(clip.start) || 0;
    const target = startContainingBatch(master, viewStart);
    if (!target) continue;
    // Cross-window move: if the id lives in another batch, drop it there first.
    let hit: BatchClip | undefined;
    if (clip.id) {
      for (const batch of master.batchBlocks || []) {
        const list = byBatch.get(batch.id) || [];
        const found = list.find((c) => c.id === clip.id || c.legacyClipId === clip.id);
        if (found) {
          hit = found;
          if (batch.id !== target.id) {
            byBatch.set(batch.id, list.filter((c) => c !== found));
          }
          break;
        }
      }
    }
    // Synthetic playable-take preview ids (bbclip_*) are display fallbacks,
    // never Master rows — refuse to CREATE them (updates to real rows allowed).
    if (!hit && String(clip.id || "").startsWith("bbclip_")) continue;
    const localStart = Math.max(0, viewStart - (offsets.get(target.id) ?? 0));
    const list = byBatch.get(target.id) || [];
    const row = {
      ...(hit || {
        id: clip.id || `clip_${Math.random().toString(36).slice(2, 10)}`,
        trimStart: 0,
        volume: 1,
        fade_in: 0,
        fade_out: 0,
        label: clip.label || clip.kind,
      }),
      ...clip,
      kind: clip.kind,
      start: localStart,
    } as BatchClip;
    byBatch.set(target.id, hit && list.includes(hit) ? list.map((c) => (c === hit ? row : c)) : [...list.filter((c) => c !== hit), row]);
  }
  for (const batch of master.batchBlocks || []) {
    const next = byBatch.get(batch.id) || [];
    const prev = (batch[attr] as BatchClip[]) || [];
    if (next.map(clipKey).join(",") === prev.map(clipKey).join(",") && next.length === prev.length) {
      const same = next.every((c, i) => {
        const before = prev[i];
        if (!before) return false;
        if (c.start !== before.start || c.length !== before.length || c.assetId !== before.assetId) return false;
        if (attr !== "audioClips" && attr !== "sfxClips") return true;
        return (
          (c.label || "") === (before.label || "") &&
          Number(c.volume ?? 1) === Number(before.volume ?? 1) &&
          JSON.stringify(c.metadata ?? null) === JSON.stringify(before.metadata ?? null)
        );
      });
      if (same) continue;
    }
    const patch: Record<string, unknown> = { [attr]: next };
    if (attr === "visualClips") {
      const removedTake = prev.find(
        (c) =>
          (removed.has(c.id) || removed.has(c.legacyClipId || "")) &&
          String(c.id || "").startsWith("bbvclip_") &&
          c.assetId &&
          !next.some((kept) => kept.assetId === c.assetId),
      );
      if (removedTake?.assetId) {
        patch.dismissedVisualAssetId = removedTake.assetId;
        batch.dismissedVisualAssetId = removedTake.assetId;
      }
    }
    await api.directorTimelinePatchBatch(projectId, sceneId, batch.id, patch);
  }
}

export async function patchMasterClips(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster,
  clips: Array<Partial<BatchClip> & { start: number; length: number; kind: BatchClip["kind"] }>,
  attr: MasterClipAttr,
): Promise<void> {
  await syncMasterClips(projectId, sceneId, master, { attr, upserts: clips });
}

export async function removeMasterClips(
  projectId: string,
  sceneId: string,
  master: SceneTimelineMaster,
  ids: Iterable<string>,
  attr: "visualClips" | "audioClips" | "sfxClips" | "cameraInstructions",
): Promise<void> {
  const removed = ids instanceof Set ? ids : new Set(ids);
  if (!removed.size) return;
  for (const batch of master.batchBlocks || []) {
    const before = (batch[attr] as BatchClip[]) || [];
    const after = before.filter((c) => !removed.has(c.id) && !removed.has(c.legacyClipId || ""));
    if (after.length === before.length) continue;
    await api.directorTimelinePatchBatch(projectId, sceneId, batch.id, { [attr]: after });
  }
}

const MANAGED_TAKE_PREFIXES = ["bbvclip_", "rtclip_", "rtb_"];
const COMPOSITION_REMNANT_ROLES = new Set(["original_a", "original_b", "retake"]);

/**
 * True when a stored visual clip must stay on the batch. Range pieces
 * (A|Middle|B, retake clips) stay. A lone whole-window video does not:
 * the creator can remove that bar. The Library asset stays.
 *
 * A library still reuses the imgclip_ id and image_frame role without the
 * composition stamp (sourceBatchId). That still belongs to the creator and
 * must stay removable.
 */
function compositionProtected(clip: BatchClip): boolean {
  const meta = clip.metadata as Record<string, unknown> | undefined;
  if (meta && meta.sourceBatchId) return true;
  const role = String((meta && meta.role) || clip.role || "");
  return COMPOSITION_REMNANT_ROLES.has(role);
}

/**
 * A lone bbvclip_ row is the whole-window video on Visual. The creator can
 * remove that bar. The same id beside other visuals is an A|Middle|B piece
 * and stays protected, as do retake/range clips.
 */
export function isManagedVisualClip(clip: BatchClip, visualCount = 1): boolean {
  const id = String(clip.id || "");
  if (id.startsWith("bbvclip_")) {
    if (visualCount > 1 || compositionProtected(clip)) return true;
    return false;
  }
  if (MANAGED_TAKE_PREFIXES.some((p) => id.startsWith(p))) return true;
  if (compositionProtected(clip)) return true;
  return false;
}

/**
 * Filter view clip ids down to those safe to delete from Master visualClips
 * (creator-placed clips only; managed/composition pieces are excluded).
 */
export function removableVisualClipIds(
  master: SceneTimelineMaster | null | undefined,
  ids: Iterable<string>,
): Set<string> {
  const wanted = ids instanceof Set ? ids : new Set(ids);
  const out = new Set<string>();
  if (!wanted.size) return out;
  for (const batch of master?.batchBlocks || []) {
    const visuals = batch.visualClips || [];
    for (const c of visuals) {
      if ((wanted.has(c.id) || wanted.has(c.legacyClipId || "")) && !isManagedVisualClip(c, visuals.length)) {
        out.add(c.id);
        if (c.legacyClipId) out.add(c.legacyClipId);
      }
    }
  }
  return out;
}

export function projectMasterPreviewClips(master: SceneTimelineMaster | null | undefined): {
  imageClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; role?: string }>;
  videoClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null }>;
  audioClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; title: string; description: string; volume: number; metadata?: Record<string, unknown> }>;
  sfxClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; title: string; description: string; volume: number; metadata?: Record<string, unknown> }>;
} {
  const imageClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; role?: string }> = [];
  const videoClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null }> = [];
  const audioClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; title: string; description: string; volume: number; metadata?: Record<string, unknown> }> = [];
  const sfxClips: Array<{ id: string; start: number; length: number; label: string; asset_id: string | null; title: string; description: string; volume: number; metadata?: Record<string, unknown> }> = [];
  // BATCH-LOCAL COORDINATE LAW: stored BatchClip.start is batch-local; the
  // view is scene-absolute. Add the owning batch's window start on project.
  const offsets = batchWindowStarts(master);
  for (const batch of master?.batchBlocks || []) {
    const windowStart = offsets.get(batch.id) ?? 0;
    for (const c of batch.visualClips || []) {
      const row = {
        id: c.id,
        start: (Number(c.start) || 0) + windowStart,
        length: Number(c.length) || 0,
        label: c.label || "Clip",
        asset_id: c.assetId ?? null,
        role: c.role || undefined,
      };
      if (c.kind === "video") videoClips.push(row);
      else imageClips.push(row);
    }
    for (const c of batch.audioClips || []) {
      audioClips.push({
        id: c.id,
        start: (Number(c.start) || 0) + windowStart,
        length: Number(c.length) || 0,
        label: c.label || "Audio",
        asset_id: c.assetId ?? null,
        title: textFromAudioMetadata(c.metadata, "title"),
        description: textFromAudioMetadata(c.metadata, "description"),
        volume: Number(c.volume ?? 1),
        metadata: c.metadata,
      });
    }
    for (const c of batch.sfxClips || []) {
      sfxClips.push({
        id: c.id,
        start: (Number(c.start) || 0) + windowStart,
        length: Number(c.length) || 0,
        label: c.label || "SFX",
        asset_id: c.assetId ?? null,
        title: textFromAudioMetadata(c.metadata, "title"),
        description: textFromAudioMetadata(c.metadata, "description"),
        volume: Number(c.volume ?? 1),
        metadata: c.metadata,
      });
    }
  }
  return { imageClips, videoClips, audioClips, sfxClips };
}
