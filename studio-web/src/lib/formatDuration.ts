/**
 * Creator-facing duration formatting.
 *
 * Raw float seconds like 5.004000000000001 must never reach the UI. Two
 * decimals is enough for creators and stays stable for frame-derived values
 * (e.g. 121 frames @ 24 fps = 5.0416… → "5.04 s").
 */
export function formatDurationSeconds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)} s`;
}

/**
 * Creator-facing timestamp for job rows ("Aug 7, 12:20 AM").
 *
 * API timestamps are naive UTC ("2026-08-07 16:04:25.449425"); parse them as
 * UTC and render in the creator's local timezone so a stale failure is visibly
 * old instead of looking current.
 */
export function formatJobTimestamp(value: string | null | undefined): string {
  if (!value) return "";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized) ? normalized : `${normalized}Z`;
  const date = new Date(withZone);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
