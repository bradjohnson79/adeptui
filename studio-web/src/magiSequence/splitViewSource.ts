import type { MagiClip, MagiFinishingState } from "./types";

export type SplitViewAsset = {
  id: string;
  parent_asset_id?: string | null;
  prompt_meta?: Record<string, unknown> | string | null;
  labels?: string[] | null;
};

const MAGI_VISUAL_OPS = new Set(["color_grade", "upscale", "magi_final_render", "final_render"]);

function parseMeta(asset?: SplitViewAsset | null): Record<string, unknown> {
  const raw = asset?.prompt_meta;
  if (!raw) return {};
  if (typeof raw === "object") return raw as Record<string, unknown>;
  try {
    const parsed = JSON.parse(String(raw));
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

function parentIdOf(asset?: SplitViewAsset | null): string {
  const meta = parseMeta(asset);
  return String(asset?.parent_asset_id || meta.parentAssetId || meta.sourceAssetId || "").trim();
}

function opOf(asset?: SplitViewAsset | null): string {
  const meta = parseMeta(asset);
  return String(meta.op || meta.operation || "").trim();
}

export function walkToOriginalAssetId(
  assetId: string | null | undefined,
  assets: SplitViewAsset[],
): string | null {
  const byId = new Map(assets.map((item) => [item.id, item]));
  let current = String(assetId || "").trim();
  const seen = new Set<string>();
  while (current && !seen.has(current)) {
    seen.add(current);
    const row = byId.get(current);
    const parent = parentIdOf(row);
    if (!parent || parent === current) return current;
    // Stop at the published / ingest source. Timeline stitch/draft parents
    // are production lineage and must not become Split View LEFT.
    if (!MAGI_VISUAL_OPS.has(opOf(row))) return current;
    current = parent;
  }
  return current || null;
}

export function isDescendantOf(
  assetId: string | null | undefined,
  ancestorId: string | null | undefined,
  assets: SplitViewAsset[],
): boolean {
  const ancestor = String(ancestorId || "").trim();
  let current = String(assetId || "").trim();
  if (!ancestor || !current || current === ancestor) return false;
  const byId = new Map(assets.map((item) => [item.id, item]));
  const seen = new Set<string>();
  while (current && !seen.has(current)) {
    seen.add(current);
    const parent = parentIdOf(byId.get(current));
    if (!parent) return false;
    if (parent === ancestor) return true;
    current = parent;
  }
  return false;
}

export function resolveSplitOriginalAssetId(input: {
  publishedAssetId?: string | null;
  ingestMasterAssetId?: string | null;
  currentAssetId?: string | null;
  assets: SplitViewAsset[];
}): string | null {
  const published = String(input.publishedAssetId || "").trim();
  if (published) return published;
  const ingest = String(input.ingestMasterAssetId || "").trim();
  if (ingest) return ingest;
  return walkToOriginalAssetId(input.currentAssetId, input.assets);
}

export function isMagiVisualChild(
  asset: SplitViewAsset | null | undefined,
  originalId: string,
  assets: SplitViewAsset[] = [],
): boolean {
  if (!asset || !originalId) return false;
  if (asset.id === originalId) return false;
  const parent = parentIdOf(asset);
  const op = opOf(asset);
  if (parent === originalId && (MAGI_VISUAL_OPS.has(op) || !op)) return true;
  const pool = assets.length ? assets : [asset];
  return isDescendantOf(asset.id, originalId, pool) && (MAGI_VISUAL_OPS.has(op) || parent === originalId);
}

export function resolveSplitProcessed(input: {
  originalAssetId: string | null;
  visualResultAssetId?: string | null;
  playheadClip?: MagiClip | null;
  finishing?: MagiFinishingState | null;
  assets: SplitViewAsset[];
  liveGradeActive?: boolean;
}): { assetId: string | null; liveGrade: boolean } {
  const original = String(input.originalAssetId || "").trim();
  if (input.liveGradeActive && original) {
    return { assetId: original, liveGrade: true };
  }
  const byId = new Map(input.assets.map((item) => [item.id, item]));
  const baked = String(input.visualResultAssetId || input.finishing?.visualResultAssetId || "").trim();
  if (baked && original) {
    const row = byId.get(baked);
    if (row && baked !== original && isDescendantOf(baked, original, input.assets)) {
      return { assetId: baked, liveGrade: false };
    }
  }
  const playheadAssetId = String(input.playheadClip?.assetId || "").trim();
  if (playheadAssetId && original && playheadAssetId !== original) {
    const row = byId.get(playheadAssetId);
    if (row && isMagiVisualChild(row, original, input.assets)) {
      return { assetId: playheadAssetId, liveGrade: false };
    }
  }
  return { assetId: original || null, liveGrade: true };
}

export function ingestMasterAssetId(clips: MagiClip[] | undefined, sceneId?: string | null): string | null {
  const sid = String(sceneId || "").trim();
  const hit = (clips || []).find(
    (clip) =>
      clip.ingestRole === "published_master" && (!sid || String(clip.sceneId || "") === sid),
  );
  return hit?.assetId || null;
}
