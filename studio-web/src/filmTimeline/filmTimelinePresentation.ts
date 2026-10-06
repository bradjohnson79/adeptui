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

export type RenderStatusSnapshot = {
  progress?: number;
  progressGrounded?: boolean;
  phaseLabel?: string;
  elapsedSec?: number;
  status?: string;
};

export type FilmRenderHudModel = {
  headline: string;
  percent: number | null;
  bar: "live" | "held" | "wait" | "none";
  elapsed: string;
  model: string;
  place: string;
  detail: string;
  kind: "active" | "complete" | "cancelled" | "failed";
};

const CREATOR_PHASES = new Set([
  "Queued",
  "Preparing model",
  "Loading references",
  "Encoding prompt",
  "Generating",
  "Decoding",
  "Finalizing",
  "Generation may be stalled",
  "Generation stalled during model initialization.",
]);

const LEAK = /fps_mode|job[_ ]?id|\bnode\b|\bsteps?\b|max[_ ]?frames|sampling|\{|\}|Â|Ã|â€|[0-9a-f]{8}-[0-9a-f]{4}-/i;

/** Drop technical and broken-encoding text before it can reach the creator. */
export function creatorFacing(text: string): string {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (!value || LEAK.test(value)) return "";
  return value;
}

function clock(seconds: number | undefined): string {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return "";
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function phaseOf(status: RenderStatusSnapshot | undefined): string {
  const label = creatorFacing(status?.phaseLabel || "");
  return CREATOR_PHASES.has(label) ? label : "";
}

function storedPercent(status: RenderStatusSnapshot | undefined): number | null {
  if (!status || typeof status.progress !== "number" || !Number.isFinite(status.progress)) return null;
  return Math.max(0, Math.min(100, Math.round(status.progress * 100)));
}

function creatorModel(label: string | undefined): string {
  const value = creatorFacing(label || "");
  if (!value) return "";
  if (/^[a-z0-9_.:-]+$/i.test(value) && value.includes("-")) return "";
  return value;
}

type HudSegment = {
  id?: string;
  order?: number;
  status?: string;
  error?: string | null;
  shotNumber?: number | null;
  generationMetadata?: { renderStatus?: RenderStatusSnapshot; retakePreviousAssetId?: string } | null;
};

function canonicalShot(segment: HudSegment | undefined): number {
  return Math.max(0, Math.floor(Number(segment?.shotNumber) || 0));
}

/**
 * One view model for the preview line and the bottom-left HUD.
 * A percent is shown only when the existing telemetry grounded it, or held
 * from the last grounded value. This function never invents one.
 */
export function filmTimelineRenderHud(input: {
  segments?: HudSegment[] | null;
  stitchStatus?: string | null;
  modelLabel?: string;
  sceneName?: string;
  shotName?: string;
  showComplete?: boolean;
  showTerminal?: boolean;
}): FilmRenderHudModel | null {
  const segments = [...(input.segments || [])].sort((a, b) => (a.order || 0) - (b.order || 0));
  const model = creatorModel(input.modelLabel);
  const active = segments.find((item) => item.status === "generating" || item.status === "queued");
  const shotN = canonicalShot(active);
  const shotName = shotN > 0 ? `Shot ${shotN}` : creatorFacing(input.shotName || "");
  const place = [creatorFacing(input.sceneName || ""), shotName].filter(Boolean).join(" — ");

  if (!active && String(input.stitchStatus || "") === "stitching") {
    return { headline: "Stitching scene…", percent: null, bar: "wait", elapsed: "", model, place, detail: "", kind: "active" };
  }

  if (active) {
    const snapshot = active.generationMetadata?.renderStatus;
    const phase = phaseOf(snapshot);
    if (phase === "Generation stalled during model initialization.") {
      return {
        headline: phase,
        percent: null,
        bar: "wait",
        elapsed: clock(snapshot?.elapsedSec),
        model,
        place,
        detail: "",
        kind: "active",
      };
    }
    const grounded = Boolean(snapshot?.progressGrounded);
    const percent = storedPercent(snapshot);
    const index = Math.max(1, segments.findIndex((item) => item === active) + 1);
    const many = segments.length > 1;
    const named = shotN > 0 ? `Shot ${shotN}` : "";
    const retaking = Boolean(active.generationMetadata?.retakePreviousAssetId);
    const progressVerb = (fallback: string) => (retaking ? "Re-Taking" : phase || fallback);
    let headline = retaking ? "Re-Taking" : phase || "Preparing model...";
    if (!grounded && !headline.endsWith("...")) headline = `${headline}...`;
    if (grounded && percent !== null) {
      const verb = progressVerb("Generating");
      if (named) headline = `${verb} ${named} — ${percent}%`;
      else if (many) headline = `${verb} segment ${index}/${segments.length} — ${percent}%`;
      else headline = `${verb} — ${percent}%`;
    } else if (named) {
      const verb = progressVerb("Preparing");
      headline = `${verb} ${named}...`;
    } else if (many) {
      const verb = progressVerb("Preparing");
      headline = `${verb} segment ${index}/${segments.length}...`;
    }
    return {
      headline,
      percent: percent,
      bar: percent === null ? "wait" : grounded ? "live" : "held",
      elapsed: clock(snapshot?.elapsedSec),
      model,
      place,
      detail: "",
      kind: "active",
    };
  }

  if (input.showComplete) {
    const finished = creatorFacing(input.shotName || "");
    const headline = /^Shot \d+$/.test(finished) ? `${finished} complete — 100%` : "Render complete — 100%";
    return { headline, percent: 100, bar: "live", elapsed: "", model, place, detail: "", kind: "complete" };
  }

  if (input.showTerminal) {
    const terminal = [...segments].reverse().find((item) => item.status === "cancelled" || item.status === "failed");
    if (terminal?.status === "cancelled") {
      return { headline: "Render cancelled", percent: null, bar: "none", elapsed: "", model: "", place: "", detail: "", kind: "cancelled" };
    }
    if (terminal?.status === "failed") {
      return {
        headline: "Render failed",
        percent: null,
        bar: "none",
        elapsed: "",
        model: "",
        place: "",
        detail: creatorFacing(terminal.error || ""),
        kind: "failed",
      };
    }
  }

  return null;
}

/** The one progress sentence both the preview line and the HUD render. */
export function filmTimelineRenderLine(model: FilmRenderHudModel): string {
  if (model.bar === "held" && model.percent !== null) return `${model.headline} ${model.percent}%`;
  return model.headline;
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

/** Timeline LTX generator. Legacy production ids fold onto this id. */
export const LTX_TIMELINE_GENERATOR_ID = "ltx-2.5-distilled";

const LEGACY_PRODUCTION_MODE: Record<string, "text" | "one_frame" | "three_frame"> = {
  "text-to-video": "text",
  text_to_video: "text",
  txt2vid: "text",
  t2v: "text",
  "one-frame": "one_frame",
  one_frame: "one_frame",
  one: "one_frame",
  "1-frame": "one_frame",
  "1_frame": "one_frame",
  "three-frame": "three_frame",
  three_frame: "three_frame",
  three: "three_frame",
  "3-frame": "three_frame",
  "3_frame": "three_frame",
};

/** Read boundary: old production ids become LTX 2.5 plus the matching mode token. */
export function foldLegacyProductionSelection(
  modelId: string,
  ltxMode: string,
): { modelId: string; ltxMode: string } {
  const legacy = LEGACY_PRODUCTION_MODE[String(modelId || "").trim().toLowerCase()];
  if (!legacy) return { modelId: String(modelId || ""), ltxMode: String(ltxMode || "") };
  return { modelId: LTX_TIMELINE_GENERATOR_ID, ltxMode: ltxMode || legacy };
}

/** Display token for a stored LTX mode. three_frame is not a certified mode. */
export function displayLtxMode(storedMode: string, startId: string): "text" | "one_frame" | "start_end" {
  const raw = String(storedMode || "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "_");
  if (raw === "one_frame" || raw === "start_frame" || raw === "1_frame" || raw === "1frame") return "one_frame";
  if (raw === "start_end" || raw === "start_end_frame" || raw === "start_and_end_frame" || raw === "first_last") {
    return "start_end";
  }
  if ((raw === "three_frame" || raw === "3_frame" || raw === "3frame") && startId) return "one_frame";
  return "text";
}
