/** Film Timeline presentation helpers — sticky error + Live Plan dims. */

import { legalCanvasSize } from "../video/legalCanvas";
import { normalizeH3Aspect } from "../timelineMaster/legalCanvas";

export type PlanDims = { width: number; height: number; source: "resolvedGeneration" | "h3_auto_quality" };

/** True when sticky copy is legacy V2 R2V duration/grid authority (not Director-era). */
export function isLegacyR2vFilmmakerError(rawError: string): boolean {
  const t = String(rawError || "");
  if (!t) return false;
  const lower = t.toLowerCase();
  return (
    lower.includes("reference-to-video") ||
    lower.includes("reference to video") ||
    /n\s*[≡=]\s*5\s*\(\s*mod\s*17\s*\)/i.test(t) ||
    lower.includes("will not pad") ||
    lower.includes("timeline_r2v_required") ||
    /\b336 frames\b/i.test(t)
  );
}

/**
 * Suppress sticky segment failure copy after creator changes gen-defining settings.
 * On the Film Timeline H3 Director path, legacy R2V duration/grid sticky errors are
 * not current Generate truth — hide them (Phase 10) unless a fresh Director error arrives.
 */
export type RenderNotice = { key: string; status: "completed" | "failed" | "cancelled"; text: string };

/** Latest finished render the creator can dismiss. The key stays stable across polls. */
export function renderNoticeForSegments(
  segments: Array<{ id?: string; status?: string | null; error?: string | null }> | null | undefined,
): RenderNotice | null {
  const latest = [...(segments || [])].reverse().find((item) => {
    const status = String(item.status || "");
    return status === "completed" || status === "failed" || status === "cancelled";
  });
  if (!latest?.id) return null;
  const status = latest.status as RenderNotice["status"];
  const text = status === "failed" ? latest.error || "Render failed" : status === "cancelled" ? "Render cancelled" : "Render complete";
  return { key: `${latest.id}:${status}`, status, text };
}

export function visibleRenderNotice(notice: RenderNotice | null, dismissedKey: string): RenderNotice | null {
  if (!notice || notice.key === dismissedKey) return null;
  return notice;
}

export function visibleSegmentError(
  rawError: string,
  stickyHidden: boolean,
  opts?: { hideLegacyR2v?: boolean },
): string {
  if (!rawError) return "";
  if (stickyHidden) return "";
  if (opts?.hideLegacyR2v && isLegacyR2vFilmmakerError(rawError)) return "";
  return rawError;
}

type ResolvedLike = Record<string, unknown> | null | undefined;

function dimsFromResolved(rg: ResolvedLike): PlanDims | null {
  if (!rg || typeof rg !== "object" || Array.isArray(rg)) return null;
  const width = Number(rg.width);
  const height = Number(rg.height);
  if (Number.isFinite(width) && Number.isFinite(height) && width > 0 && height > 0) {
    return { width: Math.round(width), height: Math.round(height), source: "resolvedGeneration" };
  }
  return null;
}

/**
 * Prefer stamped Film resolvedGeneration (segment or shot). When H3 is selected
 * but nothing is stamped yet, fall back honestly to Auto Quality 0.7 → 1152×640.
 * Never returns Scene/project canvas.
 */
export function resolveFilmTimelinePlanDims(input: {
  generatorId?: string | null;
  shotResolvedGeneration?: ResolvedLike;
  segments?: Array<{ generationMetadata?: ResolvedLike }>;
  h3Resolution?: { mode?: "auto" | "manual"; megapixels?: number } | null;
  aspect?: string | null;
}): PlanDims | null {
  const segments = input.segments || [];
  for (const seg of segments) {
    const meta = seg.generationMetadata;
    if (!meta || typeof meta !== "object") continue;
    const fromSeg =
      dimsFromResolved((meta as Record<string, unknown>).resolvedGeneration as ResolvedLike) ||
      dimsFromResolved((meta as Record<string, unknown>).legalCanvas as ResolvedLike);
    if (fromSeg) return fromSeg;
  }
  const fromShot = dimsFromResolved(input.shotResolvedGeneration);
  if (fromShot) return fromShot;

  const gid = String(input.generatorId || "").toLowerCase();
  if (!gid.includes("minimax-h3")) return null;

  // A picture shape outside H3_SUPPORTED_ASPECTS (+ the ≈16:9 / ~16:9 aliases)
  // is refused by the backend fail-closed, so there are no H3 plan dims to show.
  // legalCanvasSize would otherwise coerce the unknown shape to 16:9-class dims
  // via video/legalCanvas h3VideoDisplayAspect — a display the backend refuses.
  const aspectToken = String(input.aspect || "").trim();
  if (aspectToken && !normalizeH3Aspect(aspectToken)) return null;
  // An absent shape means the backend default, which is 16:9.
  const aspect = aspectToken || "16:9";

  const h3 = input.h3Resolution;
  const mp =
    h3 && h3.mode === "manual" && h3.megapixels != null && Number(h3.megapixels) > 0
      ? Number(h3.megapixels)
      : 0.7;
  const label = Number.isInteger(mp) ? `${mp}.0 MP` : `${mp} MP`;
  // legalCanvasSize accepts megapixel labels for MiniMax.
  const size = legalCanvasSize("minimax-h3", label, aspect);
  if (size && size.width > 0 && size.height > 0) {
    return { width: size.width, height: size.height, source: "h3_auto_quality" };
  }
  // Hard-coded certified Auto Quality table entry if FE helper misses.
  if (Math.abs(mp - 0.7) < 0.001) {
    return { width: 1152, height: 640, source: "h3_auto_quality" };
  }
  return { width: 1152, height: 640, source: "h3_auto_quality" };
}
