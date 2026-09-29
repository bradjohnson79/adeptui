/**
 * Scene duration is the creative clock. Generator max is one pass, not the scene.
 *
 * SCENE DURATION  = Scene.duration_sec (synced to Timeline duration_sec)
 * H3 NATIVE       = 15s per generation (existing capability)
 * TIMED PROMPT    = start + length inside the scene — never silent scene mutation
 *
 * There is no product duration preset. The creator sets any length they want.
 */
import { MINIMAX_H3_NEW_SCENE_SEC } from "../components/timelineSceneDuration";

export const SCENE_DURATION_AUTHORITY = "Scene.duration_sec";
export const H3_NATIVE_GENERATION_SEC = MINIMAX_H3_NEW_SCENE_SEC;

export function formatSceneClockSec(value: number): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return "0";
  return Number.isInteger(n) ? String(n) : String(Math.round(n * 10) / 10);
}

export function canonicalSceneDurationSec(
  scene?: { duration_sec?: number | null } | null,
  timeline?: { duration_sec?: number | null } | null,
): number {
  const fromScene = Number(scene?.duration_sec || 0);
  if (fromScene > 0) return fromScene;
  return Math.max(0, Number(timeline?.duration_sec || 0));
}

/** In-flight clock: after duration persist, timeline may update before Scene hydrates. */
export function liveSceneClockSec(
  scene?: { duration_sec?: number | null } | null,
  timeline?: { duration_sec?: number | null } | null,
): number {
  return Math.max(Number(scene?.duration_sec || 0), Number(timeline?.duration_sec || 0));
}

export function sanitizeSceneDurationSec(raw: number): { ok: boolean; durationSec: number; error?: string } {
  if (!Number.isFinite(raw) || raw <= 0) {
    return { ok: false, durationSec: 0, error: "Enter how long this scene should be." };
  }
  if (raw < 0.1) {
    return { ok: false, durationSec: 0, error: "A scene needs to be at least 0.1 seconds." };
  }
  return { ok: true, durationSec: raw };
}

export function h3ExtensionWindows(sceneDurationSec: number, nativeSec: number = H3_NATIVE_GENERATION_SEC): Array<{ start: number; end: number }> {
  const duration = Math.max(0, Number(sceneDurationSec) || 0);
  const window = Math.max(0.1, Number(nativeSec) || H3_NATIVE_GENERATION_SEC);
  if (duration <= 0) return [];
  const out: Array<{ start: number; end: number }> = [];
  let start = 0;
  while (start < duration - 1e-6) {
    const end = Math.min(start + window, duration);
    out.push({ start, end });
    start = end;
  }
  return out;
}

export function sceneDurationHelp(engine: string | null | undefined, sceneDurationSec: number): string {
  const token = String(engine || "").toLowerCase();
  const isH3 = !token || token === "auto" || token.startsWith("minimax-h3");
  if (!isH3) {
    return "How long this scene is — any length you want. This is the scene clock, not one generator clip.";
  }
  if (sceneDurationSec > H3_NATIVE_GENERATION_SEC + 1e-6) {
    const windows = h3ExtensionWindows(sceneDurationSec);
    const plan = windows.map((w) => `${formatSceneClockSec(w.start)}–${formatSceneClockSec(w.end)}s`).join(" then ");
    return `How long this scene is — any length you want. MiniMax H3 generates up to ${H3_NATIVE_GENERATION_SEC} seconds per pass. This ${formatSceneClockSec(sceneDurationSec)}s scene continues as ${plan}.`;
  }
  return `How long this scene is — any length you want. MiniMax H3 generates up to ${H3_NATIVE_GENERATION_SEC} seconds per pass. Longer scenes continue automatically.`;
}

export type TimedPromptRangeDecision =
  | { ok: true }
  | {
      ok: false;
      reason: "overflow" | "invalid";
      neededSceneSec: number;
      message: string;
    };

export function decideTimedPromptRange(
  start: number,
  length: number,
  sceneDurationSec: number,
  sceneLabel = "Scene 1",
): TimedPromptRangeDecision {
  const s = Number(start);
  const l = Number(length);
  const scene = Number(sceneDurationSec);
  if (!Number.isFinite(s) || s < 0) {
    return { ok: false, reason: "invalid", neededSceneSec: scene, message: "Start must be zero or later." };
  }
  if (!Number.isFinite(l) || l < 0.1) {
    return { ok: false, reason: "invalid", neededSceneSec: scene, message: "Length must be at least 0.1 seconds." };
  }
  if (!Number.isFinite(scene) || scene <= 0) {
    return { ok: false, reason: "invalid", neededSceneSec: l, message: "Set the scene duration before placing this Timed Prompt." };
  }
  const end = s + l;
  if (end <= scene + 1e-6) return { ok: true };
  const needed = Math.round(end * 10) / 10;
  const label = String(sceneLabel || "Scene 1").trim() || "Scene 1";
  return {
    ok: false,
    reason: "overflow",
    neededSceneSec: needed,
    message: `This Timed Prompt extends beyond the current ${formatSceneClockSec(scene)}-second scene. Extend ${label} to ${formatSceneClockSec(needed)} seconds?`,
  };
}
