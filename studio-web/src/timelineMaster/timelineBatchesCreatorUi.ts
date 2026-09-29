/**
 * Creator-facing Timeline Batches chrome (BATCHES track, Batch +/-, "N batches" scene label).
 *
 * Owner CLEAR only — do not re-enable without Brad.
 * Owner UI authority — do not re-enable Timeline Batches without Brad CLEAR.
 * Certs/bots must not flip this. When false, FE contract tests fail if Batches creator chrome returns.
 */
export const TIMELINE_BATCHES_CREATOR_UI = false as const;
