/**
 * Creator-facing Timeline Lip Sync chrome (toolbar Lip Sync +/-, Lip Sync track authoring, Prepare Lip Sync).
 *
 * Owner CLEAR only — do not re-enable without Brad.
 * Owner UI authority — do not re-enable Timeline Lip Sync without Brad CLEAR.
 * Certs/bots must not flip this. When false, FE contract tests fail if Lip Sync creator chrome returns.
 */
export const TIMELINE_LIPSYNC_CREATOR_UI = false as const;
