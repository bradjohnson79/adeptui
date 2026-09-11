/** Per-scene local Timeline render cap. Project-total summing is stale. */
export const LOCAL_SCENE_DURATION_CAP_SEC = 20;

/** MiniMax H3 Timeline max request (= creator new-scene default). Matches H3_TIMELINE_MAX_REQUEST_SEC. */
export const MINIMAX_H3_NEW_SCENE_SEC = 15;

/**
 * Fallback product default for NEW Timeline scenes when engine is not MiniMax H3
 * and no generator capability max is supplied.
 *
 * MiniMax H3 must use MINIMAX_H3_NEW_SCENE_SEC (15) — creator fidelity, do not silently
 * seed shorter than the H3 envelope. Legacy 8 predated the H3 15s envelope; 12 was an
 * interim J3 "typical" seed that still stole 3s of H3 headroom on every Add Scene.
 */
export const DEFAULT_NEW_SCENE_SEC = 12;

/** LTX 2.5 Timeline new-scene default (creator fidelity — whole seconds). */
export const LTX_NEW_SCENE_SEC = 20;

export function isMinimaxH3Engine(engine?: string | null): boolean {
  // Product default engine is MiniMax H3; blank/missing counts as H3 for new-scene
  // seeding — and so does the legal EngineName "auto", which resolves to H3 at
  // generation time. Seeding "auto" scenes the non-H3 fallback was the 12.0s bug.
  const token = String(engine || "minimax-h3").toLowerCase().trim();
  return token === "auto" || token.startsWith("minimax-h3");
}

export function isLtxEngine(engine?: string | null): boolean {
  const token = String(engine || "").toLowerCase().trim().replace(/_/g, "-");
  if (!token) return false;
  if (token === "ltx" || token === "ltx-local" || token === "ltx2.5" || token === "ltx-2.5") return true;
  return token.startsWith("ltx-2.5") || token.startsWith("ltx2.5");
}

/**
 * Desired new-scene duration before the local per-scene cap.
 * H3 -> 15s (capability max). Other engines -> min(fallback, capability max) when known.
 */
export function defaultNewSceneDurationSec(
  engine?: string | null,
  maxDurationSec?: number | null,
): number {
  if (isMinimaxH3Engine(engine)) return MINIMAX_H3_NEW_SCENE_SEC;
  if (isLtxEngine(engine)) return LTX_NEW_SCENE_SEC;
  if (typeof maxDurationSec === "number" && Number.isFinite(maxDurationSec) && maxDurationSec > 0) {
    return Math.min(DEFAULT_NEW_SCENE_SEC, maxDurationSec);
  }
  return DEFAULT_NEW_SCENE_SEC;
}

export function nextLocalSceneDurationSec(
  capSec: number = LOCAL_SCENE_DURATION_CAP_SEC,
  opts?: { engine?: string | null; maxDurationSec?: number | null },
): {
  ok: boolean;
  durationSec: number;
  reason?: string;
} {
  const desired = defaultNewSceneDurationSec(opts?.engine, opts?.maxDurationSec);
  const durationSec = Math.min(desired, capSec);
  if (durationSec < 0.5) {
    return {
      ok: false,
      durationSec: 0,
      reason: "A new Scene needs at least half a second.",
    };
  }
  return { ok: true, durationSec };
}
